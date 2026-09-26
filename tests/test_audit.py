"""The traceability audit: every number in the management pack and on the Overview page traces to its source.

Synthetic data only. The audit runs in full, as `make audit` runs it: against a warehouse built from the default seed,
with a control warehouse built from another. The committed report must match what it finds.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pytest
import yaml

from fabsync import audit
from fabsync.ingest.generate_sources import DEFAULT_SEED
from fabsync.pack import charts, document
from fabsync.provenance import ledger, total, trace, word

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    return audit.build_warehouse(tmp_path_factory.mktemp("audit-real"), DEFAULT_SEED)


@pytest.fixture(scope="module")
def found(warehouse, tmp_path_factory):
    control = audit.build_control(tmp_path_factory.mktemp("audit-control"))
    return audit.audit(warehouse, control, tmp_path_factory.mktemp("audit-out"))


def test_every_number_traces_to_a_source(found):
    assert [(f.place, f.token, f.context) for f in found if f.kind == "untraced"] == []


def test_the_audit_reads_every_page_chart_and_the_overview(found):
    places = {f.place for f in found}
    assert {f"Pack page {n}" for n in range(1, 17)} <= places
    charts_read = {p.removeprefix("Pack figure ") for p in places if p.startswith("Pack figure ")}
    assert len(charts_read) == 12 and "10-target-architecture" not in charts_read  # the only chart with no numbers
    assert "App Overview page" in places
    assert len(found) > 800


def test_the_overview_shows_only_warehouse_figures(found):
    """Every figure on the Overview page is a query result; the rest are identifiers and the scenario's one date."""
    kinds = {f.kind for f in found if f.place == "App Overview page"}
    assert kinds <= {"warehouse", "structure", "scenario"}
    assert [f.token for f in found if f.place == "App Overview page" and f.kind == "scenario"] == ["2006"]


def test_each_number_cites_the_same_source_in_the_control_build(found):
    paired = [f for f in found if f.same_source is not None]
    assert len(paired) > 0.9 * len(found)
    assert [(f.place, f.token, f.origin.name, f.control) for f in paired if not f.same_source] == []


def test_warehouse_numbers_change_with_the_data(found):
    varied = [f for f in found if f.kind == "warehouse" and f.varies]
    fixed = [f for f in found if f.kind == "warehouse" and f.varies is False]
    assert len(varied) > len(fixed)


def test_the_committed_report_is_current(found):
    assert (ROOT / "docs/traceability-audit.md").read_text(encoding="utf-8") == audit.report(found), \
        "run make audit"


def test_a_number_typed_by_hand_is_caught(warehouse, tmp_path, monkeypatch):
    cover = document.Pack.cover

    def typed(self):
        out = cover(self)
        return out[:1] + [self.p("Typed by hand: 4,321 hours saved.")] + out[1:]

    monkeypatch.setattr(document.Pack, "cover", typed)
    untraced = [(f.place, f.token) for f in audit.read(warehouse, tmp_path) if f.kind == "untraced"]
    assert untraced == [("Pack page 1", "4,321")]


def test_a_printed_number_records_its_source():
    with ledger() as entries:
        value = trace(4_314_978.2, "warehouse", "value at risk", "SELECT value FROM recon.headline")
        systems = trace(3, "warehouse", "systems", "SELECT 3")
        text = f"£{value / 1e6:.2f}m across {word(systems)} systems, {total([systems, systems], 'twice'):.0f} in all"
    assert text == "£4.31m across three systems, 6 in all"
    assert [(t, o.name) for t, o, _ in entries] == [("4.31", "value at risk"), ("three", "systems"), ("6", "twice")]


def test_identifiers_and_scales_are_not_taken_for_figures():
    text = "Page 3. R04 and KPI-05 under EN 1090 and DQ-22; the index is out of 100; phases 2 and 3; scored from 1 to 5"
    assert {f.kind for f in audit.scan("test", text)} == {"structure"}


def test_config_caveats_that_describe_the_data_hold(warehouse):
    """Two KPI caveats in config/kpis.yaml describe the data in words; the audit lists them as config, so they are
    checked here."""
    caveats = [k["caveat"] for k in yaml.safe_load((ROOT / "config/kpis.yaml").read_text(encoding="utf-8"))["kpis"]]
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        promised = next(c for c in caveats if "no promised date" in c)
        missing, notes = con.execute("SELECT count(*) FILTER (WHERE promised_date IS NULL), count(*) "
                                     "FROM core.delivery_notes").fetchone()
        assert round(100 * missing / notes) == int(re.search(r"no promised date \(about (\d+)%\)", promised).group(1))
        stock = next(c for c in caveats if "last counted more than 90 days ago" in c)
        assert "about a third" in stock
        stale, counted = con.execute(
            "SELECT count(*) FILTER (WHERE last_count_date < (SELECT as_of_date FROM marts.parameters) - 90), "
            "count(*) FROM recon.stock_lines WHERE counted_qty IS NOT NULL").fetchone()
        assert 0.25 <= stale / counted <= 0.42
    finally:
        con.close()


def test_risk_bands_on_the_heat_map_match_the_register():
    text = " ".join((ROOT / "docs/risk-register.md").read_text(encoding="utf-8").split())
    bands = re.findall(r"(\d+) to (\d+) ([a-z ]+?)(?:,|\.)", re.search(r"Scores fall into four bands: ([^.]+\.)",
                                                                        text).group(1))
    assert [(int(hi), name) for _, hi, name in bands] == [(top, name) for top, name, _ in charts.BANDS]
    assert [int(lo) for lo, _, _ in bands] == [1] + [top + 1 for top, _, _ in charts.BANDS[:-1]]
