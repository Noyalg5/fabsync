"""KPI layer: definitions complete and honest, views documented, figures reproducible from source."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.kpi.build import KPI_PATH, KpiError, build_marts, load_definitions, status
from fabsync.match.pipeline import run_match
from fabsync.reconcile.pipeline import run_reconcile

REQUIRED_KPIS = ["OTIF", "Labour variance", "yield", "Stock accuracy", "Three-way match", "traceability",
                 "WIP", "Capacity utilisation", "cost of quality"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("kpi")
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "p.md")
    run_match(root / "wh.duckdb", root / "m.md")
    run_reconcile(root / "wh.duckdb", root / "r.md")
    result = build_marts(root / "wh.duckdb", dictionary=root / "dictionary.md", report=root / "kpi.md")
    con = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    yield root, result, con
    con.close()


def one(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


def value(result, kpi_id: str) -> float:
    return float(result.scorecard.set_index("kpi_id").loc[kpi_id, "value"])


def edited(tmp_path: Path, change) -> Path:
    doc = yaml.safe_load(KPI_PATH.read_text(encoding="utf-8"))
    change(doc)
    path = tmp_path / "kpis.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


# ---- definitions ------------------------------------------------------------------ #

def test_every_required_kpi_is_defined() -> None:
    names = " ".join(k["name"] for k in load_definitions()["kpis"])
    for needle in REQUIRED_KPIS:
        assert needle.lower() in names.lower(), needle


def test_every_definition_is_complete() -> None:
    for k in load_definitions()["kpis"]:
        for field in ("name", "definition", "formula", "sources", "owner", "refresh", "caveat"):
            assert str(k[field]).strip(), (k["id"], field)
        assert len(k["definition"].split(".")) <= 2, "definition should be one sentence"
        assert any(s in k["sources"] for s in ("corvus_mrp", "finance", "shop_floor"))


@pytest.mark.parametrize("caveat", ["", "May be wrong."])
def test_a_kpi_without_an_honest_caveat_is_refused(tmp_path, caveat) -> None:
    def change(doc):
        doc["kpis"][0]["caveat"] = caveat
    with pytest.raises(KpiError, match="caveat"):
        load_definitions(edited(tmp_path, change))


def test_undocumented_view_is_refused(built, tmp_path) -> None:
    root, _, _ = built
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")

    def change(doc):
        doc["kpis"][0]["views"].pop("marts.otif_by_site")
    with pytest.raises(KpiError, match="undocumented"):
        build_marts(tmp_path / "wh.duckdb", edited(tmp_path, change), dictionary=tmp_path / "d.md",
                    report=tmp_path / "k.md")


def test_status_logic() -> None:
    assert status({"direction": "higher", "target": 95}, 96) == "on target"
    assert status({"direction": "lower", "target": 5}, 6) == "off target"
    assert status({"direction": "abs_lower", "target": 10}, -9) == "on target"
    assert status({"direction": "band", "target_low": 75, "target_high": 95}, 97) == "off target"
    assert status({"direction": "none"}, 1.0) == "for information"


# ---- the views -------------------------------------------------------------------- #

def test_every_marts_object_is_documented(built) -> None:
    _, result, con = built
    views = con.execute("SELECT view_name, comment FROM duckdb_views() WHERE schema_name = 'marts'").fetchall()
    assert len(views) >= 20
    assert all(c and len(c) > 20 for _, c in views)
    assert {f"marts.{v}" for v, _ in views} | {"marts.parameters"} == set(result.views.view)


def test_breakdowns_required_by_the_brief(built) -> None:
    _, _, con = built
    cols = lambda v: {c for (c,) in con.execute(  # noqa: E731
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'marts' AND table_name = ?",
        [v]).fetchall()}
    assert "month" in cols("otif_by_month") and "customer_name" in cols("otif_by_customer")
    assert "site_code" in cols("otif_by_site")
    assert "wo_no" in cols("labour_variance_by_works_order") and "job_no" in cols("labour_variance_by_job")
    assert {"section_type", "offcut_waste_pct"} <= cols("material_yield_by_section_type")
    assert {"week_commencing", "site_code", "utilisation_pct"} <= cols("capacity_utilisation")
    assert [b for (b,) in con.execute("SELECT age_bucket FROM marts.wip_ageing").fetchall()] == [
        "0-30 days", "31-60 days", "61-90 days", "90+ days"]


def test_otif_reproduces_from_delivery_notes(built) -> None:
    _, result, con = built
    rows = con.execute("SELECT despatch_date, promised_date, tonnage, works_order_tonnes FROM marts.otif_deliveries"
                       ).fetchall()
    measured = [r for r in rows if r[1] is not None]
    hits = sum(1 for d, p, t, w in measured if d <= p and t is not None and w is not None and float(t) >= 0.98 * w)
    assert value(result, "KPI-01") == round(100 * hits / len(measured), 1)
    assert len(rows) == one(con, "SELECT count(*) FROM core.delivery_notes")
    assert one(con, "SELECT sum(deliveries) FROM marts.otif_by_month") == len(rows)


def test_kpis_agree_with_reconciliation(built) -> None:
    _, result, con = built
    head = dict(con.execute("SELECT engine || '.' || key, value FROM recon.headline").fetchall())
    assert abs(value(result, "KPI-04") - head["stock.line_accuracy"]) < 0.06
    assert abs(value(result, "KPI-06") - head["traceability.coverage"]) < 0.06
    secondary = result.scorecard.set_index("kpi_id").loc["KPI-05", "secondary_value"]
    assert abs(secondary - head["three_way.value_at_risk"]) < 0.01


def test_labour_and_quality_cost_reproduce(built) -> None:
    _, result, con = built
    planned, actual = con.execute("""
        SELECT sum(w.planned_hours), sum(coalesce(b.h, 0)) FROM core.works_orders w
        LEFT JOIN (SELECT wo_no, sum(hours) h FROM core.time_bookings WHERE wo_matched GROUP BY 1) b USING (wo_no)
        WHERE w.status IN ('COMPLETE', 'CLOSED')""").fetchone()
    assert value(result, "KPI-02") == round(100 * float(actual - planned) / float(planned), 1)
    cost = float(one(con, "SELECT sum(cost_impact) FROM core.ncrs"))
    turnover = float(one(con, "SELECT sum(net_amount) FROM staging.finance_sales_invoices"))
    assert value(result, "KPI-09") == round(100 * cost / turnover, 2)


def test_yield_is_physically_sensible(built) -> None:
    _, result, con = built
    assert one(con, "SELECT count(*) FROM marts.material_yield_lines WHERE bought_m < used_m - 1e-6") == 0
    assert one(con, "SELECT count(*) FROM marts.material_yield_lines WHERE length_mm = 12000 AND offcut_m > 0") == 0
    assert one(con, "SELECT cut_yield_pct FROM marts.material_yield_by_section_type "
                    "WHERE section_type = 'PLATE'") is None
    assert 0 < value(result, "KPI-03") < 100


def test_capacity_and_wip(built) -> None:
    _, result, con = built
    assert one(con, "SELECT count(*) FROM marts.capacity_utilisation") == one(
        con, "SELECT count(*) FROM core.weekly_capacity")
    assert 50 < value(result, "KPI-08") < 120
    assert abs(value(result, "KPI-07") - float(one(con, "SELECT sum(wip_value) FROM marts.wip_ageing"))) < 0.05
    despatched = one(con, """SELECT count(*) FROM marts.wip_works_orders w
                             JOIN marts.works_order_despatch d USING (wo_no)""")
    assert despatched == 0


# ---- documents and idempotency ------------------------------------------------------ #

def test_dictionary_lists_every_kpi_with_its_caveat(built) -> None:
    root, result, _ = built
    text = (root / "dictionary.md").read_text(encoding="utf-8")
    assert "synthetic" in text.lower()
    assert "| ID | KPI | Definition | Formula | Sources and systems | Owner | Refresh | Target | Caveat |" in text
    for d in result.definitions.itertuples():
        row = next(line for line in text.splitlines() if line.startswith(f"| {d.kpi_id} |"))
        assert d.caveat.replace("|", "\\|") in row


def test_report_never_shows_a_figure_without_its_caveat(built) -> None:
    root, result, _ = built
    text = (root / "kpi.md").read_text(encoding="utf-8")
    for d in result.definitions.itertuples():
        section = text.split(f"## {d.kpi_id} ")[1].split("\n## ")[0]
        assert "**Caveat.**" in section and d.caveat[:60] in section
    assert not re.search(r"\bnan\b", text)


def test_rebuild_is_identical(built, tmp_path) -> None:
    root, first, _ = built
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    second = build_marts(tmp_path / "wh.duckdb", dictionary=tmp_path / "d.md", report=tmp_path / "k.md")
    assert first.scorecard.equals(second.scorecard)
    assert (tmp_path / "d.md").read_bytes() == (root / "dictionary.md").read_bytes()
    assert (tmp_path / "k.md").read_bytes() == (root / "kpi.md").read_bytes()
