"""Run the four reconciliation engines and publish their results in the recon schema.

Everything is rebuilt in one transaction. Before committing, every headline is
recomputed from its own rows with its own SQL; if any figure does not
reproduce, nothing is published. recon.headline then holds each figure beside
the SQL that produces it and the SQL that lists the rows behind it.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import duckdb
import pandas as pd

from fabsync.ingest.contracts import RULES
from fabsync.ingest.warehouse import WAREHOUSE_PATH, Recorder, new_run_id, now, rule_layer
from fabsync.reconcile.common import RECONCILE_CONFIG, SCHEMA, EngineResult, load_config
from fabsync.reconcile.job_cost import job_cost_reconciliation
from fabsync.reconcile.report import render_report
from fabsync.reconcile.stock import stock_accuracy
from fabsync.reconcile.three_way import three_way_match
from fabsync.reconcile.traceability import material_traceability

REPORT_PATH = Path("docs/reconciliation-report.md")
ENGINES = [("RC-01", three_way_match), ("RC-02", job_cost_reconciliation), ("RC-03", stock_accuracy),
           ("RC-04", material_traceability)]


class UnexplainedFigure(AssertionError):
    """A headline figure could not be reproduced from its rows."""


def verify(con: duckdb.DuckDBPyConnection, results: list[EngineResult]) -> None:
    problems = []
    for res in results:
        for h in res.headlines:
            got = con.execute(h.value_sql).fetchone()[0]
            got = 0.0 if got is None else float(got)
            if abs(got - float(h.value)) > max(0.011, 1e-9 * abs(h.value)):
                problems.append(f"{h.engine}.{h.key}: published {h.value}, rows give {got}")
    if problems:
        raise UnexplainedFigure("; ".join(problems))


def run_reconcile(warehouse: Path = WAREHOUSE_PATH, report: Path = REPORT_PATH,
                  config_path: Path = RECONCILE_CONFIG) -> list[EngineResult]:
    if not warehouse.exists():
        raise FileNotFoundError(f"{warehouse} not found. Run make ingest and make match.")
    cfg = load_config(config_path)
    run_id = new_run_id()
    con = duckdb.connect(str(warehouse))
    try:
        con.execute("BEGIN")
        con.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        con.execute(f"CREATE SCHEMA {SCHEMA}")
        con.execute("DELETE FROM governance.lineage WHERE layer = 'reconcile'")
        con.executemany("INSERT OR REPLACE INTO governance.rule VALUES (?, ?, ?)",
                        [(r, rule_layer(r), d) for r, d in RULES.items() if r.startswith("RC-")])
        rec = Recorder(con, run_id)
        rec.step = con.execute("SELECT coalesce(max(step_id), 0) FROM governance.lineage").fetchone()[0]
        results = []
        for rule_id, engine in ENGINES:
            started = now()
            res = engine(con, cfg)
            for name, frame in res.tables.items():
                con.register("_recon_frame", frame)
                con.execute(f"CREATE TABLE {SCHEMA}.{name} AS SELECT * FROM _recon_frame")
                con.unregister("_recon_frame")
            rec.lineage(layer="reconcile", source_system="multiple", source_table=res.engine,
                        source_file="staging, core", target_table=f"{SCHEMA}.{next(iter(res.tables))}",
                        rule_id=rule_id, rows_in=len(res.rows), rows_out=len(res.rows),
                        rows_affected=len(res.headlines),
                        detail=f"{res.exposure_label}: {res.exposure:,.2f}", started_at=started)
            results.append(res)
        verify(con, results)
        heads = pd.DataFrame([{**asdict(h), "value_sql": h.value_sql, "rows_sql": h.rows_sql}
                              for res in results for h in res.headlines])
        heads.insert(0, "ordinal", range(1, len(heads) + 1))
        con.register("_heads", heads)
        con.execute(f"CREATE TABLE {SCHEMA}.headline AS SELECT * FROM _heads")
        exposures = pd.DataFrame([{"engine": r.engine, "exposure": r.exposure, "exposure_label": r.exposure_label,
                                   "rows": len(r.rows)} for r in results])
        con.register("_exp", exposures)
        con.execute(f"CREATE TABLE {SCHEMA}.exposure AS SELECT * FROM _exp")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        con.close()
        raise
    con.close()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(results, cfg), encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the four reconciliation engines.")
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        results = run_reconcile(args.warehouse, args.report)
    except (FileNotFoundError, UnexplainedFigure) as exc:
        sys.exit(f"reconcile failed: {exc}")
    print("Reconciliation  (synthetic data)")
    for r in results:
        print(f"  {r.engine:<14}{r.exposure:>16,.2f}  {r.exposure_label}   ({len(r.headlines)} headline figures)")
    print(f"Every headline reproduced from its rows. Drill-down: recon.headline   Report: {args.report}")


if __name__ == "__main__":
    main()
