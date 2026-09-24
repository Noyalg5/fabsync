"""Data quality: the scorecard by owning role, source system and dimension, and the exception queue."""

import streamlit as st

from fabsync import ui

ui.title("Data quality", "Every rule is declared in business language with an owner, a threshold and a "
         "consequence. The index weights each rule by severity.")
ui.require("governance", "dq_run", "make quality")

run = ui.q("SELECT * FROM governance.dq_run ORDER BY finished_at DESC LIMIT 1").iloc[0]
LATEST = "SELECT rule_id, rule_name, dimension, severity, owner, system_of_record, records_checked, " \
         "records_failed, round(100 * pass_rate, 2) AS pass_pct, round(100 * threshold, 1) AS threshold_pct, " \
         "threshold_met FROM governance.v_dq_latest"

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.headline("Data quality index", f"{run.dq_index:.1f} / 100", f"{LATEST} ORDER BY score, rule_id", "dq_index",
                explanation="100 x sum(weight x min(1, pass rate / threshold)) / sum(weight); weights: critical 8, "
                            "high 4, medium 2, low 1")
with c2:
    ui.headline("Rules meeting their threshold", f"{run.rules_met} of {run.rules_run}",
                f"{LATEST} WHERE threshold_met ORDER BY rule_id", "dq_met")
with c3:
    ui.headline("Critical rules breached", f"{run.critical_breaches}",
                f"{LATEST} WHERE severity = 'critical' AND NOT threshold_met ORDER BY rule_id", "dq_crit")
with c4:
    ui.headline("Records in the exception queue", f"{int(run.records_failed):,}",
                "SELECT * FROM governance.v_dq_exception_queue", "dq_exc")

tab_owner, tab_system, tab_dim, tab_queue, tab_rules, tab_trend = st.tabs(
    ["By owning role", "By source system", "By dimension", "Exception queue", "Rules", "Trend"])

with tab_owner:
    st.markdown("Each role owns its rules, its exceptions and its score. This is the view that turns a data "
                "quality problem into someone's job.")
    card = ui.q("SELECT * FROM governance.v_dq_scorecard_by_owner")
    ui.bar_h(card, "owner", "dq_index", "Data quality index (0 to 100)")
    ui.table(card)

with tab_system:
    card = ui.q("SELECT * FROM governance.v_dq_scorecard_by_system")
    card["system"] = card.system.map(ui.SYSTEM_LABELS)
    ui.bar_h(card, "system", "dq_index", "Data quality index (0 to 100)",
             colours={ui.SYSTEM_LABELS[k]: v for k, v in ui.SYSTEM_COLOURS.items()})
    ui.table(card)

with tab_dim:
    card = ui.q("SELECT * FROM governance.v_dq_scorecard_by_dimension")
    ui.bar_h(card, "dimension", "dq_index", "Data quality index (0 to 100)")
    ui.table(card)

with tab_queue:
    st.markdown("The records that fail a rule in the latest run, most severe first, each with the action that "
                "fixes it. Pick a row to see the source line it came from.")
    queue = ui.q("SELECT * FROM governance.v_dq_exception_queue")
    f1, f2, f3 = st.columns(3)
    owner = f1.selectbox("Owner", ["All"] + sorted(queue.owner.unique()))
    severity = f2.selectbox("Severity", ["All", "critical", "high", "medium", "low"])
    rules = sorted(queue.rule_id.unique())
    rule = f3.selectbox("Rule", ["All"] + rules,
                        format_func=lambda r: r if r == "All" else f"{r} {queue[queue.rule_id == r].rule_name.iloc[0]}")
    shown = queue
    if owner != "All":
        shown = shown[shown.owner == owner]
    if severity != "All":
        shown = shown[shown.severity == severity]
    if rule != "All":
        shown = shown[shown.rule_id == rule]
    st.caption(f"{len(shown):,} open exceptions")
    ui.table(shown[["exception_id", "rule_id", "rule_name", "severity", "owner", "record_key", "observed",
                    "suggested_action", "source_file", "source_row"]], height=380)
    ui.trace_rows(shown, key="dq_trace")

with tab_rules:
    rules = ui.q("""SELECT r.id AS rule_id, r.name, r.description, r.dimension, r.severity, r.owner,
                           r.system_of_record, round(100 * l.pass_rate, 2) AS pass_pct,
                           round(100 * r.threshold, 1) AS threshold_pct, l.threshold_met, r.consequence,
                           r.corrective_action
                    FROM governance.dq_rule r JOIN governance.v_dq_latest l ON l.rule_id = r.id ORDER BY r.id""")
    ui.table(rules, height=420)

with tab_trend:
    trend = ui.q("SELECT finished_at, dq_index, rules_met, critical_breaches FROM governance.v_dq_trend")
    if len(trend) < 2:
        st.markdown("One run so far. Each `make quality` adds a point; history is kept across rebuilds.")
    ui.line(trend, "finished_at", "dq_index", "Run", "Data quality index (0 to 100)", y_format=".0f")
    ui.table(trend)
