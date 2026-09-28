"""Reconciliation: the four engines, each leading with its exposure and drilling to source rows."""

import tomllib
from pathlib import Path

import streamlit as st

from fabsync import ui

TOLERANCES = tomllib.loads(Path("config/reconcile.toml").read_text(encoding="utf-8"))

ui.title("Reconciliation", "Four reconciliations, each leading with what is at stake. Every figure is recomputed "
         "from the rows behind it before it is published, and every row traces to its source line.")
ui.require("recon", "headline", "make reconcile")

heads = ui.q("SELECT * FROM recon.headline ORDER BY ordinal")
LEAD = {"three_way": ("value_at_risk", "Purchase-to-pay value at risk"),
        "job_cost": ("gross_gap", "Job cost that does not reconcile"),
        "stock": ("value_error", "Stock value miscounted"),
        "traceability": ("exposed_kg", "Steel on site with an EN 1090 compliance exposure")}
TITLE = {"three_way": "Three-way match", "job_cost": "Job cost", "stock": "Stock accuracy",
         "traceability": "Material traceability"}


def figures(engine: str) -> None:
    st.markdown("**Every figure from this engine**")
    for h in heads[heads.engine == engine].itertuples():
        ui.figure_row(h.label, ui.fmt(h.value, h.unit), h.rows_sql, f"rc_{engine}_{h.key}", h.explanation)


def lead(engine: str, note: str) -> None:
    key, label = LEAD[engine]
    h = heads[(heads.engine == engine) & (heads.key == key)].iloc[0]
    ui.headline(label, ui.fmt(h.value, h.unit), h.rows_sql, f"rc_lead_{engine}", note=note, explanation=h.explanation)


tabs = st.tabs([TITLE[e] for e in LEAD])

with tabs[0]:
    tw = TOLERANCES["three_way"]
    lead("three_way", f"Order to receipt to invoice, tolerances: quantity {tw['qty_tolerance']:.0%}, "
                      f"price {tw['price_tolerance_pct']:.0%}")
    cats = ui.q("""SELECT category, count(*) AS lines, sum(value_at_risk) AS value_at_risk FROM recon.three_way_lines
                   WHERE is_exception GROUP BY 1""")
    cats["label"] = [f"{ui.gbp(v)}  ({n:,} lines)" for v, n in zip(cats.value_at_risk, cats.lines, strict=True)]
    ui.bar_h(cats, "category", "value_at_risk", "Value at risk (£)", label="label")
    st.markdown("**Ageing of unmatched items, lines**")
    ageing = ui.q("SELECT * FROM recon.three_way_ageing")
    ui.table(ageing.pivot_table(index="category", columns="age_bucket", values="lines", aggfunc="sum", fill_value=0)
             .reindex(columns=["0-30 days", "31-60 days", "61-90 days", "91-180 days", "over 180 days"], fill_value=0)
             .reset_index())
    figures("three_way")

with tabs[1]:
    lead("job_cost", "Finance cost against Corvus BOM material and shop-floor hours, summed over jobs")
    st.markdown("Most of the material gap is steel charged to the wrong job: finance posts each steel invoice to one "
                "job, but one order feeds several. Totals agree; individual job margins do not.")
    top = ui.q("SELECT job_no, customer_name, unexplained_gap, explanation FROM recon.job_cost "
               "ORDER BY rank LIMIT 15")
    top["label"] = top.unexplained_gap.map(ui.gbp)
    ui.bar_h(top, "job_no", "unexplained_gap", "Unexplained gap (£, finance above operational is positive)",
             label="label", sort=None)
    figures("job_cost")

with tabs[2]:
    lead("stock", "Counted against book quantity, valued at unit cost")
    acc = ui.q("SELECT site_code || ' · ' || section_type AS grp, 100 * line_accuracy AS accuracy, lines "
               "FROM recon.stock_summary ORDER BY line_accuracy, grp")
    acc["label"] = [f"{a:.0f}%  ({n} lines)" for a, n in zip(acc.accuracy, acc.lines, strict=True)]
    ui.bar_h(acc, "grp", "accuracy", "Line accuracy (%); dashed line is the 95% target", label="label", sort=None,
             target=95)
    st.markdown("**Top offending lines by value**")
    ui.table(ui.q("SELECT offender_rank, material_code, site_code, location, book_qty, counted_qty, uom, "
                  "value_error, source_file, source_row FROM recon.stock_lines WHERE top_offender "
                  "ORDER BY offender_rank"))
    figures("stock")

with tabs[3]:
    lead("traceability", "EXC3 steel whose chain back to the mill certificate is incomplete, and S355 on EXC2 work "
                         "with no 3.1 certificate")
    st.markdown("What EN 1090-2 requires depends on each job's execution class, recorded on its works orders. On "
                "EXC3 work every piece must be traceable from receipt to hand over; on EXC2 work full traceability is "
                "good practice rather than a requirement, but S355 still needs a 3.1 inspection document. Corvus "
                "records no material issues, so which delivery supplied which works order is reconstructed "
                "first-in first-out. One untraceable delivery taints every job it fed.")
    meaning = ui.q("SELECT exposure, count(*) AS lines, sum(kg) / 1000 AS tonnes FROM recon.trace_lines "
                   "WHERE exposure IS NOT NULL GROUP BY 1")
    meaning["label"] = [f"{t:,.0f} t  ({n:,} BOM lines)" for t, n in zip(meaning.tonnes, meaning.lines, strict=True)]
    ui.bar_h(meaning, "exposure", "tonnes", "Despatched steel by what its gap means (tonnes)", label="label")
    breaks = ui.q("SELECT break_at, lines, kg / 1000 AS tonnes FROM recon.trace_breaks WHERE break_at <> 'complete'")
    breaks["label"] = [f"{t:,.0f} t  ({n:,} BOM lines)" for t, n in zip(breaks.tonnes, breaks.lines, strict=True)]
    ui.bar_h(breaks, "break_at", "tonnes", "Steel where the chain first breaks (tonnes)", label="label")
    cust = ui.q("SELECT customer_name, exposed_kg / 1000 AS tonnes, exposed_jobs FROM recon.trace_customers "
                "ORDER BY exposed_kg DESC LIMIT 12")
    cust["label"] = [f"{t:,.0f} t  ({j} jobs)" for t, j in zip(cust.tonnes, cust.exposed_jobs, strict=True)]
    st.markdown("**EN 1090 compliance exposure by customer, top 12**")
    ui.bar_h(cust, "customer_name", "tonnes", "Steel with a compliance exposure (tonnes)", label="label")
    figures("traceability")
