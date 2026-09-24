"""Build the marts schema: documented KPI views, their definitions and a scorecard.

1. Validate config/kpis.yaml. Every KPI needs every field, and the caveat is
   not optional.
2. Rebuild marts from the SQL files in src/fabsync/kpi/sql, in file order, in
   one transaction.
3. Check that the views created are exactly the views the definitions describe,
   and attach each description to its view as a warehouse comment.
4. Evaluate each KPI's headline (and secondary) figure into marts.kpi_scorecard,
   and store the definitions in marts.kpi_definition.
5. Write docs/data-dictionary.md and docs/kpi-report.md.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from fabsync.ingest.warehouse import WAREHOUSE_PATH
from fabsync.kpi.report import render_dictionary, render_kpi_report

KPI_PATH = Path("config/kpis.yaml")
RECONCILE_CONFIG = Path("config/reconcile.toml")
SQL_DIR = Path(__file__).parent / "sql"
DICTIONARY_PATH = Path("docs/data-dictionary.md")
REPORT_PATH = Path("docs/kpi-report.md")
ROLES = ("Purchasing Manager", "Production Controller", "Finance Manager", "Quality Manager")
REQUIRED = ("id", "name", "definition", "formula", "sources", "owner", "refresh", "caveat", "unit", "direction",
            "headline", "rows", "views")
DIRECTIONS = ("higher", "lower", "abs_lower", "band", "none")
MIN_CAVEAT_WORDS = 20


class KpiError(ValueError):
    """The KPI definitions are incomplete or disagree with the views built."""


@dataclass
class KpiBuild:
    definitions: pd.DataFrame
    scorecard: pd.DataFrame
    views: pd.DataFrame
    doc: dict


def load_definitions(path: Path = KPI_PATH) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems, seen = [], set()
    for k in doc.get("kpis") or []:
        where = k.get("id", "a KPI")
        missing = [f for f in REQUIRED if not k.get(f)]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        if k["id"] in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(k["id"])
        if len(str(k["caveat"]).split()) < MIN_CAVEAT_WORDS:
            problems.append(f"{where}: caveat must say honestly what the KPI does not tell you "
                            f"(at least {MIN_CAVEAT_WORDS} words)")
        if k["owner"] not in ROLES:
            problems.append(f"{where}: owner '{k['owner']}' is not one of {', '.join(ROLES)}")
        if k["direction"] not in DIRECTIONS:
            problems.append(f"{where}: direction must be one of {', '.join(DIRECTIONS)}")
        elif k["direction"] == "band" and (k.get("target_low") is None or k.get("target_high") is None):
            problems.append(f"{where}: a band needs target_low and target_high")
        elif k["direction"] in ("higher", "lower", "abs_lower") and k.get("target") is None:
            problems.append(f"{where}: direction {k['direction']} needs a target")
    if not doc.get("kpis"):
        problems.append("no KPIs defined")
    if problems:
        raise KpiError(f"{path}: " + "; ".join(problems))
    return doc


def status(k: dict, value: float | None) -> str:
    if value is None or pd.isna(value):
        return "no data"
    d = k["direction"]
    if d == "none":
        return "for information"
    if d == "band":
        return "on target" if k["target_low"] <= value <= k["target_high"] else "off target"
    met = {"higher": value >= k.get("target", 0), "lower": value <= k.get("target", 0),
           "abs_lower": abs(value) <= k.get("target", 0)}[d]
    return "on target" if met else "off target"


def target_text(k: dict) -> str:
    unit = "%" if k["unit"] == "percent" else ""
    return {"higher": f">= {k.get('target')}{unit}", "lower": f"<= {k.get('target')}{unit}",
            "abs_lower": f"within ±{k.get('target')}{unit}", "none": "no target",
            "band": f"{k.get('target_low')}{unit} to {k.get('target_high')}{unit}"}[k["direction"]]


def parameters(doc: dict, reconcile_config: Path) -> dict:
    rc = tomllib.loads(reconcile_config.read_text(encoding="utf-8"))
    return {"as_of_date": rc["as_of_date"], "labour_rate": float(rc["labour_rate"]),
            "despatch_window_days": int(rc["traceability"]["despatch_window_days"]),
            "bar_length_mm": int(doc["parameters"]["bar_length_mm"]),
            "stock_accuracy_target_pct": 100 * float(rc["stock"]["accuracy_target"])}


def build_marts(warehouse: Path = WAREHOUSE_PATH, kpi_path: Path = KPI_PATH,
                reconcile_config: Path = RECONCILE_CONFIG, dictionary: Path = DICTIONARY_PATH,
                report: Path = REPORT_PATH) -> KpiBuild:
    doc = load_definitions(kpi_path)
    if not warehouse.exists():
        raise FileNotFoundError(f"{warehouse} not found. Run make ingest, make match and make reconcile.")
    params = parameters(doc, reconcile_config)
    con = duckdb.connect(str(warehouse))
    try:
        has_recon = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'recon' "
                                "AND table_name = 'headline'").fetchone()[0]
        if not has_recon:
            raise FileNotFoundError("reconciliation results not found. Run make reconcile.")
        con.execute("BEGIN")
        con.execute("DROP SCHEMA IF EXISTS marts CASCADE")
        con.execute("CREATE SCHEMA marts")
        con.execute("""CREATE TABLE marts.parameters (as_of_date DATE, labour_rate DOUBLE, despatch_window_days INTEGER,
                       bar_length_mm INTEGER, stock_accuracy_target_pct DOUBLE)""")
        con.execute("INSERT INTO marts.parameters VALUES (?, ?, ?, ?, ?)",
                    [params["as_of_date"], params["labour_rate"], params["despatch_window_days"],
                     params["bar_length_mm"], params["stock_accuracy_target_pct"]])
        for sql_file in sorted(SQL_DIR.glob("*.sql")):
            con.execute(sql_file.read_text(encoding="utf-8"))

        described = dict(doc["helpers"])
        owner_of = {}
        for k in doc["kpis"]:
            for view, text in k["views"].items():
                described[view] = text
                owner_of[view] = k["id"]
        built = {f"marts.{t}" for (t,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts'").fetchall()}
        undocumented, missing = built - set(described), set(described) - built
        if undocumented or missing:
            raise KpiError("views and definitions disagree: "
                           + (f"undocumented {sorted(undocumented)} " if undocumented else "")
                           + (f"described but not built {sorted(missing)}" if missing else ""))
        for name, text in described.items():
            kind = "TABLE" if name == "marts.parameters" else "VIEW"
            con.execute(f"COMMENT ON {kind} {name} IS '{text.replace(chr(39), chr(39) * 2)}'")

        rows, defs = [], []
        for k in doc["kpis"]:
            value = con.execute(k["headline"]).fetchone()[0]
            value = None if value is None else float(value)
            sec = k.get("secondary")
            sec_value = None
            if sec:
                sec_value = con.execute(sec["sql"]).fetchone()[0]
                sec_value = None if sec_value is None else float(sec_value)
            rows.append({"kpi_id": k["id"], "name": k["name"], "value": value, "unit": k["unit"],
                         "target": target_text(k), "status": status(k, value), "owner": k["owner"],
                         "secondary_label": sec["label"] if sec else None, "secondary_value": sec_value,
                         "secondary_unit": sec["unit"] if sec else None, "headline_sql": k["headline"],
                         "rows_sql": k["rows"], "rows": int(con.execute(f"SELECT count(*) FROM ({k['rows']})")
                                                            .fetchone()[0])})
            defs.append({"kpi_id": k["id"], "name": k["name"], "definition": k["definition"],
                         "formula": k["formula"], "sources": k["sources"], "owner": k["owner"],
                         "refresh": k["refresh"], "caveat": " ".join(str(k["caveat"]).split()),
                         "unit": k["unit"], "target": target_text(k), "views": ", ".join(k["views"])})
        scorecard, definitions = pd.DataFrame(rows), pd.DataFrame(defs)
        views = pd.DataFrame([{"view": v, "kpi_id": owner_of.get(v, "helper"), "description": d}
                              for v, d in described.items()])
        for name, frame in (("kpi_scorecard", scorecard), ("kpi_definition", definitions)):
            con.register("_kpi_frame", frame)
            con.execute(f"CREATE TABLE marts.{name} AS SELECT * FROM _kpi_frame")
            con.unregister("_kpi_frame")
        con.execute("COMMENT ON TABLE marts.kpi_scorecard IS 'Current value of every KPI against its target.'")
        con.execute("COMMENT ON TABLE marts.kpi_definition IS 'Definition record for every KPI, including its caveat.'")
        breakdowns = {name: con.execute(sql).df() for name, sql in {
            "otif_by_site": "SELECT * FROM marts.otif_by_site",
            "otif_by_customer": "SELECT * FROM marts.otif_by_customer WHERE measured >= 5 ORDER BY otif_pct, "
                                "customer_name LIMIT 5",
            "labour_by_job": "SELECT * FROM marts.labour_variance_by_job LIMIT 5",
            "yield": "SELECT * FROM marts.material_yield_by_section_type",
            "stock": "SELECT * FROM marts.stock_accuracy",
            "three_way": "SELECT * FROM marts.three_way_value_at_risk",
            "trace_by_site": "SELECT site_code, round(100 * sum(CASE WHEN t.material_chain_complete THEN t.kg END) "
                             "/ sum(t.kg), 1) AS coverage_pct FROM recon.trace_lines t JOIN core.works_orders w "
                             "USING (wo_no) GROUP BY 1 ORDER BY 1",
            "wip": "SELECT * FROM marts.wip_ageing",
            "capacity": "SELECT * FROM marts.capacity_utilisation_by_site",
            "ncr": "SELECT * FROM marts.ncr_by_category",
        }.items()}
        con.execute("COMMIT")
    except BaseException:
        try:
            con.execute("ROLLBACK")
        except duckdb.Error:
            pass
        con.close()
        raise
    con.close()
    dictionary.parent.mkdir(parents=True, exist_ok=True)
    dictionary.write_text(render_dictionary(definitions, views, params), encoding="utf-8")
    report.write_text(render_kpi_report(scorecard, definitions, breakdowns, params), encoding="utf-8")
    return KpiBuild(definitions, scorecard, views, doc)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the KPI marts, data dictionary and KPI report.")
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    args = parser.parse_args(argv)
    try:
        result = build_marts(args.warehouse)
    except (FileNotFoundError, KpiError) as exc:
        sys.exit(f"kpi failed: {exc}")
    print("KPI scorecard  (synthetic data)")
    for r in result.scorecard.itertuples():
        value = "no data" if r.value is None or pd.isna(r.value) else (
            f"£{r.value:,.0f}" if r.unit == "GBP" else f"{r.value:,.1f}{'%' if r.unit == 'percent' else ''}")
        print(f"  {r.kpi_id}  {r.name:<34}{value:>14}   {r.target:<16}{r.status}")
    print(f"{len(result.views)} documented views in marts. Data dictionary: {DICTIONARY_PATH}   Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
