"""Delivery planning documents: complete, internally consistent, in step with the roadmap config, and every
figure they quote reproducible from the warehouse."""

from __future__ import annotations

import re
from collections import Counter
from itertools import pairwise
from pathlib import Path

import duckdb
import pytest
import yaml

from fabsync.design.figures import FIGURES, count, hours, money, pct, tonnes
from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.kpi.build import build_marts
from fabsync.match.pipeline import run_match
from fabsync.quality.engine import run_quality
from fabsync.reconcile.pipeline import run_reconcile

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/rollout-plan.md"
REGISTER = ROOT / "docs/risk-register.md"
TRAINING = ROOT / "docs/training-plan.md"
BENEFITS = ROOT / "docs/benefits-case.md"
ROADMAP = ROOT / "config/roadmap.yaml"

PHASES = ["1. Discovery and baseline", "2. Master data cleanse", "3. Read-only integration and reporting",
          "4. Process change and write-back", "5. Embed and handover"]
OWNERS = {"Purchasing Manager", "Production Controller", "Finance Manager", "Quality Manager", "Programme sponsor",
          "Programme manager", "Integration lead"}
CATEGORIES = {"Technical", "Data", "People", "Commercial", "Compliance"}
ROLES = ["Shop-floor operators", "Site supervisors", "Purchasing", "Finance", "Project managers", "Senior management"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def table_rows(text: str, header_start: str, occurrence: int = 0) -> list[list[str]]:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(header_start)]
    rows = []
    for line in lines[starts[occurrence] + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def all_tables(text: str, header_start: str) -> list[list[str]]:
    n = sum(line.startswith(header_start) for line in text.splitlines())
    return [row for k in range(n) for row in table_rows(text, header_start, k)]


def section(text: str, heading: str, level: int = 2) -> str:
    hashes = "#" * level
    m = re.search(rf"^{hashes} {re.escape(heading)}\n(.*?)(?=^#{{1,{level}}} |\Z)", text, re.S | re.M)
    assert m, heading
    return m.group(1)


def paragraph(sec: str, label: str) -> str:
    m = re.search(rf"\*\*{re.escape(label)}\.\*\* (.*?)(?:\n\n|\Z)", sec, re.S)
    return " ".join(m.group(1).split()) if m else ""


def bullets(sec: str, label: str) -> list[str]:
    m = re.search(rf"\*\*{re.escape(label)}\*\*\n\n(.*?)(?:\n\n|\Z)", sec, re.S)
    if not m:
        return []
    return [" ".join(i.split()) for i in re.split(r"^- ", m.group(1), flags=re.M) if i.strip()]


def months(label: str) -> tuple[int, int]:
    a, b = re.fullmatch(r"(\d+) to (\d+)", label).groups()
    return int(a), int(b)


def lead_duration(text: str) -> str:
    return re.match(r"\d+ (?:hours?|minutes)(?: \d+ minutes)?", text).group(0)


def band(score: int) -> str:
    return "low" if score <= 4 else "medium" if score <= 9 else "high" if score <= 14 else "very high"


# ---- rollout plan ------------------------------------------------------------------ #

def test_rollout_plan_has_five_phases_each_fully_specified() -> None:
    text = read(PLAN)
    assert "all data is synthetic" in text.lower()
    rows = table_rows(text, "| Phase | Months |")
    assert [r[0] for r in rows] == PHASES
    for name, span, _ in rows:
        sec = section(text, f"Phase {name}")
        first, last = months(span)
        assert paragraph(sec, "Duration") == f"Months {first} to {last}.", name
        for label in ["Objective", "Dependencies", "Roles involved"]:
            assert len(paragraph(sec, label).split()) >= 10, (name, label)
        for label in ["Activities", "Entry criteria", "Exit criteria"]:
            assert len(bullets(sec, label)) >= 2, (name, label)


def test_timeline_covers_18_months_with_a_review_every_quarter() -> None:
    text = read(PLAN)
    header = next(line for line in text.splitlines() if line.startswith("| | M1 |"))
    assert [c.strip() for c in header.strip("|").split("|")][1:] == [f"M{m}" for m in range(1, 19)]
    grid = {r[0]: r[1:] for r in table_rows(text, "| | M1 |")}
    spans = {r[0]: months(r[1]) for r in table_rows(text, "| Phase | Months |")}
    for name, (first, last) in spans.items():
        active = [m for m, cell in enumerate(grid[name], start=1) if cell == "■"]
        assert active == list(range(first, last + 1)), name
    assert spans[PHASES[0]][0] == 1 and spans[PHASES[-1]][1] == 18
    quarterly = [3, 6, 9, 12, 15, 18]
    assert [m for m, cell in enumerate(grid["Management committee review"], start=1) if cell == "◆"] == quarterly
    reviews = table_rows(text, "| Review | Month | Decisions |")
    assert [int(r[1]) for r in reviews] == quarterly and all(len(r) == 4 and all(r) for r in reviews)


def test_each_phase_starts_no_earlier_than_its_predecessor_and_overlaps_are_stated() -> None:
    spans = [months(r[1]) for r in table_rows(read(PLAN), "| Phase | Months |")]
    for (a_start, a_end), (b_start, b_end) in pairwise(spans):
        assert a_start <= b_start and a_end <= b_end


# ---- risk register ------------------------------------------------------------------ #

def register() -> list[dict]:
    keys = ["id", "category", "risk", "likelihood", "impact", "inherent", "mitigation", "owner",
            "residual_likelihood", "residual_impact", "residual"]
    out = []
    for row in table_rows(read(REGISTER), "| ID | Category | Risk |"):
        r = dict(zip(keys, row, strict=True))
        for k in ["likelihood", "impact", "inherent", "residual_likelihood", "residual_impact", "residual"]:
            r[k] = int(r[k].strip("*"))
        out.append(r)
    return out


def test_risk_register_is_scored_consistently() -> None:
    risks = register()
    assert "all data is synthetic" in read(REGISTER).lower()
    assert len(risks) >= 15
    assert len({r["id"] for r in risks}) == len(risks)
    categories = Counter(r["category"] for r in risks)
    assert set(categories) == CATEGORIES and min(categories.values()) >= 2
    for r in risks:
        scores = [r["likelihood"], r["impact"], r["residual_likelihood"], r["residual_impact"]]
        assert all(1 <= s <= 5 for s in scores), r["id"]
        assert r["inherent"] == r["likelihood"] * r["impact"], r["id"]
        assert r["residual"] == r["residual_likelihood"] * r["residual_impact"], r["id"]
        assert r["residual"] < r["inherent"], r["id"]
        assert r["owner"] in OWNERS, r["id"]
        assert len(r["mitigation"].split()) >= 30, f"{r['id']}: mitigation too thin to be specific"


def test_register_prose_and_heat_maps_agree_with_the_scores() -> None:
    text, risks = read(REGISTER), register()
    inherent = Counter(band(r["inherent"]) for r in risks)
    residual = Counter(band(r["residual"]) for r in risks)
    assert (f"Before mitigation, {inherent['very high']} risks are very high, {inherent['high']} high and "
            f"{inherent['medium']} medium.") in " ".join(text.split())
    still_high = [r["id"] for r in risks if band(r["residual"]) == "high"]
    assert (f"After mitigation, {len(still_high)} remain high ({' and '.join(still_high)}), {residual['medium']} are "
            f"medium and {residual['low']} low.") in " ".join(text.split())
    assert f"It holds {len(risks)} risks" in text
    for k, (lk, ik) in enumerate([("likelihood", "impact"), ("residual_likelihood", "residual_impact")]):
        grid = table_rows(text, "| Impact \\ Likelihood |", k)
        placed = {rid: (likelihood, 5 - i) for i, row in enumerate(grid)
                  for likelihood, cell in enumerate(row[1:], start=1) for rid in filter(None, cell.split(", "))}
        assert placed == {r["id"]: (r[lk], r[ik]) for r in risks}
    watched = table_rows(text, "| ID | Indicator |")
    assert [w[0] for w in watched] == [r["id"] for r in risks] and all(all(w) for w in watched)


def test_register_carries_the_risks_that_sink_projects_like_this() -> None:
    text, risks = read(REGISTER), {r["id"]: r["risk"].lower() for r in register()}
    must = {"R01": ["shop-floor", "time-booking"], "R02": ["cleanse", "order of magnitude"],
            "R03": ["key-person", "corvus"], "R04": ["en 1090", "transition"], "R05": ["dual-running", "fatigue"],
            "R06": ["finance calendar", "production week"], "R07": ["benefits", "baseline"]}
    for rid, words in must.items():
        assert all(w in risks[rid] for w in words), rid
        sec = section(text, f"{rid}. {register()[int(rid[1:]) - 1]['risk']}", level=3)
        for label in ["Why it sinks projects", "Early warning", "If it happens anyway"]:
            assert paragraph(sec, label), (rid, label)


# ---- training plan ------------------------------------------------------------------ #

def test_training_plan_covers_every_role() -> None:
    text = read(TRAINING)
    assert "all data is synthetic" in text.lower()
    summary = table_rows(text, "| Role | Method | Duration per person |")
    assert [r[0] for r in summary][:len(ROLES)] == ROLES
    for row in summary:
        assert len(row) == 5 and all(row), row[0]
        sec = section(text, row[0])
        for label in ["What changes for them", "Delivery method", "How competence is checked", "When"]:
            assert len(paragraph(sec, label).split()) >= 3, (row[0], label)
        assert len(bullets(sec, "What they need to learn.")) >= 3, row[0]
        assert lead_duration(paragraph(sec, "Duration")) == lead_duration(row[2]), \
            f"{row[0]}: duration in the summary disagrees with the role section"


# ---- roadmap config ------------------------------------------------------------------ #

def test_roadmap_config_agrees_with_the_documents() -> None:
    config = yaml.safe_load(read(ROADMAP))
    plan = read(PLAN)
    phases = []
    for name, span, _ in table_rows(plan, "| Phase | Months |"):
        sec = section(plan, f"Phase {name}")
        phases.append({"phase": name, "timing": f"Months {span}", "objective": paragraph(sec, "Objective"),
                       "entry": " ".join(bullets(sec, "Entry criteria")),
                       "exit": " ".join(bullets(sec, "Exit criteria"))})
    assert config["phases"] == phases
    assert config["reviews"] == [{"review": int(r), "month": int(m), "decisions": d, "evidence": e}
                                 for r, m, d, e in table_rows(plan, "| Review | Month | Decisions |")]
    assert config["risks"] == register()
    assert config["training"] == [dict(zip(["role", "method", "duration", "competence check", "when"], r, strict=True))
                                  for r in table_rows(read(TRAINING), "| Role | Method | Duration per person |")]


# ---- benefits case: labelling ------------------------------------------------------------------ #

def test_benefits_case_is_labelled_illustrative_throughout() -> None:
    text = read(BENEFITS)
    lines = text.splitlines()
    assert lines[0] == "# Benefits case (ILLUSTRATIVE)"
    assert lines[2].startswith("> **ILLUSTRATIVE.") and "synthetic" in lines[2].lower()
    assert [line for line in lines if line.strip()][-2].startswith("**ILLUSTRATIVE.**")
    for i, line in enumerate(lines):
        if line.startswith("|") and not lines[i - 1].startswith("|"):
            caption = next(lines[j] for j in range(i - 1, 0, -1) if lines[j].strip())
            if not caption.startswith("*ILLUSTRATIVE"):
                caption = " ".join(lines[j] for j in range(i - 3, i))
            assert "*ILLUSTRATIVE" in caption, f"table at line {i + 1} has no ILLUSTRATIVE caption"


def test_benefits_case_never_labels_a_modelled_figure_as_measured() -> None:
    text = read(BENEFITS)
    lines = text.splitlines()
    headers = [line for line, below in pairwise(lines) if line.startswith("| ") and below.startswith("| ---")]
    for line in headers:
        for cell in [c.strip().lower() for c in line.strip("|").split("|")]:
            if cell.startswith("baseline"):
                assert "measured (synthetic)" in cell, cell
            if cell.startswith("measured"):
                assert cell.endswith("(synthetic)"), cell
            if cell.startswith("target"):
                assert "modelled" in cell, cell
    for row in all_tables(text, "| ID | Measure | Baseline, measured (synthetic) | Target, modelled |"):
        assert "measured" not in row[3].lower(), row[0]


# ---- figures, rebuilt from the warehouse ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def con(tmp_path_factory):
    root = tmp_path_factory.mktemp("planning")
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "p.md")
    run_match(root / "wh.duckdb", root / "m.md")
    run_quality(root / "wh.duckdb")
    run_reconcile(root / "wh.duckdb", root / "r.md")
    build_marts(root / "wh.duckdb", dictionary=root / "d.md", report=root / "k.md")
    connection = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    yield connection
    connection.close()


def value(con, sql: str) -> float:
    return float(con.execute(sql).fetchone()[0])


def fig(con, key: str) -> str:
    sql, fmt = FIGURES[key]
    return fmt(value(con, sql))


def kpi(con, kpi_id: str, column: str = "value") -> str:
    return pct(value(con, f"SELECT {column} FROM marts.kpi_scorecard WHERE kpi_id = '{kpi_id}'"))


LATEST_DQ = ("SELECT * FROM governance.dq_results WHERE status = 'ok' AND run_id = "
             "(SELECT run_id FROM governance.dq_results ORDER BY evaluated_at DESC LIMIT 1)")
STRADDLES = "month(week_commencing) <> month(week_commencing + 6)"
TWELVE_MONTHS = "month > (SELECT as_of_date FROM marts.parameters) - INTERVAL 12 MONTH"


def dq_failed(con, rule: str) -> str:
    return count(value(con, f"SELECT records_failed FROM ({LATEST_DQ}) WHERE rule_id = '{rule}'"))


def dqi(con, met: tuple[str, ...] = ()) -> str:
    score = "CASE WHEN severity IN ({}) THEN 1 ELSE score END".format(",".join(f"'{s}'" for s in met) or "''")
    return f"{value(con, f'SELECT 100 * sum(weight * {score}) / sum(weight) FROM ({LATEST_DQ})'):.1f}"


def baselines(con) -> dict[str, list[str]]:
    capacity = "FROM marts.capacity_utilisation WHERE booked_hours IS NOT NULL"
    cert_ncr = "FROM marts.ncr_by_category WHERE category = 'Missing mill certificate'"
    out = {k: [kpi(con, k)] for k in ["KPI-01", "KPI-02", "KPI-03", "KPI-04", "KPI-05", "KPI-06", "KPI-08",
                                      "KPI-09"]}
    out["KPI-07"] = [kpi(con, "KPI-07", "secondary_value")]
    out["DQI"] = [dqi(con)]
    out["S-01"] = [f"{count(value(con, 'SELECT count(*) FROM core.v_match_review_queue'))} items"]
    out["S-02"] = [fig(con, "job_finance_only_codes")]
    out["S-03"] = [f"{fig(con, 'supplier_dupes_confirmed')} confirmed",
                   f"{fig(con, 'supplier_dupes_likely')} more likely"]
    out["S-04"] = [f"{fig(con, 'receipts_missing_cert')} of "
                   f"{count(value(con, 'SELECT count(*) FROM staging.corvus_mrp_goods_received'))} receipts"]
    out["S-05"] = [fig(con, "over_90_days")]
    open_lines = value(con, FIGURES["missing_grn_lines"][0]) + value(con, FIGURES["missing_invoice_lines"][0])
    out["S-06"] = [f"{count(open_lines)} lines "
                   f"({fig(con, 'missing_grn_lines')} and {fig(con, 'missing_invoice_lines')})"]
    out["S-07"] = [f"{fig(con, 'no_po_lines')} invoices", fig(con, "no_po_value")]
    out["S-08"] = [fig(con, "material_misallocated")]
    out["S-09"] = [fig(con, "unallocated_hours")]
    out["S-10"] = [f"{fig(con, 'ncr_uncosted')} of {fig(con, 'ncr_total')}"]
    out["S-11"] = [money(value(con, f"SELECT sum(ncr_cost) {cert_ncr}")),
                   f"{count(value(con, f'SELECT sum(ncrs) {cert_ncr}'))} NCRs"]
    out["S-13"] = [f"{count(value(con, f'SELECT count(*) {capacity} AND supervisor_vs_sheets_hours <> 0'))} of "
                   f"{count(value(con, f'SELECT count(*) {capacity}'))} site-weeks",
                   hours(value(con, f"SELECT sum(abs(supervisor_vs_sheets_hours)) {capacity}"))]
    return out


def test_every_benefits_baseline_is_measured_from_the_warehouse(con) -> None:
    text, expected = read(BENEFITS), baselines(con)
    rows = all_tables(text, "| ID | Measure | Baseline, measured (synthetic) |")
    assert {r[0] for r in rows} == set(expected), "a baseline with no query behind it, or a query with no baseline"
    for row in rows:
        for figure in expected[row[0]]:
            assert figure in row[2], f"{row[0]}: expected {figure} in '{row[2]}'"


def test_what_is_not_claimed_quotes_measured_figures(con) -> None:
    expected = {
        "Invoices with no purchase order": fig(con, "no_po_value"),
        "Short deliveries beyond the 2% tolerance": fig(con, "qty_var_value"),
        "Material cost charged to the wrong job": fig(con, "material_misallocated"),
        "Gross unexplained job cost gap": fig(con, "job_gap"),
        "WIP more than 90 days old": money(value(con, "SELECT sum(wip_value) FROM marts.wip_works_orders "
                                                      "WHERE age_days > 90")),
        "Goods received but not invoiced": fig(con, "missing_invoice_value"),
        "Stock value error": fig(con, "stock_value_error"),
        "Hours booked to works orders not in Corvus": fig(con, "unallocated_hours"),
        "Sales on jobs with incomplete traceability": fig(con, "trace_exposed_sales"),
        "Office time spent re-keying": "Not measured",
    }
    rows = table_rows(read(BENEFITS), "| Measured figure (synthetic) | Value |")
    assert {r[0]: r[1] for r in rows} == expected


def test_modelled_figures_follow_from_measured_inputs_and_stated_assumptions(con) -> None:
    text = " ".join(read(BENEFITS).split())
    assumptions = {r[0]: r[2] for r in table_rows(read(BENEFITS), "| ID | Assumption | Value used |")}
    a1 = a2 = 0.80
    a3, a5, a6, a8 = 180.0, 0.60, 0.25, 0.75
    a2_range, a4_range, a7_range = (0.50, 0.80, 0.95), (1, 2, 4), (0.50, 0.75, 0.90)
    assert assumptions["A1"] == "80%" and assumptions["A2"] == "80% (low 50%, high 95%)"
    assert assumptions["A3"] == "£180 a tonne" and assumptions["A4"] == "2 points (low 1, high 4)"
    assert assumptions["A5"] == "60%" and assumptions["A6"] == "25%" and assumptions["A8"] == "75%"
    assert assumptions["A7"] == "75% (low 50%, high 90%)"

    lines = dict(con.execute("SELECT category, count(*) FROM recon.three_way_lines GROUP BY 1").fetchall())
    assessed = sum(lines[c] for c in ["matched", "quantity variance", "price variance", "missing GRN",
                                      "missing invoice"])
    remaining = (lines["quantity variance"] * (1 - a1) + lines["price variance"] * (1 - a2)
                 + (lines["missing GRN"] + lines["missing invoice"]) * (1 - a8))
    assert f"| {kpi(con, 'KPI-05')} | {pct(100 * remaining / assessed)} |" in text
    assert f"/ {assessed:,} lines assessed" in text

    otif = value(con, "SELECT value FROM marts.kpi_scorecard WHERE kpi_id = 'KPI-01'")
    assert f"| {pct(otif + (100 - otif) * a6)} on today's definition |" in text

    wip, old = con.execute("SELECT sum(wip_value), sum(wip_value) FILTER (WHERE age_days > 90) "
                           "FROM marts.wip_works_orders").fetchone()
    assert f"| {pct(100 * old * (1 - a5) / (wip - old * a5))} |" in text

    assert f"| {dqi(con, ('critical', 'high'))}, held for three months |" in text

    coq = value(con, "SELECT 100 * sum(ncr_cost) / sum(turnover) FROM marts.quality_cost_by_month")
    ncrs, uncosted = value(con, FIGURES["ncr_total"][0]), value(con, FIGURES["ncr_uncosted"][0])
    assert f"rises to about {coq * ncrs / (ncrs - uncosted):.2f}%" in text

    used, bought = con.execute("SELECT sum(used_kg), sum(bought_kg) FROM marts.material_yield_lines").fetchone()
    per_tonne = 1000 * value(con, "SELECT sum(bought_kg * price_per_kg) / sum(bought_kg) FROM "
                                  "marts.material_yield_lines JOIN marts.material_price USING (canonical_code)")
    overcharge = value(con, FIGURES["price_var_value"][0])
    cert = value(con, "SELECT sum(ncr_cost) FROM marts.ncr_by_category WHERE category = 'Missing mill certificate'")
    assert (f"{tonnes(bought / 1000)} of bars bought for {tonnes(used / 1000)} used over 24 months "
            f"({pct(100 * used / bought)} yield), at an average £{per_tonne:,.0f} a tonne") in text
    assert f"(£{per_tonne - a3:,.0f} a tonne net)" in text
    assert f"{money(overcharge / 2)} a year, times A2" in text and f"{money(cert / 2)} a year, times A7" in text
    totals = []
    for a2s, up, a7s in zip(a2_range, a4_range, a7_range, strict=True):
        saved_t = (bought - used / (used / bought + up / 100)) / 2 / 1000
        parts = [overcharge / 2 * a2s, saved_t * (per_tonne - a3), cert / 2 * a7s]
        totals.append([money(p) for p in parts] + [money(sum(parts))])
    rows = {r[0]: r[3:6] for r in table_rows(read(BENEFITS), "| Benefit | Measured input (synthetic) |")}
    for k, name in enumerate(["Overcharges stopped", "Offcuts reused", "NCRs for a missing certificate avoided"]):
        assert rows[name] == [t[k] for t in totals], name
    assert rows["**Total a year**"] == [f"**{t[3]}**" for t in totals]


def test_ranges_and_turnover_quoted_in_the_benefits_case_are_measured(con) -> None:
    text = " ".join(read(BENEFITS).split())
    otif = con.execute(f"SELECT min(otif_pct), max(otif_pct) FROM marts.otif_by_month WHERE {TWELVE_MONTHS} "
                       "AND measured >= 20").fetchone()
    three_way = con.execute("SELECT min(exception_rate_pct), max(exception_rate_pct) FROM "
                            f"marts.three_way_exception_rate WHERE {TWELVE_MONTHS} "
                            "AND po_lines_assessed >= 20").fetchone()
    coq = con.execute(f"SELECT min(cost_of_quality_pct), max(cost_of_quality_pct) FROM marts.quality_cost_by_month "
                      f"WHERE {TWELVE_MONTHS}").fetchone()
    assert f"monthly OTIF ranged from {pct(otif[0])} to {pct(otif[1])}" in text
    assert f"ranged from {pct(three_way[0])} to {pct(three_way[1])}" in text
    assert f"monthly cost of quality from {coq[0]:.2f}% to {coq[1]:.2f}%" in text
    turnover = value(con, f"SELECT sum(turnover) FROM marts.quality_cost_by_month WHERE {TWELVE_MONTHS}")
    assert f"synthetic turnover of {money(turnover)} in the 12 months" in text


def test_figures_quoted_in_the_plan_and_register_are_measured(con) -> None:
    capacity = "FROM marts.capacity_utilisation"
    trace = {k: count(value(con, f"SELECT value FROM recon.headline WHERE engine = 'traceability' AND key = '{k}'"))
             for k in ["exposed_jobs", "exposed_customers", "break_heat_number_missing",
                       "break_mill_certificate_missing", "break_receipt_grade_unconfirmed",
                       "break_no_receipt_on_record", "break_no_delivery_note"]}
    straddle_hours = value(con, f"SELECT sum(booked_hours) FILTER (WHERE {STRADDLES}) {capacity}")
    all_hours = value(con, f"SELECT sum(booked_hours) {capacity}")
    weeks = value(con, f"SELECT count(DISTINCT week_commencing) {capacity}")
    straddling = value(con, f"SELECT count(DISTINCT week_commencing) FILTER (WHERE {STRADDLES}) {capacity}")
    register_text = " ".join(read(REGISTER).split())
    for phrase in [
        f"{fig(con, 'shopfloor_quarantined')} shop-floor rows are quarantined",
        f"{dq_failed(con, 'DQ-28')} bookings name no operation and {dq_failed(con, 'DQ-27')} name no operator",
        f"{fig(con, 'unallocated_hours')} are booked to {fig(con, 'orphan_wos')} works orders Corvus has never "
        "heard of",
        f"The match review queue is {count(value(con, 'SELECT count(*) FROM core.v_match_review_queue'))} decisions, "
        f"estimated at {value(con, 'SELECT sum(est_minutes) / 60 FROM core.v_match_review_queue'):.1f} hours",
        f"{fig(con, 'receipts_missing_cert')} receipts whose certificates must be recovered and "
        f"{fig(con, 'grade_unconfirmed_lines')} order and receipt lines with no grade",
        f"There are {fig(con, 'over_90_days')} purchasing exceptions older than 90 days, "
        f"{dq_failed(con, 'DQ-18')} stock lines not counted for 90 days, and "
        f"{count(value(con, 'SELECT count(*) FROM marts.wip_works_orders WHERE age_days > 90'))} works orders in WIP",
        f"come {fig(con, 'job_finance_only_codes')} finance-only job codes and {fig(con, 'supplier_dupes_confirmed')} "
        f"duplicate supplier entities, with {fig(con, 'supplier_dupes_likely')} more likely",
        f"The prototype holds {count(value(con, 'SELECT count(*) FROM core.material_golden'))} materials and "
        f"{count(value(con, 'SELECT count(*) FROM core.supplier_golden'))} supplier entities",
        f"Traceability coverage is {fig(con, 'coverage')} by weight. {fig(con, 'trace_exposed_tonnes')} have been "
        f"despatched on {trace['exposed_jobs']} jobs for {trace['exposed_customers']} customers",
        f"heat number is missing ({trace['break_heat_number_missing']} lines), the certificate is missing "
        f"({trace['break_mill_certificate_missing']}), the grade is unconfirmed on receipt "
        f"({trace['break_receipt_grade_unconfirmed']}), there is no receipt on record "
        f"({trace['break_no_receipt_on_record']}) or there is no delivery note ({trace['break_no_delivery_note']})",
        f"Of {count(weeks)} production weeks in the synthetic capacity sheets, {count(straddling)} straddle a "
        f"month end. They carry {count(straddle_hours)} of the {count(all_hours)} hours",
        f"booked, {100 * straddle_hours / all_hours:.0f}%.",
    ]:
        assert phrase in register_text, phrase
    plan_text = " ".join(read(PLAN).split())
    assert f"({fig(con, 'receipts_missing_cert')} in the prototype)" in plan_text
    assert f"({fig(con, 'job_finance_only_codes')} in the prototype)" in plan_text
    assert f"({fig(con, 'over_90_days')} lines in the prototype)" in plan_text
