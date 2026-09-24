"""Master data: matching results, golden records, the review queue, the crosswalks, and what is still unmatched."""

import streamlit as st

from fabsync import ui

ui.title("Master data", "Materials, suppliers, jobs and works orders matched across the three systems. Nothing is "
         "merged destructively: every crosswalk keeps the value as written beside the canonical value, with how "
         "and why it was matched.")
ui.require("governance", "match_quality", "make match")

quality = ui.q("SELECT * FROM governance.match_quality ORDER BY domain").set_index("domain")
XREF = {"material": "core.material_xref", "supplier": "core.supplier_xref", "job": "core.job_xref",
        "works_order": "core.works_order_xref"}
POP = {"supplier": "source_system = 'corvus_mrp' AND "}
LABEL = {"material": "Materials", "supplier": "Suppliers", "job": "Jobs", "works_order": "Works orders"}

cols = st.columns(4)
for col, domain in zip(cols, ["material", "supplier", "job", "works_order"], strict=True):
    r = quality.loc[domain]
    with col:
        st.markdown(f"**{LABEL[domain]}**")
        st.caption(r.population)
        ui.figure_row("Matched automatically", f"{r.auto_pct:.1f}%",
                      f"SELECT * FROM {XREF[domain]} WHERE {POP.get(domain, '')}status = 'auto'", f"md_auto_{domain}")
        ui.figure_row("Waiting for review", f"{int(r.review_queue):,}",
                      f"SELECT * FROM core.v_match_review_queue WHERE domain = '{domain}'", f"md_rev_{domain}")
        ui.figure_row("Unmatched", f"{int(r.unmatched):,}",
                      f"SELECT * FROM {XREF[domain]} WHERE {POP.get(domain, '')}status = 'unmatched'",
                      f"md_un_{domain}")
        ui.figure_row("Hours to clear", f"{r.est_minutes / 60:.1f}",
                      f"SELECT * FROM core.v_match_review_queue WHERE domain = '{domain}'", f"md_h_{domain}")

st.caption("Scores of 95 or more are accepted automatically, 80 to 95 go to a person, and anything below 80 is never "
           "merged. Thresholds and the minutes per review are set in config/matching.toml.")

tab_queue, tab_golden, tab_xref, tab_unmatched = st.tabs(["Review queue", "Golden records", "Crosswalks", "Unmatched"])

with tab_queue:
    st.markdown("Decisions a person must make. Each item carries the evidence for it, such as invoices that "
                "corroborate a supplier match, and a suggested action.")
    queue = ui.q("SELECT * FROM core.v_match_review_queue ORDER BY domain, score DESC, item_id")
    domain = st.selectbox("Domain", ["All"] + sorted(queue.domain.unique()), key="queue_domain")
    ui.table(queue if domain == "All" else queue[queue.domain == domain], height=420)

with tab_golden:
    which = st.radio("Golden record", ["Materials", "Suppliers"], horizontal=True)
    if which == "Materials":
        st.markdown("One row per canonical material, built by the survivorship rule shown in each row. Units seen "
                    "lists every unit the material is transacted in; more than one is a unit-of-measure conflict.")
        golden = ui.q("SELECT canonical_code, description, section_type, grade, mass, mass_basis, mass_source, "
                      "observed_uoms, uom_conflict, source_codes, source_rows, pending_review_rows, survivorship_rule "
                      "FROM core.material_golden ORDER BY canonical_code")
        if st.checkbox("Only materials written more than one way", value=True):
            golden = golden[golden.source_codes.str.contains(",")]
    else:
        st.markdown("One row per supplier entity: every Corvus code and finance account found to be the same "
                    "supplier. The canonical name is the finance account with most invoices.")
        golden = ui.q("SELECT * FROM core.supplier_golden ORDER BY supplier_id")
        if st.checkbox("Only suppliers held under more than one record", value=True):
            golden = golden[golden.duplicate_records > 0]
    ui.table(golden, height=420)

with tab_xref:
    domain = st.selectbox("Crosswalk", list(XREF), format_func=LABEL.get, key="xref_domain")
    xref = ui.q(f"SELECT * FROM {XREF[domain]}")
    f1, f2 = st.columns([1, 2])
    statuses = f1.multiselect("Status", ["auto", "review", "unmatched"], default=["auto", "review", "unmatched"])
    text = f2.text_input("Find a source value", "")
    shown = xref[xref.status.isin(statuses)]
    value_col = "source_code" if "source_code" in shown.columns else "source_value"
    if text:
        shown = shown[shown[value_col].astype(str).str.contains(text, case=False, regex=False)]
    st.caption(f"{len(shown):,} of {len(xref):,} crosswalk rows")
    ui.table(shown, height=420)

with tab_unmatched:
    st.markdown("**Jobs, on all three sides**")
    ui.table(ui.q("SELECT side, value, reason FROM core.job_unmatched ORDER BY side, value"))
    st.markdown("**Corvus supplier codes with no finance account at or above the review floor**")
    ui.table(ui.q("SELECT source_code, source_name, best_counterpart, score, matched_on FROM core.supplier_xref "
                  "WHERE source_system = 'corvus_mrp' AND status <> 'auto' ORDER BY score DESC"))
    st.markdown("**Works order numbers Corvus does not hold**")
    ui.table(ui.q("SELECT parsed_number, string_agg(source_value, ', ') AS written_as, sum(row_count) AS rows, "
                  "any_value(matched_on) AS matched_on FROM core.works_order_xref WHERE wo_no IS NULL "
                  "GROUP BY 1 ORDER BY 1"))
