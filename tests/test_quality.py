"""The declarative data quality engine, judged against the seeded defect manifest."""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest
import yaml

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.match.pipeline import run_match
from fabsync.quality.engine import dq_index, run_quality
from fabsync.quality.rules import DIMENSIONS, RULES_PATH, RuleError, load_rules
from fabsync.quality.scorecard import render_scorecard

ROLES = {"Purchasing Manager", "Production Controller", "Finance Manager", "Quality Manager"}


@pytest.fixture(scope="module")
def assessed(tmp_path_factory):
    root = tmp_path_factory.mktemp("quality")
    manifest = generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "profiling.md")
    run_match(root / "wh.duckdb", root / "match.md")
    result = run_quality(root / "wh.duckdb")
    con = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    yield root, manifest, result, con
    con.close()


def keys(con, rule_id: str) -> set[str]:
    return {k for (k,) in con.execute("SELECT record_key FROM governance.dq_exceptions WHERE rule_id = ?",
                                      [rule_id]).fetchall()}


def one(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


def write_rules(path: Path, rules: list[dict], **extra) -> Path:
    doc = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    doc["rules"] = rules
    doc.update(extra)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def base_rule(**over) -> dict:
    rule = {"id": "T-01", "name": "Test", "description": "d", "dimension": "validity", "severity": "low",
            "system_of_record": "corvus_mrp", "owner": "Production Controller", "threshold": 1.0,
            "consequence": "c", "corrective_action": "a",
            "check": {"sql": "SELECT CAST(wo_no AS VARCHAR) AS record_key, qty > 1 AS passed, "
                             "CAST(qty AS VARCHAR) AS observed FROM staging.corvus_mrp_works_orders"}}
    rule.update(over)
    return rule


# ---- the rule file ----------------------------------------------------------- #

def test_rule_file_is_complete() -> None:
    rs = load_rules()
    assert len(rs.rules) >= 25
    assert {r.dimension for r in rs.rules} == set(DIMENSIONS)
    assert {r.severity for r in rs.rules} == {"critical", "high", "medium", "low"}
    assert {r.owner for r in rs.rules} == ROLES
    assert {r.check_type for r in rs.rules} == {"sql", "python"}
    assert {d for r in rs.rules for d in r.covers_defects} == set(range(1, 14)) - {12}  # 12: job cost engine
    for r in rs.rules:
        assert r.description and r.consequence and r.corrective_action and 0 < r.threshold <= 1


def test_real_world_rules_present() -> None:
    names = " ".join(r.name.lower() for r in load_rules().rules)
    for phrase in ["named on every booking", "bom lines belong to a works order", "unit of measure valid",
                   "dates in sequence", "duplicate", "positive", "real works order", "stock counted within"]:
        assert phrase in names, phrase


@pytest.mark.parametrize("change,message", [
    ({"dimension": "tidiness"}, "dimension"), ({"severity": "urgent"}, "severity"),
    ({"owner": "Tea Lady"}, "owner"), ({"threshold": 1.5}, "threshold"),
    ({"check": {"sql": "SELECT 1", "python": "x:y"}}, "exactly one"),
    ({"check": {"python": "fabsync.quality.checks:nope"}}, "not found"),
    ({"consequence": ""}, "missing consequence"),
])
def test_invalid_rules_refused(tmp_path, change, message) -> None:
    with pytest.raises(RuleError, match=message):
        load_rules(write_rules(tmp_path / "r.yaml", [base_rule(**change)]))


def test_duplicate_rule_ids_refused(tmp_path) -> None:
    with pytest.raises(RuleError, match="duplicate id"):
        load_rules(write_rules(tmp_path / "r.yaml", [base_rule(), base_rule()]))


# ---- every seeded defect is detected ---------------------------------------------- #

def test_defect_1_material_drift_and_missing_grade(assessed) -> None:
    _, manifest, _, con = assessed
    drift_codes = {v for m in manifest["defects"]["1_material_code_drift"]["materials"].values()
                   for v in m["code_variants"][1:]}
    observed = {o.split(" -> ")[0] for (o,) in con.execute(
        "SELECT observed FROM governance.dq_exceptions WHERE rule_id = 'DQ-04'").fetchall()}
    assert observed and observed <= drift_codes
    assert len(keys(con, "DQ-03")) > 0


def test_defect_2_supplier_duplicates(assessed) -> None:
    _, manifest, _, con = assessed
    flagged = keys(con, "DQ-07") | keys(con, "DQ-08")
    for s in manifest["defects"]["2_supplier_duplicates"]["suppliers"]:
        codes = {m["code"] for m in s["mrp"]} | {f["account"] for f in s["finance"]}
        assert codes & (flagged | keys(con, "DQ-09")), s["canonical"]


def test_defect_3_job_gap(assessed) -> None:
    _, manifest, _, con = assessed
    assert keys(con, "DQ-10") == set(manifest["defects"]["3_job_code_mapping_gap"]["finance_only_job_codes"])


def test_defect_4_uom(assessed) -> None:
    _, manifest, _, con = assessed
    assert keys(con, "DQ-05") == set(manifest["defects"]["4_uom_conflicts"]["materials"])


def test_defect_5_three_way_match(assessed) -> None:
    _, manifest, result, con = assessed
    twm = manifest["defects"]["5_three_way_match"]
    assert keys(con, "DQ-12") == set(twm["po_without_grn"])
    assert keys(con, "DQ-14") == {e["invoice_no"] for e in twm["invoice_over_po_by_more_than_5pct"]}
    grace = date.fromisoformat(result.rules.parameters["as_of_date"]) - timedelta(
        days=result.rules.parameters["invoice_grace_days"])
    grn_dates = dict(con.execute("SELECT grn_no, received_date FROM staging.corvus_mrp_goods_received").fetchall())
    expected = {g for g in twm["grn_without_invoice"] if grn_dates[g] <= grace}
    assert keys(con, "DQ-13") == expected


def test_defect_6_traceability(assessed) -> None:
    _, manifest, _, con = assessed
    assert keys(con, "DQ-01") | keys(con, "DQ-02") == set(
        manifest["defects"]["6_traceability_gaps"]["grn_missing_heat_or_cert"])


def test_defect_7_labour_variance(assessed) -> None:
    _, manifest, _, con = assessed
    assert keys(con, "DQ-16") == set(manifest["defects"]["7_labour_variance"]["jobs"])


def test_defect_8_stock_accuracy(assessed) -> None:
    _, manifest, _, con = assessed
    expected = {f"{e['material_code']}|{e['site']}|{e['location']}"
                for e in manifest["defects"]["8_stock_accuracy"]["lines_with_count_variance"]}
    assert keys(con, "DQ-17") == expected


def test_defect_9_structural_noise(assessed) -> None:
    _, manifest, _, con = assessed
    noise = manifest["defects"]["9_structural_noise"]
    assert len(keys(con, "DQ-19")) == sum(noise["duplicate_rows"].values())
    collisions = [e for e in noise["entry_errors"] if e["fault"] == "key_collision"]
    unreadable = [e for e in noise["entry_errors"] if e["fault"] != "key_collision"]
    assert len(keys(con, "DQ-21")) == len(collisions)
    assert len(keys(con, "DQ-20")) == len(unreadable)
    assert len(keys(con, "DQ-22")) > 1000


def test_defect_10_orphans(assessed) -> None:
    _, manifest, _, con = assessed
    orphans = {str(n) for n in manifest["defects"]["10_orphans"]["works_orders_in_bookings_not_in_mrp"]}
    written = {o.split(" (")[0] for (o,) in con.execute(
        "SELECT observed FROM governance.dq_exceptions WHERE rule_id = 'DQ-23'").fetchall()}
    assert {"".join(ch for ch in w if ch.isdigit())[:5] for w in written} == orphans


def test_clean_controls_pass(assessed) -> None:
    _, _, result, _ = assessed
    met = dict(zip(result.results.rule_id, result.results.threshold_met, strict=True))
    for rule in ["DQ-06", "DQ-15", "DQ-25", "DQ-26", "DQ-31", "DQ-32"]:
        assert met[rule], rule


# ---- results, scorecards, exceptions, index ------------------------------------------ #

def test_results_and_exceptions_agree(assessed) -> None:
    _, _, result, con = assessed
    assert one(con, "SELECT count(*) FROM governance.dq_exceptions") == int(result.results.records_failed.sum())
    assert one(con, "SELECT count(*) FROM governance.dq_exceptions WHERE suggested_action IS NULL "
                    "OR severity IS NULL OR owner IS NULL") == 0
    assert one(con, "SELECT count(*) FROM governance.dq_results WHERE status <> 'ok'") == 0


def test_index_matches_documented_formula(assessed) -> None:
    _, _, result, con = assessed
    rows = con.execute("SELECT weight, pass_rate, threshold FROM governance.v_dq_latest").fetchall()
    expected = round(100 * sum(w * min(1, p / t) for w, p, t in rows) / sum(w for w, _, _ in rows), 1)
    assert result.dq_index == expected == one(con, "SELECT dq_index FROM governance.dq_run")
    assert 0 < expected < 100


def test_three_scorecards(assessed) -> None:
    _, _, result, con = assessed
    for view, n in (("system", 3), ("dimension", 6), ("owner", 4)):
        rows = con.execute(f"SELECT * FROM governance.v_dq_scorecard_by_{view}").fetchall()
        assert len(rows) == n, view
        assert sum(r[1] for r in rows) == len(result.results)
    assert {r[0] for r in con.execute("SELECT owner FROM governance.v_dq_scorecard_by_owner").fetchall()} == ROLES


def test_scorecard_report(assessed) -> None:
    _, _, result, _ = assessed
    text = render_scorecard(result)
    assert "synthetic" in text.lower()
    for heading in ["## Headline data quality index", "### How the index is calculated", "## By owning role",
                    "## By source system", "## By quality dimension"]:
        assert heading in text
    assert f"{result.dq_index:.1f}" in text
    assert render_scorecard(result) == text


def test_results_accumulate_for_trend(assessed, tmp_path) -> None:
    root, _, first, _ = assessed
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    second = run_quality(tmp_path / "wh.duckdb")
    con = duckdb.connect(str(tmp_path / "wh.duckdb"), read_only=True)
    trend = con.execute("SELECT run_id, dq_index FROM governance.v_dq_trend").fetchall()
    assert [r[0] for r in trend] == [first.run_id, second.run_id]
    assert trend[0][1] == trend[1][1]
    assert one(con, "SELECT count(DISTINCT run_id) FROM governance.dq_exceptions") == 1
    con.close()


def test_history_survives_reingest(assessed, tmp_path) -> None:
    root, _, first, _ = assessed
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    run_ingest(root / "raw", tmp_path / "wh.duckdb", tmp_path / "p.md")
    con = duckdb.connect(str(tmp_path / "wh.duckdb"), read_only=True)
    assert one(con, "SELECT count(*) FROM governance.dq_run WHERE run_id = ?", first.run_id) == 1
    con.close()


def test_broken_rule_is_recorded_not_fatal(assessed, tmp_path) -> None:
    root, _, _, _ = assessed
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    rules = write_rules(tmp_path / "r.yaml", [base_rule(), base_rule(id="T-02", check={"sql": "SELECT nonsense"})])
    result = run_quality(tmp_path / "wh.duckdb", rules)
    status = dict(zip(result.results.rule_id, result.results.status, strict=True))
    assert status == {"T-01": "ok", "T-02": "error"}
    assert result.dq_index == dq_index(result.results[result.results.rule_id == "T-01"])


def test_engine_is_generic(assessed, tmp_path) -> None:
    """A rule the engine has never seen runs from the file alone."""
    root, _, _, _ = assessed
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    result = run_quality(tmp_path / "wh.duckdb", write_rules(tmp_path / "r.yaml", [base_rule()]))
    con = duckdb.connect(str(tmp_path / "wh.duckdb"), read_only=True)
    single = one(con, "SELECT count(*) FROM staging.corvus_mrp_works_orders WHERE qty = 1")
    con.close()
    assert int(result.results.records_failed.iloc[0]) == single > 0
