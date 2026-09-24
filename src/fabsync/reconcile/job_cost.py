"""Job cost reconciliation: three views of every job side by side.

* Corvus MRP view. Corvus records no actual cost, so its view of a job is
  what its works orders say should have been consumed: BOM material valued at
  the average price paid per kg for that material on Corvus purchase orders,
  plus planned hours at the standard labour rate.
* Finance view: job costs posted in the ledger, by cost type.
* Shop-floor view: hours operators booked against the job's works orders,
  valued at the standard labour rate.

Two comparisons have a counterpart on both sides and make up the gap:

* material gap = finance material - Corvus BOM material
* labour gap   = finance labour   - shop-floor hours x standard rate

unexplained gap = material gap + labour gap, shown in pounds and as a percentage
of the operational reference (Corvus material + booked labour). Subcontract
and plant costs have no operational counterpart; they are shown but excluded
from the gap. Planned against booked hours is an efficiency measure, not a
reconciliation gap, and is shown for context.

Finance job codes with no Corvus job appear with their whole finance cost as the
gap, because nothing operational explains any of it.

Every figure is the sum of rows in recon.job_cost_detail: one row per BOM line,
finance cost line and time booking, each with its source file and line.

The material gap is explained in recon.job_material, one row per job and
material: steel issued on the job's BOM against steel on supplier invoices that
finance charged to the job. Finance charges each steel invoice to a single job,
but one purchase order usually feeds several jobs, so material cost moves
between jobs even when the total is right. The allocation share of the gross
material gap is the part that nets to zero across jobs.
"""

from __future__ import annotations

import pandas as pd

from fabsync.reconcile.common import EngineResult, Headline

PRICE_SQL = """
-- Average price paid per kg for each canonical material, from Corvus purchase orders.
SELECT x.canonical_code,
       sum(p.qty * p.unit_price) / sum(CASE p.uom WHEN 'KG' THEN p.qty WHEN 'M' THEN p.qty * g.mass
                                                   WHEN 'EA' THEN p.qty * g.kg_per_ea END) AS price_per_kg
FROM staging.corvus_mrp_purchase_orders p
JOIN core.material_xref x ON x.source_table = 'purchase_orders' AND x.source_code = p.material_code
     AND x.status = 'auto'
JOIN core.material_golden g ON g.canonical_code = x.canonical_code
GROUP BY 1
"""

DETAIL_SQL = """
WITH prices AS ({prices}),
bom AS (
    SELECT w.job_no, 'corvus' AS view, 'material' AS component, x.canonical_code,
           'BOM ' || b.wo_no || '/' || b.line_no AS reference,
           x.canonical_code || ' ' || printf('%g', b.qty) || ' ' || b.uom AS detail,
           CASE b.uom WHEN 'KG' THEN b.qty ELSE b.qty * g.mass END AS kg,
           NULL::DOUBLE AS hours,
           CASE b.uom WHEN 'KG' THEN b.qty ELSE b.qty * g.mass END * pr.price_per_kg AS amount,
           b._source_file AS source_file, b._source_row AS source_row
    FROM staging.corvus_mrp_bom_lines b
    JOIN core.works_orders w ON w.wo_no = b.wo_no
    JOIN core.material_xref x ON x.source_table = 'bom_lines' AND x.source_code = b.material_code
         AND x.source_description IS NOT DISTINCT FROM b.description AND x.source_grade IS NOT DISTINCT FROM b.grade
         AND x.source_section_type IS NOT DISTINCT FROM b.section_type
    JOIN core.material_golden g ON g.canonical_code = x.canonical_code
    LEFT JOIN prices pr ON pr.canonical_code = x.canonical_code
    WHERE w.status <> 'CANCELLED'),
planned AS (
    SELECT job_no, 'corvus', 'labour (planned)', NULL, 'WO ' || wo_no, part_code || ' ' || status, NULL, planned_hours,
           planned_hours * {rate}, _source_file, _source_row
    FROM core.works_orders WHERE status <> 'CANCELLED'),
finance AS (
    SELECT coalesce(c.job_no, 'finance ' || c.job_code), 'finance', c.cost_type, NULL, c.job_code || ' ' || c.period,
           c.cost_type || ' ' || c.period, NULL, NULL, c.amount, c._source_file, c._source_row
    FROM core.job_costs c),
ops AS (
    SELECT t.job_no, 'ops', 'labour', NULL, 'booking ' || t.booking_id,
           t.works_order_raw || ' ' || coalesce(t.operation_code, '?') || ' ' || strftime(t.booking_date, '%d/%m/%Y'),
           NULL, t.hours, t.hours * {rate}, t._source_file, t._source_row
    FROM core.time_bookings t WHERE t.wo_matched)
SELECT * FROM bom UNION ALL SELECT * FROM planned UNION ALL SELECT * FROM finance UNION ALL SELECT * FROM ops
"""


INVOICED_SQL = """
-- Steel invoiced to each job, by material: invoice -> Corvus PO -> material crosswalk.
WITH prices AS ({prices})
SELECT coalesce(i.job_no, 'finance ' || i.job_code) AS job_no,
       coalesce(x.canonical_code, x.source_code || ' (grade unconfirmed)') AS canonical_code,
       CASE p.uom WHEN 'KG' THEN p.qty WHEN 'M' THEN p.qty * g.mass WHEN 'EA' THEN p.qty * g.kg_per_ea END AS kg,
       i.net_amount AS amount, i.invoice_no, i._source_file AS source_file, i._source_row AS source_row
FROM core.purchase_invoices i
JOIN core.purchase_orders p ON p.po_no = i.po_reference
JOIN core.material_xref x ON x.source_table = 'purchase_orders' AND x.source_code = p.material_code
LEFT JOIN core.material_golden g ON g.canonical_code = coalesce(x.canonical_code, x.proposed_code,
                                                                split_part(x.candidates, ', ', 1))
WHERE i.job_code IS NOT NULL
"""


def job_materials(con, detail: pd.DataFrame) -> pd.DataFrame:
    issued = (detail[(detail.view == "corvus") & (detail.component == "material")]
              .groupby(["job_no", "canonical_code"]).agg(issued_kg=("kg", "sum"), issued_value=("amount", "sum")))
    invoiced = (con.execute(INVOICED_SQL.format(prices=PRICE_SQL)).df()
                .groupby(["job_no", "canonical_code"]).agg(invoiced_kg=("kg", "sum"), invoiced_value=("amount", "sum"),
                                                           invoices=("invoice_no", "count")))
    both = issued.join(invoiced, how="outer").fillna(0.0).reset_index()
    both["value_gap"] = (both.invoiced_value - both.issued_value).round(2)
    both["kg_gap"] = (both.invoiced_kg - both.issued_kg).round(1)
    return both.sort_values(["job_no", "value_gap"]).reset_index(drop=True)


def job_cost_reconciliation(con, cfg: dict) -> EngineResult:
    rate = float(cfg["labour_rate"])
    detail = con.execute(DETAIL_SQL.format(prices=PRICE_SQL, rate=rate)).df()
    detail["amount"] = detail.amount.astype(float).round(2)
    unpriced = detail[(detail.view == "corvus") & (detail.component == "material") & detail.amount.isna()]
    if len(unpriced):
        raise AssertionError(f"{len(unpriced)} BOM lines have no purchase price; cannot value the Corvus view")

    pivot = detail.pivot_table(index="job_no", columns=["view", "component"], values="amount", aggfunc="sum",
                               fill_value=0.0)
    pivot.columns = [f"{v}_{c.replace(' ', '_').replace('(', '').replace(')', '')}" for v, c in pivot.columns]
    for col in ["corvus_material", "corvus_labour_planned", "finance_material", "finance_labour",
                "finance_subcontract", "finance_plant", "ops_labour"]:
        if col not in pivot:
            pivot[col] = 0.0
    hours = detail[detail.view == "ops"].groupby("job_no").hours.sum()
    planned = detail[detail.component == "labour (planned)"].groupby("job_no").hours.sum()
    jobs = pivot.reset_index()
    jobs["ops_hours"] = jobs.job_no.map(hours).fillna(0.0).astype(float)
    jobs["planned_hours"] = jobs.job_no.map(planned).fillna(0.0).astype(float)

    meta = con.execute("""
        SELECT j.job_no, j.finance_job_code, j.site_code, s.customer_name
        FROM core.jobs j LEFT JOIN (SELECT job_code, mode(customer_name) AS customer_name
                                    FROM staging.finance_sales_invoices GROUP BY 1) s ON s.job_code = j.finance_job_code
        UNION ALL
        SELECT 'finance ' || f.finance_job_code, f.finance_job_code, NULL, s.customer_name
        FROM core.finance_jobs f LEFT JOIN (SELECT job_code, mode(customer_name) AS customer_name
                                            FROM staging.finance_sales_invoices GROUP BY 1) s
             ON s.job_code = f.finance_job_code
        WHERE NOT f.mrp_matched""").df()
    jobs = jobs.merge(meta, on="job_no", how="left")
    jobs["in_corvus"] = ~jobs.job_no.str.startswith("finance ")

    jobs["material_gap"] = (jobs.finance_material - jobs.corvus_material).round(2)
    jobs["labour_gap"] = (jobs.finance_labour - jobs.ops_labour).round(2)
    jobs["unexplained_gap"] = (jobs.material_gap + jobs.labour_gap).round(2)
    jobs["reference_cost"] = (jobs.corvus_material + jobs.ops_labour).round(2)
    jobs["gap_pct"] = (jobs.unexplained_gap / jobs.reference_cost.where(jobs.reference_cost != 0)).round(4)
    jobs["labour_gap_pct"] = (jobs.labour_gap / jobs.ops_labour.where(jobs.ops_labour != 0)).round(4)
    jobs["hours_vs_plan_pct"] = ((jobs.ops_hours - jobs.planned_hours) /
                                 jobs.planned_hours.where(jobs.planned_hours != 0)).round(4)

    materials = job_materials(con, detail)
    over = materials[materials.value_gap > 0].sort_values("value_gap", ascending=False).groupby("job_no").head(1)
    under = materials[materials.value_gap < 0].sort_values("value_gap").groupby("job_no").head(1)
    over, under = over.set_index("job_no"), under.set_index("job_no")

    def explain(r) -> str:
        if not r.in_corvus:
            return "finance job code with no Corvus job: none of this cost has an operational record"
        parts = []
        if abs(r.material_gap) >= 1:
            text = f"finance material £{r.finance_material:,.0f} vs BOM material £{r.corvus_material:,.0f}"
            if r.job_no in over.index:
                o = over.loc[r.job_no]
                text += f"; charged £{o.value_gap:,.0f} more {o.canonical_code} than issued"
            if r.job_no in under.index:
                u = under.loc[r.job_no]
                text += f"; issued £{-u.value_gap:,.0f} of {u.canonical_code} charged elsewhere"
            parts.append(text)
        if abs(r.labour_gap) >= 1:
            parts.append(f"finance labour £{r.finance_labour:,.0f} vs {r.ops_hours:,.1f} booked hours "
                         f"(£{r.ops_labour:,.0f})")
        return "; ".join(parts) or "reconciles"
    jobs["explanation"] = jobs.apply(explain, axis=1)
    jobs["abs_gap"] = jobs.unexplained_gap.abs()
    jobs = jobs.sort_values(["abs_gap", "job_no"], ascending=[False, True]).reset_index(drop=True)
    jobs.insert(0, "rank", range(1, len(jobs) + 1))

    detail["job_in_corvus"] = ~detail.job_no.str.startswith("finance ")
    unallocated = con.execute("""SELECT count(*), coalesce(sum(hours), 0) FROM core.time_bookings
                                 WHERE NOT wo_matched""").fetchone()

    totals = {
        "corvus_material": jobs.corvus_material.sum(), "finance_material": jobs.finance_material.sum(),
        "finance_labour": jobs.finance_labour.sum(), "ops_labour": jobs.ops_labour.sum(),
        "finance_subcontract": jobs.finance_subcontract.sum(), "finance_plant": jobs.finance_plant.sum()}
    gross = float(jobs.abs_gap.sum())
    corvus_jobs = jobs[jobs.in_corvus]
    material_gross = float(corvus_jobs.material_gap.abs().sum())
    material_net = float(corvus_jobs.material_gap.sum())
    allocation = material_gross - abs(material_net)
    summary = pd.DataFrame([
        {"measure": "jobs reconciled", "value": len(jobs)},
        {"measure": "jobs with a gap over 10%", "value": int((jobs.gap_pct.abs() > 0.10).sum())},
        {"measure": "gross unexplained gap (sum of absolute job gaps), GBP", "value": round(gross, 2)},
        {"measure": "net unexplained gap, GBP", "value": round(float(jobs.unexplained_gap.sum()), 2)},
        *({"measure": f"total {k.replace('_', ' ')}, GBP", "value": round(float(v), 2)} for k, v in totals.items()),
        {"measure": "hours booked to works orders not in Corvus", "value": round(float(unallocated[1]), 2)},
        {"measure": "gross material gap on Corvus jobs, GBP", "value": round(material_gross, 2)},
        {"measure": "of which nets to zero across jobs (charged to the wrong job), GBP", "value": round(allocation, 2)},
    ])

    t, d = "recon.job_cost", "recon.job_cost_detail"
    top = jobs.iloc[0]
    heads = [
        Headline("job_cost", "gross_gap", "Unexplained job cost gap (gross)", round(gross, 2), "GBP", t, "true",
                 "round(sum(abs(unexplained_gap)), 2)",
                 "Sum over jobs of |(finance material - BOM material) + (finance labour - booked hours x rate)|"),
        Headline("job_cost", "net_gap", "Unexplained job cost gap (net)", round(float(jobs.unexplained_gap.sum()), 2),
                 "GBP", t, "true", "round(sum(unexplained_gap), 2)", "Signed sum of job gaps"),
        Headline("job_cost", "labour_gap_gross", "Labour gap, finance vs shop floor (gross)",
                 round(float(jobs.labour_gap.abs().sum()), 2), "GBP", t, "true", "round(sum(abs(labour_gap)), 2)",
                 "Sum over jobs of |finance labour - booked hours x standard rate|"),
        Headline("job_cost", "material_gap_gross", "Material gap on Corvus jobs (gross)", round(material_gross, 2),
                 "GBP", t, "in_corvus", "round(sum(abs(material_gap)), 2)",
                 "Sum over Corvus jobs of |finance material - BOM material|"),
        Headline("job_cost", "material_misallocated", "Material cost charged to the wrong job", round(allocation, 2),
                 "GBP", t, "in_corvus", "round(sum(abs(material_gap)) - abs(sum(material_gap)), 2)",
                 "Gross material gap less the net: the part that cancels out across jobs because steel "
                 "invoiced to one job was issued to another. Detail by material in recon.job_material"),
        Headline("job_cost", "jobs_over_10pct", "Jobs with a gap over 10%", int((jobs.gap_pct.abs() > 0.10).sum()),
                 "count", t, "abs(gap_pct) > 0.10", "count(*)", "Jobs whose gap exceeds 10% of reference cost"),
        Headline("job_cost", "finance_only_cost", "Finance cost on jobs Corvus does not hold",
                 round(float(jobs.loc[~jobs.in_corvus, ["finance_material", "finance_labour", "finance_subcontract",
                                                        "finance_plant"]].sum().sum()), 2),
                 "GBP", d, "NOT job_in_corvus", "round(sum(amount), 2)", "All finance cost lines on unmapped codes"),
        Headline("job_cost", "top_job_gap", f"Largest gap: {top.job_no}", float(top.unexplained_gap), "GBP", t,
                 f"job_no = '{top.job_no}'", "round(sum(unexplained_gap), 2)", str(top.explanation)),
        Headline("job_cost", "unallocated_hours", "Hours booked to works orders not in Corvus",
                 round(float(unallocated[1]), 2), "hours", "core.time_bookings", "NOT wo_matched",
                 "round(sum(hours), 2)", "Bookings on orphan works orders: cost that reaches no job"),
    ]
    for col in ("corvus_material", "finance_material", "finance_labour", "ops_labour"):
        view, comp = col.split("_", 1)
        heads.append(Headline("job_cost", f"total_{col}", f"Total {view} {comp}", round(float(totals[col]), 2), "GBP",
                              d, f"view = '{view}' AND component = '{comp}'", "round(sum(amount), 2)",
                              f"Sum of {view} {comp} detail rows"))
    return EngineResult("job_cost", jobs, summary, gross, "gross unexplained job cost gap (GBP)", heads,
                        {"job_cost": jobs.drop(columns="abs_gap"), "job_cost_detail": detail,
                         "job_material": materials, "job_cost_summary": summary})
