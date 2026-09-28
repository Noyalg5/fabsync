"""Material traceability: mill certificate and heat number, through receipt and issue, to works order and despatch.

The chain an EN 1090-2 factory production control auditor expects:

    mill certificate + heat number -> goods receipt -> material issue -> works order -> delivery note

Corvus holds no material issue transactions, so which receipt supplied which
works order is not recorded. That is itself a traceability weakness. The issue
link is reconstructed: for each canonical material, confirmed-grade receipts are
allocated first-in first-out, in kilograms, to the BOM lines of started works
orders in planned-start order. A receipt can only supply a works order if it was
received by that works order's planned finish. The allocation is written to
recon.trace_allocations so every link can be inspected.

Each BOM line is checked link by link, and the first failing link is where its
chain breaks:

1. receipt: heat number recorded on every allocated receipt
2. receipt: mill certificate recorded on every allocated receipt
3. issue: enough confirmed-grade receipts to cover the line. If only receipts
   whose code omits the grade exist for that section, the break is "grade
   unconfirmed"; otherwise "no receipt on record".
4. despatch: a finished works order has a delivery note for its job within the
   despatch window

Coverage is the share of BOM kilograms whose chain is complete through the
material links (1 to 3).

What EN 1090-2 (clause 5.2) requires depends on the execution class the designer
specified for the structure, which Corvus records on every works order:

* EXC3 and EXC4: constituent products traceable at all stages from receipt to
  hand over. Steel despatched on an EXC3 job with an incomplete chain is an
  EN 1090 compliance exposure.
* EXC2: full traceability is not required, but S355 needs a 3.1 inspection
  document (in this scenario every mill certificate is EN 10204 type 3.1) and
  mixed grades must be marked. S355 steel despatched on an EXC2 job whose
  supplying receipts do not all carry a certificate, or that no certified receipt
  covers, is an EN 1090 compliance exposure. Any other incomplete chain on an
  EXC2 job is a quality and good-practice gap, reported separately.

A job whose works orders carry no single class is treated as EXC3. The 3.1 check
on S355 applies at every class: `recon.trace_receipts` lists every receipt with
its confirmed grade and whether it carries a certificate.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from fabsync.reconcile.common import EngineResult, Headline

RECEIPTS_SQL = """
SELECT g.grn_no, g.po_no, g.received_date, g.heat_number, g.mill_cert_ref, trim(g.material_code) AS material_code,
       x.status AS grade_status, x.canonical_code, x.section_type,
       CASE WHEN x.status = 'auto' THEN m.grade END AS grade,
       regexp_replace(coalesce(x.proposed_code, split_part(x.candidates, ', ', 1), x.canonical_code), '-.*$', '')
           AS designation_key,
       CAST(CASE g.uom WHEN 'KG' THEN g.qty_received WHEN 'M' THEN g.qty_received * m.mass
                       WHEN 'EA' THEN g.qty_received * m.kg_per_ea END AS DOUBLE) AS kg,
       g._source_file AS source_file, g._source_row AS source_row
FROM staging.corvus_mrp_goods_received g
JOIN core.material_xref x ON x.source_table = 'goods_received' AND x.source_code = g.material_code
LEFT JOIN core.material_golden m ON m.canonical_code = coalesce(x.canonical_code, x.proposed_code,
                                                                split_part(x.candidates, ', ', 1))
ORDER BY g.received_date, g.grn_no
"""

DEMAND_SQL = """
SELECT b.wo_no, b.line_no, w.job_no, coalesce(j.execution_class, 'unknown') AS execution_class, w.status,
       w.planned_start, w.planned_finish, w.actual_finish, x.canonical_code, m.grade,
       regexp_replace(x.canonical_code, '-.*$', '') AS designation_key,
       CAST(CASE b.uom WHEN 'KG' THEN b.qty ELSE b.qty * m.mass END AS DOUBLE) AS kg,
       b._source_file AS source_file, b._source_row AS source_row
FROM staging.corvus_mrp_bom_lines b
JOIN core.works_orders w ON w.wo_no = b.wo_no
JOIN core.jobs j ON j.job_no = w.job_no
JOIN core.material_xref x ON x.source_table = 'bom_lines' AND x.source_code = b.material_code
     AND x.source_description IS NOT DISTINCT FROM b.description AND x.source_grade IS NOT DISTINCT FROM b.grade
     AND x.source_section_type IS NOT DISTINCT FROM b.section_type
JOIN core.material_golden m ON m.canonical_code = x.canonical_code
WHERE w.status IN ('RELEASED', 'OPEN', 'COMPLETE', 'CLOSED')
ORDER BY w.planned_start, b.wo_no, b.line_no
"""

DESPATCH_SQL = """
SELECT w.wo_no, min(d.dn_no) AS dn_no, min(d.despatch_date) AS despatch_date
FROM core.works_orders w
JOIN core.delivery_notes d ON d.job_no = w.job_no
     AND d.despatch_date BETWEEN w.actual_finish AND w.actual_finish + {window}
WHERE w.actual_finish IS NOT NULL
GROUP BY 1
"""

CUSTOMER_SQL = """
SELECT j.job_no, s.customer_name, s.sales_value, d.tonnage_despatched, d.delivery_notes
FROM core.jobs j
LEFT JOIN (SELECT job_code, mode(customer_name) AS customer_name, sum(net_amount) AS sales_value
           FROM staging.finance_sales_invoices GROUP BY 1) s ON s.job_code = j.finance_job_code
LEFT JOIN (SELECT job_no, sum(tonnage) AS tonnage_despatched, count(*) AS delivery_notes
           FROM core.delivery_notes GROUP BY 1) d ON d.job_no = j.job_no
"""

LINKS = ["receipt: heat number missing", "receipt: mill certificate missing", "issue: receipt grade unconfirmed",
         "issue: no receipt on record"]
EXC3_INCOMPLETE = "EN 1090: EXC3 chain incomplete"
S355_NO_31 = "EN 1090: S355 with no 3.1 document shown"
EXC2_GAP = "good practice: EXC2 chain incomplete"


def allocate(receipts: pd.DataFrame, demand: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """First-in first-out allocation of confirmed-grade receipt kilograms to BOM lines."""
    lag = pd.Timedelta(days=cfg["traceability"]["receipt_after_finish_days"])
    pools: dict[str, list[list]] = defaultdict(list)
    for r in receipts[receipts.grade_status == "auto"].itertuples():
        pools[r.canonical_code].append([pd.Timestamp(r.received_date), r.grn_no, float(r.kg)])
    rows = []
    for d in demand.itertuples():
        need, limit = float(d.kg), pd.Timestamp(d.planned_finish) + lag
        for rec in pools.get(d.canonical_code, []):
            if need <= 1e-9:
                break
            if rec[2] <= 1e-9 or rec[0] > limit:
                continue
            take = min(need, rec[2])
            rec[2] -= take
            need -= take
            rows.append({"wo_no": d.wo_no, "line_no": d.line_no, "grn_no": rec[1], "kg": round(take, 3)})
    return pd.DataFrame(rows, columns=["wo_no", "line_no", "grn_no", "kg"])


def material_traceability(con, cfg: dict) -> EngineResult:
    receipts = con.execute(RECEIPTS_SQL).df()
    demand = con.execute(DEMAND_SQL).df()
    alloc = allocate(receipts, demand, cfg)
    alloc = alloc.merge(receipts[["grn_no", "po_no", "received_date", "heat_number", "mill_cert_ref",
                                  "source_file", "source_row"]], on="grn_no", how="left")
    alloc["heat_ok"] = alloc.heat_number.notna()
    alloc["cert_ok"] = alloc.mill_cert_ref.notna()

    unconfirmed = set(receipts[receipts.grade_status != "auto"].designation_key)
    per_line = alloc.groupby(["wo_no", "line_no"]).agg(
        kg_allocated=("kg", "sum"), receipts=("grn_no", lambda g: ", ".join(g)),
        heat_ok=("heat_ok", "all"), cert_ok=("cert_ok", "all"),
        missing_heat=("heat_ok", lambda s: ", ".join(alloc.loc[s.index[~s]].grn_no)),
        missing_cert=("cert_ok", lambda s: ", ".join(alloc.loc[s.index[~s]].grn_no))).reset_index()
    lines = demand.merge(per_line, on=["wo_no", "line_no"], how="left")
    lines["kg_allocated"] = lines.kg_allocated.fillna(0.0)
    lines["kg_short"] = (lines.kg - lines.kg_allocated).clip(lower=0).round(3)
    lines["heat_ok"] = lines.heat_ok.fillna(True).astype(bool)
    lines["cert_ok"] = lines.cert_ok.fillna(True).astype(bool)

    despatch = con.execute(DESPATCH_SQL.format(window=cfg["traceability"]["despatch_window_days"])).df()
    lines = lines.merge(despatch, on="wo_no", how="left")
    lines["finished"] = lines.actual_finish.notna()
    lines["despatched"] = lines.dn_no.notna()

    def chain(r) -> tuple[str, str]:
        if not r.heat_ok:
            return LINKS[0], f"receipts without a heat number: {r.missing_heat}"
        if not r.cert_ok:
            return LINKS[1], f"receipts without a mill certificate: {r.missing_cert}"
        if r.kg_short > 0.5:
            if r.designation_key in unconfirmed:
                return LINKS[2], (f"{r.kg_short:,.0f} kg not covered; receipts of {r.designation_key} exist but their "
                                  "code does not state the grade")
            return LINKS[3], f"{r.kg_short:,.0f} kg not covered by any receipt received by the planned finish"
        if r.finished and not r.despatched:
            return "despatch: no delivery note", "finished but no delivery note for the job within the window"
        return "complete", ("traced to " + r.receipts + (f", despatched on {r.dn_no}" if r.despatched else
                                                        ", not yet despatched"))
    outcome = lines.apply(chain, axis=1, result_type="expand")
    lines["break_at"], lines["reason"] = outcome[0], outcome[1]
    lines["material_chain_complete"] = ~lines.break_at.isin(LINKS)
    lines["exposed"] = lines.despatched & ~lines.material_chain_complete
    # EN 1090-2 5.2 asks for full traceability only on EXC3 and EXC4 work; a job with no single class counts.
    lines["traceability_required"] = lines.execution_class != "EXC2"
    lines["s355"] = lines.grade.fillna("").str.startswith("S355")
    # A 3.1 document can be shown for S355 only if certified receipts cover the whole line.
    lines["document_31_shown"] = pd.Series(
        [bool(c and short <= 0.5) if s355 else None for s355, c, short in
         zip(lines.s355, lines.cert_ok, lines.kg_short, strict=True)], index=lines.index, dtype="boolean")

    def exposure(r) -> str | None:
        if not r.despatched:
            return None
        if r.traceability_required and not r.material_chain_complete:
            return EXC3_INCOMPLETE
        if r.s355 and not r.document_31_shown:
            return S355_NO_31
        if not r.material_chain_complete:
            return EXC2_GAP
        return None
    lines["exposure"] = lines.apply(exposure, axis=1)
    lines["compliance_exposure"] = lines.exposure.isin([EXC3_INCOMPLETE, S355_NO_31])
    lines["practice_gap"] = lines.exposure == EXC2_GAP
    lines.insert(0, "line_id", lines.wo_no.astype(str) + "/" + lines.line_no.astype(str))
    for c in ("planned_start", "planned_finish", "actual_finish", "despatch_date"):
        lines[c] = pd.to_datetime(lines[c]).dt.date

    customers = con.execute(CUSTOMER_SQL).df()
    jobs = lines.groupby("job_no").agg(
        execution_class=("execution_class", "first"), bom_lines=("line_id", "size"), kg=("kg", "sum"),
        kg_traced=("kg", lambda s: s[lines.loc[s.index, "material_chain_complete"]].sum()),
        broken_lines=("material_chain_complete", lambda s: int((~s).sum())),
        despatched_lines=("despatched", "sum"), exposed_lines=("compliance_exposure", "sum"),
        exposed_kg=("kg", lambda s: s[lines.loc[s.index, "compliance_exposure"]].sum()),
        gap_lines=("practice_gap", "sum"),
        gap_kg=("kg", lambda s: s[lines.loc[s.index, "practice_gap"]].sum())).reset_index()
    jobs = jobs.merge(customers, on="job_no", how="left")
    jobs["coverage"] = (jobs.kg_traced / jobs.kg).round(4)
    jobs["despatched"] = jobs.despatched_lines > 0
    # Exposed lines and kilograms are EN 1090 compliance exposures; the gap is good practice on EXC2 work.
    jobs["en1090_exposure"] = jobs.exposed_lines > 0
    jobs["practice_gap"] = jobs.gap_lines > 0
    jobs["exposed_kg"] = jobs.exposed_kg.round(1)
    jobs["gap_kg"] = jobs.gap_kg.round(1)
    jobs = jobs.sort_values(["en1090_exposure", "exposed_kg", "job_no"], ascending=[False, False, True])

    exposed_jobs = jobs[jobs.en1090_exposure]
    by_customer = exposed_jobs.groupby("customer_name", dropna=False).agg(
        exposed_jobs=("job_no", "size"), exposed_lines=("exposed_lines", "sum"), exposed_kg=("exposed_kg", "sum"),
        tonnage_despatched=("tonnage_despatched", "sum"), sales_value=("sales_value", "sum"),
        jobs=("job_no", lambda j: ", ".join(sorted(j)))).reset_index()
    by_customer["customer_name"] = by_customer.customer_name.fillna("(no finance customer)")
    by_customer = by_customer.sort_values(["exposed_kg", "customer_name"], ascending=[False, True])

    breaks = (lines.groupby("break_at").agg(lines=("line_id", "size"), kg=("kg", "sum"),
                                            exposed_lines=("exposed", "sum")).reset_index())

    def share(mask) -> float:
        return float(lines.loc[mask & lines.material_chain_complete, "kg"].sum() / lines.loc[mask, "kg"].sum())

    def tonnes(mask) -> float:
        return round(float(lines.loc[mask, "kg"].sum()) / 1000, 3)

    exposure_kg = float(lines.loc[lines.compliance_exposure, "kg"].sum())
    receipts_out = receipts[["grn_no", "po_no", "received_date", "material_code", "grade_status", "grade",
                             "heat_number", "mill_cert_ref", "source_file", "source_row"]].copy()
    receipts_out["s355"] = receipts_out.grade.fillna("").str.startswith("S355")
    receipts_out["document_31"] = receipts_out.mill_cert_ref.notna()
    receipts_out["received_date"] = pd.to_datetime(receipts_out.received_date).dt.date

    t, tj, tr = "recon.trace_lines", "recon.trace_jobs", "recon.trace_receipts"
    chain_share = "round(100 * sum(CASE WHEN material_chain_complete THEN kg END) / sum(kg), 2)"
    heads = [
        Headline("traceability", "coverage", "Material traceability coverage, all work",
                 round(100 * share(lines.kg == lines.kg), 2), "percent", t, "true", chain_share,
                 "Share of BOM kilograms on started works orders traced to a receipt with heat number and certificate"),
        Headline("traceability", "coverage_exc3", "Material traceability coverage on EXC3 work",
                 round(100 * share(lines.traceability_required), 2), "percent", t, "traceability_required",
                 chain_share, "The same share on EXC3 jobs, where EN 1090-2 requires full traceability"),
        Headline("traceability", "coverage_exc2", "Material traceability coverage on EXC2 work",
                 round(100 * share(~lines.traceability_required), 2), "percent", t, "NOT traceability_required",
                 chain_share, "The same share on EXC2 jobs, where full traceability is good practice"),
        Headline("traceability", "exposed_jobs", "Jobs with an EN 1090 compliance exposure",
                 int(jobs.en1090_exposure.sum()), "count", tj, "en1090_exposure", "count(*)",
                 "EXC3 jobs despatched with an incomplete chain, and EXC2 jobs despatched with S355 whose 3.1 "
                 "inspection document cannot be shown"),
        Headline("traceability", "exposed_customers", "Customers with an EN 1090 compliance exposure",
                 int(by_customer.customer_name.nunique()), "count", tj, "en1090_exposure",
                 "count(DISTINCT coalesce(customer_name, '(no finance customer)'))",
                 "Distinct customers of jobs with a compliance exposure"),
        Headline("traceability", "exposed_kg", "Despatched steel with an EN 1090 compliance exposure",
                 round(exposure_kg / 1000, 3), "tonnes", t, "compliance_exposure", "round(sum(kg) / 1000, 3)",
                 "BOM kilograms already on site where EN 1090-2 clause 5.2 is not met"),
        Headline("traceability", "exposed_kg_exc3", "EXC3 steel despatched with an incomplete chain",
                 tonnes(lines.exposure == EXC3_INCOMPLETE), "tonnes", t, f"exposure = '{EXC3_INCOMPLETE}'",
                 "round(sum(kg) / 1000, 3)", "Part of the compliance exposure: full traceability is required"),
        Headline("traceability", "exposed_kg_s355", "EXC2 S355 steel despatched with no 3.1 document shown",
                 tonnes(lines.exposure == S355_NO_31), "tonnes", t, f"exposure = '{S355_NO_31}'",
                 "round(sum(kg) / 1000, 3)",
                 "Part of the compliance exposure: S355 needs a 3.1 inspection document at every class, and no "
                 "certified receipt covers this steel"),
        Headline("traceability", "exposed_sales", "Sales value of jobs with a compliance exposure",
                 round(float(exposed_jobs.sales_value.fillna(0).sum()), 2), "GBP", tj, "en1090_exposure",
                 "round(sum(coalesce(sales_value, 0)), 2)",
                 "Invoiced sales on jobs with an EN 1090 compliance exposure"),
        Headline("traceability", "gap_jobs", "EXC2 jobs despatched with an incomplete chain",
                 int(jobs.practice_gap.sum()), "count", tj, "practice_gap", "count(*)",
                 "A quality and good-practice gap, not an EN 1090 requirement on EXC2 work"),
        Headline("traceability", "gap_kg", "EXC2 steel despatched with an incomplete chain",
                 tonnes(lines.practice_gap), "tonnes", t, "practice_gap", "round(sum(kg) / 1000, 3)",
                 "A quality and good-practice gap, not an EN 1090 requirement on EXC2 work"),
        Headline("traceability", "s355_receipts_no_31", "S355 receipts without a 3.1 inspection document",
                 int((receipts_out.s355 & ~receipts_out.document_31).sum()), "count", tr,
                 "s355 AND NOT document_31", "count(*)",
                 "Receipts of confirmed S355 steel with no mill certificate; required at every execution class"),
    ]
    for link in LINKS + ["despatch: no delivery note"]:
        heads.append(Headline("traceability", "break_" + link.split(": ")[1].replace(" ", "_"), f"Break at {link}",
                              int((lines.break_at == link).sum()), "count", t, f"break_at = '{link}'", "count(*)",
                              f"BOM lines whose chain first fails at: {link}"))
    return EngineResult("traceability", lines, breaks, exposure_kg / 1000,
                        "tonnes despatched with an EN 1090 compliance exposure", heads,
                        {"trace_lines": lines, "trace_allocations": alloc, "trace_jobs": jobs,
                         "trace_customers": by_customer, "trace_breaks": breaks, "trace_receipts": receipts_out})
