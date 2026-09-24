"""The Streamlit app: every page renders, in the right order, fast, with the banner, and follows the design rules.

Design rules checked on the charts each page actually produces: no pie charts, no
dual axes, every data axis titled, no legends (direct labelling), and the
source-system colours used where systems are compared.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from fabsync import ui
from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.kpi.build import build_marts
from fabsync.match.pipeline import run_match
from fabsync.quality.engine import run_quality
from fabsync.reconcile.pipeline import run_reconcile

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app/app.py")
PAGES = ["views/overview.py", "views/source_systems.py", "views/data_quality.py", "views/master_data.py",
         "views/reconciliation.py", "views/performance.py", "views/governance.py", "views/roadmap.py"]
TITLES = ["Overview", "Source systems", "Data quality", "Master data", "Reconciliation", "Performance", "Governance",
          "Roadmap"]


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    root = tmp_path_factory.mktemp("app")
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "p.md")
    run_match(root / "wh.duckdb", root / "m.md")
    run_quality(root / "wh.duckdb")
    run_reconcile(root / "wh.duckdb", root / "r.md")
    build_marts(root / "wh.duckdb", dictionary=root / "d.md", report=root / "k.md")
    return root / "wh.duckdb"


@pytest.fixture()
def app(warehouse, monkeypatch) -> AppTest:
    monkeypatch.setenv("FABSYNC_WAREHOUSE", str(warehouse))
    return AppTest.from_file(APP, default_timeout=60).run()


def specs(at: AppTest) -> list[dict]:
    return [json.loads(c.proto.spec) for c in at.get("vega_lite_chart")]


def layers(spec: dict) -> list[dict]:
    return spec.get("layer", [spec])


def test_pages_are_in_story_order() -> None:
    text = Path(APP).read_text(encoding="utf-8")
    assert re.findall(r'st\.Page\("[^"]+", title="([^"]+)"', text) == TITLES
    assert re.findall(r'st\.Page\("([^"]+)"', text) == PAGES


def test_every_page_renders_with_banner_fast(app) -> None:
    for page in PAGES:
        app.switch_page(page).run()  # first visit fills the cache
        started = time.perf_counter()
        app.switch_page(page).run()
        elapsed = time.perf_counter() - started
        assert not app.exception, (page, [e.value for e in app.exception])
        assert elapsed < 3.0, (page, elapsed)
        banners = [h for h in app.get("html") if ui.BANNER in str(h.proto)]
        assert banners, page
        assert app.title, page


def test_charts_follow_the_design_rules(app) -> None:
    seen = 0
    for page in PAGES:
        app.switch_page(page).run()
        for spec in specs(app):
            seen += 1
            assert "resolve" not in json.dumps(spec), f"{page}: independent scales mean a dual axis"
            for layer in layers(spec):
                mark = layer["mark"]["type"] if isinstance(layer["mark"], dict) else layer["mark"]
                assert mark not in ("arc", "pie"), page
                colour = layer.get("encoding", {}).get("color", {})
                if isinstance(colour, dict) and "field" in colour:
                    assert colour.get("legend", "missing") is None, f"{page}: legends are replaced by labels"
            data_layer = next(la for la in layers(spec) if la["mark"]["type"] in ("bar", "line"))
            for axis in ("x", "y"):
                enc = data_layer["encoding"][axis]
                if enc["type"] in ("quantitative", "temporal"):
                    assert enc.get("title"), f"{page}: {axis} axis has no title"
    assert seen >= 8


def test_system_colours_used_where_systems_are_compared(app) -> None:
    app.switch_page("views/data_quality.py").run()
    chart = next(c for c in app.get("vega_lite_chart") if "_colour" in c.proto.spec)
    payload = b"".join(d.data.data for d in chart.proto.datasets)
    for colour in ui.SYSTEM_COLOURS.values():
        assert colour.encode() in payload


def test_headline_figures_open_their_rows(app) -> None:
    opened = 0
    for page in PAGES:
        app.switch_page(page).run()
        keys = [b.key for b in app.button if b.key and b.key.startswith(("hl_", "hlrow_"))][:4]
        for key in keys:
            app.switch_page(page).run()
            app.button(key=key).click().run()
            assert not app.exception, (page, key, [e.value for e in app.exception])
            assert any(m.value.startswith("**") and ":" in m.value for m in app.markdown), (page, key)
            opened += 1
    assert opened >= 20


def test_every_kpi_figure_is_clickable(app) -> None:
    app.switch_page("views/performance.py").run()
    keys = [b.key for b in app.button if b.key and b.key.startswith("hl_kpi_")]
    assert len(keys) == 9
    captions = " ".join(c.value for c in app.caption)
    assert captions.count("Caveat:") >= 9


def test_money_is_shown_in_pounds(app) -> None:
    app.switch_page("views/overview.py").run()
    labels = [b.label for b in app.button if b.key and b.key.startswith("hl_")]
    assert any(re.fullmatch(r"£\d{1,3}(,\d{3})+", label) for label in labels)
    assert ui.gbp(-1234567.4) == "-£1,234,567"


def test_offline_and_neutral() -> None:
    config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config
    assert 'address = "localhost"' in config  # otherwise Streamlit fetches the public IP at startup
    for path in [ROOT / "src/fabsync/ui.py", *sorted((ROOT / "app").rglob("*.py"))]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), path
        assert "gradient" not in text.lower(), path
    assert len({ui.ACCENT}) == 1 and ui.ACCENT not in ui.SYSTEM_COLOURS.values()


def test_missing_warehouse_explains_what_to_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FABSYNC_WAREHOUSE", str(tmp_path / "none.duckdb"))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("make run-all" in i.value for i in at.info)
