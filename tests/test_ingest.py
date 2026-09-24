"""Ingestion: contracts, raw fidelity, lineage, quarantine, core conformance, profiling, idempotency.

The seeded defect manifest (defects.json) is the oracle: every row it says a
parser should reject must be in quarantine under the expected rule, and every
orphan and unmapped job code must be flagged in core.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from fabsync.ingest.contracts import RULES, ContractViolation
from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import SOURCES, run_ingest

FAULT_RULE = {"blank_required": "ST-03", "invalid_date": "ST-04", "unparseable_number": "ST-05",
              "key_collision": "ST-08"}
RUN_COLUMNS = {"run_id", "_run_id", "_loaded_at", "started_at", "finished_at", "quarantined_at", "loaded_at"}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("ingest")
    manifest = generate(root / "raw", seed=DEFAULT_SEED)
    result = run_ingest(root / "raw", root / "wh.duckdb", root / "profiling-report.md")
    con = duckdb.connect(str(result.warehouse), read_only=True)
    yield root, manifest, result, con
    con.close()


def q(con, sql, *params):
    return con.execute(sql, list(params)).fetchall()


def scalar(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


# ---- contracts and raw ----------------------------------------------------- #

def test_contracts_cover_every_generated_file(built) -> None:
    root, manifest, _, _ = built
    declared = {t.file for s in SOURCES for t in s.tables}
    assert declared == set(manifest["row_counts"])


def test_raw_is_exactly_as_received(built) -> None:
    root, manifest, _, con = built
    for s in SOURCES:
        for t in s.tables:
            assert scalar(con, f"SELECT count(*) FROM raw.{s.system}_{t.name}") == manifest["row_counts"][t.file]
            types = {r[0] for r in q(con, """SELECT data_type FROM information_schema.columns
                                             WHERE table_schema = 'raw' AND table_name = ?
                                             AND column_name NOT LIKE '\\_%' ESCAPE '\\'""", f"{s.system}_{t.name}")}
            assert types == {"VARCHAR"}, t.file
    # padding is preserved and the physical line number points at the right line
    line, status = q(con, "SELECT _source_row, status FROM raw.corvus_mrp_works_orders ORDER BY _source_row LIMIT 1")[0]
    assert status != status.strip()
    file_line = (root / "raw/corvus_mrp/works_orders.csv").read_text(encoding="utf-8").splitlines()[line - 1]
    assert f",{status}," in file_line


def test_source_files_record_header_and_hash(built) -> None:
    _, _, _, con = built
    rows = q(con, "SELECT header_comment, length(sha256) FROM governance.source_file")
    assert len(rows) == 13
    assert all(h.startswith("# SYNTHETIC DATA") and n == 64 for h, n in rows)


def test_contract_mismatch_is_refused(tmp_path: Path) -> None:
    generate(tmp_path / "raw", seed=DEFAULT_SEED)
    f = tmp_path / "raw/finance/job_costs.csv"
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[1] = lines[1].replace("amount", "value")
    f.write_text("".join(lines), encoding="utf-8")
    existing = tmp_path / "wh.duckdb"
    with pytest.raises(ContractViolation):
        run_ingest(tmp_path / "raw", existing, tmp_path / "r.md")
    assert not existing.exists()
    assert not list(tmp_path.glob("*.building.duckdb"))


# ---- balance, quarantine, lineage ------------------------------------------ #

def test_nothing_silently_dropped(built) -> None:
    _, _, result, con = built
    assert result.balanced
    for f, lines, raw, staged, core, quar, ok in q(con, """
            SELECT source_file, data_lines, raw_rows, staged_rows, core_rows, quarantined_rows, balanced
            FROM governance.table_balance"""):
        assert ok and lines == raw == staged + quar and core == staged, f


def test_every_seeded_entry_error_is_quarantined_under_its_rule(built) -> None:
    _, manifest, _, con = built
    errors = manifest["defects"]["9_structural_noise"]["entry_errors"]
    for e in errors:
        key_col = e["key_column"]
        rows = q(con, f"""SELECT rule_id, failing_column, failing_value, original_record ->> '{key_col}'
                          FROM governance.quarantine WHERE source_file = ?
                          AND (original_record ->> '{key_col}') = ?""", e["file"], e["key"])
        rules = {r[0] for r in rows}
        assert FAULT_RULE[e["fault"]] in rules, e
        if e["fault"] != "key_collision":
            hit = [r for r in rows if r[0] == FAULT_RULE[e["fault"]]][0]
            assert hit[1] == e["column"] and hit[2] == e["value"], e


def test_duplicates_quarantined_not_dropped(built) -> None:
    _, manifest, _, con = built
    expected = manifest["defects"]["9_structural_noise"]["duplicate_rows"]
    for f, n in expected.items():
        assert scalar(con, "SELECT count(*) FROM governance.quarantine WHERE source_file = ? AND rule_id = 'ST-02'",
                      f) == n


def test_quarantine_is_only_what_the_manifest_predicts(built) -> None:
    _, manifest, _, con = built
    noise = manifest["defects"]["9_structural_noise"]
    assert scalar(con, "SELECT count(*) FROM governance.quarantine") == (
        sum(noise["duplicate_rows"].values()) + len(noise["entry_errors"]))


def test_quarantine_keeps_original_untrimmed_values(built) -> None:
    _, _, _, con = built
    record, raw_line = q(con, """SELECT q.original_record, q.source_row FROM governance.quarantine q
                                 WHERE q.rule_id = 'ST-05' AND q.source_table = 'time_bookings' LIMIT 1""")[0]
    original = json.loads(record)
    raw = q(con, "SELECT * EXCLUDE (_source_file, _source_row, _run_id, _loaded_at) "
                 "FROM raw.shop_floor_time_bookings WHERE _source_row = ?", raw_line)[0]
    assert tuple(original.values()) == raw


def test_lineage_chains_for_every_staged_table(built) -> None:
    _, _, _, con = built
    for s in SOURCES:
        for t in s.tables:
            steps = q(con, """SELECT rule_id, rows_in, rows_out, rows_rejected FROM governance.lineage
                              WHERE target_table = ? ORDER BY step_id""", f"staging.{s.system}_{t.name}")
            assert [r[0] for r in steps][:2] == ["ST-01", "ST-02"] and steps[-1][0] == "ST-09"
            for (_, _, out_prev, _), (_, rows_in, _, _) in zip(steps, steps[1:], strict=False):
                assert rows_in == out_prev
            raw_rows = scalar(con, f"SELECT count(*) FROM raw.{s.system}_{t.name}")
            staged = scalar(con, f"SELECT count(*) FROM staging.{s.system}_{t.name}")
            assert steps[0][1] == raw_rows and steps[-1][2] == staged
            assert raw_rows - staged == sum(r[3] for r in steps)


def test_every_lineage_rule_is_catalogued(built) -> None:
    _, _, _, con = built
    used = {r[0] for r in q(con, "SELECT DISTINCT rule_id FROM governance.lineage")}
    assert used <= set(RULES)
    assert {r[0] for r in q(con, "SELECT rule_id FROM governance.rule")} == set(RULES)
    assert scalar(con, "SELECT count(*) FROM governance.lineage WHERE rows_in <> rows_out + rows_rejected") == 0


def test_every_core_table_traces_to_a_raw_line(built) -> None:
    _, _, _, con = built
    tables = [r[0] for r in q(con, """SELECT table_name FROM information_schema.columns
                                      WHERE table_schema = 'core' AND column_name = '_source_row'""")]
    assert len(tables) == 13
    for t in tables:
        system = scalar(con, f"SELECT split_part(any_value(_source_file), '/', 1) FROM core.{t}")
        table = scalar(con, f"SELECT regexp_replace(split_part(any_value(_source_file), '/', 2), '\\.csv$', '') "
                            f"FROM core.{t}")
        missing = scalar(con, f"""SELECT count(*) FROM core.{t} c ANTI JOIN raw.{system}_{table} r
                                  USING (_source_file, _source_row)""")
        assert missing == 0, t


# ---- core conformance ------------------------------------------------------ #

def test_orphan_works_orders_flagged_in_core(built) -> None:
    _, manifest, _, con = built
    orphans = set(manifest["defects"]["10_orphans"]["works_orders_in_bookings_not_in_mrp"])
    flagged = {r[0] for r in q(con, "SELECT DISTINCT wo_no FROM core.time_bookings WHERE NOT wo_matched")}
    assert flagged == orphans
    assert scalar(con, "SELECT count(*) FROM core.time_bookings WHERE wo_no IS NULL") == 0


def test_finance_only_jobs_flagged_in_core(built) -> None:
    _, manifest, _, con = built
    expected = set(manifest["defects"]["3_job_code_mapping_gap"]["finance_only_job_codes"])
    assert {r[0] for r in q(con, "SELECT finance_job_code FROM core.finance_jobs WHERE NOT mrp_matched")} == expected


def test_sites_operations_and_jobs_conformed(built) -> None:
    _, _, _, con = built
    assert scalar(con, "SELECT count(*) FROM core.time_bookings WHERE site_code IS NULL") == 0
    assert {r[0] for r in q(con, "SELECT DISTINCT site_code FROM core.weekly_capacity")} == {"WKF", "TEE"}
    assert scalar(con, """SELECT count(*) FROM core.time_bookings
                          WHERE operation_raw IS NOT NULL AND operation_code IS NULL""") == 0
    assert scalar(con, "SELECT count(*) FROM core.delivery_notes WHERE NOT job_matched") == 0
    assert scalar(con, """SELECT count(*) FROM core.delivery_notes
                          WHERE job_no NOT SIMILAR TO 'J-[0-9]{2}-[0-9]{4}'""") == 0


# ---- profiling ------------------------------------------------------------- #

def test_profiling_finds_the_seeded_noise(built) -> None:
    root, manifest, result, con = built
    dup = manifest["defects"]["9_structural_noise"]["duplicate_rows"]
    for f, n in dup.items():
        table = f.split("/")[1].removesuffix(".csv")
        assert scalar(con, "SELECT exact_duplicate_rows FROM governance.profile_table WHERE source_table = ?",
                      table) == n
    anomalies = {(t, c, a.split(" (")[0]) for t, c, a in q(
        con, "SELECT source_table, column_name, anomaly FROM governance.profile_anomaly")}
    assert ("time_bookings", "booking_date", "mixed date formats") in anomalies
    assert ("works_orders", "status", "leading or trailing whitespace") in anomalies
    assert ("purchase_invoices", "net_amount", "number stored as text") in anomalies
    assert ("bom_lines", "material_code", "not in canonical form") in anomalies
    assert ("time_bookings", "works_order", "not in canonical form") in anomalies
    mismatched = {r[0] for r in q(con, """SELECT column_name FROM governance.profile_column
                                          WHERE source_table = 'purchase_invoices' AND type_mismatch""")}
    assert {"net_amount", "vat", "gross"} <= mismatched
    report = result.report.read_text(encoding="utf-8")
    assert "synthetic" in report.lower() and "| `time_bookings` |" in report


# ---- idempotency ----------------------------------------------------------- #

def table_contents(path: Path) -> dict[str, list]:
    con = duckdb.connect(str(path), read_only=True)
    out = {}
    for schema, table in q(con, """SELECT table_schema, table_name FROM information_schema.tables
                                   WHERE table_type = 'BASE TABLE' ORDER BY ALL"""):
        cols = [r[0] for r in q(con, """SELECT column_name FROM information_schema.columns
                                        WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position""",
                                schema, table)]
        keep = ", ".join(f'"{c}"' for c in cols if c not in RUN_COLUMNS)
        out[f"{schema}.{table}"] = q(con, f"SELECT {keep} FROM {schema}.{table} ORDER BY ALL")
    con.close()
    return out


def test_rebuild_is_idempotent(built, tmp_path: Path) -> None:
    root, _, first, _ = built
    second = run_ingest(root / "raw", tmp_path / "again.duckdb", tmp_path / "again.md")
    assert second.run_id != first.run_id
    assert table_contents(first.warehouse) == table_contents(second.warehouse)
    assert first.report.read_bytes() == second.report.read_bytes()
    third = run_ingest(root / "raw", second.warehouse, tmp_path / "again.md")
    assert table_contents(third.warehouse) == table_contents(first.warehouse)
