"""Run the whole ingestion: raw, profiling, staging, core, balance check, report.

The warehouse is always rebuilt from empty into a temporary file and moved into
place only when every step has succeeded, so a failed run leaves the previous
warehouse intact and repeated runs over the same data give the same tables.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

from fabsync.ingest import corvus_mrp, finance, shop_floor
from fabsync.ingest.contracts import SourceContract
from fabsync.ingest.core import CONFORMANCE_PATH, build_core
from fabsync.ingest.profiling import profile_sources, render_report
from fabsync.ingest.raw_loader import load_raw_table, raw_table_name
from fabsync.ingest.staging import stage_table
from fabsync.ingest.warehouse import WAREHOUSE_PATH, Recorder, create_warehouse, new_run_id, now

SOURCES: list[SourceContract] = [corvus_mrp.CONTRACT, finance.CONTRACT, shop_floor.CONTRACT]
RAW_DIR = Path("data/raw")
REPORT_PATH = Path("docs/profiling-report.md")

CORE_FOR = {
    "corvus_mrp_works_orders": "core.works_orders", "corvus_mrp_bom_lines": "core.bom_lines",
    "corvus_mrp_stock": "core.stock", "corvus_mrp_purchase_orders": "core.purchase_orders",
    "corvus_mrp_goods_received": "core.goods_received", "finance_purchase_invoices": "core.purchase_invoices",
    "finance_sales_invoices": "core.sales_invoices", "finance_job_costs": "core.job_costs",
    "finance_supplier_master": "core.supplier_master", "shop_floor_time_bookings": "core.time_bookings",
    "shop_floor_delivery_notes": "core.delivery_notes", "shop_floor_ncr_log": "core.ncrs",
    "shop_floor_weekly_capacity": "core.weekly_capacity",
}


@dataclass
class IngestResult:
    run_id: str
    warehouse: Path
    report: Path
    rows_raw: int
    rows_staged: int
    rows_quarantined: int
    balanced: bool


def write_balance(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    for src in SOURCES:
        for t in src.tables:
            name = raw_table_name(src.system, t.name)
            con.execute(f"""
                INSERT INTO governance.table_balance
                SELECT ?, ?, ?, ?,
                       (SELECT data_lines FROM governance.source_file WHERE source_file = ?),
                       (SELECT count(*) FROM raw.{name}),
                       (SELECT count(*) FROM staging.{name}),
                       (SELECT count(*) FROM {CORE_FOR[name]}),
                       (SELECT count(*) FROM governance.quarantine WHERE source_file = ?),
                       NULL""", [run_id, src.system, t.name, t.file, t.file, t.file])
    con.execute("""UPDATE governance.table_balance
                   SET balanced = (data_lines = staged_rows + quarantined_rows AND core_rows = staged_rows)""")


def run_ingest(raw_dir: Path = RAW_DIR, warehouse: Path = WAREHOUSE_PATH, report: Path = REPORT_PATH,
               config: Path = CONFORMANCE_PATH) -> IngestResult:
    missing = [t.file for s in SOURCES for t in s.tables if not (raw_dir / t.file).exists()]
    if missing:
        raise FileNotFoundError(f"missing source files in {raw_dir}: {', '.join(missing)}. Run make generate.")
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    building = warehouse.with_name(warehouse.stem + ".building.duckdb")
    for leftover in (building, Path(str(building) + ".wal")):
        leftover.unlink(missing_ok=True)

    run_id = new_run_id()
    started = now()
    con = duckdb.connect(str(building))
    try:
        create_warehouse(con, SOURCES)
        rec = Recorder(con, run_id)
        rows_raw = sum(load_raw_table(con, rec, raw_dir, s, t) for s in SOURCES for t in s.tables)
        profiles = profile_sources(con, run_id, SOURCES)
        rows_staged = sum(stage_table(con, rec, s, t) for s in SOURCES for t in s.tables)
        build_core(con, rec, config)
        write_balance(con, run_id)

        rows_q = con.execute("SELECT count(*) FROM governance.quarantine").fetchone()[0]
        balanced = con.execute("SELECT bool_and(balanced) FROM governance.table_balance").fetchone()[0]
        comment = con.execute("SELECT header_comment FROM governance.source_file LIMIT 1").fetchone()[0]
        balance = con.execute("""SELECT source_file, raw_rows, staged_rows, quarantined_rows, balanced
                                 FROM governance.table_balance ORDER BY source_system, source_table""").df()
        qsum = con.execute("""SELECT source_file, rule_id, rule_description, failing_column, count(*) AS rows
                              FROM governance.quarantine GROUP BY ALL ORDER BY ALL""").df()
        con.execute("INSERT INTO governance.run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [run_id, started, now(), "succeeded" if balanced else "unbalanced", str(raw_dir),
                     sum(len(s.tables) for s in SOURCES), rows_raw, rows_staged, rows_q,
                     "All data is synthetic."])
        con.execute("CHECKPOINT")
        con.close()
    except BaseException:
        con.close()
        building.unlink(missing_ok=True)
        raise
    os.replace(building, warehouse)

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(profiles, SOURCES, balance, qsum, comment), encoding="utf-8")
    if not balanced:
        raise AssertionError("row balance failed: see governance.table_balance")
    return IngestResult(run_id, warehouse, report, rows_raw, rows_staged, rows_q, bool(balanced))


def print_summary(result: IngestResult) -> None:
    con = duckdb.connect(str(result.warehouse), read_only=True)
    rows = con.execute("""SELECT source_file, raw_rows, staged_rows, quarantined_rows, core_rows, balanced
                          FROM governance.table_balance ORDER BY source_system, source_table""").fetchall()
    rules = con.execute("""SELECT rule_id, count(*) FROM governance.quarantine GROUP BY 1 ORDER BY 1""").fetchall()
    steps = con.execute("SELECT count(*) FROM governance.lineage").fetchone()[0]
    con.close()
    print(f"Run {result.run_id}  (synthetic data)")
    print(f"{'source file':<34}{'raw':>8}{'staged':>8}{'quar.':>7}{'core':>8}  balanced")
    for f, r, s, q, c, ok in rows:
        print(f"{f:<34}{r:>8,}{s:>8,}{q:>7,}{c:>8,}  {'yes' if ok else 'NO'}")
    print(f"{'total':<34}{result.rows_raw:>8,}{result.rows_staged:>8,}{result.rows_quarantined:>7,}")
    print("Quarantined by rule: " + ", ".join(f"{r} {n}" for r, n in rules))
    print(f"Lineage steps recorded: {steps}")
    print(f"Warehouse: {result.warehouse}   Profiling report: {result.report}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load data/raw into the DuckDB warehouse.")
    parser.add_argument("--raw", type=Path, default=RAW_DIR)
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        result = run_ingest(args.raw, args.warehouse, args.report)
    except (FileNotFoundError, AssertionError) as exc:
        sys.exit(f"ingest failed: {exc}")
    print_summary(result)


if __name__ == "__main__":
    main()
