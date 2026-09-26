"""Overview: the business problem, the three disconnected systems, and the headline findings."""

import streamlit as st

from fabsync import ui
from fabsync.provenance import word

counted = ui.has_table("governance", "table_balance") and ui.has_table("core", "works_orders")
systems = ui.scalar("SELECT count(DISTINCT split_part(source_file, '/', 1)) FROM governance.table_balance") \
    if counted else None
sites = ui.scalar("SELECT count(DISTINCT site_code) FROM core.works_orders") if counted else None
# The finance system's code for the example job, looked up rather than typed.
job_code = ui.scalar("SELECT CAST(finance_job_code AS INTEGER) FROM core.job_crosswalk WHERE job_no = 'J-24-0871'") \
    if ui.has_table("core", "job_crosswalk") else None
ui.title(f"{word(systems).capitalize() if systems else 'Separate'} systems, no single version of the truth")

st.markdown(f"""
A structural steelwork and architectural metalwork fabricator, working across {word(sites) if sites else 'its'}
sites on telecoms towers and masts, rail structures and stadium steelwork, runs its business on
{word(systems) if systems else 'separate'} systems that do not talk to each other.

- **Corvus MRP**, installed in 2006, holds works orders, bills of material, stock and purchasing.
- **The finance system** holds the ledgers, invoices and job costs.
- **Shop-floor spreadsheets** hold time bookings, delivery notes, NCRs and capacity, kept by each site's
  supervisors.

Each has drifted from the others, and nothing checks that the copies agree. Management cannot get one
trustworthy answer to simple questions: what is this job making, what do we owe, can we trace this steel?
""")
if ui.has_table("core", "material_xref"):
    codes = ui.scalar("SELECT max(n) FROM (SELECT count(DISTINCT trim(source_code)) AS n FROM core.material_xref "
                      "WHERE canonical_code IS NOT NULL GROUP BY canonical_code)")
    names = ui.scalar("SELECT max(n) FROM (SELECT count(DISTINCT source_name) AS n FROM core.supplier_xref "
                      "GROUP BY supplier_id)")
    orphans = ui.scalar("SELECT count(DISTINCT wo_no) FROM core.time_bookings WHERE NOT wo_matched")
    st.markdown(f"The same steel is coded up to {codes:.0f} different ways and one supplier sits under up to "
                f"{names:.0f} names. Job J-24-0871 in Corvus is {job_code:.0f} in finance, and hours "
                f"are booked to {orphans:.0f} works orders that Corvus has never issued.")


def box(x, y, system, lines):
    colour = ui.SYSTEM_COLOURS[system]
    body = "".join(f'<text x="{x + 16}" y="{y + 62 + 20 * i}" font-size="13" fill="{ui.INK}">{t}</text>'
                   for i, t in enumerate(lines))
    return (f'<rect x="{x}" y="{y}" width="250" height="150" fill="#FFFFFF" stroke="{colour}" stroke-width="2"/>'
            f'<rect x="{x}" y="{y}" width="250" height="34" fill="{colour}"/>'
            f'<text x="{x + 16}" y="{y + 23}" font-size="15" font-weight="600" fill="#FFFFFF">'
            f"{ui.SYSTEM_LABELS[system]}</text>{body}")


def gap(x1, y1, x2, y2, lx, ly, text):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ui.MUTED}" stroke-width="2" '
            f'stroke-dasharray="6 6"/>'
            f'<text x="{lx}" y="{ly}" font-size="12" fill="{ui.INK}" text-anchor="middle">{text}</text>')


svg = f"""
<svg viewBox="0 0 900 430" width="100%" style="max-width:900px" role="img"
     aria-label="Three disconnected systems: Corvus MRP, finance system and shop-floor spreadsheets">
  <style>text {{ font-family: sans-serif; }}</style>
  {box(20, 20, "corvus_mrp", ["Works orders, BOMs, stock", "Purchase orders, goods received", "UPPERCASE, DD/MM/YYYY",
                             "No supplier master"])}
  {box(630, 20, "finance", ["Ledgers, invoices, job costs", "Supplier accounts", "Title Case, YYYY-MM-DD",
                           f"Job codes like {job_code:.0f}" if job_code else "Its own job numbering"])}
  {box(325, 265, "shop_floor", ["Bookings, delivery notes, NCRs", "Weekly capacity, per site",
                               "Free text, mixed date formats", "Works orders typed by hand"])}
  {gap(270, 95, 630, 95, 450, 80, f"Job J-24-0871 is {job_code:.0f}" if job_code else "Its own job numbers")}
  {gap(270, 95, 630, 95, 450, 118, "One supplier, several accounts")}
  {gap(145, 170, 360, 265, 190, 238, "Hours on works orders")}
  {gap(145, 170, 360, 265, 190, 254, "Corvus has never heard of")}
  {gap(755, 170, 540, 265, 720, 238, "Labour cost does not match")}
  {gap(755, 170, 540, 265, 720, 254, "the hours booked")}
  <text x="450" y="200" font-size="14" font-weight="600" fill="{ui.ACCENT}"
        text-anchor="middle">No link between them</text>
</svg>
"""
st.html(svg)

st.subheader("What it finds")
ui.require("recon", "headline", "make run-all")
heads = ui.q("SELECT * FROM recon.headline").set_index(["engine", "key"])


def recon(engine, key):
    return heads.loc[(engine, key)]


dq = ui.q("SELECT dq_index, rules_met, rules_run, critical_breaches FROM governance.dq_run "
          "ORDER BY finished_at DESC LIMIT 1").iloc[0]
tw, jc = recon("three_way", "value_at_risk"), recon("job_cost", "gross_gap")
tx, tj = recon("traceability", "exposed_kg"), recon("traceability", "exposed_jobs")

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.headline("Purchase-to-pay value at risk", ui.gbp(tw.value), tw.rows_sql, "ov_var",
                note="Orders, receipts and invoices that do not match, or spend with no order",
                explanation=tw.explanation)
with c2:
    ui.headline("Data quality index", f"{dq.dq_index:.1f} / 100",
                "SELECT rule_id, rule_name, severity, owner, records_checked, records_failed, pass_rate, threshold, "
                "threshold_met FROM governance.v_dq_latest ORDER BY score, rule_id", "ov_dqi",
                note=f"{dq.rules_met} of {dq.rules_run} rules met; {dq.critical_breaches} critical rules breached")
with c3:
    ui.headline("Steel despatched without full traceability", f"{tx.value:,.0f} tonnes", tx.rows_sql, "ov_trace",
                note=f"{tj.value:.0f} jobs already on site carry an EN 1090 exposure", explanation=tx.explanation)
with c4:
    ui.headline("Job cost that does not reconcile", ui.gbp(jc.value), jc.rows_sql, "ov_jobgap",
                note="Finance against Corvus and the shop floor, summed over jobs", explanation=jc.explanation)

raw_rows = ui.scalar("SELECT sum(raw_rows) FROM governance.table_balance")
quarantined = ui.scalar("SELECT count(*) FROM governance.quarantine")
review = ui.scalar("SELECT count(*) FROM core.v_match_review_queue")
review_h = ui.scalar("SELECT sum(est_minutes) / 60 FROM core.v_match_review_queue")
off = ui.scalar("SELECT count(*) FROM marts.kpi_scorecard WHERE status = 'off target'") if ui.has_table(
    "marts", "kpi_scorecard") else None
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.headline("Source rows received", f"{raw_rows:,.0f}",
                "SELECT source_file, data_lines, raw_rows, staged_rows, quarantined_rows, core_rows, balanced "
                "FROM governance.table_balance ORDER BY source_file", "ov_rows",
                note="Every one accounted for: staged or quarantined")
with c2:
    ui.headline("Rows quarantined, originals kept", f"{quarantined:,.0f}",
                "SELECT quarantine_id, source_file, source_row, rule_id, failing_column, failing_value, "
                "original_record FROM governance.quarantine ORDER BY quarantine_id", "ov_quar")
with c3:
    ui.headline("Master data decisions waiting for a person", f"{review:,.0f}",
                "SELECT * FROM core.v_match_review_queue ORDER BY domain, score DESC", "ov_review",
                note=f"About {review_h:.0f} hours of work")
with c4:
    if off is not None:
        kpis = ui.scalar("SELECT count(*) FROM marts.kpi_scorecard")
        ui.headline("KPIs off target", f"{off:.0f} of {kpis:.0f}",
                    "SELECT kpi_id, name, value, unit, target, status, owner FROM marts.kpi_scorecard "
                    "ORDER BY kpi_id", "ov_kpi")

st.subheader("How to read this demonstrator")
st.markdown("Each page takes one step of the story. Every headline number can be clicked to see the rows behind "
            "it, and any row can be traced to the line in the file it came from.")
steps = [
    ("views/source_systems.py", "Source systems", "What breaks: each extract as received, with its defects marked."),
    ("views/data_quality.py", "Data quality", "How bad it is, rule by rule, and who owns each problem."),
    ("views/master_data.py", "Master data", "How it is reconciled without destroying the originals."),
    ("views/reconciliation.py", "Reconciliation",
     "What the mismatches cost: purchasing, job cost, stock, traceability."),
    ("views/performance.py", "Performance", "What management can finally see, with the caveats."),
    ("views/governance.py", "Governance", "The rules, owners and definitions that stop it recurring."),
    ("views/roadmap.py", "Roadmap", "How to get there: phases, risks and training."),
]
for page, label, text in steps:
    left, right = st.columns([1, 4])
    left.page_link(page, label=label)
    right.markdown(text)
