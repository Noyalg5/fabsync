"""Assert that the synthetic generator is reproducible and that every seeded defect is present.

Each test reads the raw exports the way a downstream stage would (as text, with the
SYNTHETIC DATA header skipped) and checks the defect against defects.json.
"""

from __future__ import annotations

import filecmp
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from fabsync.ingest.generate_sources import DEFAULT_SEED, LABOUR_RATE, generate

RAW_FILES = [
    "corvus_mrp/works_orders.csv", "corvus_mrp/bom_lines.csv", "corvus_mrp/stock.csv",
    "corvus_mrp/purchase_orders.csv", "corvus_mrp/goods_received.csv",
    "finance/purchase_invoices.csv", "finance/sales_invoices.csv", "finance/job_costs.csv",
    "finance/supplier_master.csv",
    "shop_floor/time_bookings.csv", "shop_floor/delivery_notes.csv", "shop_floor/ncr_log.csv",
    "shop_floor/weekly_capacity.csv",
]


@pytest.fixture(scope="module")
def raw(tmp_path_factory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("raw")
    manifest = generate(out, seed=DEFAULT_SEED)
    return out, manifest


def load(out: Path, rel: str) -> pd.DataFrame:
    return pd.read_csv(out / rel, skiprows=1, dtype=str, keep_default_na=False)


def amount(text: str) -> float:
    return float(text.replace(",", "").replace("£", "").strip())


def wo_digits(text: str) -> int | None:
    match = re.search(r"\d{5}", text)
    return int(match.group()) if match else None


# ---- reproducibility and hygiene ------------------------------------------ #

def test_same_seed_is_byte_identical(tmp_path: Path) -> None:
    generate(tmp_path / "a", seed=DEFAULT_SEED)
    generate(tmp_path / "b", seed=DEFAULT_SEED)
    for rel in RAW_FILES + ["defects.json", "DEFECTS.md"]:
        assert filecmp.cmp(tmp_path / "a" / rel, tmp_path / "b" / rel, shallow=False), rel


def test_different_seed_differs(tmp_path: Path) -> None:
    generate(tmp_path / "a", seed=DEFAULT_SEED)
    generate(tmp_path / "b", seed=DEFAULT_SEED + 1)
    assert not filecmp.cmp(tmp_path / "a/corvus_mrp/works_orders.csv",
                           tmp_path / "b/corvus_mrp/works_orders.csv", shallow=False)


def test_every_file_declares_synthetic_data(raw) -> None:
    out, _ = raw
    for rel in RAW_FILES:
        first = (out / rel).read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith("# SYNTHETIC DATA"), rel
    assert "synthetic" in (out / "DEFECTS.md").read_text(encoding="utf-8").lower()


def test_manifest_matches_files(raw) -> None:
    out, manifest = raw
    on_disk = json.loads((out / "defects.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    for rel, rows in manifest["row_counts"].items():
        assert len(load(out, rel)) == rows, rel


def test_volumes(raw) -> None:
    _, manifest = raw
    v = manifest["volumes"]
    assert 700 <= v["works_orders"] <= 950
    assert v["jobs_mrp"] == 150
    assert v["suppliers"] == 60
    assert v["customers"] == 40
    assert 5000 <= v["bom_lines"] <= 7500
    assert 10500 <= v["time_bookings"] <= 14000


def test_history_spans_24_months(raw) -> None:
    out, _ = raw
    wos = load(out, "corvus_mrp/works_orders.csv")
    starts = pd.to_datetime(wos["planned_start"], format="%d/%m/%Y")
    assert starts.min().year == 2024 and starts.max() >= pd.Timestamp("2026-07-01")


# ---- the ten seeded defects ------------------------------------------------ #

def test_1_material_code_drift(raw) -> None:
    out, manifest = raw
    drift = manifest["defects"]["1_material_code_drift"]
    bom = load(out, "corvus_mrp/bom_lines.csv")
    stock = load(out, "corvus_mrp/stock.csv")
    bom_codes = bom["material_code"].str.strip()
    for canonical, variants in drift["materials"].items():
        seen = set(bom_codes[bom_codes.isin(variants["code_variants"])])
        assert len(seen) >= 2, f"{canonical} should appear under at least two codes in BOM lines"
    stock_codes = set(stock["material_code"].str.strip())
    for legacy in drift["legacy_stock_records"]:
        assert legacy["legacy_code"] in stock_codes and legacy["canonical"] in stock_codes
    example = next(iter(drift["materials"].values()))
    assert len(example["description_variants"]) == 4


def test_2_supplier_duplicates(raw) -> None:
    out, manifest = raw
    pos = load(out, "corvus_mrp/purchase_orders.csv")
    master = load(out, "finance/supplier_master.csv")
    po_pairs = set(zip(pos["supplier_code"], pos["supplier_name"].str.strip(), strict=True))
    accounts = dict(zip(master["supplier_account"], master["supplier_name"], strict=True))
    entries = manifest["defects"]["2_supplier_duplicates"]["suppliers"]
    assert len(entries) == 8
    for s in entries:
        names = set()
        for m in s["mrp"]:
            assert (m["code"], m["name"]) in po_pairs
            names.add(m["name"])
        for f in s["finance"]:
            assert accounts[f["account"]] == f["name"]
            names.add(f["name"])
        assert len(names) == 3, s["canonical"]
        assert len({m["code"] for m in s["mrp"]} | {f["account"] for f in s["finance"]}) == 3


def test_3_job_code_mapping_gap(raw) -> None:
    out, manifest = raw
    gap = manifest["defects"]["3_job_code_mapping_gap"]
    wos = load(out, "corvus_mrp/works_orders.csv")
    mapped = {f"{j.split('-')[1]}{int(j.split('-')[2])}" for j in wos["job_no"]}
    finance_codes = set(load(out, "finance/job_costs.csv")["job_code"]) | set(
        load(out, "finance/sales_invoices.csv")["job_code"])
    finance_codes.discard("")
    unmapped = finance_codes - mapped
    assert unmapped == set(gap["finance_only_job_codes"])
    assert 0.10 <= len(unmapped) / len(finance_codes) <= 0.14


def test_4_uom_conflicts(raw) -> None:
    out, manifest = raw
    conflicts = manifest["defects"]["4_uom_conflicts"]["materials"]
    bom = load(out, "corvus_mrp/bom_lines.csv")
    stock = load(out, "corvus_mrp/stock.csv")
    pos = load(out, "corvus_mrp/purchase_orders.csv")
    grn = load(out, "corvus_mrp/goods_received.csv")
    for code in conflicts:
        assert set(bom.loc[bom["material_code"].str.strip() == code, "uom"]) == {"M"}
        assert set(stock.loc[stock["material_code"].str.strip() == code, "uom"]) == {"EA"}
        assert set(pos.loc[pos["material_code"].str.strip() == code, "uom"]) == {"KG"}
        assert set(grn.loc[grn["material_code"].str.strip() == code, "uom"]) == {"KG"}
    assert len(conflicts) >= 10


def test_5_three_way_match(raw) -> None:
    out, manifest = raw
    twm = manifest["defects"]["5_three_way_match"]
    pos = load(out, "corvus_mrp/purchase_orders.csv")
    grn = load(out, "corvus_mrp/goods_received.csv")
    inv = load(out, "finance/purchase_invoices.csv")
    grn_pos = set(grn["po_no"])
    invoiced_pos = set(inv["po_reference"]) - {""}
    for po_no in twm["po_without_grn"]:
        assert po_no in set(pos["po_no"]) and po_no not in grn_pos
    grn_by_no = grn.set_index("grn_no")
    for grn_no in twm["grn_without_invoice"]:
        assert grn_by_no.loc[grn_no, "po_no"] not in invoiced_pos
    po_value = {r.po_no: amount(r.qty) * amount(r.unit_price) for r in pos.itertuples()}
    inv_by_no = inv.set_index("invoice_no")
    for entry in twm["invoice_over_po_by_more_than_5pct"]:
        net = amount(inv_by_no.loc[entry["invoice_no"], "net_amount"])
        assert net > po_value[entry["po_no"]] * 1.05
    assert all(n > 20 for n in twm["counts"].values())


def test_6_traceability_gaps(raw) -> None:
    out, manifest = raw
    trace = manifest["defects"]["6_traceability_gaps"]
    grn = load(out, "corvus_mrp/goods_received.csv")
    missing = grn[(grn["heat_number"].str.strip() == "") | (grn["mill_cert_ref"].str.strip() == "")]
    assert sorted(missing["grn_no"]) == trace["grn_missing_heat_or_cert"]
    assert 0.16 <= len(missing) / len(grn) <= 0.20


def test_7_labour_variance(raw) -> None:
    out, manifest = raw
    lab = manifest["defects"]["7_labour_variance"]
    wos = load(out, "corvus_mrp/works_orders.csv")
    wo_to_job = {int(r.wo_no): f"{r.job_no.split('-')[1]}{int(r.job_no.split('-')[2])}"
                 for r in wos.itertuples()}
    injected = {e["key"] for e in manifest["defects"]["9_structural_noise"]["entry_errors"]
                if e["file"] == "shop_floor/time_bookings.csv" and e["fault"] != "key_collision"}
    bookings = load(out, "shop_floor/time_bookings.csv").drop_duplicates("booking_id")
    bookings = bookings[~bookings["booking_id"].isin(injected)]
    hours_by_job: dict[str, float] = {}
    for r in bookings.itertuples():
        job = wo_to_job.get(wo_digits(r.works_order))
        if job:
            hours_by_job[job] = hours_by_job.get(job, 0.0) + amount(r.hours)
    costs = load(out, "finance/job_costs.csv")
    labour = costs[costs["cost_type"] == "labour"]
    finance_by_job: dict[str, float] = {}
    for r in labour.itertuples():
        finance_by_job[r.job_code] = finance_by_job.get(r.job_code, 0.0) + amount(r.amount)
    variance_codes = {v["finance_code"]: v["factor"] for v in lab["jobs"].values()}
    checked = 0
    for job, hours in hours_by_job.items():
        ratio = finance_by_job[job] / (hours * LABOUR_RATE)
        if job in variance_codes:
            assert abs(ratio - variance_codes[job]) < 0.02 and abs(ratio - 1) > 0.15, job
        else:
            assert abs(ratio - 1) < 0.02, job
        checked += 1
    assert checked > 100 and len(variance_codes) == 30


def test_8_stock_accuracy(raw) -> None:
    out, manifest = raw
    stock = load(out, "corvus_mrp/stock.csv")
    expected = manifest["defects"]["8_stock_accuracy"]
    differs = stock[stock["qty_on_hand"].map(amount) != stock["counted_qty"].map(amount)]
    found = {(r.material_code.strip(), r.site, r.location.strip()) for r in differs.itertuples()}
    assert found == {(e["material_code"], e["site"], e["location"]) for e in expected["lines_with_count_variance"]}
    assert 0.10 <= len(found) / expected["total_counted_lines"] <= 0.20


def test_9_structural_noise(raw) -> None:
    out, manifest = raw
    noise = manifest["defects"]["9_structural_noise"]
    bookings = load(out, "shop_floor/time_bookings.csv")
    assert bookings.duplicated().sum() == noise["duplicate_rows"]["shop_floor/time_bookings.csv"]
    assert load(out, "shop_floor/ncr_log.csv").duplicated().sum() == noise["duplicate_rows"]["shop_floor/ncr_log.csv"]
    wos = load(out, "corvus_mrp/works_orders.csv")
    assert (wos["description"] != wos["description"].str.strip()).any()
    dates = bookings["booking_date"]
    for pattern in (r"^\d{2}/\d{2}/\d{4}$", r"^\d{4}-\d{2}-\d{2}$", r"^\d{2}-[A-Z][a-z]{2}-\d{2}$"):
        assert dates.str.match(pattern).any(), pattern
    invoices = load(out, "finance/purchase_invoices.csv")
    assert invoices["net_amount"].str.contains(",").any()
    assert (bookings["operator"] == "").any() and (load(out, "shop_floor/ncr_log.csv")["closed_date"] == "").any()
    assert bookings["works_order"].str.match(r"^WO \d+$").any()
    assert bookings["works_order"].str.match(r"^wo-\d+$").any()
    assert bookings["works_order"].str.match(r"^\d+ \(rev B\)$").any()


def test_9_entry_errors_present(raw) -> None:
    out, manifest = raw
    errors = manifest["defects"]["9_structural_noise"]["entry_errors"]
    assert len(errors) >= 20
    for e in errors:
        rows = load(out, e["file"])
        match = rows[rows[e["key_column"]] == e["key"]]
        if e["fault"] == "key_collision":
            assert len(match) >= 2 and match.drop_duplicates().shape[0] >= 2
        else:
            assert (match[e["column"]] == e["value"]).any(), e


def test_10_orphan_works_orders(raw) -> None:
    out, manifest = raw
    orphans = set(manifest["defects"]["10_orphans"]["works_orders_in_bookings_not_in_mrp"])
    mrp = set(load(out, "corvus_mrp/works_orders.csv")["wo_no"].astype(int))
    booked = {wo_digits(w) for w in load(out, "shop_floor/time_bookings.csv")["works_order"]} - {None}
    assert len(orphans) == 6
    assert orphans.isdisjoint(mrp)
    assert orphans <= booked
    assert booked - mrp == orphans
