"""Command-line entry point: ``python -m fabsync.quality`` runs every declared rule."""

import argparse
import sys
from pathlib import Path

from fabsync.ingest.warehouse import WAREHOUSE_PATH
from fabsync.quality.engine import run_quality
from fabsync.quality.rules import RULES_PATH, RuleError
from fabsync.quality.scorecard import group_scorecard, render_scorecard

REPORT_PATH = Path("docs/dq-scorecard.md")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the declarative data quality rules.")
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--rules", type=Path, default=RULES_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        result = run_quality(args.warehouse, args.rules)
    except (FileNotFoundError, RuleError) as exc:
        sys.exit(f"quality failed: {exc}")
    args.report.write_text(render_scorecard(result), encoding="utf-8")
    res = result.results
    print(f"Quality run {result.run_id}  (synthetic data)")
    print(f"Data quality index: {result.dq_index:.1f}   rules met: {int(res.threshold_met.sum())} of {len(res)}   "
          f"exceptions: {len(result.exceptions):,}")
    for r in group_scorecard(res, "owner").itertuples():
        print(f"  {r.owner:<24}{r.index:>6.1f}   {r.met} of {r.rules} rules met   {r.failed:,} failing records")
    print(f"Scorecard: {args.report}   Exceptions: governance.v_dq_exception_queue")
    errors = res[res.status == "error"]
    if len(errors):
        for r in errors.itertuples():
            print(f"  ERROR {r.rule_id}: {r.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
