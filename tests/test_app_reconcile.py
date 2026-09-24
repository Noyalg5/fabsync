"""The reconciliation page renders and drills from each engine's headline to rows to a source line."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.match.pipeline import run_match
from fabsync.reconcile.pipeline import run_reconcile

PAGE = str(Path(__file__).resolve().parents[1] / "app/pages/2_Reconciliation.py")


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    root = tmp_path_factory.mktemp("app_recon")
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "p.md")
    run_match(root / "wh.duckdb", root / "m.md")
    run_reconcile(root / "wh.duckdb", root / "r.md")
    return root / "wh.duckdb"


def test_drill_from_every_engine(warehouse, monkeypatch) -> None:
    monkeypatch.setenv("FABSYNC_WAREHOUSE", str(warehouse))
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception and len(at.metric) == 4
    for engine in ["three_way", "job_cost", "stock", "traceability"]:
        at.radio[0].set_value(engine).run()
        assert not at.exception, engine
        assert any("Recomputed now" in m.value for m in at.markdown)
    at.radio[0].set_value("stock").run()
    assert any(m.value.startswith("As received in") for m in at.markdown)
