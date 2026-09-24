"""Governance: the data dictionary, the ownership matrix, the rule set, and lineage and quarantine."""

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from fabsync import ui

ui.title("Governance", "What stops the drift coming back: named owners, declared rules, defined measures, and a "
         "record of where every row went.")
ui.require("governance", "dq_rule", "make quality")

tab_dict, tab_owners, tab_rules, tab_lineage = st.tabs(
    ["Data dictionary", "Ownership matrix", "Rule set", "Lineage and quarantine"])

with tab_dict:
    if ui.has_table("marts", "kpi_definition"):
        st.markdown("Every KPI with its definition, formula, sources, owner, refresh and caveat. The same table is in "
                    "docs/data-dictionary.md for the pack.")
        ui.table(ui.q("SELECT kpi_id, name, definition, formula, sources, owner, refresh, target, caveat "
                      "FROM marts.kpi_definition ORDER BY kpi_id"), height=420)
        st.markdown("**Views in the marts schema**")
        ui.table(ui.q("SELECT schema_name || '.' || view_name AS view, comment AS description FROM duckdb_views() "
                      "WHERE schema_name = 'marts' ORDER BY view_name"))
    else:
        st.info("Run `make kpi` to build the KPI definitions.")

with tab_owners:
    st.markdown("Who owns what. Each role owns rules, exceptions, KPIs and a data domain; the counts are live.")
    matrix = ui.q("""
        WITH r AS (SELECT owner, count(*) AS rules, count(*) FILTER (WHERE severity = 'critical') AS critical_rules
                   FROM governance.dq_rule GROUP BY 1),
             b AS (SELECT owner, count(*) FILTER (WHERE NOT threshold_met) AS rules_breaching
                   FROM governance.v_dq_latest GROUP BY 1),
             e AS (SELECT owner, count(*) AS open_exceptions FROM governance.dq_exceptions GROUP BY 1)
        SELECT r.owner, r.rules, r.critical_rules, coalesce(b.rules_breaching, 0) AS rules_breaching,
               coalesce(e.open_exceptions, 0) AS open_exceptions
        FROM r LEFT JOIN b USING (owner) LEFT JOIN e USING (owner) ORDER BY r.owner""")
    if ui.has_table("marts", "kpi_scorecard"):
        kpis = ui.q("SELECT owner, count(*) AS kpis_owned, count(*) FILTER (WHERE status = 'off target') "
                    "AS kpis_off_target FROM marts.kpi_scorecard GROUP BY 1")
        matrix = matrix.merge(kpis, on="owner", how="left").fillna({"kpis_owned": 0, "kpis_off_target": 0})
    ui.table(matrix)
    st.markdown("**Rules by owner and system of record**")
    grid = ui.q("SELECT owner, system_of_record, count(*) AS n FROM governance.dq_rule GROUP BY ALL")
    grid["system_of_record"] = grid.system_of_record.map(ui.SYSTEM_LABELS)
    ui.table(grid.pivot_table(index="owner", columns="system_of_record", values="n", aggfunc="sum", fill_value=0)
             .reset_index())
    st.markdown("**Data domains**")
    roadmap = yaml.safe_load(Path("config/roadmap.yaml").read_text(encoding="utf-8"))
    ui.table(pd.DataFrame(roadmap["ownership"]))

with tab_rules:
    st.markdown("The data quality rule set, as declared in config/dq_rules.yaml, with the latest result.")
    ui.table(ui.q("""SELECT r.id AS rule_id, r.name, r.description, r.dimension, r.severity, r.owner,
                            r.system_of_record, round(100 * r.threshold, 1) AS threshold_pct,
                            round(100 * l.pass_rate, 2) AS pass_pct, l.threshold_met, r.consequence,
                            r.corrective_action, r.check_type, r.check AS check_definition
                     FROM governance.dq_rule r LEFT JOIN governance.v_dq_latest l ON l.rule_id = r.id
                     ORDER BY r.id"""), height=460)

with tab_lineage:
    st.markdown("Every row received is either staged or quarantined with its original values. Nothing is dropped "
                "silently and nothing is edited in place.")
    balance = ui.q("SELECT source_file, data_lines, raw_rows, staged_rows, quarantined_rows, core_rows, balanced "
                   "FROM governance.table_balance ORDER BY source_file")
    ui.table(balance)
    target = st.selectbox("Rule chain for", ui.q("SELECT DISTINCT target_table FROM governance.lineage "
                                                 "ORDER BY 1").target_table.tolist(),
                          index=None, placeholder="Choose a table")
    if target:
        ui.table(ui.q("SELECT step_id, rule_id, rule_description, rows_in, rows_out, rows_rejected, rows_affected, "
                      "detail FROM governance.lineage WHERE target_table = ? ORDER BY step_id", (target,)))
    st.markdown("**Quarantine**")
    ui.table(ui.q("SELECT * FROM governance.v_quarantine_summary"))
    quarantine = ui.q("SELECT quarantine_id, source_file, source_row, rule_id, failing_column, failing_value, "
                      "original_record, status FROM governance.quarantine ORDER BY quarantine_id")
    ui.table(quarantine, height=300)
    ui.trace_rows(quarantine, key="gov_trace")
