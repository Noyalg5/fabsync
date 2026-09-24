"""Run the four matchers against the warehouse and write the match quality report.

The match stage reads staging and core, and writes only its own tables
(crosswalks, golden records, review queues) plus lineage rows with layer
``match``. It runs in one transaction and replaces its previous output, so it
can be rerun at will without re-ingesting and without touching source data.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from fabsync.ingest.contracts import RULES
from fabsync.ingest.warehouse import WAREHOUSE_PATH, Recorder, new_run_id, now, rule_layer
from fabsync.match.common import MATCHING_CONFIG, MatchContext, load_config
from fabsync.match.jobs import match_jobs
from fabsync.match.materials import match_materials
from fabsync.match.report import quality_rows, render_report
from fabsync.match.suppliers import match_suppliers
from fabsync.match.works_orders import match_works_orders

REPORT_PATH = Path("docs/match-quality-report.md")
MATCH_TABLES = [
    "core.material_xref", "core.material_golden", "core.material_review_queue", "core.supplier_candidate_pairs",
    "core.supplier_xref", "core.supplier_golden", "core.supplier_review_queue", "core.job_xref",
    "core.job_crosswalk", "core.job_unmatched", "core.works_order_xref", "core.works_order_review_queue",
]

REVIEW_VIEW = """
CREATE VIEW core.v_match_review_queue AS
SELECT 'supplier' AS domain, review_id AS item_id, left_entity || ' ' || left_name AS source_value,
       right_entity || ' ' || right_name AS proposed_match, score, method, evidence AS evidence,
       suggested_action, est_minutes
FROM core.supplier_review_queue
UNION ALL
SELECT 'material', xref_id, source_table || ': ' || trim(source_code), coalesce(proposed_code, candidates),
       score, method, matched_on,
       CASE WHEN method = 'grade_ambiguous' THEN 'choose the grade from the mill certificate'
            ELSE 'confirm the grade from the mill certificate' END, est_minutes
FROM core.material_review_queue
UNION ALL
SELECT 'works_order', review_id, written_as, CAST(candidate_wo_no AS VARCHAR) || ' (' || candidate_job_no || ')',
       score, method, matched_on, suggested_action, est_minutes
FROM core.works_order_review_queue
UNION ALL
SELECT 'job', source_system || ': ' || source_value, source_value, job_no, score, method, matched_on,
       'confirm the job with the contract manager', est_minutes
FROM core.job_xref WHERE status = 'review'
"""

QUALITY_DDL = """
CREATE TABLE governance.match_quality (
    match_run_id VARCHAR, domain VARCHAR, population VARCHAR, values_total INTEGER, auto INTEGER,
    auto_pct DOUBLE, auto_rows_pct DOUBLE, review_queue INTEGER, unmatched INTEGER, est_minutes DOUBLE
)
"""


@dataclass
class MatchResult:
    run_id: str
    report: Path
    quality: pd.DataFrame


def run_match(warehouse: Path = WAREHOUSE_PATH, report: Path = REPORT_PATH,
              config_path: Path = MATCHING_CONFIG) -> MatchResult:
    if not warehouse.exists():
        raise FileNotFoundError(f"{warehouse} not found. Run make ingest.")
    config = load_config(config_path)
    run_id = new_run_id()
    con = duckdb.connect(str(warehouse))
    try:
        con.execute("BEGIN")
        con.execute("DROP VIEW IF EXISTS core.v_match_review_queue")
        for t in MATCH_TABLES:
            con.execute(f"DROP TABLE IF EXISTS {t}")
        con.execute("DROP TABLE IF EXISTS governance.match_quality")
        con.execute("DELETE FROM governance.lineage WHERE layer = 'match'")
        con.executemany("INSERT OR REPLACE INTO governance.rule VALUES (?, ?, ?)",
                        [(r, rule_layer(r), d) for r, d in RULES.items() if r.startswith("MA-")])
        rec = Recorder(con, run_id)
        rec.step = con.execute("SELECT coalesce(max(step_id), 0) FROM governance.lineage").fetchone()[0]
        ctx = MatchContext(con, rec, config, run_id, now())

        results = {"material": match_materials(ctx), "supplier": match_suppliers(ctx),
                   "job": match_jobs(ctx), "works_order": match_works_orders(ctx)}
        con.execute(REVIEW_VIEW)
        quality = pd.DataFrame(quality_rows(results, ctx))
        con.execute(QUALITY_DDL)
        con.register("_quality", quality.assign(match_run_id=run_id))
        con.execute("""INSERT INTO governance.match_quality SELECT match_run_id, domain, population, values_total,
                       auto, auto_pct, auto_rows_pct, review_queue, unmatched, est_minutes FROM _quality""")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        con.close()
        raise
    con.close()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(results, quality, ctx), encoding="utf-8")
    return MatchResult(run_id, report, quality)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Match master data across the three systems.")
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        result = run_match(args.warehouse, args.report)
    except FileNotFoundError as exc:
        sys.exit(f"match failed: {exc}")
    q = result.quality
    print(f"Match run {result.run_id}  (synthetic data)")
    print(f"{'domain':<13}{'values':>8}{'auto':>7}{'auto %':>8}{'review':>8}{'unmatched':>11}{'effort h':>10}")
    for r in q.itertuples():
        print(f"{r.domain:<13}{r.values_total:>8,}{r.auto:>7,}{r.auto_pct:>7.1f}%{r.review_queue:>8,}"
              f"{r.unmatched:>11,}{r.est_minutes / 60:>10.1f}")
    print(f"Review queue: core.v_match_review_queue   Report: {result.report}")


if __name__ == "__main__":
    main()
