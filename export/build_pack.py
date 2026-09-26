"""Build the FabSync management pack from the warehouse.

Writes a 16-page A4 PDF, and every chart and diagram in it as a 300 dpi PNG for slides:

    export/fabsync-management-pack.pdf
    export/figures/*.png

Run through `make pack`, which rebuilds the warehouse from a clean run first. The same warehouse gives
byte-identical files. All data behind the pack is synthetic.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fabsync.pack.build import build_pack

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data/warehouse/fabsync.duckdb")
    parser.add_argument("--out", type=Path, default=ROOT / "export")
    args = parser.parse_args()
    if not args.warehouse.exists():
        raise SystemExit(f"{args.warehouse} not found. Run make run-all first.")
    result = build_pack(args.warehouse, args.out)
    print(f"Pack: {result.pdf}")
    print(f"Figures: {len(result.figures)} PNGs at 300 dpi in {result.pdf.parent / 'figures'}")


if __name__ == "__main__":
    main()
