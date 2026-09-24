"""Fill the diagram templates with measured figures and render them to SVG and PNG.

Templates live in docs/diagrams/templates. Each ``{{name}}`` placeholder is
replaced with a figure from :mod:`fabsync.design.figures`, and the result is
written as plain Mermaid source to docs/diagrams/<name>.mmd, then rendered to
<name>.svg and <name>.png. docs/process-maps.md is filled the same way.

Rendering is a documentation build step, not part of the app. It uses the
Mermaid command-line renderer (mmdc), found on the PATH, through the MMDC
environment variable, or in the local npm cache. Rendered files are committed,
so the pack never needs the renderer.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

from fabsync.design.figures import compute
from fabsync.ingest.warehouse import WAREHOUSE_PATH

DIAGRAMS = Path("docs/diagrams")
TEMPLATES = DIAGRAMS / "templates"
CONFIG = DIAGRAMS / "mermaid-config.json"
DOC_TEMPLATE = TEMPLATES / "process-maps.md"
DOC_OUT = Path("docs/process-maps.md")
PLACEHOLDER = re.compile(r"\{\{([a-z_0-9]+)\}\}")


class RenderError(RuntimeError):
    """A template references an unknown figure, or the renderer is unavailable or failed."""


def fill(text: str, figures: dict[str, str]) -> str:
    unknown = sorted({m for m in PLACEHOLDER.findall(text) if m not in figures})
    if unknown:
        raise RenderError(f"unknown figures: {', '.join(unknown)}")
    return PLACEHOLDER.sub(lambda m: figures[m.group(1)], text)


def find_mmdc() -> str | None:
    if os.environ.get("MMDC"):
        return os.environ["MMDC"]
    on_path = shutil.which("mmdc")
    if on_path:
        return on_path
    cached = sorted(Path.home().glob(".npm/_npx/*/node_modules/.bin/mmdc"))
    return str(cached[-1]) if cached else None


def render(mmdc: str, source: Path) -> list[Path]:
    outputs = []
    for suffix, extra in ((".svg", []), (".png", ["--scale", "2", "--width", "1600"])):
        target = source.with_suffix(suffix)
        result = subprocess.run([mmdc, "--input", str(source), "--output", str(target), "--configFile", str(CONFIG),
                                 "--backgroundColor", "white", "--quiet", *extra],
                                capture_output=True, text=True, timeout=180)
        if result.returncode != 0 or not target.exists():
            raise RenderError(f"rendering {source.name} failed: {result.stderr.strip()[:500]}")
        if suffix == ".svg":
            # The renderer adds a style rule for clickable nodes; these diagrams have none.
            svg = target.read_text(encoding="utf-8")
            target.write_text(re.sub(r"#[\w-]+ \.node\.clickable\{[^}]*\}", "", svg), encoding="utf-8")
        outputs.append(target)
    return outputs


def build(warehouse: Path = WAREHOUSE_PATH, render_images: bool = True) -> list[Path]:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        figures = compute(con)
    finally:
        con.close()
    written = []
    for template in sorted(TEMPLATES.glob("*.mmd")):
        target = DIAGRAMS / template.name
        target.write_text(fill(template.read_text(encoding="utf-8"), figures), encoding="utf-8")
        written.append(target)
    DOC_OUT.write_text(fill(DOC_TEMPLATE.read_text(encoding="utf-8"), figures), encoding="utf-8")
    written.append(DOC_OUT)
    if render_images:
        mmdc = find_mmdc()
        if not mmdc:
            raise RenderError("Mermaid renderer (mmdc) not found. Install @mermaid-js/mermaid-cli, or set MMDC. "
                              "The .mmd sources have been written; only the images are missing.")
        for source in [w for w in written if w.suffix == ".mmd"]:
            written += render(mmdc, source)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fill and render the design diagrams.")
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--no-render", action="store_true", help="write the .mmd sources only")
    args = parser.parse_args(argv)
    try:
        written = build(args.warehouse, render_images=not args.no_render)
    except (RenderError, ValueError) as exc:
        sys.exit(f"diagrams failed: {exc}")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
