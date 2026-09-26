"""docs/reconciliation-report.md: the four reconciliations, each figure with the query behind it.

No run ids or timestamps, so the report changes only when the data or the
settings change.
"""

from __future__ import annotations

import pandas as pd

from fabsync.reconcile.common import EngineResult, Headline, bucket_order

TITLES = {"three_way": "Three-way match", "job_cost": "Job cost reconciliation", "stock": "Stock accuracy",
          "traceability": "Material traceability"}


def fmt(h: Headline) -> str:
    v = h.value
    money = f"-£{-v:,.2f}" if v < 0 else f"£{v:,.2f}"
    return {"GBP": money, "percent": f"{v:.2f}%", "count": f"{int(v):,}", "kg": f"{v:,.1f} kg",
            "tonnes": f"{v:,.3f} t", "hours": f"{v:,.1f} h"}.get(h.unit, str(v))


def md(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).replace("|", "\\|")


def table(frame: pd.DataFrame, cols: list[str], heads: list[str], money: set[str] = frozenset(),
          pct: set[str] = frozenset()) -> list[str]:
    out = ["| " + " | ".join(heads) + " |", "|" + "|".join(" --- " for _ in heads) + "|"]
    for r in frame[cols].itertuples(index=False):
        cells = []
        for c, v in zip(cols, r, strict=True):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cells.append("")
            elif c in money:
                cells.append(f"-£{-v:,.0f}" if v < 0 else f"£{v:,.0f}")
            elif c in pct:
                cells.append(f"{v:.1%}")
            elif isinstance(v, float):
                cells.append(f"{v:,.1f}")
            elif isinstance(v, int | float) and not isinstance(v, bool):
                cells.append(f"{v:,}")
            else:
                cells.append(md(v))
        out.append("| " + " | ".join(cells) + " |")
    return out


def headline_block(res: EngineResult) -> list[str]:
    out = ["| Figure | Value | How it is calculated | Rows behind it |", "| --- | ---: | --- | --- |"]
    for h in res.headlines:
        out.append(f"| {md(h.label)} | **{fmt(h)}** | {md(h.explanation)} | `{md(h.rows_sql)}` |")
    return out


def render_report(results: list[EngineResult], cfg: dict) -> str:
    by = {r.engine: r for r in results}
    tw, jc, st, tr = by["three_way"], by["job_cost"], by["stock"], by["traceability"]
    twc = cfg["three_way"]
    out = [
        "# Reconciliation report",
        "",
        "**All data reconciled here is synthetic.** It represents no real company, supplier, customer or job.",
        "",
        f"Produced by `make reconcile` as at {cfg['as_of_date']}. Every figure below is stored in `recon.headline`",
        "with the SQL that produces it and the SQL that lists its rows. The pipeline recomputes each figure from",
        "those rows before publishing and refuses to publish one that does not reproduce. Every row carries its",
        "source file and line.",
        "",
        "## Exposure",
        "",
        "| Engine | Exposure | Measured as |",
        "| --- | ---: | --- |",
    ]
    for r in results:
        value = f"{r.exposure:,.3f} t" if "tonnes" in r.exposure_label else f"£{r.exposure:,.2f}"
        out.append(f"| {TITLES[r.engine]} | **{value}** | {r.exposure_label} |")

    # ---- three-way ----------------------------------------------------------------
    ageing = tw.tables["three_way_ageing"].pivot_table(index="category", columns="age_bucket", values="lines",
                                                      aggfunc="sum", fill_value=0)
    ageing = ageing.reindex(columns=[b for b in bucket_order(twc["ageing_buckets"]) if b in ageing.columns])
    no_po = tw.rows[tw.rows.category == "invoice with no PO"].groupby("spend_type").agg(
        invoices=("line_id", "size"), value=("value_at_risk", "sum")).reset_index().sort_values("value",
                                                                                                ascending=False)
    out += ["", "## 1. Three-way match", "",
            f"Purchase order to goods received note to purchase invoice. Tolerances: quantity ±"
            f"{twc['qty_tolerance']:.0%}; price ±{twc['price_tolerance_pct']:.0%}. "
            "Rows: `recon.three_way_lines`, one per PO line and per invoice "
            "with no PO, each with its category, value at risk, age and a one-line reason.", "",
            *headline_block(tw), "",
            *table(tw.summary, ["category", "lines", "value_at_risk", "oldest_days"],
                   ["Category", "Lines", "Value at risk", "Oldest (days)"], money={"value_at_risk"}), "",
            "Ageing of unmatched items, by lines:", "",
            *table(ageing.reset_index(), ["category", *ageing.columns], ["Category", *ageing.columns]), "",
            f"Invoices with no PO, by spend type. Overheads on nominal {', '.join(twc['po_exempt_nominals'])} are "
            "exempt:", "",
            *table(no_po, ["spend_type", "invoices", "value"], ["Spend type", "Invoices", "Value"], money={"value"})]

    # ---- job cost -----------------------------------------------------------------
    jobs = jc.rows
    out += ["", "## 2. Job cost reconciliation", "",
            f"Three views per job: Corvus (BOM material at average purchase price per kg, planned hours at "
            f"£{cfg['labour_rate']:.0f}/h), finance (job cost ledger), shop floor (booked hours at "
            f"£{cfg['labour_rate']:.0f}/h). Gap = (finance material - BOM material) + (finance labour - booked "
            "labour). Rows: `recon.job_cost`, one per job; `recon.job_cost_detail` holds every BOM line, cost line "
            "and booking behind it; `recon.job_material` explains the material gap by material.", "",
            *headline_block(jc), "",
            "Most of the material gap is steel charged to the wrong job. Finance posts each steel invoice to a "
            "single job, but one purchase order feeds several jobs. Totals agree while individual job margins "
            "are wrong. The labour gap cannot move between jobs this way, because bookings name the works order, "
            "so a labour gap is a genuine disagreement between payroll allocation and the shop floor.", "",
            "Top 20 jobs by unexplained gap:", "",
            *table(jobs.head(20), ["rank", "job_no", "customer_name", "corvus_material", "finance_material",
                                   "ops_labour", "finance_labour", "unexplained_gap", "gap_pct"],
                   ["#", "Job", "Customer", "BOM material", "Finance material", "Booked labour", "Finance labour",
                    "Gap", "Gap %"],
                   money={"corvus_material", "finance_material", "ops_labour", "finance_labour", "unexplained_gap"},
                   pct={"gap_pct"}), "",
            "Top 10 jobs by labour gap, where finance and the shop floor disagree on hours:", "",
            *table(jobs[jobs.in_corvus].assign(a=lambda d: d.labour_gap.abs()).sort_values(["a", "job_no"],
                                                                                             ascending=[False, True])
                   .head(10), ["job_no", "ops_hours", "ops_labour", "finance_labour", "labour_gap", "labour_gap_pct"],
                   ["Job", "Booked hours", "Booked labour", "Finance labour", "Labour gap", "Gap %"],
                   money={"ops_labour", "finance_labour", "labour_gap"}, pct={"labour_gap_pct"})]

    # ---- stock ---------------------------------------------------------------------
    sc = cfg["stock"]
    offenders = st.rows[st.rows.top_offender].sort_values("offender_rank")
    out += ["", "## 3. Stock accuracy", "",
            f"Book against counted quantity. A line is accurate when the count agrees within "
            f"{sc['line_tolerance']:.0%} of book; target {sc['accuracy_target']:.0%} of lines. Rows: "
            "`recon.stock_lines`.", "",
            *headline_block(st), "",
            *table(st.summary, ["site_code", "section_type", "lines", "accurate_lines", "line_accuracy",
                                "abs_error_kg", "value_error", "value_accuracy", "meets_target"],
                   ["Site", "Section", "Lines", "Accurate", "Accuracy", "Error kg", "Value error", "Value accuracy",
                    "Meets target"], money={"value_error"}, pct={"line_accuracy", "value_accuracy"}), "",
            f"Top offending lines by value ({len(offenders)} of the {int((~st.rows.accurate).sum())} lines that "
            f"disagree; the list stops at {sc['top_offenders']}):", "",
            *table(offenders, ["offender_rank", "material_code", "site_code", "location", "book_qty", "counted_qty",
                               "uom", "value_error"],
                   ["#", "Material", "Site", "Location", "Book", "Counted", "Unit", "Value error"],
                   money={"value_error"})]

    # ---- traceability ----------------------------------------------------------------
    tj = tr.tables["trace_jobs"]
    out += ["", "## 4. Material traceability", "",
            "Chain: mill certificate and heat number, goods receipt, material issue, works order, delivery note.",
            "Corvus records no material issues, so which receipt supplied which works order is reconstructed by "
            "allocating confirmed-grade receipts first-in first-out, in kg, to BOM lines. That the link has to be "
            "inferred at all is a finding. Rows: `recon.trace_lines`, one per BOM line on a started works order; "
            "`recon.trace_allocations`, receipt to BOM line; `recon.trace_jobs` and `recon.trace_customers`.", "",
            *headline_block(tr), "",
            "Where chains break:", "",
            *table(tr.summary, ["break_at", "lines", "kg", "exposed_lines"],
                   ["Break point", "BOM lines", "kg", "Already despatched"]), "",
            "A single receipt without a heat number or certificate taints every works order it supplied. Because "
            "one delivery of steel feeds many jobs, a minority of untraceable receipts reaches almost every job.",
            "", "EN 1090 exposure by customer:", "",
            *table(tr.tables["trace_customers"], ["customer_name", "exposed_jobs", "exposed_lines", "exposed_kg",
                                                  "sales_value"],
                   ["Customer", "Jobs", "BOM lines", "Untraceable kg", "Sales value"], money={"sales_value"}), "",
            "Top 15 exposed jobs:", "",
            *table(tj[tj.en1090_exposure].head(15), ["job_no", "customer_name", "coverage", "exposed_lines",
                                                     "exposed_kg", "tonnage_despatched"],
                   ["Job", "Customer", "Coverage", "Exposed lines", "Untraceable kg", "Tonnes despatched"],
                   pct={"coverage"}), ""]
    return "\n".join(out)
