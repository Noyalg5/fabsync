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

from fabsync.design.figures import FIGURES

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
    benefits: dict[str, list[list[str]]]
    reconcile: dict
    sites: dict[str, str]
    labour_rate: float
    jobs_reconciled: float
    lines_assessed: float

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


def load(con: duckdb.DuckDBPyConnection) -> Facts:
    head = {(e, k): float(v) for e, k, v in con.execute("SELECT engine, key, value FROM recon.headline").fetchall()}
    fig = {key: _one(con, sql) for key, (sql, _) in FIGURES.items()}
    dq = _df(con, "SELECT * FROM governance.dq_run ORDER BY finished_at DESC LIMIT 1").iloc[0].to_dict()

    definitions = yaml.safe_load((CONFIG / "kpis.yaml").read_text(encoding="utf-8"))["kpis"]
    kpis = _df(con, "SELECT kpi_id, name, value, unit, target, status, owner, secondary_label, secondary_value, "
                    "secondary_unit FROM marts.kpi_scorecard ORDER BY kpi_id")
    extra = pd.DataFrame([{"kpi_id": k["id"], "definition": k["definition"], "refresh": k["refresh"],
                           "caveat": k["caveat"]} for k in definitions])
    kpis = kpis.merge(extra, on="kpi_id", how="left", validate="one_to_one")

    three_way = _df(con, "SELECT category, count(*) AS lines, sum(value_at_risk) AS value FROM recon.three_way_lines "
                         "WHERE is_exception GROUP BY 1 ORDER BY value DESC")
    ageing = _df(con, "SELECT category, age_bucket, lines FROM recon.three_way_ageing")
    job_top = _df(con, "SELECT job_no, customer_name, unexplained_gap FROM recon.job_cost ORDER BY rank LIMIT 15")
    stock = _df(con, "SELECT site_code, section_type, lines, accurate_lines, 100 * line_accuracy AS accuracy, "
                     "value_error FROM recon.stock_summary ORDER BY line_accuracy, site_code, section_type")
    breaks = _df(con, "SELECT break_at, lines, kg / 1000 AS tonnes FROM recon.trace_breaks "
                      "WHERE break_at <> 'complete' ORDER BY kg DESC")
    customers = _df(con, "SELECT customer_name, exposed_kg / 1000 AS tonnes, exposed_jobs FROM recon.trace_customers "
                         "ORDER BY exposed_kg DESC, customer_name LIMIT 12")
    rules = _df(con, "SELECT dimension, severity, count(*) AS rules, count(*) FILTER (WHERE threshold_met) AS met "
                     "FROM governance.v_dq_latest GROUP BY ALL ORDER BY ALL")

    match = {
        "review_items": _one(con, "SELECT count(*) FROM core.v_match_review_queue"),
        "review_hours": _one(con, "SELECT sum(est_minutes) / 60 FROM core.v_match_review_queue"),
        "material_forms": _one(con, "SELECT values_total FROM governance.match_quality WHERE domain = 'material'"),
        "golden_materials": _one(con, "SELECT count(*) FROM core.material_golden"),
        "supplier_entities": _one(con, "SELECT count(*) FROM core.supplier_golden"),
    }
    source = {
        "raw_rows": _one(con, "SELECT sum(raw_rows) FROM governance.table_balance"),
        "files": _one(con, "SELECT count(*) FROM governance.table_balance"),
        "quarantined": _one(con, "SELECT count(*) FROM governance.quarantine"),
        "months": _one(con, "SELECT count(DISTINCT month) FROM marts.quality_cost_by_month"),
    }
    turnover = _one(con, "SELECT sum(turnover) FROM marts.quality_cost_by_month WHERE month > "
                         "(SELECT as_of_date FROM marts.parameters) - INTERVAL 12 MONTH")

    plan = (DOCS / "rollout-plan.md").read_text(encoding="utf-8")
    timeline = {r[0]: r[1:] for r in md_table(plan, "| | M1 |")}
    ownership_doc = (DOCS / "data-ownership.md").read_text(encoding="utf-8")
    benefits_doc = (DOCS / "benefits-case.md").read_text(encoding="utf-8")
    conformance = tomllib.loads((CONFIG / "conformance.toml").read_text(encoding="utf-8"))

    return Facts(
        as_of=con.execute("SELECT as_of_date FROM marts.parameters").fetchone()[0],
        head=head, fig=fig, dq=dq,
        dq_by_owner=_df(con, "SELECT owner, dq_index, rules, rules_met, critical_breaches "
                             "FROM governance.v_dq_scorecard_by_owner ORDER BY dq_index"),
        dq_by_system=_df(con, "SELECT system, dq_index, rules, rules_met, critical_breaches "
                              "FROM governance.v_dq_scorecard_by_system ORDER BY dq_index"),
        rules=rules, kpis=kpis, three_way=three_way, ageing=ageing, job_top=job_top, stock=stock,
        trace_breaks=breaks, trace_customers=customers, match=match, source=source, turnover_12m=turnover,
        roadmap=yaml.safe_load((CONFIG / "roadmap.yaml").read_text(encoding="utf-8")),
        timeline=timeline,
        ownership=md_table(ownership_doc, "| Entity | Corvus MRP |"),
        escalation=md_table(ownership_doc, "| Step | Who |"),
        diagrams={p.stem: p.read_text(encoding="utf-8") for p in sorted((DOCS / "diagrams").glob("*.mmd"))},
        benefits={
            "summary": md_table(benefits_doc, "| ID | Measure | Baseline, measured (synthetic) | Source |"),
            "pounds": md_table(benefits_doc, "| Benefit | Measured input (synthetic) |"),
            "not_claimed": md_table(benefits_doc, "| Measured figure (synthetic) | Value |"),
            "worse": md_table(benefits_doc, "| Measure | Why it may worsen |"),
            "assumptions": md_table(benefits_doc, "| ID | Assumption | Value used |"),
        },
        reconcile=tomllib.loads((CONFIG / "reconcile.toml").read_text(encoding="utf-8")),
        sites={s["site_code"]: s["site_name"] for s in conformance["site"]},
        labour_rate=_one(con, "SELECT labour_rate FROM marts.parameters"),
        jobs_reconciled=_one(con, "SELECT count(*) FROM recon.job_cost"),
        lines_assessed=_one(con, "SELECT count(*) FROM recon.three_way_lines WHERE category IN ('matched', "
                                 "'quantity variance', 'price variance', 'missing GRN', 'missing invoice')"),
    )


def strip_md(text: str) -> str:
    """Plain text from a markdown table cell: no emphasis, no code spans."""
    return re.sub(r"[*`]", "", text)
