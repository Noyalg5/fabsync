"""Reconciliation engines, judged against the seeded defect manifest.

The overriding rule: no figure may be unexplainable. Every headline must be
reproduced from the rows its own SQL selects, and every row must lead back to a
source line.
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.match.pipeline import run_match
from fabsync.reconcile.common import EngineResult, Headline
from fabsync.reconcile.pipeline import UnexplainedFigure, run_reconcile, verify
from fabsync.reconcile.three_way import CATEGORIES


@pytest.fixture(scope="module")
def reconciled(tmp_path_factory):
    root = tmp_path_factory.mktemp("recon")
    manifest = generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "profiling.md")
    run_match(root / "wh.duckdb", root / "match.md")
    results = {r.engine: r for r in run_reconcile(root / "wh.duckdb", root / "recon.md")}
    con = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    yield root, manifest, results, con
    con.close()


def df(con, sql, *params) -> pd.DataFrame:
    return con.execute(sql, list(params)).df()


def one(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


# ---- nothing unexplainable ----------------------------------------------------- #

def test_every_headline_reproduces_from_its_rows(reconciled) -> None:
    _, _, results, con = reconciled
    heads = df(con, "SELECT * FROM recon.headline")
    assert len(heads) == sum(len(r.headlines) for r in results.values()) >= 40
    assert set(heads.engine) == {"three_way", "job_cost", "stock", "traceability"}
    for h in heads.itertuples():
        got = one(con, h.value_sql)
        assert abs(float(got or 0) - h.value) <= 0.011, h.key
        assert len(df(con, h.rows_sql)) > 0 or h.value == 0, h.key


def test_a_figure_that_does_not_reproduce_is_refused(reconciled) -> None:
    _, _, _, con = reconciled
    bad = Headline("stock", "x", "x", 12345.0, "GBP", "recon.stock_lines", "true", "sum(value_error)", "x")
    with pytest.raises(UnexplainedFigure):
        verify(con, [EngineResult("stock", pd.DataFrame(), pd.DataFrame(), 0.0, "x", [bad])])


def test_rows_trace_to_source_lines(reconciled) -> None:
    _, _, _, con = reconciled
    for table in ["three_way_lines", "stock_lines", "trace_lines", "job_cost_detail", "trace_allocations"]:
        missing = one(con, f"SELECT count(*) FROM recon.{table} WHERE source_file IS NULL OR source_row IS NULL")
        assert missing == 0, table
    orphans = one(con, """SELECT count(*) FROM recon.stock_lines s
                          ANTI JOIN raw.corvus_mrp_stock r ON r._source_row = s.source_row""")
    assert orphans == 0


def test_each_engine_returns_rows_summary_and_exposure(reconciled) -> None:
    _, _, results, con = reconciled
    for r in results.values():
        assert len(r.rows) and len(r.summary) and r.exposure > 0 and r.exposure_label
    assert one(con, "SELECT count(*) FROM recon.exposure") == 4


# ---- three-way match -------------------------------------------------------------- #

def test_every_po_line_in_exactly_one_category(reconciled) -> None:
    _, _, results, con = reconciled
    rows = results["three_way"].rows
    assert set(rows.category) <= set(CATEGORIES)
    assert rows[rows.line_type == "PO line"].line_id.is_unique
    assert len(rows[rows.line_type == "PO line"]) == one(con, "SELECT count(*) FROM staging.corvus_mrp_purchase_orders")


def test_three_way_finds_the_seeded_failures(reconciled) -> None:
    _, manifest, results, con = reconciled
    twm = manifest["defects"]["5_three_way_match"]
    rows = results["three_way"].rows
    assert set(rows[rows.category == "missing GRN"].po_no) == set(twm["po_without_grn"])
    grn_po = dict(con.execute("SELECT grn_no, po_no FROM staging.corvus_mrp_goods_received").fetchall())
    uninvoiced = {grn_po[g] for g in twm["grn_without_invoice"]}
    flagged = set(rows[(rows.category == "missing invoice") |
                       ((rows.category == "not yet due") & rows.received_date.notna())].po_no)
    assert flagged == uninvoiced
    over = {e["po_no"] for e in twm["invoice_over_po_by_more_than_5pct"]}
    price = rows[rows.category == "price variance"]
    assert set(price.po_no) <= over
    assert len(price) >= 0.8 * len(over)


def test_three_way_values_and_ageing(reconciled) -> None:
    _, _, results, con = reconciled
    rows = results["three_way"].rows
    missing = rows[rows.category == "missing GRN"]
    assert (missing.value_at_risk - missing.order_value).abs().max() < 0.01
    assert rows[rows.category.isin(["matched", "not yet due"])].value_at_risk.sum() == 0
    ageing = df(con, "SELECT sum(lines) AS n, sum(value_at_risk) AS v FROM recon.three_way_ageing").iloc[0]
    exc = rows[rows.is_exception]
    assert ageing.n == len(exc) and abs(ageing.v - exc.value_at_risk.sum()) < 0.01
    no_po = one(con, "SELECT count(*) FROM staging.finance_purchase_invoices WHERE po_reference IS NULL "
                     "AND nominal_code <> '7000'")
    assert (rows.category == "invoice with no PO").sum() == no_po
    assert rows.reason.notna().all()


def test_three_way_tolerances_come_from_config(reconciled, tmp_path) -> None:
    root, _, results, _ = reconciled
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    loose = Path("config/reconcile.toml").read_text(encoding="utf-8").replace("qty_tolerance = 0.02",
                                                                             "qty_tolerance = 0.15")
    (tmp_path / "loose.toml").write_text(loose, encoding="utf-8")
    again = {r.engine: r for r in run_reconcile(tmp_path / "wh.duckdb", tmp_path / "r.md", tmp_path / "loose.toml")}
    assert (again["three_way"].rows.category == "quantity variance").sum() == 0
    assert (results["three_way"].rows.category == "quantity variance").sum() > 100


# ---- job cost ---------------------------------------------------------------------- #

def test_labour_gap_finds_the_seeded_jobs(reconciled) -> None:
    _, manifest, results, _ = reconciled
    jobs = results["job_cost"].rows
    flagged = set(jobs[jobs.in_corvus & (jobs.labour_gap_pct.abs() > 0.15)].job_no)
    assert flagged == set(manifest["defects"]["7_labour_variance"]["jobs"])


def test_job_views_sum_from_detail(reconciled) -> None:
    _, _, _, con = reconciled
    mismatch = one(con, """
        WITH d AS (SELECT job_no, sum(amount) FILTER (WHERE view = 'finance' AND component = 'labour') AS fl,
                          sum(amount) FILTER (WHERE view = 'ops') AS ol,
                          sum(amount) FILTER (WHERE view = 'corvus' AND component = 'material') AS cm
                   FROM recon.job_cost_detail GROUP BY 1)
        SELECT count(*) FROM recon.job_cost j JOIN d USING (job_no)
        WHERE abs(coalesce(d.fl, 0) - j.finance_labour) > 0.05 OR abs(coalesce(d.ol, 0) - j.ops_labour) > 0.05
           OR abs(coalesce(d.cm, 0) - j.corvus_material) > 0.05""")
    assert mismatch == 0


def test_material_gap_explained_by_material(reconciled) -> None:
    _, _, results, con = reconciled
    jobs = results["job_cost"].rows.set_index("job_no")
    by_material = df(con, "SELECT job_no, sum(invoiced_value) AS inv, sum(issued_value) AS iss "
                          "FROM recon.job_material GROUP BY 1").set_index("job_no")
    both = jobs.join(by_material, how="inner")
    assert (both.inv - both.finance_material).abs().max() < 1.0
    assert (both.iss - both.corvus_material).abs().max() < 1.0


def test_job_ranking_and_finance_only_jobs(reconciled) -> None:
    _, manifest, results, con = reconciled
    jobs = results["job_cost"].rows
    assert list(jobs["rank"]) == list(range(1, len(jobs) + 1))
    assert jobs.unexplained_gap.abs().is_monotonic_decreasing
    finance_only = {j.removeprefix("finance ") for j in jobs[~jobs.in_corvus].job_no}
    with_costs = {c for (c,) in con.execute("SELECT DISTINCT job_code FROM staging.finance_job_costs").fetchall()}
    seeded = set(manifest["defects"]["3_job_code_mapping_gap"]["finance_only_job_codes"])
    assert finance_only == seeded & with_costs  # a code with sales but no costs has nothing to reconcile
    assert jobs.explanation.notna().all()


# ---- stock ---------------------------------------------------------------------------- #

def test_stock_offenders_are_the_seeded_lines(reconciled) -> None:
    _, manifest, results, _ = reconciled
    lines = results["stock"].rows
    expected = {f"{e['material_code']}|{e['site']}|{e['location']}"
                for e in manifest["defects"]["8_stock_accuracy"]["lines_with_count_variance"]}
    assert set(lines[~lines.accurate].line_id) == expected
    top = lines[lines.top_offender].sort_values("offender_rank")
    assert len(top) == min(20, len(expected)) and top.value_error.is_monotonic_decreasing


def test_stock_summary_by_site_and_section(reconciled) -> None:
    _, _, results, _ = reconciled
    s = results["stock"].summary
    assert s.lines.sum() == len(results["stock"].rows)
    assert ((s.line_accuracy >= 0.95) == s.meets_target).all()
    assert {"site_code", "section_type", "abs_error_kg", "value_error", "line_accuracy"} <= set(s.columns)


# ---- traceability ------------------------------------------------------------------------ #

def test_allocation_is_physically_possible(reconciled) -> None:
    _, _, _, con = reconciled
    over_receipt = one(con, """
        SELECT count(*) FROM (SELECT grn_no, sum(kg) AS used FROM recon.trace_allocations GROUP BY 1) a
        JOIN (SELECT g.grn_no, CAST(CASE g.uom WHEN 'KG' THEN g.qty_received WHEN 'M' THEN g.qty_received * m.mass
                                          WHEN 'EA' THEN g.qty_received * m.kg_per_ea END AS DOUBLE) AS kg
              FROM staging.corvus_mrp_goods_received g
              JOIN core.material_xref x ON x.source_table = 'goods_received' AND x.source_code = g.material_code
              JOIN core.material_golden m ON m.canonical_code = x.canonical_code) r USING (grn_no)
        WHERE a.used > r.kg + 0.01""")
    assert over_receipt == 0
    assert one(con, """SELECT count(*) FROM recon.trace_allocations a JOIN recon.trace_lines l
                       ON l.wo_no = a.wo_no AND l.line_no = a.line_no WHERE a.received_date > l.planned_finish""") == 0
    assert one(con, "SELECT count(*) FROM recon.trace_lines WHERE kg_allocated > kg + 0.01") == 0


def test_seeded_traceability_gaps_break_every_chain_they_touch(reconciled) -> None:
    _, manifest, _, con = reconciled
    gaps = set(manifest["defects"]["6_traceability_gaps"]["grn_missing_heat_or_cert"])
    touched = df(con, """SELECT DISTINCT a.grn_no, l.material_chain_complete FROM recon.trace_allocations a
                         JOIN recon.trace_lines l ON l.wo_no = a.wo_no AND l.line_no = a.line_no""")
    hit = touched[touched.grn_no.isin(gaps)]
    assert len(hit) and not hit.material_chain_complete.any()
    clean_complete = one(con, """SELECT count(*) FROM recon.trace_lines WHERE material_chain_complete
                                 AND break_at LIKE 'receipt:%'""")
    assert clean_complete == 0


def test_exposure_by_job_and_customer(reconciled) -> None:
    _, _, results, con = reconciled
    jobs = df(con, "SELECT * FROM recon.trace_jobs")
    exposed = jobs[jobs.en1090_exposure]
    assert exposed.despatched.all() and (exposed.exposed_lines > 0).all()
    customers = df(con, "SELECT * FROM recon.trace_customers")
    assert customers.exposed_jobs.sum() == len(exposed)
    assert abs(customers.exposed_kg.sum() - exposed.exposed_kg.sum()) < 1
    coverage = [h for h in results["traceability"].headlines if h.key == "coverage"][0].value
    assert 0 < coverage < 100


# ---- idempotency ------------------------------------------------------------------------- #

def test_rerun_is_identical(reconciled, tmp_path) -> None:
    root, _, _, _ = reconciled
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    run_reconcile(tmp_path / "wh.duckdb", tmp_path / "again.md")
    assert (tmp_path / "again.md").read_bytes() == (root / "recon.md").read_bytes()
    a = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    b = duckdb.connect(str(tmp_path / "wh.duckdb"), read_only=True)
    for (t,) in a.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'recon'").fetchall():
        sql = f"SELECT * FROM recon.{t} ORDER BY ALL"
        assert a.execute(sql).fetchall() == b.execute(sql).fetchall(), t
    a.close()
    b.close()


def test_as_of_date_drives_ageing(reconciled) -> None:
    _, _, results, _ = reconciled
    rows = results["three_way"].rows
    r = rows[rows.category == "missing GRN"].iloc[0]
    assert r.age_days == (date(2026, 8, 31) - r.promised_date).days
    assert r.promised_date <= date(2026, 8, 31) - timedelta(days=5)
