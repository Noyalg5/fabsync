"""Traceability audit: every number in the management pack, on the app's Overview page and in README.md, traced to
its source.

`make audit` rebuilds the pack, renders the Overview page and refills the README with provenance recording on. Every
figure the code prints is a traced value that records, as it is formatted, the query, config setting or document it
came from (see `fabsync.provenance`). The audit then reads every number back out of what a reader actually sees, the
PDF text, the text drawn in each chart and diagram, the rendered Overview page and the README, and matches each one
to a recorded entry.
Each entry can vouch for one printed number only, so a number typed into the prose by hand finds nothing to match
and is reported as untraced.

As an independent check, the pack and page are built again from a control warehouse generated from a different
seed. A number traced to the warehouse should change with the data; any that do not are listed, with the reason.

Sources:

* warehouse: a named query against the warehouse, cited with its SQL;
* config: a setting, such as a tolerance, a target or a risk score in `config/`, the Python version the project
  requires in `pyproject.toml`, or the app's port in `.streamlit/config.toml`;
* document: a committed planning or design document, such as the benefits case, whose own tests check its
  figures against the warehouse;
* scenario: a fact of the invented company that no data records;
* structure: page numbers, identifiers, section counters and axis scales, which are not figures.

The report is `docs/traceability-audit.md`. A test fails if any number is untraced, or if the report or README.md is
out of date.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict, deque
from contextlib import nullcontext
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

from fabsync.pack.document import CONTENTS
from fabsync.provenance import ENV, NUMBER, WORDS, Origin, ledger

KINDS = ["warehouse", "config", "document", "scenario", "structure"]
WORD = re.compile(r"\b(" + "|".join(WORDS.values()) + r")\b", re.I)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"\b\d{{1,2}} (?:{MONTHS}) \d{{4}}\b")
JOB = re.compile(r"\bJ-\d{2}-\d{4}\b")
STRUCTURE = [
    (re.compile(r"\bR\d{2}\b"), "risk identifier"),
    (re.compile(r"\bKPI-\d{2}\b"), "KPI identifier"),
    (re.compile(r"\bDQ-\d{2}\b"), "data quality rule identifier"),
    (re.compile(r"\bA\d\b"), "assumption identifier"),
    (re.compile(r"\bEN(?: ISO)? \d{4,5}(?:-\d)?\b"), "name of a standard"),
    (re.compile(r"\b3\.1 (?:mill )?certificate"), "certificate type under EN 10204"),
    (re.compile(r"Page \d+"), "page number"),
    (re.compile(r"What we found: \d of \d"), "section counter"),
    (re.compile(r"(?<![\w.])\d{1,2}\. (?=[A-Z*])"), "numbered step, phase or list item"),
    (re.compile(r"\bM\d{1,2}\b"), "month label"),
    (re.compile(r"(?i)\bphases? \d+(?:(?:, | and | to )\d+)*\b"), "phase identifier"),
    (re.compile(r"\bon page \d{1,2}\b"), "page reference"),
    (re.compile(r"(?:\b0 to|out of|/) 100\b"), "the scale of the index"),
    (re.compile(r"\bscored from 1 to 5\b"), "the scale of the risk scores"),
    (re.compile(r"\blast 12 months\b"), "the twelve-month window of the turnover query"),
    (re.compile(r"(?:" + "|".join(re.escape(t) for t, _ in CONTENTS) + r") \d{1,2}(?= |$)"), "contents page number"),
    (re.compile(r"(?i)\bthree-way\b"), "part of the term three-way match"),
    (re.compile(r"\bThree numbers that matter\b"), "the heading over the three headline figures"),
    (re.compile(r"\bcomparing two systems\b|\bthe two agree\b|\btwo scores\b"), "wording, not a count"),
]
README = "README.md"


class AuditError(RuntimeError):
    pass


SCENARIO = {"2006": "the year the invented company installed its MRPII; a scenario fact, recorded by no data"}


@dataclass
class Found:
    place: str
    token: str
    context: str
    origin: Origin | None = None
    varies: bool | None = None
    same_source: bool | None = None  # cites the same kind of source, query and column in the control build
    control: str = ""  # what the number in the same position of the control build cites
    scope: str = ""  # the provenance scope its entry was recorded under: a chart, a section of the pack, or the app

    @property
    def kind(self) -> str:
        return self.origin.kind if self.origin else "untraced"


def core(token: str) -> str:
    """A printed number reduced to its digits, so £4.31m, 4.31 and 4.31% all match the recorded 4.31."""
    t = token.lower().replace("£", "").replace(",", "").replace("%", "").lstrip("-")
    return re.sub(r"(?<=\d)[mk]$", "", t)


def context(text: str, start: int, end: int, width: int = 48) -> str:
    return text[max(0, start - width):min(len(text), end + width)].strip()


def scan(place: str, text: str, where: str = "") -> list[Found]:
    """Every number in a piece of text, in reading order; structural ones are classified straight away."""
    text = " ".join(text.split())
    spans: list[tuple[int, int, Found]] = []
    masked = text

    def take(pattern: re.Pattern, origin=None) -> None:
        nonlocal masked
        for m in pattern.finditer(masked):
            spans.append((m.start(), m.end(),
                          Found(place, m.group(0), context(text, m.start(), m.end()), origin, scope=where)))
        masked = pattern.sub(lambda m: " " * len(m.group(0)), masked)

    for pattern, why in STRUCTURE:
        take(pattern, Origin("structure", why, ""))
    take(DATE)
    take(JOB)
    take(NUMBER)
    take(WORD)
    return [f for _, _, f in sorted(spans, key=lambda x: x[0]) if re.search(r"\d", f.token) or f.token.lower() in
            {w.lower() for w in WORDS.values()} or f.origin]


def scan_figures(figures) -> list[Found]:
    from matplotlib.text import Text
    found = []
    for _, name, fig in figures:
        fig.canvas.draw()  # tick labels exist only once the figure is drawn
        ticks, hidden = set(), set()
        for ax in fig.axes:
            for tick in ax.xaxis.get_major_ticks() + ax.yaxis.get_major_ticks():
                (hidden if not ax.axison else ticks).update({id(tick.label1), id(tick.label2)})
        for t in fig.findobj(Text):
            text = t.get_text()
            if not (re.search(r"\d", text) or WORD.search(text)) or id(t) in hidden or not t.get_visible():
                continue
            if id(t) in ticks and not JOB.search(text):
                found += [Found(f"Pack figure {name}", tok, text, Origin("structure", "axis scale", ""), scope=name)
                          for tok in NUMBER.findall(text)]
                continue
            found += scan(f"Pack figure {name}", text, where=name)
    return found


def attribute(found: list[Found], entries: list[tuple[str, Origin, str]], con: duckdb.DuckDBPyConnection) -> None:
    """Pair each printed number with the entry recorded when it was printed.

    Each chart, each section of the pack and the app page records its numbers under its own scope. Within a scope,
    entries are recorded in the order the text is written and numbers are read back in the order they appear, so the
    two sequences are aligned the way a diff aligns two files. A number the alignment cannot place takes the first
    unused entry for the same digits in the same scope. What is left is checked against the data, or is untraced.
    """
    recorded: dict[str, list[tuple[str, Origin]]] = defaultdict(list)
    for text, origin, where in entries:
        recorded[where].append((core(text), origin))
    printed: dict[str, list[Found]] = defaultdict(list)
    for f in found:
        if not f.origin:
            printed[f.scope].append(f)
    for where, tokens in printed.items():
        book = recorded.get(where, [])
        used = set()
        matcher = SequenceMatcher(None, [core(f.token) for f in tokens], [c for c, _ in book], autojunk=False)
        for block in matcher.get_matching_blocks():
            for i in range(block.size):
                tokens[block.a + i].origin = book[block.b + i][1]
                used.add(block.b + i)
        pool: dict[str, deque] = defaultdict(deque)
        for j, (c, origin) in enumerate(book):
            if j not in used:
                pool[c].append(origin)
        for f in tokens:
            if not f.origin and pool[core(f.token)]:
                f.origin = pool[core(f.token)].popleft()
    jobs = {j for (j,) in con.execute("SELECT job_no FROM core.job_crosswalk").fetchall()}
    for f in found:
        if f.origin:
            continue
        if f.token in jobs:
            f.origin = Origin("warehouse", "a job that exists", "SELECT job_no FROM core.job_crosswalk")
        elif f.token.rstrip(",;") in SCENARIO:
            f.origin = Origin("scenario", SCENARIO[f.token.rstrip(",;")], "")


def overview(warehouse: Path, recording: bool) -> tuple[list[str], list]:
    """The Overview page's text as rendered from this warehouse, and what it recorded if recording."""
    from streamlit.testing.v1 import AppTest

    before = {k: os.environ.get(k) for k in (ENV, "FABSYNC_WAREHOUSE")}
    os.environ.pop(ENV, None)
    if recording:
        os.environ[ENV] = "1"
    os.environ["FABSYNC_WAREHOUSE"] = str(warehouse)
    entries: list = []
    try:
        # An open ledger switches recording on, so the plain rendering must not open one.
        with ledger() if recording else nullcontext(entries) as entries:
            at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app/app.py"), default_timeout=60).run()
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return page_text(at), entries


def page_text(at) -> list[str]:
    """The text of a rendered page, element by element in the order a reader meets it."""
    from streamlit.testing.v1.element_tree import Block, Button, HeadingBase, Markdown
    texts = []
    for node in [*at.main, *at.sidebar]:
        if isinstance(node, Block):
            continue
        if node.type == "html":
            texts.append(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<style>.*?</style>", " ", str(node.proto.body))))
        elif isinstance(node, Button):
            texts.append(node.label)
        elif isinstance(node, (HeadingBase, Markdown)):
            texts.append(node.value)
    return texts


def read(warehouse: Path, out: Path) -> list[Found]:
    """Build the pack, render the Overview and refill the README with recording on; read every number back out."""
    from matplotlib import pyplot as plt
    from pypdf import PdfReader

    from fabsync.pack import charts
    from fabsync.pack.build import make_figures
    from fabsync.pack.document import build_pdf
    from fabsync.pack.facts import load
    from fabsync.readme import render

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        with ledger() as entries:
            facts = load(con)
            figures = make_figures(facts)  # each chart is recorded under its own scope
            found = scan_figures(figures)
            paths = {key: charts.save(fig, out / "figures" / f"{name}.png") for key, name, fig in figures}
            sections: list[str] = []
            pdf = build_pdf(facts, paths, out / "pack.pdf", sections)
        pages = PdfReader(pdf).pages
        if len(pages) != len(sections):
            raise AuditError(f"the pack has {len(pages)} pages but its sections fill {len(sections)}: a section has "
                             "run over its page, so the audit cannot tell which section printed which page")
        for n, (page, section) in enumerate(zip(pages, sections, strict=True), start=1):
            found += scan(f"Pack page {n}", page.extract_text(), where=section)
        attribute(found, entries, con)
        # The app only records while auditing, and a traced value can print differently from a plain one, so the
        # page is rendered both ways: what is audited must be exactly what a user sees.
        seen, _ = overview(warehouse, recording=False)
        texts, app_entries = overview(warehouse, recording=True)
        if texts != seen:
            diff = next((a, b) for a, b in zip(seen, texts, strict=False) if a != b) if len(seen) == len(texts) \
                else (f"{len(seen)} elements", f"{len(texts)} elements")
            raise AuditError(f"the Overview page reads differently when audited: {diff[0]!r} becomes {diff[1]!r}")
        app = [f for t in texts for f in scan("App Overview page", t)]
        attribute(app, app_entries, con)
        with ledger() as readme_entries:
            readme = scan(README, render(facts, con))
        attribute(readme, readme_entries, con)
    finally:
        con.close()
        plt.close("all")
    return found + app + readme


def readme_is_current(warehouse: Path) -> bool:
    """Whether the committed README.md is exactly what its template fills to from this warehouse."""
    from fabsync.readme import README as path
    from fabsync.readme import build
    return path.read_text(encoding="utf-8") == build(warehouse)


def source(f: Found) -> tuple[str, str, str]:
    """What a number is, leaving out which row of a ranked table it sits in: kind, query or file, and column."""
    if not f.origin:
        return ("untraced", "", "")
    name = f.origin.name.rsplit(", ", 1)[-1] if f.origin.kind == "warehouse" else f.origin.name
    return (f.origin.kind, f.origin.detail, name)


def audit(warehouse: Path, control: Path, out: Path) -> list[Found]:
    """Trace every number, then pair each with the number in the same position of the control build.

    Only places laid out alike in both builds are paired: a chart whose control has a different number of rows
    would pair each number with its neighbour's twin.
    """
    found = read(warehouse, out / "real")
    twins: dict[str, list[Found]] = defaultdict(list)
    for f in read(control, out / "control"):
        twins[f.place].append(f)
    mine: dict[str, list[Found]] = defaultdict(list)
    for f in found:
        mine[f.place].append(f)
    for place, items in mine.items():
        if len(items) != len(twins[place]):
            continue
        for f, twin in zip(items, twins[place], strict=True):
            f.same_source = source(f) == source(twin)
            f.control = twin.origin.name if twin.origin else "untraced"
            if f.kind == "warehouse":
                f.varies = twin.token != f.token
    return found


CONTROL_SEED = 2027


def build_control(folder: Path) -> Path:
    """A second warehouse from an independent seed, the control for the audit."""
    return build_warehouse(folder, CONTROL_SEED)


def build_warehouse(folder: Path, seed: int) -> Path:
    """The whole pipeline, from generating the extracts to the KPI marts, into a folder of its own."""
    from fabsync.ingest.generate_sources import generate
    from fabsync.ingest.pipeline import run_ingest
    from fabsync.kpi.build import build_marts
    from fabsync.match.pipeline import run_match
    from fabsync.quality.engine import run_quality
    from fabsync.reconcile.pipeline import run_reconcile
    folder.mkdir(parents=True, exist_ok=True)
    wh = folder / "warehouse.duckdb"
    wh.unlink(missing_ok=True)
    generate(folder / "raw", seed=seed)
    run_ingest(folder / "raw", wh, folder / "profiling.md")
    run_match(wh, folder / "match.md")
    run_quality(wh)
    run_reconcile(wh, folder / "reconciliation.md")
    build_marts(wh, dictionary=folder / "dictionary.md", report=folder / "kpi.md")
    return wh


# ---- the report ------------------------------------------------------------------------------------------------- #

def place_key(place: str) -> tuple:
    m = re.search(r"page (\d+)", place)
    return (0 if "Pack page" in place else 1 if "figure" in place else 2, int(m.group(1)) if m else 0, place)


def report(found: list[Found]) -> str:
    kinds = KINDS + ["untraced"]
    groups = {"Pack pages": [f for f in found if f.place.startswith("Pack page")],
              "Pack charts and diagrams": [f for f in found if f.place.startswith("Pack figure")],
              "App Overview page": [f for f in found if f.place.startswith("App")],
              "README.md": [f for f in found if f.place == README]}
    lines = [
        "# Traceability audit",
        "",
        "**Demonstration prototype. All data is synthetic.** This audit shows where every number shown to management "
        "comes from: in the management pack, on the app's Overview page and in the README.",
        "",
        "Generated by `make audit`. The pack is rebuilt, the app's Overview page rendered and the README refilled "
        "from its template with provenance recording on: every figure the code prints records, as it is formatted, "
        "the query, config setting or document it came from. Every number is then read back out of what a reader "
        "sees (the PDF text, the text in each chart and diagram, the rendered page and the README) and matched to "
        "one recorded entry. A number typed by hand has no entry, and is listed as untraced. A test fails if any "
        "number is untraced, or if this file or the README is out of date.",
        "",
        "As an independent check, the pack, page and README are built a second time from a control warehouse "
        "generated from a different seed. A number traced to the warehouse should change with the data.",
        "",
        "## Summary",
        "",
        "| Where | " + " | ".join(k.capitalize() for k in kinds) + " | All |",
        "| --- | " + " | ".join("---:" for _ in kinds) + " | ---: |",
    ]
    for label, items in groups.items():
        c = defaultdict(int)
        for f in items:
            c[f.kind] += 1
        lines.append(f"| {label} | " + " | ".join(f"{c[k]:,}" for k in kinds) + f" | {len(items):,} |")
    total = defaultdict(int)
    for f in found:
        total[f.kind] += 1
    lines.append("| **All** | " + " | ".join(f"**{total[k]:,}**" for k in kinds) + f" | **{len(found):,}** |")
    varied = [f for f in found if f.kind == "warehouse" and f.varies]
    fixed = [f for f in found if f.kind == "warehouse" and f.varies is False]
    unpaired = sorted({f.place for f in found if f.same_source is None}, key=place_key)
    paired = [f for f in found if f.same_source is not None]
    moved = [f for f in paired if not f.same_source]
    lines += ["", "Each number is counted every time it appears. **Warehouse** is the result of a named query, listed "
              "at the end with its SQL. **Config** is a setting: in `config/`, or the Python version in "
              "`pyproject.toml` and the app's port in `.streamlit/config.toml`. **Document** is a committed "
              "planning or design document whose own tests check its figures against the warehouse. **Scenario** "
              "is a fact of the invented company that no data records. **Structure** is a page number, identifier, "
              "section counter or axis scale, which is not a figure.", "",
              "## The control build", "",
              "The pack, page and README were built again from a control warehouse generated from a different "
              "seed. Each number was paired with the number in the same position of the control build, on every "
              "page and chart laid out alike in both. Places whose control has a different number of rows are not "
              "paired"
              + (f" ({', '.join(unpaired)})." if unpaired else "."), "",
              f"* **Same source.** Of {len(paired):,} numbers paired, {len(paired) - len(moved):,} cite the same kind "
              "of source, the same query or file and the same column in both builds. A number paired with an entry "
              "by coincidence of digits would cite a different one when the values change."
              + (" The rest are listed below." if moved else ""),
              f"* **Varies with the data.** Of the {len(varied) + len(fixed):,} paired warehouse numbers, "
              f"{len(varied):,} changed with the data and {len(fixed):,} did not. Those are listed below.", ""]
    if moved:
        lines += ["| Where | Number | Source | Source in the control build |", "| --- | --- | --- | --- |"]
        lines += [f"| {f.place} | {f.token} | {f.origin.name if f.origin else 'untraced'} | {f.control} |"
                  for f in moved]
        lines.append("")
    untraced = [f for f in found if f.kind == "untraced"]
    lines += ["## Untraced numbers", ""]
    if untraced:
        lines += ["| Where | Number | Context |", "| --- | --- | --- |"]
        lines += [f"| {f.place} | {f.token} | {f.context.replace('|', '/')} |" for f in untraced]
    else:
        lines.append("None. Every number traces to a source.")
    lines += ["", "## Warehouse numbers that did not change in the control", "",
              "Traced to a query, but the same when the pack was built from the control warehouse. A number stays "
              "the same for one of four reasons: it is part of the invented company that the generator holds "
              "constant across seeds (its sites and systems, the months of history, the example job); it is a "
              "planted defect whose count the generator fixes; it counts the rule set or a chart's rows, which are "
              "the same in both builds; or it is a small count that happens to agree. Text labels read from the "
              "warehouse, such as a KPI's secondary label, are also listed here.", "",
              "| Number | Query | Where |", "| --- | --- | --- |"]
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for f in fixed:
        grouped[(f.token, f.origin.name)].add(f.place)
    for (token, name), where in sorted(grouped.items(), key=lambda x: (x[0][1], x[0][0])):
        lines.append(f"| {token} | {name} | {', '.join(sorted(where, key=place_key))} |")
    lines += ["", "## Numbers not traced to a warehouse query", ""]
    for kind in ("config", "document", "scenario", "structure"):
        items = [f for f in found if f.kind == kind]
        if not items:
            continue
        grouped = defaultdict(set)
        for f in items:
            grouped[(f.token, f.origin.name)].add(f.place)
        lines += [f"### {kind.capitalize()}", "", "| Number | Source | Where |", "| --- | --- | --- |"]
        for (token, name), where in sorted(grouped.items(), key=lambda x: (x[0][1], x[0][0])):
            lines.append(f"| {token} | {name} | {', '.join(sorted(where, key=place_key))} |")
        lines.append("")
    queries: dict[str, str] = {}
    per_number: dict[str, set[str]] = defaultdict(set)
    for f in found:
        if f.kind == "warehouse":
            queries[f.origin.name] = f.origin.detail
            per_number[f.origin.name].add(f.token)
    lines += ["## Queries cited", "", "Every query a warehouse number traces to, with the numbers it produced.", "",
              "| Query | Numbers | SQL |", "| --- | --- | --- |"]
    for name in sorted(queries):
        nums = ", ".join(sorted(per_number[name], key=lambda t: (len(t), t))[:8])
        more = len(per_number[name]) - 8
        lines.append(f"| {name} | {nums}{f' and {more} more' if more > 0 else ''} | "
                     f"`{' '.join(queries[name].split()).replace('|', '/')}` |")
    return "\n".join(lines) + "\n"


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    out = root / "export" / "audit"
    found = audit(root / "data/warehouse/fabsync.duckdb", build_control(out / "control-warehouse"), out)
    (root / "docs/traceability-audit.md").write_text(report(found), encoding="utf-8")
    counts = defaultdict(int)
    for f in found:
        counts[f.kind] += 1
    print("Traceability audit (synthetic data): " + ", ".join(f"{k} {counts[k]:,}" for k in KINDS + ["untraced"]))
    paired = [f for f in found if f.same_source is not None]
    moved = [f for f in paired if not f.same_source]
    print(f"Control build: {len(paired) - len(moved):,} of {len(paired):,} paired numbers cite the same source")
    print("Report: docs/traceability-audit.md")
    if counts["untraced"]:
        raise SystemExit(f"{counts['untraced']} numbers do not trace to a source")
    published = root / "export" / "fabsync-management-pack.pdf"
    if published.exists() and published.read_bytes() != (out / "real" / "pack.pdf").read_bytes():
        raise SystemExit("the pack the audit read differs from export/fabsync-management-pack.pdf: run make pack")
    if not readme_is_current(root / "data/warehouse/fabsync.duckdb"):
        raise SystemExit("README.md is out of date: run make readme, and edit docs/templates/readme.md, not README.md")
    if moved:
        raise SystemExit(f"{len(moved)} numbers cite a different source in the control build")


if __name__ == "__main__":
    main()
