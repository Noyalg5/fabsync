"""Master data matching, judged against the seeded defect manifest.

Precision: nothing is merged that should not be. Recall: every seeded
duplicate is either merged, queued for review, or reported as a likely miss.
And the non-negotiables: no source value is lost or overwritten, every match
record is explainable, and nothing below the review floor is merged.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.match.common import load_config
from fabsync.match.jobs import parse_ops_job
from fabsync.match.materials import parse
from fabsync.match.pipeline import MATCH_TABLES, run_match
from fabsync.match.suppliers import normalise
from fabsync.match.works_orders import parse_wo, transpositions

AUDIT = {"matched_at", "match_run_id"}


@pytest.fixture(scope="module")
def matched(tmp_path_factory):
    root = tmp_path_factory.mktemp("match")
    manifest = generate(root / "raw", seed=DEFAULT_SEED)
    ingest = run_ingest(root / "raw", root / "wh.duckdb", root / "profiling.md")
    before = snapshot(ingest.warehouse, ("raw", "staging"))
    result = run_match(ingest.warehouse, root / "match-report.md")
    con = duckdb.connect(str(ingest.warehouse), read_only=True)
    yield root, manifest, result, con, before
    con.close()


def rows(con, sql, *params):
    return con.execute(sql, list(params)).fetchall()


def one(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


def snapshot(path: Path, schemas: tuple[str, ...], exclude: set[str] = frozenset()) -> dict:
    con = duckdb.connect(str(path), read_only=True)
    out = {}
    for schema, table in rows(con, """SELECT table_schema, table_name FROM information_schema.tables
                                      WHERE table_type = 'BASE TABLE' ORDER BY ALL"""):
        if schema not in schemas:
            continue
        cols = [c for (c,) in rows(con, """SELECT column_name FROM information_schema.columns
                                           WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position""",
                                   schema, table) if c not in exclude]
        select = ", ".join(f'CAST("{c}" AS VARCHAR)' for c in cols)
        out[f"{schema}.{table}"] = rows(con, f"SELECT {select} FROM {schema}.{table} ORDER BY ALL")
    con.close()
    return out


# ---- parsers ----------------------------------------------------------------- #

@pytest.mark.parametrize("text", ["UB 203x133x25 S355J2", "UB203X133X25", "203x133x25UB", "UNIV BEAM 203X133X25",
                                  "UB203X133X25-S355J2", "ub 203 x 133 x 25"])
def test_section_variants_parse_to_one_designation(text) -> None:
    p = parse(text)
    assert (p.kind, p.dims) == ("UB", "203X133X25")


@pytest.mark.parametrize("text,thickness", [("PLT12-S355J2", "12"), ("PLATE12", "12"), ("PL12MM", "12"),
                                            ("12mm PLATE", "12"), ("PLATE 12MM S355J2", "12")])
def test_plate_variants(text, thickness) -> None:
    assert (parse(text).kind, parse(text).dims) == ("PLATE", thickness)


def test_grade_normalised_and_bad_input_rejected() -> None:
    assert parse("L75X75X8-S355JO").grade == "S355J0"
    assert parse("CHS114.3X5-S355J2").dims == "114.3X5"
    for bad in ["UB203X133", "BOLT-M20X60-88-HDG", "", None, "STEEL"]:
        assert parse(bad) is None


def test_job_and_works_order_parsers() -> None:
    assert parse_ops_job("J24-0871") == ("J-24-0871", "missing_hyphen", 97.0)
    assert parse_ops_job("J-24-871")[0] == "J-24-0871"
    assert parse_ops_job("24-0871")[0] == parse_ops_job("j-24-0871")[0] == "J-24-0871"
    assert parse_wo("12345 (rev B)") == (12345, "B", "revision_suffix", 97.0)
    assert parse_wo("wo-12345")[0] == parse_wo("WO 12345")[0] == parse_wo("WO12345")[0] == 12345
    assert parse_wo("see job pack")[0] is None
    assert 12435 in transpositions(12345) and 21345 in transpositions(12345)


# ---- non-negotiables ----------------------------------------------------------- #

def test_source_data_untouched_by_matching(matched) -> None:
    root, _, _, _, before = matched
    shutil.copy(root / "wh.duckdb", root / "after.duckdb")
    assert snapshot(root / "after.duckdb", ("raw", "staging")) == before


def test_every_match_record_is_explainable(matched) -> None:
    _, _, _, con, _ = matched
    for t in ["core.material_xref", "core.supplier_xref", "core.supplier_candidate_pairs", "core.job_xref",
              "core.works_order_xref", "core.material_review_queue", "core.supplier_review_queue",
              "core.works_order_review_queue"]:
        cols = {c for (c,) in rows(con, "SELECT column_name FROM information_schema.columns WHERE "
                                        "table_schema || '.' || table_name = ?", t)}
        assert {"method", "score", "matched_on", "matched_at", "match_run_id"} <= cols, t
        assert one(con, f"SELECT count(*) FROM {t} WHERE method IS NULL OR matched_on IS NULL "
                        f"OR matched_at IS NULL") == 0 or t == "core.supplier_xref", t
    assert one(con, "SELECT count(*) FROM core.supplier_xref WHERE matched_on IS NULL OR matched_at IS NULL") == 0


def test_source_values_kept_beside_canonical(matched) -> None:
    _, _, _, con, _ = matched
    distinct_written = one(con, """SELECT count(*) FROM (
        SELECT DISTINCT 'b', material_code, description, grade, section_type FROM staging.corvus_mrp_bom_lines UNION ALL
        SELECT DISTINCT 's', material_code, description, NULL, NULL FROM staging.corvus_mrp_stock UNION ALL
        SELECT DISTINCT 'p', material_code, NULL, NULL, NULL FROM staging.corvus_mrp_purchase_orders UNION ALL
        SELECT DISTINCT 'g', material_code, NULL, NULL, NULL FROM staging.corvus_mrp_goods_received)""")
    assert one(con, "SELECT count(*) FROM core.material_xref") == distinct_written
    assert one(con, "SELECT sum(row_count) FROM core.material_xref") == one(con, """SELECT
        (SELECT count(*) FROM staging.corvus_mrp_bom_lines) + (SELECT count(*) FROM staging.corvus_mrp_stock) +
        (SELECT count(*) FROM staging.corvus_mrp_purchase_orders) +
        (SELECT count(*) FROM staging.corvus_mrp_goods_received)""")
    assert one(con, "SELECT count(*) FROM core.material_xref WHERE source_code IS NULL") == 0
    assert one(con, "SELECT count(DISTINCT works_order) FROM staging.shop_floor_time_bookings") == one(
        con, "SELECT count(*) FROM core.works_order_xref WHERE source_table = 'time_bookings'")


def test_bands_respected(matched) -> None:
    _, _, _, con, _ = matched
    for t in ["core.material_xref", "core.job_xref", "core.works_order_xref", "core.supplier_candidate_pairs"]:
        assert one(con, f"""SELECT count(*) FROM {t} WHERE
                           (status = 'auto' AND score < 95) OR (status = 'review' AND (score < 80 OR score >= 95))
                           OR (status = 'unmatched' AND score >= 80)""") == 0, t


def test_nothing_merged_below_the_floor(matched) -> None:
    """Every multi-record supplier entity is explained by auto-accepted pairs alone."""
    _, _, _, con, _ = matched
    links = rows(con, "SELECT left_key, right_key FROM core.supplier_candidate_pairs WHERE status = 'auto'")
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x
    for a, b in links:
        parent[find(a)] = find(b)
    entities: dict[str, set] = {}
    for sid, system, code in rows(con, "SELECT supplier_id, source_system, source_code FROM core.supplier_xref"):
        entities.setdefault(sid, set()).add(find(f"{system}:{code}"))
    assert all(len(roots) == 1 for roots in entities.values())


# ---- materials ------------------------------------------------------------------ #

def test_every_bom_line_resolves(matched) -> None:
    _, _, _, con, _ = matched
    assert one(con, "SELECT count(*) FROM core.material_xref WHERE source_table = 'bom_lines' "
                    "AND status <> 'auto'") == 0


def test_seeded_drift_resolves_or_is_queued_with_the_right_answer(matched) -> None:
    _, manifest, _, con, _ = matched
    drift = manifest["defects"]["1_material_code_drift"]["materials"]
    for canonical, variants in drift.items():
        for variant in variants["code_variants"]:
            for status, code, proposed, candidates in rows(
                    con, """SELECT status, canonical_code, proposed_code, candidates FROM core.material_xref
                            WHERE trim(source_code) = ? AND source_table <> 'bom_lines'""", variant):
                if status == "auto":
                    assert code == canonical
                else:
                    assert status == "review"
                    assert canonical in (proposed or "") or canonical in (candidates or ""), (variant, canonical)
    golden = {c for (c,) in rows(con, "SELECT canonical_code FROM core.material_golden")}
    assert set(drift) <= golden


def test_golden_records_carry_uom_conflicts_and_survivorship(matched) -> None:
    _, manifest, _, con, _ = matched
    conflicts = {c for (c,) in rows(con, "SELECT canonical_code FROM core.material_golden WHERE uom_conflict")}
    assert conflicts == set(manifest["defects"]["4_uom_conflicts"]["materials"])
    assert one(con, "SELECT count(*) FROM core.material_golden WHERE mass IS NULL OR survivorship_rule IS NULL") == 0
    assert one(con, "SELECT count(DISTINCT canonical_code) = count(*) FROM core.material_golden")


# ---- suppliers -------------------------------------------------------------------- #

def truth(name: str, manifest: dict) -> str:
    for s in manifest["defects"]["2_supplier_duplicates"]["suppliers"]:
        if name in [m["name"] for m in s["mrp"]] + [f["name"] for f in s["finance"]]:
            return s["canonical"].upper()
    return normalise(name, load_config())


def test_supplier_precision_no_false_merges(matched) -> None:
    _, manifest, _, con, _ = matched
    by_entity: dict[str, set] = {}
    for sid, name in rows(con, "SELECT supplier_id, source_name FROM core.supplier_xref"):
        by_entity.setdefault(sid, set()).add(truth(name, manifest))
    assert all(len(v) == 1 for v in by_entity.values()), {k: v for k, v in by_entity.items() if len(v) > 1}


def test_supplier_recall_every_duplicate_is_accounted_for(matched) -> None:
    _, manifest, result, con, _ = matched
    report = result.report.read_text(encoding="utf-8")
    queued = " ".join(a + " " + b for a, b in rows(con, "SELECT left_members, right_members "
                                                         "FROM core.supplier_review_queue"))
    for s in manifest["defects"]["2_supplier_duplicates"]["suppliers"]:
        keys = [f"corvus_mrp:{m['code']}" for m in s["mrp"]] + [f"finance:{f['account']}" for f in s["finance"]]
        entities = {one(con, "SELECT supplier_id FROM core.supplier_xref WHERE source_system || ':' || "
                             "source_code = ?", k) for k in keys}
        if len(entities) == 1:
            continue
        stray = [k for k in keys if k in queued]
        missed = [m["name"] for m in s["mrp"] if m["name"] in report]
        assert stray or missed, s["canonical"]


def test_supplier_review_queue_is_decisions_with_evidence(matched) -> None:
    _, _, _, con, _ = matched
    items = rows(con, "SELECT left_entity, right_entity, score, evidence FROM core.supplier_review_queue")
    assert items and len({(a, b) for a, b, _, _ in items}) == len(items)
    assert all(80 <= s < 95 and e for _, _, s, e in items)


# ---- jobs and works orders --------------------------------------------------------- #

def test_job_crosswalk_unmatched_lists(matched) -> None:
    _, manifest, _, con, _ = matched
    finance_only = set(manifest["defects"]["3_job_code_mapping_gap"]["finance_only_job_codes"])
    assert {v for (v,) in rows(con, "SELECT value FROM core.job_unmatched WHERE side = 'finance'")} == finance_only
    assert one(con, "SELECT count(*) FROM core.job_xref WHERE source_system = 'shop_floor' AND job_no IS NULL") == 0
    assert {s for (s,) in rows(con, "SELECT DISTINCT side FROM core.job_unmatched")} <= {"corvus_mrp", "finance",
                                                                                      "shop_floor"}
    assert one(con, "SELECT min(confidence) FROM core.job_crosswalk WHERE job_no IS NOT NULL") >= 95


def test_orphan_works_orders_found_and_queued(matched) -> None:
    _, manifest, _, con, _ = matched
    orphans = set(manifest["defects"]["10_orphans"]["works_orders_in_bookings_not_in_mrp"])
    assert {n for (n,) in rows(con, "SELECT DISTINCT parsed_number FROM core.works_order_xref "
                                    "WHERE wo_no IS NULL AND parsed_number IS NOT NULL")} == orphans
    assert {n for (n,) in rows(con, "SELECT DISTINCT parsed_number FROM core.works_order_review_queue")} == orphans
    assert one(con, "SELECT count(*) FROM core.works_order_xref WHERE parse_method = 'unparsed'") == 0
    assert one(con, "SELECT count(*) FROM core.works_order_xref WHERE drawing_revision IS NOT NULL") > 0


# ---- report, config, idempotency ---------------------------------------------------- #

def test_report_has_the_headline_metrics(matched) -> None:
    _, _, result, con, _ = matched
    text = result.report.read_text(encoding="utf-8")
    assert "synthetic" in text.lower()
    for phrase in ["Auto %", "Review queue", "Unmatched", "Estimated manual effort to clear the review queue"]:
        assert phrase in text
    assert one(con, "SELECT count(*) FROM governance.match_quality") == 4
    assert one(con, "SELECT sum(review_queue) FROM governance.match_quality") == one(
        con, "SELECT count(*) FROM core.v_match_review_queue")


def test_match_lineage_recorded(matched) -> None:
    _, _, _, con, _ = matched
    assert {r for (r,) in rows(con, "SELECT rule_id FROM governance.lineage WHERE layer = 'match'")} == {
        "MA-01", "MA-02", "MA-03", "MA-04", "MA-05"}


def test_rerun_is_idempotent(matched, tmp_path: Path) -> None:
    root, _, first, _, _ = matched
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    second = run_match(tmp_path / "wh.duckdb", tmp_path / "report.md")
    assert second.run_id != first.run_id
    assert (tmp_path / "report.md").read_bytes() == first.report.read_bytes()
    exclude = AUDIT | {"run_id", "started_at", "finished_at"}
    a = snapshot(root / "wh.duckdb", ("core", "governance"), exclude)
    b = snapshot(tmp_path / "wh.duckdb", ("core", "governance"), exclude)
    assert a == b
    assert all(t in b for t in MATCH_TABLES)


def test_thresholds_come_from_config(matched, tmp_path: Path) -> None:
    root, _, _, _, _ = matched
    shutil.copy(root / "wh.duckdb", tmp_path / "wh.duckdb")
    strict = Path("config/matching.toml").read_text(encoding="utf-8").replace("auto_accept = 95", "auto_accept = 99.5")
    (tmp_path / "strict.toml").write_text(strict, encoding="utf-8")
    run_match(tmp_path / "wh.duckdb", tmp_path / "r.md", tmp_path / "strict.toml")
    con = duckdb.connect(str(tmp_path / "wh.duckdb"), read_only=True)
    assert one(con, "SELECT count(*) FROM core.supplier_candidate_pairs WHERE status = 'auto' AND score < 99.5") == 0
    assert one(con, "SELECT review_queue FROM governance.match_quality WHERE domain = 'material'") > 83
    con.close()
