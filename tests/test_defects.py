"""Every defect planted in the synthetic data is detected, exactly, by the controls meant to catch it.

The expected set is the seeded defects register, `DEFECTS.md`, which the generator writes beside the data. Its
defect sections and the counts they state are read from the markdown. The exact identifiers behind each count
come from `defects.json`, which the register names as its machine-readable detail; the first test proves that
every count in the markdown agrees with it.

Each defect has the controls meant to catch it: data quality rules, the reconciliation engines, the matcher,
staging quarantine and profiling. The tests assert that:

* every planted record is detected by at least one control, so a planted defect that is missed fails;
* each control detects exactly its planted records, with no misses and no false alarms, on the records it can
  see (a row quarantined as unreadable is not in staging, so a staging rule cannot see it, but quarantine has
  detected it, and the test checks that it has);
* no rule reports a failure that no planted defect explains, and no rule claims a defect it does not detect.

Where a control is fuzzy by design (supplier name matching, which sends doubtful pairs to a person), the test
asserts precision, that it flags only planted duplicates, and recall across the supplier controls together.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from fabsync.ingest.generate_sources import DEFAULT_SEED, generate
from fabsync.ingest.pipeline import run_ingest
from fabsync.match.pipeline import run_match
from fabsync.pack.facts import md_table
from fabsync.quality.engine import run_quality
from fabsync.quality.rules import load_rules
from fabsync.reconcile.pipeline import run_reconcile

REGISTER_DEFECTS = 13


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("defects")
    generate(root / "raw", seed=DEFAULT_SEED)
    run_ingest(root / "raw", root / "wh.duckdb", root / "p.md")
    run_match(root / "wh.duckdb", root / "m.md")
    run_quality(root / "wh.duckdb")
    run_reconcile(root / "wh.duckdb", root / "r.md")
    con = duckdb.connect(str(root / "wh.duckdb"), read_only=True)
    yield {"md": (root / "raw/DEFECTS.md").read_text(encoding="utf-8"),
           "detail": json.loads((root / "raw/defects.json").read_text(encoding="utf-8")), "con": con}
    con.close()


# ---- reading the register ------------------------------------------------------------------------------- #

def sections(md: str) -> dict[int, tuple[str, str]]:
    parts = re.split(r"(?m)^### (\d+)\. (.+)$", md)
    return {int(parts[i]): (parts[i + 1].strip(), parts[i + 2]) for i in range(1, len(parts), 3)}


def number(body: str, pattern: str) -> int:
    """The number captured by `pattern` in a register section, with thousands separators removed."""
    m = re.search(pattern, body)
    assert m, f"register does not state: {pattern}"
    return int(m.group(1).replace(",", ""))


def expected(world) -> dict[str, int]:
    """Every count the register states, read from the markdown."""
    s = {n: body for n, (_, body) in sections(world["md"]).items()}
    counts = {
        "1_materials": number(s[1], r"(\d+) materials are written several ways"),
        "1_legacy": number(s[1], r"(\d+) legacy stock records"),
        "2_suppliers": number(s[2], r"(\d+) steel suppliers"),
        "3_codes": number(s[3], r"(\d+) of \d+ finance job codes"),
        "4_materials": number(s[4], r"(\d+) sections are transacted"),
        "5_no_grn": number(s[5], r"no goods receipt \(past promised date\): (\d+)"),
        "5_no_invoice": number(s[5], r"with no purchase invoice: (\d+)"),
        "5_over": number(s[5], r"by more than 5%: (\d+)"),
        "5_overdue": number(s[5], r"invoice, (\d+) were received more than 30 days"),
        "5_window": number(s[5], r"(\d+) were received in the last 30 days"),
        "5_short": number(s[5], r"Short deliveries: (\d+) receipts"),
        "5_services": number(s[5], r"no PO reference: (\d+) for subcontract"),
        "5_overheads": number(s[5], r"(\d+) overheads on nominal"),
        "6_grns": number(s[6], r"(\d+) of \d+ goods receipts"),
        "6_s355": number(s[6], r"(\d+) of these receipts are S355"),
        "7_jobs": number(s[7], r"On (\d+) jobs"),
        "8_lines": number(s[8], r"on (\d+) of the \d+ counted"),
        "8_counted": number(s[8], r"of the (\d+) counted stock lines"),
        "9_entry_errors": number(s[9], r"no parser should accept: (\d+)"),
        "10_orphans": number(s[10], r"(\d+) works orders appear"),
        "11_open_wos": number(s[11], r"never closed off: (\d+)"),
        "11_stale_stock": number(s[11], r"more than 90 days before the extract: (\d+)"),
        "11_open_ncrs": number(s[11], r"and never closed: (\d+)"),
        "12_orders": number(s[12], r"(\d+) purchase orders supply"),
        "13_records": number(s[13], r"yet (\d+) records"),
        "13_orders": number(s[13], r"(\d+) purchase orders placed"),
        "13_invoices": number(s[13], r"(\d+) supplier\s+invoices"),
        "13_bookings": number(s[13], r"(\d+) time bookings"),
        "13_finishes": number(s[13], r"(\d+) works orders\s+finished"),
    }
    for m in re.finditer(r"(\w+)\.csv ([a-z ]+?) on (\d+) records", s[9]):
        counts[f"9_blank:{m.group(1)}:{m.group(2).replace(' ', '_')}"] = int(m.group(3))
    for m in re.finditer(r"(\w+)\.csv ([a-z ]+?) ([\d,]+)(?=[;.])", s[9].split("UK house format")[1].split("\n")[0]):
        counts[f"9_dates:{m.group(1)}:{m.group(2).replace(' ', '_')}"] = int(m.group(3).replace(",", ""))
    dups = re.search(r"Duplicate rows: (\{.*\})", s[9]).group(1)
    for f, n in re.findall(r"'shop_floor/(\w+)\.csv': (\d+)", dups):
        counts[f"9_dups:{f}"] = int(n)
    counts["10_ids"] = sorted(int(x) for x in re.search(r"not in Corvus: ([\d, ]+)\.", s[10]).group(1).split(", "))
    return counts


def rows(con, sql: str, *params) -> list[tuple]:
    return con.execute(sql, list(params)).fetchall()


def failing(con, rule: str) -> set[str]:
    return {k for (k,) in rows(con, "SELECT record_key FROM governance.dq_exceptions WHERE rule_id = ?", rule)}


def staged(con, table: str, key: str) -> set[str]:
    return {str(k) for (k,) in rows(con, f"SELECT {key} FROM staging.{table}")}


def quarantined(con, file: str, key: str) -> set[str]:
    return {str(json.loads(r)[key]).strip() for (r,) in rows(
        con, "SELECT original_record FROM governance.quarantine WHERE source_file = ?", file)}


def category(con, cat: str) -> set[str]:
    return {p for (p,) in rows(con, "SELECT po_no FROM recon.three_way_lines WHERE category = ?", cat)}


# ---- the register ----------------------------------------------------------------------------------------- #

def test_the_project_brief_lists_every_registered_defect(world) -> None:
    """The README quotes the number of defects from the brief's table, so the table must match the register."""
    brief = (Path(__file__).resolve().parents[1] / "docs/project-brief.md").read_text(encoding="utf-8")
    rows = md_table(brief, "| # | Defect | Where |")
    assert [int(r[0]) for r in rows] == sorted(sections(world["md"]))


def test_register_lists_every_defect_and_its_markdown_agrees_with_its_detail(world) -> None:
    secs, d, e = sections(world["md"]), world["detail"]["defects"], expected(world)
    assert sorted(secs) == list(range(1, REGISTER_DEFECTS + 1))
    assert sorted(int(k.split("_")[0]) for k in d) == list(range(1, REGISTER_DEFECTS + 1))
    twm, noise = d["5_three_way_match"], d["9_structural_noise"]
    pairs = {
        "1_materials": len(d["1_material_code_drift"]["materials"]),
        "1_legacy": len(d["1_material_code_drift"]["legacy_stock_records"]),
        "2_suppliers": len(d["2_supplier_duplicates"]["suppliers"]),
        "3_codes": len(d["3_job_code_mapping_gap"]["finance_only_job_codes"]),
        "4_materials": len(d["4_uom_conflicts"]["materials"]),
        "5_no_grn": len(twm["po_without_grn"]), "5_no_invoice": len(twm["grn_without_invoice"]),
        "5_over": len(twm["invoice_over_po_by_more_than_5pct"]),
        "5_overdue": len(twm["grn_without_invoice_overdue"]),
        "5_window": len(twm["grn_without_invoice_within_invoicing_window"]),
        "5_short": len(twm["short_deliveries"]), "5_services": len(twm["invoices_without_po"]["services"]),
        "5_overheads": len(twm["invoices_without_po"]["overheads"]),
        "6_grns": len(d["6_traceability_gaps"]["grn_missing_heat_or_cert"]),
        "6_s355": len(d["6_traceability_gaps"]["s355_grn_without_certificate"]),
        "7_jobs": len(d["7_labour_variance"]["jobs"]),
        "8_lines": len(d["8_stock_accuracy"]["lines_with_count_variance"]),
        "8_counted": d["8_stock_accuracy"]["total_counted_lines"],
        "9_entry_errors": len(noise["entry_errors"]),
        "10_orphans": len(d["10_orphans"]["works_orders_in_bookings_not_in_mrp"]),
        "11_open_wos": len(d["11_housekeeping_lapses"]["works_orders_open_30_days_after_planned_finish"]),
        "11_stale_stock": len(d["11_housekeeping_lapses"]["stock_lines_not_counted_in_90_days"]),
        "11_open_ncrs": len(d["11_housekeeping_lapses"]["ncrs_open_more_than_60_days"]),
        "12_orders": len(d["12_steel_charged_to_ordering_job"]["purchase_orders"]),
        "13_records": d["13_dates_after_extract"]["count"],
        "13_orders": len(d["13_dates_after_extract"]["purchase_orders"]),
        "13_invoices": len(d["13_dates_after_extract"]["purchase_invoices"]),
        "13_bookings": len(d["13_dates_after_extract"]["time_bookings"]),
        "13_finishes": len(d["13_dates_after_extract"]["works_order_finish"]),
        "10_ids": sorted(d["10_orphans"]["works_orders_in_bookings_not_in_mrp"]),
    }
    for key, value in pairs.items():
        assert e[key] == value, f"{key}: the register says {e[key]}, its detail {value}"
    for f, cols in noise["blank_cell_records"].items():
        for col, ids in cols.items():
            assert e[f"9_blank:{Path(f).stem}:{col}"] == len(ids), (f, col)
    for f, cols in noise["dates_not_in_uk_format"].items():
        for col, n in cols.items():
            assert e[f"9_dates:{Path(f).stem}:{col}"] == n, (f, col)
    for f, n in noise["duplicate_rows"].items():
        assert e[f"9_dups:{Path(f).stem}"] == n


def test_every_rule_is_accounted_for(world) -> None:
    """A rule that claims a defect detects it; a rule that claims none raises nothing."""
    con, defects = world["con"], set(sections(world["md"]))
    for rule in load_rules().rules:
        found = failing(con, rule.id)
        assert set(rule.covers_defects) <= defects, f"{rule.id} claims a defect the register does not list"
        if rule.covers_defects:
            assert found, f"{rule.id} claims defect {rule.covers_defects} but detects nothing"
        else:
            assert not found, f"{rule.id} raises {len(found)} failures that no planted defect explains"
    covered = {d for rule in load_rules().rules for d in rule.covers_defects}
    assert covered | {12} == defects, "every defect has a rule, except 12, which only the job cost engine can see"


# ---- 1 to 4: master data ------------------------------------------------------------------------------------ #

def test_1_material_code_drift(world) -> None:
    con, d, e = world["con"], world["detail"]["defects"]["1_material_code_drift"], expected(world)
    variants: dict[str, set[str]] = {}
    for code, m in d["materials"].items():
        for v in m["code_variants"][1:]:
            variants.setdefault(v, set()).add(code)
    assert len(d["materials"]) == e["1_materials"]
    bom = {f"{w}/{n}" for w, n, c in rows(con, "SELECT wo_no, line_no, trim(material_code) FROM "
                                               "staging.corvus_mrp_bom_lines") if c in variants}
    stock = {f"{c}|{s}|{loc}" for c, s, loc in rows(con, "SELECT material_code, site, location FROM "
                                                         "staging.corvus_mrp_stock") if c.strip() in variants}
    po = {p for p, c in rows(con, "SELECT po_no, trim(material_code) FROM staging.corvus_mrp_purchase_orders")
          if c in variants}
    grn = {g for g, c in rows(con, "SELECT grn_no, trim(material_code) FROM staging.corvus_mrp_goods_received")
           if c in variants}
    assert failing(con, "DQ-04") == bom | stock | po | grn
    assert failing(con, "DQ-03") == po | grn, "an order or receipt with a drifted code carries no grade"
    legacy = {(x["legacy_code"], x["site"]) for x in d["legacy_stock_records"]}
    assert len(legacy) == e["1_legacy"]
    assert legacy <= {(k.split("|")[0].strip(), k.split("|")[1]) for k in stock}
    for written, canonical in variants.items():
        resolved = {r[0] for r in rows(con, "SELECT coalesce(canonical_code, proposed_code) FROM core.material_xref "
                                            "WHERE trim(source_code) = ?", written)}
        assert resolved <= canonical | {None}, (written, resolved)


def test_2_supplier_duplicates(world) -> None:
    con, suppliers, e = world["con"], world["detail"]["defects"]["2_supplier_duplicates"]["suppliers"], expected(world)
    assert len(suppliers) == e["2_suppliers"]
    planted_codes = {m["code"] for s in suppliers for m in s["mrp"]}
    multi_code = {m["code"] for s in suppliers if len(s["mrp"]) > 1 for m in s["mrp"]}
    multi_account = {f["account"] for s in suppliers if len(s["finance"]) > 1 for f in s["finance"]}
    assert failing(con, "DQ-07") == multi_code
    assert failing(con, "DQ-08") == multi_account
    assert failing(con, "DQ-09") <= planted_codes, "only planted duplicates are left unlinked"
    flagged = failing(con, "DQ-07") | failing(con, "DQ-08") | failing(con, "DQ-09")
    for s in suppliers:
        ids = {m["code"] for m in s["mrp"]} | {f["account"] for f in s["finance"]}
        assert ids & flagged, f"{s['canonical']} is planted but no supplier control detects it"


def test_3_job_code_mapping_gap(world) -> None:
    con, d, e = world["con"], world["detail"]["defects"]["3_job_code_mapping_gap"], expected(world)
    codes = set(d["finance_only_job_codes"])
    assert len(codes) == e["3_codes"]
    assert failing(con, "DQ-10") == codes
    on_codes = {i for i, c in rows(con, "SELECT invoice_no, job_code FROM staging.finance_sales_invoices")
                if c in codes}
    assert failing(con, "DQ-11") == on_codes
    engine = {j.removeprefix("finance ") for (j,) in rows(con, "SELECT DISTINCT job_no FROM recon.job_cost_detail "
                                                                "WHERE NOT job_in_corvus")}
    with_cost = {c for (c,) in rows(con, "SELECT DISTINCT job_code FROM staging.finance_job_costs")} & codes
    assert engine == with_cost


def test_4_uom_conflicts(world) -> None:
    con, d, e = world["con"], world["detail"]["defects"]["4_uom_conflicts"], expected(world)
    assert len(d["materials"]) == e["4_materials"]
    assert failing(con, "DQ-05") == set(d["materials"])
    flagged = {c for (c,) in rows(con, "SELECT canonical_code FROM core.material_golden WHERE uom_conflict")}
    assert flagged == set(d["materials"])


# ---- 5: three-way match --------------------------------------------------------------------------------- #

def test_5_three_way_match(world) -> None:
    con, twm, e = world["con"], world["detail"]["defects"]["5_three_way_match"], expected(world)
    grn_po = dict(rows(con, "SELECT grn_no, po_no FROM staging.corvus_mrp_goods_received"))
    over_invoices = {x["invoice_no"] for x in twm["invoice_over_po_by_more_than_5pct"]}
    over_pos = {x["po_no"] for x in twm["invoice_over_po_by_more_than_5pct"]}
    assert (len(twm["po_without_grn"]), len(over_invoices)) == (e["5_no_grn"], e["5_over"])
    assert len(twm["grn_without_invoice_overdue"]) + len(twm["grn_without_invoice_within_invoicing_window"]) \
        == e["5_no_invoice"] == e["5_overdue"] + e["5_window"]
    # the rules
    assert failing(con, "DQ-12") == set(twm["po_without_grn"])
    assert failing(con, "DQ-13") == set(twm["grn_without_invoice_overdue"])
    assert failing(con, "DQ-14") == over_invoices
    # the engine
    assert category(con, "missing GRN") == set(twm["po_without_grn"])
    assert category(con, "missing invoice") == {grn_po[g] for g in twm["grn_without_invoice_overdue"]}
    waiting = {p for (p,) in rows(con, "SELECT po_no FROM recon.three_way_lines WHERE category = 'not yet due' "
                                       "AND received_date IS NOT NULL")}
    assert waiting == {grn_po[g] for g in twm["grn_without_invoice_within_invoicing_window"]}
    assert category(con, "price variance") == over_pos
    tolerance = 0.02
    short = {x["po_no"] for x in twm["short_deliveries"]}
    assert len(short) == e["5_short"]
    earlier = (category(con, "missing GRN") | category(con, "missing invoice") | category(con, "price variance")
               | waiting)
    beyond = {p for p, ordered, received in rows(con, "SELECT po_no, qty_ordered, qty_received FROM "
                                                      "recon.three_way_lines WHERE qty_received IS NOT NULL")
              if p in short and ordered - received > tolerance * ordered + 1e-9}
    assert category(con, "quantity variance") == beyond - earlier, "every short delivery beyond 2%, and no other"
    assert {x["po_no"] for x in twm["short_deliveries"] if x["received_share"] <= 0.95} - earlier <= beyond
    no_po = {i for (i,) in rows(con, "SELECT invoice_nos FROM recon.three_way_lines "
                                     "WHERE category = 'invoice with no PO'")}
    assert no_po == set(twm["invoices_without_po"]["services"]) and len(no_po) == e["5_services"]
    exempt = {i for i, n in rows(con, "SELECT invoice_no, nominal_code FROM staging.finance_purchase_invoices "
                                      "WHERE po_reference IS NULL") if n == "7000"}
    assert exempt == set(twm["invoices_without_po"]["overheads"]) and len(exempt) == e["5_overheads"]


# ---- 6 to 8 -------------------------------------------------------------------------------------------------- #

def test_6_traceability_gaps(world) -> None:
    con, d, e = world["con"], world["detail"]["defects"]["6_traceability_gaps"], expected(world)
    gaps = set(d["grn_missing_heat_or_cert"])
    assert len(gaps) == e["6_grns"]
    assert failing(con, "DQ-01") | failing(con, "DQ-02") == gaps
    no_heat = staged_where(con, "corvus_mrp_goods_received", "grn_no", "heat_number IS NULL")
    no_cert = staged_where(con, "corvus_mrp_goods_received", "grn_no", "mill_cert_ref IS NULL")
    assert (failing(con, "DQ-01"), failing(con, "DQ-02")) == (no_heat, no_cert) and no_heat | no_cert == gaps
    # S355 needs a 3.1 document at every execution class. DQ-41 can test only receipts whose code states the grade;
    # the rest of the planted S355 receipts wait in the grade review queue.
    s355 = set(d["s355_grn_without_certificate"])
    assert len(s355) == e["6_s355"] and s355 <= no_cert
    confirmed = {g for (g,) in rows(con, """SELECT g.grn_no FROM staging.corvus_mrp_goods_received g
        JOIN core.material_xref x ON x.source_table = 'goods_received' AND x.source_code = g.material_code
        WHERE x.status = 'auto'""")}
    assert failing(con, "DQ-41") == s355 & confirmed
    assert failing(con, "DQ-41") == {g for (g,) in rows(con, "SELECT grn_no FROM recon.trace_receipts "
                                                           "WHERE s355 AND NOT document_31")}
    supplied: dict[tuple, set[str]] = {}
    for w, n, g in rows(con, """SELECT a.wo_no, a.line_no, a.grn_no FROM recon.trace_allocations a
                                 JOIN recon.trace_lines l USING (wo_no, line_no) WHERE l.break_at LIKE 'receipt:%'"""):
        supplied.setdefault((w, n), set()).add(g)
    assert supplied and all(grns & gaps for grns in supplied.values()), \
        "a chain breaks at receipt only on a planted one"
    used = {g for (g,) in rows(con, "SELECT DISTINCT grn_no FROM recon.trace_allocations")}
    assert gaps & used <= {g for (g,) in rows(con, """SELECT DISTINCT a.grn_no FROM recon.trace_allocations a
        JOIN recon.trace_lines l USING (wo_no, line_no) WHERE NOT l.material_chain_complete""")}


def staged_where(con, table: str, key: str, where: str) -> set[str]:
    return {str(k) for (k,) in rows(con, f"SELECT {key} FROM staging.{table} WHERE {where}")}


def test_7_labour_variance(world) -> None:
    con, d, e = world["con"], world["detail"]["defects"]["7_labour_variance"], expected(world)
    jobs = set(d["jobs"])
    assert len(jobs) == e["7_jobs"]
    assert failing(con, "DQ-16") == jobs
    engine = {j for (j,) in rows(con, "SELECT job_no FROM recon.job_cost "
                                      "WHERE in_corvus AND abs(labour_gap_pct) > 0.15")}
    assert engine == jobs


def test_8_stock_accuracy(world) -> None:
    con, d, e = world["con"], world["detail"]["defects"]["8_stock_accuracy"], expected(world)
    lines = {f"{x['material_code']}|{x['site']}|{x['location']}" for x in d["lines_with_count_variance"]}
    assert len(lines) == e["8_lines"]
    assert failing(con, "DQ-17") == lines
    engine = {k for (k,) in rows(con, "SELECT trim(material_code) || '|' || site_code || '|' || trim(location) "
                                      "FROM recon.stock_lines WHERE NOT accurate")}
    assert engine == lines
    assert rows(con, "SELECT count(*) FROM recon.stock_lines")[0][0] == e["8_counted"]


# ---- 9: structural noise ------------------------------------------------------------------------------------ #

BLANK_RULES = {("time_bookings", "operator"): ("DQ-27", "shop_floor_time_bookings", "booking_id", "booking_id"),
               ("time_bookings", "operation"): ("DQ-28", "shop_floor_time_bookings", "booking_id", "booking_id"),
               ("delivery_notes", "promised_date"): ("DQ-29", "shop_floor_delivery_notes", "dn_no", "dn_no"),
               ("delivery_notes", "tonnage"): ("DQ-30", "shop_floor_delivery_notes", "dn_no", "dn_no"),
               ("delivery_notes", "vehicle"): ("DQ-40", "shop_floor_delivery_notes", "dn_no", "dn_no"),
               ("ncr_log", "cost_impact"): ("DQ-39", "shop_floor_ncr_log", "ncr_no", "ncr_no")}


def test_9_blank_cells_are_each_detected(world) -> None:
    con, noise, e = world["con"], world["detail"]["defects"]["9_structural_noise"], expected(world)
    blanks = noise["blank_cell_records"]
    covered = set()
    for (file, col), (rule, table, key, raw_key) in BLANK_RULES.items():
        planted = set(blanks[f"shop_floor/{file}.csv"][col])
        assert len(planted) == e[f"9_blank:{file}:{col}"]
        visible = planted & staged(con, table, key)
        assert failing(con, rule) == visible, f"{rule} against planted blank {col}"
        missing = planted - visible
        assert missing <= quarantined(con, f"shop_floor/{file}.csv", raw_key), f"{col}: {sorted(missing)[:5]}"
        covered.add((file, col))
    closed = set(blanks["shop_floor/ncr_log.csv"]["closed_date"])
    assert closed >= set(world["detail"]["defects"]["11_housekeeping_lapses"]["ncrs_open_more_than_60_days"])
    assert covered | {("ncr_log", "closed_date")} == {(Path(f).stem, c) for f, cols in blanks.items() for c in cols}


def test_9_dates_duplicates_and_entry_errors(world) -> None:
    con, noise, e = world["con"], world["detail"]["defects"]["9_structural_noise"], expected(world)
    by_column = Counter((k.split(":")[0].split("/")[1].removesuffix(".csv"), k.split(":")[2])
                        for k in failing(con, "DQ-22"))
    assert dict(by_column) == {(Path(f).stem, c): n for f, cols in noise["dates_not_in_uk_format"].items()
                               for c, n in cols.items() if n}
    assert all(by_column[(f, c)] == e[f"9_dates:{f}:{c}"] for f, c in by_column)
    assert len(failing(con, "DQ-19")) == sum(e[k] for k in e if k.startswith("9_dups:"))
    errors = noise["entry_errors"]
    assert len(errors) == e["9_entry_errors"]
    assert len(failing(con, "DQ-21")) == sum(1 for x in errors if x["fault"] == "key_collision")
    assert len(failing(con, "DQ-20")) == sum(1 for x in errors if x["fault"] != "key_collision")
    held = {(f, r) for f, r in rows(con, "SELECT source_file, source_row FROM governance.quarantine")}
    for x in errors:
        if x["fault"] != "key_collision":
            assert any(f == x["file"] for f, _ in held), x


def test_9_padding_and_numbers_as_text_are_profiled(world) -> None:
    con = world["con"]
    found = {(s, a) for s, a in rows(con, "SELECT source_system, anomaly FROM governance.profile_anomaly")}
    assert ("corvus_mrp", "leading or trailing whitespace") in found
    assert ("finance", "number stored as text (separators, currency or spaces)") in found
    assert any(s == "shop_floor" and a.startswith("mixed date formats") for s, a in found)


# ---- 10 to 13 ------------------------------------------------------------------------------------------------ #

def test_10_orphan_works_orders(world) -> None:
    con, e = world["con"], expected(world)
    orphans = set(e["10_ids"])
    assert len(orphans) == e["10_orphans"]
    written = {o for (o,) in rows(con, "SELECT observed FROM governance.dq_exceptions WHERE rule_id = 'DQ-23'")}
    assert {int("".join(ch for ch in w if ch.isdigit())[:5]) for w in written} == orphans
    engine = {w for (w,) in rows(con, "SELECT DISTINCT wo_no FROM core.time_bookings WHERE NOT wo_matched")}
    assert engine == orphans
    queue = rows(con, "SELECT source_value FROM core.v_match_review_queue WHERE domain = 'works_order'")
    review = {int(re.match(r"\d+", n).group(0)) for (n,) in queue}
    assert review == orphans


def test_11_housekeeping_lapses(world) -> None:
    con, h, e = world["con"], world["detail"]["defects"]["11_housekeeping_lapses"], expected(world)
    open_wos = {str(w) for w in h["works_orders_open_30_days_after_planned_finish"]}
    assert (len(open_wos), len(h["stock_lines_not_counted_in_90_days"]), len(h["ncrs_open_more_than_60_days"])) \
        == (e["11_open_wos"], e["11_stale_stock"], e["11_open_ncrs"])
    assert failing(con, "DQ-33") == open_wos
    assert failing(con, "DQ-18") == set(h["stock_lines_not_counted_in_90_days"])
    ncrs = set(h["ncrs_open_more_than_60_days"])
    visible = ncrs & staged(con, "shop_floor_ncr_log", "ncr_no")
    assert failing(con, "DQ-34") == visible
    assert ncrs - visible <= quarantined(con, "shop_floor/ncr_log.csv", "ncr_no"), "held back as unreadable"


def test_12_steel_charged_to_the_ordering_job(world) -> None:
    """Detected in aggregate, by design: an order charged to one job but used on several shows as a pattern of gaps
    across jobs, which the engine quantifies. Which invoice line was mis-posted needs the cutting lists."""
    con, d, e = world["con"], world["detail"]["defects"]["12_steel_charged_to_ordering_job"], expected(world)
    shared = d["purchase_orders"]
    assert len(shared) == e["12_orders"]
    finance_code = {j: f"{j[2:4]}{int(j[5:])}" for x in shared for j in [x["charged_to"], *x["also_used_by"]]}
    invoiced = rows(con, "SELECT po_reference, job_code FROM staging.finance_purchase_invoices "
                         "WHERE po_reference IN (SELECT unnest(?))", [x["po_no"] for x in shared])
    charged = {x["po_no"]: finance_code[x["charged_to"]] for x in shared}
    assert invoiced and all(job == charged[po] for po, job in invoiced), "each invoice lands on the ordering job"
    section = dict(rows(con, """SELECT p.po_no, regexp_replace(coalesce(x.canonical_code, x.proposed_code,
        split_part(x.candidates, ', ', 1)), '-S\\d+\\w*$', '') FROM staging.corvus_mrp_purchase_orders p
        JOIN core.material_xref x ON x.source_table = 'purchase_orders' AND x.source_code = p.material_code"""))
    issued = {(j, re.sub(r"-S\d+\w*$", "", m)) for j, m in rows(
        con, "SELECT job_no, canonical_code FROM recon.job_material WHERE issued_kg > 0")}
    for x in shared:
        for job in x["also_used_by"]:
            assert (job, section[x["po_no"]]) in issued, f"{x['po_no']}: the engine sees {job} use the steel"
    assert rows(con, "SELECT value FROM recon.headline WHERE key = 'material_misallocated'")[0][0] > 0


def test_13_dates_after_the_extract(world) -> None:
    con, f, e = world["con"], world["detail"]["defects"]["13_dates_after_extract"], expected(world)
    assert (len(f["purchase_orders"]), len(f["purchase_invoices"]), len(f["time_bookings"]),
            len(f["works_order_finish"])) == (e["13_orders"], e["13_invoices"], e["13_bookings"], e["13_finishes"])
    assert failing(con, "DQ-35") == set(f["purchase_orders"])
    assert failing(con, "DQ-36") == {str(w) for w in f["works_order_finish"]}
    assert failing(con, "DQ-37") == set(f["purchase_invoices"])
    assert failing(con, "DQ-38") == {str(b) for b in f["time_bookings"]}
    as_of = date.fromisoformat(world["detail"]["as_of"])
    assert all(d > as_of for (d,) in rows(con, "SELECT invoice_date FROM staging.finance_purchase_invoices "
                                               "WHERE invoice_no IN (SELECT unnest(?))", f["purchase_invoices"]))
    assert as_of - timedelta(days=0) == as_of
