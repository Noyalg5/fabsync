"""The lineage and quarantine page renders against a freshly built warehouse and its widgets work."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest

PAGE = str(Path(__file__).resolve().parents[1] / "app/pages/1_Lineage_and_quarantine.py")


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    root = tmp_path_factory.mktemp("app")
    generate(root / "raw", seed=DEFAULT_SEED)
    return run_ingest(root / "raw", root / "wh.duckdb", root / "report.md")


def page(warehouse, monkeypatch) -> AppTest:
    monkeypatch.setenv("FABSYNC_WAREHOUSE", str(warehouse.warehouse))
    return AppTest.from_file(PAGE, default_timeout=60).run()


def test_page_renders_run_summary(warehouse, monkeypatch) -> None:
    at = page(warehouse, monkeypatch)
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Rows quarantined"] == f"{warehouse.rows_quarantined:,}"
    assert metrics["Every file balances"] == "Yes"
    assert any("synthetic" in c.value.lower() for c in at.caption)


def test_quarantine_filter_and_row_trace(warehouse, monkeypatch) -> None:
    at = page(warehouse, monkeypatch)
    by_label = {s.label: s for s in at.selectbox}
    by_label["Source table"].select("time_bookings").run()
    {s.label: s for s in at.selectbox}["Rule"].select("ST-05").run()
    assert not at.exception
    inspect = {s.label: s for s in at.selectbox}["Inspect"]
    assert len(inspect.options) == 6
    at.number_input[0].set_value(3).run()
    assert not at.exception
    headings = [m.value for m in at.markdown if m.value.startswith("**")]
    assert any(h.startswith("**raw**") for h in headings)
