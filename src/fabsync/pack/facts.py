"""Every figure and fact the management pack quotes, gathered in one place.

Nothing in the pack is typed by hand. Figures come from the warehouse; the plan, reviews, risks and
training from the roadmap config; definitions from the KPI and data quality rule configs; the process
maps, target architecture, ownership matrix, escalation route and timeline from the committed design and
planning documents, which their own tests keep in step with the data.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from fabsync.design.figures import FIGURES, compute
from fabsync.design.render import PLACEHOLDER, fill
from fabsync.provenance import Origin, TracedInt, numbers, trace, trace_frame

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
CONFIG = ROOT / "config"


def md_table(text: str, header_start: str) -> list[list[str]]:
    """Rows of the markdown table whose header line starts with `header_start`."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(header_start))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


@dataclass
class Facts:
    as_of: date
    head: dict[tuple[str, str], float]
    fig: dict[str, float]
    dq: dict
    dq_by_owner: pd.DataFrame
    dq_by_system: pd.DataFrame
    rules: pd.DataFrame
    kpis: pd.DataFrame
    three_way: pd.DataFrame
    ageing: pd.DataFrame
    job_top: pd.DataFrame
    stock: pd.DataFrame
    trace_breaks: pd.DataFrame
    trace_customers: pd.DataFrame
    match: dict
    source: dict
    turnover_12m: float
    roadmap: dict
    timeline: dict[str, list[str]]
    ownership: list[list[str]]
    escalation: list[list[str]]
    diagrams: dict[str, str]
    diagram_numbers: dict[str, list[tuple[str, Origin]]]  # every number in each filled diagram, with its source
    benefits: dict[str, list[list[str]]]
    reconcile: dict
    sites: dict[str, str]
    labour_rate: float
    jobs_reconciled: float
    lines_assessed: float
    kpi_count: float
    severity_weights: dict[str, int]

    rows: dict[str, TracedInt] = None
    head_label: dict[tuple[str, str], str] = None
    months: TracedInt = None
    systems: TracedInt = None

    def h(self, engine: str, key: str) -> float:
        return self.head[(engine, key)]

    def kpi(self, kpi_id: str) -> pd.Series:
        return self.kpis.set_index("kpi_id").loc[kpi_id]


def _df(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> float:
    value = con.execute(sql).fetchone()[0]
    if value is None:
        raise ValueError(f"no value for: {sql}")
    return float(value)


# Every query the pack takes a figure from, by name, so the traceability audit can cite each one.
SCALARS = {
    "review_items": "SELECT count(*) FROM core.v_match_review_queue",
    "review_hours": "SELECT sum(est_minutes) / 60 FROM core.v_match_review_queue",
    "material_forms": "SELECT values_total FROM governance.match_quality WHERE domain = 'material'",
    "golden_materials": "SELECT count(*) FROM core.material_golden",
    "supplier_entities": "SELECT count(*) FROM core.supplier_golden",
    "max_codes_per_material": "SELECT max(n) FROM (SELECT count(DISTINCT trim(source_code)) AS n "
                              "FROM core.material_xref WHERE canonical_code IS NOT NULL GROUP BY canonical_code)",
    "max_names_per_supplier": "SELECT max(n) FROM (SELECT count(DISTINCT source_name) AS n FROM core.supplier_xref "
                              "GROUP BY supplier_id)",
    "raw_rows": "SELECT sum(raw_rows) FROM governance.table_balance",
    "files": "SELECT count(*) FROM governance.table_balance",
    "quarantined": "SELECT count(*) FROM governance.quarantine",
    "months": "SELECT count(DISTINCT month) FROM marts.quality_cost_by_month",
    "sites": "SELECT count(DISTINCT site_code) FROM core.works_orders",
    "max_units_per_material": "SELECT max(len(string_split(observed_uoms, ', '))) FROM core.material_golden",
    "turnover_12m": "SELECT sum(turnover) FROM marts.quality_cost_by_month WHERE month > "
                    "(SELECT as_of_date FROM marts.parameters) - INTERVAL 12 MONTH",
    "labour_rate": "SELECT labour_rate FROM marts.parameters",
    "jobs_reconciled": "SELECT count(*) FROM recon.job_cost",
    "lines_assessed": "SELECT count(*) FROM recon.three_way_lines WHERE category IN ('matched', "
                      "'quantity variance', 'price variance', 'missing GRN', 'missing invoice')",
    "kpi_count": "SELECT count(*) FROM marts.kpi_scorecard",
    "kpis_off_target": "SELECT count(*) FROM marts.kpi_scorecard WHERE status = 'off target'",
}
FRAMES = {
    "dq_run": "SELECT dq_index, rules_met, rules_run, critical_breaches, records_failed FROM governance.dq_run "
              "ORDER BY finished_at DESC LIMIT 1",
    "kpis": "SELECT kpi_id, name, value, unit, target, status, owner, secondary_label, secondary_value, "
            "secondary_unit FROM marts.kpi_scorecard ORDER BY kpi_id",
    "three_way": "SELECT category, count(*) AS lines, sum(value_at_risk) AS value FROM recon.three_way_lines "
                 "WHERE is_exception GROUP BY 1 ORDER BY value DESC",
    "ageing": "SELECT category, age_bucket, lines FROM recon.three_way_ageing",
    "job_top": "SELECT job_no, customer_name, unexplained_gap FROM recon.job_cost ORDER BY rank LIMIT 15",
    "stock": "SELECT site_code, section_type, lines, accurate_lines, 100 * line_accuracy AS accuracy, value_error "
             "FROM recon.stock_summary ORDER BY line_accuracy, site_code, section_type",
    "trace_breaks": "SELECT break_at, lines, kg / 1000 AS tonnes FROM recon.trace_breaks WHERE break_at <> 'complete' "
                    "ORDER BY kg DESC",
    "trace_customers": "SELECT customer_name, exposed_kg / 1000 AS tonnes, exposed_jobs FROM recon.trace_customers "
                       "ORDER BY exposed_kg DESC, customer_name LIMIT 12",
    "rules": "SELECT dimension, severity, count(*) AS rules, count(*) FILTER (WHERE threshold_met) AS met "
             "FROM governance.v_dq_latest GROUP BY ALL ORDER BY ALL",
    "dq_by_owner": "SELECT owner, dq_index, rules, rules_met, critical_breaches "
                   "FROM governance.v_dq_scorecard_by_owner ORDER BY dq_index",
    "dq_by_system": "SELECT system, dq_index, rules, rules_met, critical_breaches "
                    "FROM governance.v_dq_scorecard_by_system ORDER BY dq_index",
}


def config_values(obj, where: str):
    """Numbers in a config file, each wrapped with the file and key it came from."""
    if isinstance(obj, dict):
        return {k: config_values(v, f"{where} {k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [config_values(v, f"{where} {i}") for i, v in enumerate(obj)]
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return trace(obj, "config", where, str(obj))
    return obj


def load(con: duckdb.DuckDBPyConnection) -> Facts:
    headlines = con.execute("SELECT engine, key, label, value, value_sql FROM recon.headline").fetchall()
    head = {(e, k): trace(v, "warehouse", f"reconciliation headline: {label}", sql)
            for e, k, label, v, sql in headlines}
    head_label = {(e, k): label for e, k, label, _, _ in headlines}
    fig = {key: trace(_one(con, sql), "warehouse", f"figure: {key}", sql) for key, (sql, _) in FIGURES.items()}
    frames = {name: trace_frame(_df(con, sql), name, sql) for name, sql in FRAMES.items()}
    rows = {name: TracedInt(len(frame), Origin("warehouse", f"rows in {name}",
                                               f"SELECT count(*) FROM ({FRAMES[name]})"))
            for name, frame in frames.items()}
    scalar = {name: trace(_one(con, sql), "warehouse", f"query: {name}", sql) for name, sql in SCALARS.items()}

    definitions = yaml.safe_load((CONFIG / "kpis.yaml").read_text(encoding="utf-8"))["kpis"]
    extra = pd.DataFrame([{"kpi_id": k["id"], "definition": k["definition"], "refresh": k["refresh"],
                           "caveat": k["caveat"]} for k in definitions])
    kpis = frames["kpis"].merge(extra, on="kpi_id", how="left", validate="one_to_one")
    match = {k: scalar[k] for k in ("review_items", "review_hours", "material_forms", "golden_materials",
                                    "supplier_entities", "max_codes_per_material", "max_names_per_supplier")}
    source = {k: scalar[k] for k in ("raw_rows", "files", "quarantined", "months", "sites", "max_units_per_material")}
    dq = {col: frames["dq_run"][col].iloc[0] for col in frames["dq_run"].columns}  # to_dict() would unwrap them
    three_way, ageing, job_top, stock = frames["three_way"], frames["ageing"], frames["job_top"], frames["stock"]
    breaks, customers, rules = frames["trace_breaks"], frames["trace_customers"], frames["rules"]
    turnover = scalar["turnover_12m"]

    plan = (DOCS / "rollout-plan.md").read_text(encoding="utf-8")
    timeline = {r[0]: r[1:] for r in md_table(plan, "| | M1 |")}
    months = TracedInt(len(timeline["Quarter"]), Origin("document", "months on the rollout plan timeline",
                                                        "docs/rollout-plan.md, Timeline"))
    systems_sql = "SELECT count(DISTINCT split_part(source_file, '/', 1)) FROM governance.table_balance"
    systems = trace(int(_one(con, systems_sql)), "warehouse", "number of source systems", systems_sql)
    roadmap = yaml.safe_load((CONFIG / "roadmap.yaml").read_text(encoding="utf-8"))
    for r in roadmap["risks"]:
        for k in ("likelihood", "impact", "inherent", "residual_likelihood", "residual_impact", "residual"):
            r[k] = trace(r[k], "config", f"roadmap.yaml {r['id']} {k}", str(r[k]))
    for r in roadmap["reviews"]:
        for k in ("review", "month"):
            r[k] = trace(r[k], "config", f"roadmap.yaml review {r['review']} {k}", str(r[k]))
    live = compute(con)
    diagrams, diagram_numbers = {}, {}
    for path in sorted((DOCS / "diagrams" / "templates").glob("*.mmd")):
        template = path.read_text(encoding="utf-8")
        diagrams[path.stem] = fill(template, live)
        diagram_numbers[path.stem] = found = []
        for line in template.splitlines():
            if line.startswith("%%"):
                continue
            # split() alternates the template's own wording with the names of the figures filled into it
            for i, part in enumerate(PLACEHOLDER.split(line)):
                if i % 2:
                    found += [(t, Origin("warehouse", f"figure: {part}", FIGURES[part][0]))
                              for t in numbers(live[part])]
                else:
                    found += [(t, Origin("document", f"wording of docs/diagrams/templates/{path.name}", ""))
                              for t in numbers(part)]
    ownership_doc = (DOCS / "data-ownership.md").read_text(encoding="utf-8")
    benefits_doc = (DOCS / "benefits-case.md").read_text(encoding="utf-8")
    conformance = tomllib.loads((CONFIG / "conformance.toml").read_text(encoding="utf-8"))

    return Facts(
        as_of=con.execute("SELECT as_of_date FROM marts.parameters").fetchone()[0],
        head=head, fig=fig, dq=dq,
        dq_by_owner=frames["dq_by_owner"], dq_by_system=frames["dq_by_system"],
        rules=rules, kpis=kpis, three_way=three_way, ageing=ageing, job_top=job_top, stock=stock,
        trace_breaks=breaks, trace_customers=customers, match=match, source=source, turnover_12m=turnover,
        roadmap=roadmap,
        timeline=timeline,
        ownership=md_table(ownership_doc, "| Entity | Corvus MRP |"),
        escalation=md_table(ownership_doc, "| Step | Who |"),
        # Filled from the live warehouse, not read from the committed diagrams, so the maps cannot lag the data.
        diagrams=diagrams, diagram_numbers=diagram_numbers,
        benefits={
            "summary": md_table(benefits_doc, "| ID | Measure | Baseline, measured (synthetic) | Source |"),
            "pounds": md_table(benefits_doc, "| Benefit | Measured input (synthetic) |"),
            "not_claimed": md_table(benefits_doc, "| Measured figure (synthetic) | Value |"),
            "worse": md_table(benefits_doc, "| Measure | Why it may worsen |"),
            "assumptions": md_table(benefits_doc, "| ID | Assumption | Value used |"),
        },
        reconcile=config_values(tomllib.loads((CONFIG / "reconcile.toml").read_text(encoding="utf-8")),
                                "reconcile.toml"),
        sites={s["site_code"]: s["site_name"] for s in conformance["site"]},
        labour_rate=scalar["labour_rate"], jobs_reconciled=scalar["jobs_reconciled"],
        lines_assessed=scalar["lines_assessed"], kpi_count=scalar["kpi_count"],
        severity_weights=config_values(
            yaml.safe_load((CONFIG / "dq_rules.yaml").read_text(encoding="utf-8"))["severity_weights"],
            "dq_rules.yaml severity weight"),
        rows=rows, months=months, systems=systems, head_label=head_label,
    )


def strip_md(text: str) -> str:
    """Plain text from a markdown table cell: no emphasis, no code spans."""
    return re.sub(r"[*`]", "", text)
