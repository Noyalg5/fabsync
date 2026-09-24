"""Run every declared rule and record the results.

For each rule the engine evaluates the check, counts records checked and
failed, compares the pass rate with the rule's threshold, and scores it.
Results are appended to governance.dq_results under a run id, so each run adds
a point to the trend; they are never overwritten. The exception queue
(governance.dq_exceptions) holds the failing records of the latest run only,
because it is a to-do list, not a history.

A rule whose check errors is recorded with status ``error`` and left out of the
index; the other rules still run.

Headline data quality index (DQI)
---------------------------------
For each rule r that ran:

    pass_rate_r = 1 - records_failed_r / records_checked_r    (1 if nothing in scope)
    score_r     = min(1, pass_rate_r / threshold_r)
    weight_r    = severity weight (critical 8, high 4, medium 2, low 1; from the rule file)

    DQI = 100 x sum(weight_r x score_r) / sum(weight_r)

A rule at or above its threshold contributes its full weight. Below it, the
contribution falls in proportion to how far short it is. Doubling the weight at
each severity step means one critical rule counts as much as eight low ones.
The same formula, restricted to a group of rules, gives each scorecard line.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from fabsync.ingest.warehouse import WAREHOUSE_PATH, new_run_id, now
from fabsync.quality.rules import RULES_PATH, Rule, RuleSet, load_rules, resolve_callable

REQUIRED_COLUMNS = ("record_key", "passed", "observed")
SEVERITY_ORDER = "CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"

DDL = """
CREATE TABLE IF NOT EXISTS governance.dq_run (
    run_id VARCHAR PRIMARY KEY, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, as_of_date DATE,
    data_fingerprint VARCHAR, rules_file_sha256 VARCHAR, rules_run INTEGER, rules_met INTEGER,
    rules_errored INTEGER, critical_breaches INTEGER, records_checked BIGINT, records_failed BIGINT,
    dq_index DOUBLE
);
CREATE TABLE IF NOT EXISTS governance.dq_results (
    run_id VARCHAR, rule_id VARCHAR, rule_name VARCHAR, dimension VARCHAR, severity VARCHAR, weight DOUBLE,
    system_of_record VARCHAR, owner VARCHAR, records_checked BIGINT, records_failed BIGINT, pass_rate DOUBLE,
    threshold DOUBLE, threshold_met BOOLEAN, score DOUBLE, status VARCHAR, error VARCHAR, evaluated_at TIMESTAMPTZ
);
"""

VIEWS = f"""
CREATE OR REPLACE VIEW governance.v_dq_latest AS
SELECT r.* FROM governance.dq_results r
WHERE r.run_id = (SELECT run_id FROM governance.dq_run ORDER BY finished_at DESC LIMIT 1);

CREATE OR REPLACE VIEW governance.v_dq_trend AS
SELECT run_id, finished_at, as_of_date, data_fingerprint, dq_index, rules_met, rules_run, critical_breaches,
       records_failed
FROM governance.dq_run ORDER BY finished_at;

CREATE OR REPLACE VIEW governance.v_dq_exception_queue AS
SELECT * FROM governance.dq_exceptions ORDER BY {SEVERITY_ORDER}, rule_id, record_key;
"""


def scorecard_view(name: str, group: str) -> str:
    return f"""
CREATE OR REPLACE VIEW governance.v_dq_scorecard_by_{name} AS
SELECT {group} AS {name}, count(*) AS rules, count(*) FILTER (WHERE threshold_met) AS rules_met,
       count(*) FILTER (WHERE severity = 'critical' AND NOT threshold_met) AS critical_breaches,
       sum(records_checked) AS records_checked, sum(records_failed) AS records_failed,
       round(100 * sum(weight * score) / sum(weight), 1) AS dq_index
FROM governance.v_dq_latest WHERE status = 'ok'
GROUP BY 1 ORDER BY dq_index, 1;
"""


@dataclass
class QualityResult:
    run_id: str
    dq_index: float
    results: pd.DataFrame
    exceptions: pd.DataFrame
    rules: RuleSet


def evaluate(con: duckdb.DuckDBPyConnection, rules: RuleSet, rule: Rule) -> pd.DataFrame:
    if rule.check_type == "sql":
        frame = con.execute(rules.sql(rule)).df()
    else:
        frame = resolve_callable(rule.check)(con, rules.parameters)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"check returned no {', '.join(missing)} column")
    for c in ("source_file", "source_row"):
        if c not in frame.columns:
            frame[c] = None
    frame["passed"] = frame["passed"].fillna(False).astype(bool)
    frame["record_key"] = frame["record_key"].astype(str)
    return frame


def data_fingerprint(con: duckdb.DuckDBPyConnection) -> str:
    try:
        shas = [r[0] for r in con.execute("SELECT sha256 FROM governance.source_file ORDER BY source_file").fetchall()]
    except duckdb.Error:
        shas = []
    return hashlib.sha256("".join(shas).encode()).hexdigest()[:16]


def dq_index(results: pd.DataFrame) -> float:
    ok = results[results.status == "ok"]
    return round(100 * float((ok.weight * ok.score).sum() / ok.weight.sum()), 1) if len(ok) else 0.0


def run_quality(warehouse: Path = WAREHOUSE_PATH, rules_path: Path = RULES_PATH) -> QualityResult:
    if not warehouse.exists():
        raise FileNotFoundError(f"{warehouse} not found. Run make ingest and make match.")
    rules = load_rules(rules_path)
    run_id, started = new_run_id(), now()
    con = duckdb.connect(str(warehouse))
    try:
        con.execute(DDL)
        rows, exceptions = [], []
        for rule in rules.rules:
            weight = rules.weights[rule.severity]
            base = {"run_id": run_id, "rule_id": rule.id, "rule_name": rule.name, "dimension": rule.dimension,
                    "severity": rule.severity, "weight": weight, "system_of_record": rule.system_of_record,
                    "owner": rule.owner, "threshold": rule.threshold, "evaluated_at": now()}
            try:
                frame = evaluate(con, rules, rule)
            except Exception as exc:  # a broken rule is recorded, not fatal
                rows.append({**base, "records_checked": 0, "records_failed": 0, "pass_rate": None,
                             "threshold_met": False, "score": None, "status": "error", "error": str(exc)[:500]})
                continue
            checked, failed = len(frame), int((~frame.passed).sum())
            pass_rate = 1 - failed / checked if checked else 1.0
            rows.append({**base, "records_checked": checked, "records_failed": failed, "pass_rate": pass_rate,
                         "threshold_met": pass_rate >= rule.threshold, "score": min(1.0, pass_rate / rule.threshold),
                         "status": "ok", "error": None})
            bad = frame[~frame.passed].sort_values("record_key")
            for r in bad.itertuples():
                exceptions.append({
                    "run_id": run_id, "rule_id": rule.id, "rule_name": rule.name, "severity": rule.severity,
                    "dimension": rule.dimension, "owner": rule.owner, "system_of_record": rule.system_of_record,
                    "record_key": r.record_key, "observed": None if pd.isna(r.observed) else str(r.observed),
                    "source_file": None if pd.isna(r.source_file) else str(r.source_file),
                    "source_row": None if pd.isna(r.source_row) else int(r.source_row),
                    "suggested_action": rule.corrective_action, "status": "open", "raised_at": started})

        results = pd.DataFrame(rows)
        index = dq_index(results)
        ok = results[results.status == "ok"]
        exc = pd.DataFrame(exceptions, columns=["run_id", "rule_id", "rule_name", "severity", "dimension", "owner",
                                                "system_of_record", "record_key", "observed", "source_file",
                                                "source_row", "suggested_action", "status", "raised_at"])
        exc.insert(0, "exception_id", [f"DQX{i:06d}" for i in range(1, len(exc) + 1)])

        con.execute("BEGIN")
        con.register("_results", results)
        con.execute("""INSERT INTO governance.dq_results SELECT run_id, rule_id, rule_name, dimension, severity,
                       weight, system_of_record, owner, records_checked, records_failed, pass_rate, threshold,
                       threshold_met, score, status, error, evaluated_at FROM _results""")
        con.execute("DROP TABLE IF EXISTS governance.dq_exceptions")
        con.register("_exc", exc)
        con.execute("""CREATE TABLE governance.dq_exceptions AS SELECT exception_id, run_id, rule_id, rule_name,
                       severity, dimension, owner, system_of_record, record_key, observed, source_file,
                       CAST(source_row AS INTEGER) AS source_row, suggested_action, status,
                       CAST(raised_at AS TIMESTAMPTZ) AS raised_at FROM _exc""")
        con.execute("DROP TABLE IF EXISTS governance.dq_rule")
        catalogue = pd.DataFrame([{**r.__dict__, "covers_defects": ", ".join(map(str, r.covers_defects)),
                                   "weight": rules.weights[r.severity]} for r in rules.rules])
        con.register("_rules", catalogue)
        con.execute("CREATE TABLE governance.dq_rule AS SELECT * FROM _rules")
        con.execute("INSERT INTO governance.dq_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [run_id, started, now(), rules.parameters.get("as_of_date"), data_fingerprint(con),
                     rules.sha256, len(results), int(ok.threshold_met.sum()), int((results.status == "error").sum()),
                     int(((ok.severity == "critical") & ~ok.threshold_met).sum()), int(ok.records_checked.sum()),
                     int(ok.records_failed.sum()), index])
        con.execute(VIEWS)
        for name, group in (("system", "system_of_record"), ("dimension", "dimension"), ("owner", "owner"),
                            ("severity", "severity")):
            con.execute(scorecard_view(name, group))
        con.execute("COMMIT")
    except BaseException:
        try:
            con.execute("ROLLBACK")
        except duckdb.Error:
            pass
        con.close()
        raise
    con.close()
    return QualityResult(run_id, index, results, exc, rules)
