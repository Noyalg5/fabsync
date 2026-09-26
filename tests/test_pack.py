"""The management pack: 12 to 16 A4 pages in the order the brief sets, understandable without the app, every
figure measured, every term defined at first use, the benefits labelled illustrative, every chart at 300 dpi
in the app's colours, and byte-identical when rebuilt."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from matplotlib import pyplot as plt
from matplotlib.colors import to_hex
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.text import Text
from PIL import Image
from pypdf import PdfReader

from fabsync import palette
from fabsync.design.figures import money
from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.kpi.build import build_marts
from fabsync.match.pipeline import run_match
from fabsync.pack.build import PDF_NAME, make_figures
from fabsync.pack.document import CONTENTS, SYNTHETIC
from fabsync.pack.facts import load, strip_md
from fabsync.pack.terms import TERMS
from fabsync.quality.engine import run_quality
from fabsync.reconcile.pipeline import run_reconcile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "export/build_pack.py"
A4 = (595.28, 841.89)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("pack")
    wh = root / "wh.duckdb"
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", wh, root / "p.md")
    run_match(wh, root / "m.md")
    run_quality(wh)
    run_reconcile(wh, root / "r.md")
    build_marts(wh, dictionary=root / "d.md", report=root / "k.md")
    for run in ("first", "second"):
        subprocess.run([sys.executable, str(SCRIPT), "--warehouse", str(wh), "--out", str(root / run)], check=True,
                       capture_output=True, text=True)
    reader = PdfReader(root / "first" / PDF_NAME)
    con = duckdb.connect(str(wh), read_only=True)
    yield SimpleNamespace(out=root / "first", again=root / "second", reader=reader, con=con,
                          pages=[" ".join(p.extract_text().split()) for p in reader.pages])
    con.close()


def head(con, engine: str, key: str) -> float:
    return con.execute("SELECT value FROM recon.headline WHERE engine = ? AND key = ?", [engine, key]).fetchone()[0]


# ---- shape and order ------------------------------------------------------------------------------------ #

def test_pack_is_12_to_16_a4_pages(built) -> None:
    assert 12 <= len(built.reader.pages) <= 16
    for page in built.reader.pages:
        assert abs(float(page.mediabox.width) - A4[0]) < 1 and abs(float(page.mediabox.height) - A4[1]) < 1


def test_sections_run_in_the_order_the_brief_sets(built) -> None:
    pages = built.pages
    for title, number in CONTENTS:
        assert title in pages[number - 1][:320], f"{title} should open page {number}"
        assert f"{title} {number}" in pages[0], f"contents entry for {title}"
    assert "FabSync" in pages[0] and SYNTHETIC in pages[0]
    assert all(pages[i].count("How the work flows today") for i in (3, 4))
    for k, i in enumerate(range(5, 9), start=1):
        assert f"What we found: {k} of 4" in pages[i]
    kpis = built.con.execute("SELECT name FROM marts.kpi_scorecard").fetchall()
    assert all(name in pages[11] for (name,) in kpis), "every KPI defined on the KPI page"
    facts = load(built.con)
    assert all(p["phase"] in pages[12] for p in facts.roadmap["phases"]) and "management committee" in pages[12]
    assert all(r["id"] in pages[13] for r in facts.roadmap["risks"]), "every risk on the risk page"
    assert "ILLUSTRATIVE" in pages[14] and "on one page" in pages[15]


def test_every_page_says_the_data_is_synthetic(built) -> None:
    for number, text in enumerate(built.pages, start=1):
        assert SYNTHETIC in text, f"page {number}"


# ---- the argument -------------------------------------------------------------------------------------- #

def test_executive_summary_leads_with_the_three_numbers(built) -> None:
    text, con = built.pages[1], built.con
    dqi = con.execute("SELECT dq_index FROM governance.dq_run ORDER BY finished_at DESC LIMIT 1").fetchone()[0]
    figures = [money(head(con, "three_way", "value_at_risk")), f"{dqi:.1f}",
               f"{head(con, 'traceability', 'exposed_kg'):,.0f}"]
    places = [text.find(f) for f in figures]
    assert all(p >= 0 for p in places) and places == sorted(places), places
    assert places[-1] < text.find("What is wrong")


def test_findings_put_the_figure_before_the_method(built) -> None:
    con = built.con
    lead = [money(head(con, "three_way", "value_at_risk")), money(head(con, "job_cost", "gross_gap")),
            f"{head(con, 'stock', 'line_accuracy'):.1f}%", f"{head(con, 'traceability', 'exposed_kg'):,.0f} tonnes"]
    for text, figure in zip(built.pages[5:9], lead, strict=True):
        figure_at, method_at = text.find(figure), text.find("How it was measured")
        assert 0 <= figure_at < text.find("What it means") < method_at < text.find("Read with care"), figure


def test_no_code_file_paths_or_terminal_output(built) -> None:
    text = " ".join(built.pages)
    for pattern in [r"\b\w+\.(py|md|yaml|yml|csv|toml|duckdb|sql|json|png|pdf|txt)\b", r"\b(SELECT|FROM|WHERE|JOIN)\b",
                    r"\b[a-z]+_[a-z_]+\b", r"\b(raw|staging|core|governance|recon|marts)\.\w", r"\w/\w",
                    r">=|<=|==|`|\$ |\bmake (pack|run-all|app|test|clean)\b|\bpython\b|\bpytest\b|Traceback"]:
        found = [text[max(0, m.start() - 30):m.end() + 30] for m in re.finditer(pattern, text)]
        assert not found, (pattern, found[:3])


def test_every_technical_term_is_defined_at_first_use(built) -> None:
    text = " ".join(built.pages)
    lower = text.lower()
    for term in TERMS:
        first = re.search(term.pattern, text)
        assert first, f"{term.key} is never used; remove it from the glossary"
        definition = lower.find(" ".join(term.definition.split())[:45].lower())
        assert definition >= 0, f"{term.key} is never defined"
        assert first.start() <= definition <= first.start() + 400, (
            f"{term.key} is used before it is defined: ...{text[max(0, first.start() - 60):first.start() + 40]}...")


def test_benefits_are_labelled_illustrative_and_never_passed_off_as_measured(built) -> None:
    page = built.pages[14]
    assert page.count("ILLUSTRATIVE") >= 5 and "modelled" in page
    total = next(r for r in load(built.con).benefits["pounds"] if r[0].startswith("**Total"))
    low, central, high = (strip_md(x) for x in total[3:6])
    assert all(v in page for v in (low, central, high))
    for text in built.pages:
        for sentence in re.split(r"(?<=\.) ", text):
            if central in sentence and "Total a year" not in sentence:
                assert "modelled" in sentence.lower() and "illustrative" in sentence.lower(), sentence


# ---- figures ------------------------------------------------------------------------------------------ #

def test_every_chart_is_a_300_dpi_png_named_for_slides_and_used_in_the_pack(built) -> None:
    pngs = sorted((built.out / "figures").glob("*.png"))
    figures = make_figures(load(built.con))
    assert [p.stem for p in pngs] == [name for _, name, _ in figures]
    for _, _, fig in figures:
        plt.close(fig)
    for path in pngs:
        assert re.fullmatch(r"\d\d-[a-z-]+\.png", path.name), path.name
        with Image.open(path) as im:
            assert [round(d) for d in im.info["dpi"]] == [300, 300], path.name
    embedded = sum(len(page.images) for page in built.reader.pages)
    assert embedded == len(pngs), "every exported chart appears in the pack, once"


def _colours(fig) -> set[str]:
    seen = set()
    for obj in fig.findobj():
        if isinstance(obj, Text) and obj.get_text().strip():
            seen.add(to_hex(obj.get_color()))
        elif isinstance(obj, Patch) and obj.get_visible():
            if obj.get_facecolor()[3] > 0:
                seen.add(to_hex(obj.get_facecolor()))
            if obj.get_linewidth() > 0 and obj.get_edgecolor()[3] > 0:
                seen.add(to_hex(obj.get_edgecolor()))
        elif isinstance(obj, Line2D) and obj.get_visible() and len(obj.get_xdata()):
            seen.add(to_hex(obj.get_color()))
    return seen


def test_charts_use_the_app_colour_semantics(built) -> None:
    from fabsync import ui
    assert ui.SYSTEM_COLOURS is palette.SYSTEM_COLOURS and ui.ACCENT == palette.ACCENT
    allowed = {to_hex(c) for c in [palette.ACCENT, palette.ACCENT_FILL, palette.INK, palette.MUTED, palette.RULE,
                                   palette.GRID, palette.PAPER, "white", *palette.SYSTEM_COLOURS.values()]}
    facts = load(built.con)
    for key, name, fig in make_figures(facts):
        used = _colours(fig)
        assert used <= allowed, (name, used - allowed)
        assert not fig.legends and all(ax.get_legend() is None for ax in fig.axes), f"{name}: no legends"
        if key == "dq_by_system":
            bars = [to_hex(p.get_facecolor()) for p in fig.axes[0].patches]
            assert bars == [palette.SYSTEM_COLOURS[s].lower() for s in facts.dq_by_system.system]
        plt.close(fig)


def test_pack_is_reproducible_byte_for_byte(built) -> None:
    for first in [built.out / PDF_NAME, *sorted((built.out / "figures").glob("*.png"))]:
        second = built.again / first.relative_to(built.out)
        assert first.read_bytes() == second.read_bytes(), first.name


def test_make_pack_rebuilds_from_a_clean_run_and_clean_keeps_the_builder() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    pack = re.search(r"^pack: (.*)\n((?:\t.*\n)+)", makefile, re.M)
    assert pack.group(1).strip() == "run-all" and "export/build_pack.py" in pack.group(2)
    clean = re.search(r"^clean:.*\n((?:\t.*\n)+)", makefile, re.M).group(1)
    assert not re.search(r"\$\(EXPORT\)/\*(\s|$)", clean) and "build_pack" not in clean
    assert SCRIPT.exists()
