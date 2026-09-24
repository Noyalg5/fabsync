"""Design documentation: diagrams current with the data, complete, and the documents internally consistent."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pytest
import yaml

from fabsync.design.figures import FIGURES, compute
from fabsync.design.render import DOC_TEMPLATE, PLACEHOLDER, TEMPLATES, RenderError, fill
from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.kpi.build import build_marts
from fabsync.match.pipeline import run_match
from fabsync.reconcile.pipeline import run_reconcile

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "docs/diagrams"
ROLES = {"Purchasing Manager", "Production Controller", "Finance Manager", "Quality Manager"}
NAMES = ["as-is-order-to-cash", "as-is-procure-to-pay", "to-be-architecture"]


@pytest.fixture(scope="module")
def figures(tmp_path_factory) -> dict[str, str]:
    root = tmp_path_factory.mktemp("design")
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "p.md")
    run_match(root / "wh.duckdb", root / "m.md")
    run_reconcile(root / "wh.duckdb", root / "r.md")
    build_marts(root / "wh.duckdb", dictionary=root / "d.md", report=root / "k.md")
    con = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    try:
        return compute(con)
    finally:
        con.close()


def table_rows(text: str, header_start: str) -> list[list[str]]:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(header_start))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


# ---- diagrams ------------------------------------------------------------------------ #

def test_committed_diagrams_match_the_data(figures) -> None:
    for template in sorted(TEMPLATES.glob("*.mmd")):
        committed = (DIAGRAMS / template.name).read_text(encoding="utf-8")
        assert committed == fill(template.read_text(encoding="utf-8"), figures), f"{template.name}: run make diagrams"
    assert (ROOT / "docs/process-maps.md").read_text(encoding="utf-8") == fill(
        DOC_TEMPLATE.read_text(encoding="utf-8"), figures)


def test_every_figure_used_and_known() -> None:
    used = set()
    for template in list(TEMPLATES.glob("*.mmd")) + [DOC_TEMPLATE]:
        used |= set(PLACEHOLDER.findall(template.read_text(encoding="utf-8")))
    assert used <= set(FIGURES)
    with pytest.raises(RenderError):
        fill("{{no_such_figure}}", {})


def test_rendered_images_exist_and_carry_the_figures() -> None:
    for name in NAMES:
        svg = (DIAGRAMS / f"{name}.svg").read_text(encoding="utf-8")
        png = (DIAGRAMS / f"{name}.png").read_bytes()
        assert svg.lstrip().startswith("<svg") and png[:8] == b"\x89PNG\r\n\x1a\n", name
        source = (DIAGRAMS / f"{name}.mmd").read_text(encoding="utf-8")
        for figure in re.findall(r"£[\d.,]+[mk]?", source):
            assert figure in svg, f"{name}: {figure} not in the rendered SVG; run make diagrams"


def test_process_maps_show_boundaries_rekeys_sheets_and_costed_breaks() -> None:
    for name in NAMES[:2]:
        text = (DIAGRAMS / f"{name}.mmd").read_text(encoding="utf-8")
        assert {"Corvus MRP", "Finance system"} <= set(re.findall(r'subgraph \w+\["([^"]+)"\]', text))
        assert text.count("re-key") >= 4, name
        assert re.search(r'\[/"[^"]+"/\]', text), f"{name}: spreadsheets drawn as sheets"
        breaks = re.findall(r'B\d+\{\{"(.*?)"\}\}', text)
        assert len(breaks) >= 7, name
        for label in breaks:
            assert re.search(r"\d", label), f"{name}: break point without a measured figure: {label[:60]}"
        assert "{{" not in re.sub(r'\{\{"', "", text), name


def test_target_architecture_shows_what_stays_changes_and_is_retired() -> None:
    text = (DIAGRAMS / "to-be-architecture.mmd").read_text(encoding="utf-8")
    for component in ["Corvus MRP: retained", "Finance system: retained", "Integration layer: new",
                      "Master data service: new", "Data warehouse: new", "Reporting: new", "Shop-floor forms: new"]:
        assert component in text
    assert 'subgraph RETIRED["Retired"]' in text and 'subgraph KEY["Key"]' in text


# ---- documents -------------------------------------------------------------------------- #

def test_integration_design_is_complete() -> None:
    text = (ROOT / "docs/integration-design.md").read_text(encoding="utf-8")
    assert "synthetic" in text.lower()
    for term in ["interface", "system of record", "golden record", "crosswalk", "integration layer",
                 "master data service", "nightly extract", "quarantine", "lineage", "master data"]:
        assert re.search(rf"\*\*{term}\*\*", text, re.I), f"term not defined: {term}"
    header = ("| ID | Source system | Target system | Direction | Entity | Frequency | Mechanism | Owner | "
              "Failure mode |")
    interfaces = table_rows(text, header)
    assert len(interfaces) >= 15
    for row in interfaces:
        assert len(row) == 9 and all(row), row[0]
        assert any(role in row[7] for role in ROLES | {"Each data owner", "Owner of the entity"}), row[0]
    sor = table_rows(text, "| Entity | System of record |")
    assert len(sor) >= 14
    rules = table_rows(text, "| Entity | Field | Winner | Why |")
    assert len(rules) >= 15 and all(len(r) == 4 and all(r) for r in rules)


def test_data_ownership_matrix_is_consistent() -> None:
    text = (ROOT / "docs/data-ownership.md").read_text(encoding="utf-8")
    assert "synthetic" in text.lower()
    rows = table_rows(text, "| Entity | Corvus MRP | Finance system | Shop-floor forms |")
    assert len(rows) >= 14
    for row in rows:
        systems = row[1:6]
        assert sum(cell.startswith("C") for cell in systems) == 1, f"{row[0]}: exactly one system of record"
        assert row[6] in ROLES, row[0]
        assert row[7], row[0]
    steps = table_rows(text, "| Step | Who |")
    assert [r[0] for r in steps] == ["0", "1", "2", "3", "4"]
    for term in ["data owner", "data steward", "entity", "review queue", "exception queue"]:
        assert re.search(rf"\*\*{term}\*\*", text, re.I), term


def test_ownership_agrees_with_the_roadmap() -> None:
    domains = {d["domain"]: d["owner"] for d in yaml.safe_load(
        (ROOT / "config/roadmap.yaml").read_text(encoding="utf-8"))["ownership"]}
    rows = {r[0]: r[6] for r in table_rows((ROOT / "docs/data-ownership.md").read_text(encoding="utf-8"),
                                           "| Entity | Corvus MRP |")}
    assert rows["Material (section, grade, plate)"] == domains["Material master"]
    assert rows["Supplier"] == domains["Supplier master"]
    assert rows["Job"] == domains["Customers and jobs"]
    assert rows["Works order and bill of material"] == domains["Works orders, routings and bookings"]
    assert rows["Goods received note, heat number, mill certificate"] == domains["Goods receipts and traceability"]
    assert rows["Stock and cycle count"] == domains["Stock"]
    assert rows["Non-conformance report"] == domains["Non-conformance"]
