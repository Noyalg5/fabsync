"""Performance: the KPI dashboard. Every figure is shown with its caveat."""

import streamlit as st

from fabsync import ui

ui.title("Performance", "What management can see once the data is reconciled. Each KPI is shown with its target, "
         "its owner and its caveat, because a figure without its limitations is how dashboards lose trust.")
ui.require("marts", "kpi_scorecard", "make kpi")

cards = ui.q("""SELECT s.*, d.caveat, d.definition FROM marts.kpi_scorecard s
                JOIN marts.kpi_definition d USING (kpi_id) ORDER BY kpi_id""")

for start in range(0, len(cards), 3):
    cols = st.columns(3)
    for col, r in zip(cols, cards.iloc[start:start + 3].itertuples(), strict=False):
        with col, st.container(border=True):
            st.markdown(f"**{r.name}**")
            st.caption(r.definition)
            if st.button(ui.fmt(r.value, r.unit), key=f"hl_kpi_{r.kpi_id}", type="tertiary",
                         help="Show the rows behind this figure"):
                ui._rows_dialog(r.name, ui.fmt(r.value, r.unit), r.rows_sql, r.definition)
            status = "No target; for information" if r.target == "no target" else f"Target {r.target}: {r.status}"
            extra = f" · {r.secondary_label}: {ui.fmt(r.secondary_value, r.secondary_unit)}" if isinstance(
                r.secondary_label, str) else ""
            st.markdown(f"{status}{extra}  \nOwner: {r.owner}")
            st.caption(f"Caveat: {r.caveat}")

st.subheader("Detail")
names = dict(zip(cards.kpi_id, cards.name, strict=True))
kpi = st.selectbox("KPI", list(names), format_func=lambda k: f"{k} {names[k]}")

if kpi == "KPI-01":
    monthly = ui.q("SELECT month, otif_pct, on_time_pct FROM marts.otif_by_month WHERE measured >= 5")
    ui.line(monthly, "month", "otif_pct", "Month of despatch", "OTIF (%)", target=95, y_format=".0f")
    site = ui.q("SELECT site_code, otif_pct, measured FROM marts.otif_by_site")
    site["label"] = [f"{p:.1f}%  ({n} deliveries)" for p, n in zip(site.otif_pct, site.measured, strict=True)]
    ui.bar_h(site, "site_code", "otif_pct", "OTIF (%)", label="label")
    ui.table(ui.q("SELECT * FROM marts.otif_by_customer"))
elif kpi == "KPI-02":
    jobs = ui.q("SELECT job_no, variance_pct, actual_hours, planned_hours FROM marts.labour_variance_by_job "
                "WHERE variance_pct IS NOT NULL LIMIT 15")
    jobs["label"] = [f"{v:+.1f}%" for v in jobs.variance_pct]
    ui.bar_h(jobs, "job_no", "variance_pct", "Booked against planned hours on completed works (%)", label="label",
             sort=None)
    ui.table(ui.q("SELECT * FROM marts.labour_variance_by_job"))
elif kpi == "KPI-03":
    y = ui.q("SELECT section_type, cut_yield_pct, offcut_waste_pct FROM marts.material_yield_by_section_type "
             "WHERE cut_yield_pct IS NOT NULL")
    y["label"] = [f"{v:.1f}%" for v in y.cut_yield_pct]
    ui.bar_h(y, "section_type", "cut_yield_pct", "Cut yield on 12 m bars (%); dashed line is the 85% target",
             label="label", target=85)
    ui.table(ui.q("SELECT * FROM marts.material_yield_by_section_type"))
elif kpi == "KPI-04":
    s = ui.q("SELECT site_code, accuracy_pct, counted_lines FROM marts.stock_accuracy")
    s["label"] = [f"{a:.1f}%  ({n} lines)" for a, n in zip(s.accuracy_pct, s.counted_lines, strict=True)]
    ui.bar_h(s, "site_code", "accuracy_pct", "Stock line accuracy (%); dashed line is the 95% target", label="label",
             target=95, sort=None)
    ui.table(ui.q("SELECT * FROM marts.stock_accuracy"))
elif kpi == "KPI-05":
    rate = ui.q("SELECT month, exception_rate_pct FROM marts.three_way_exception_rate "
                "WHERE po_lines_assessed >= 5")
    ui.line(rate, "month", "exception_rate_pct", "Month ordered", "Exception rate, PO lines (%)", target=5,
            y_format=".0f")
    ui.table(ui.q("SELECT * FROM marts.three_way_value_at_risk"))
elif kpi == "KPI-06":
    cov = ui.q("SELECT month, site_code, coverage_pct FROM marts.traceability_coverage")
    ui.line(cov, "month", "coverage_pct", "Month of works order start", "Traceability coverage (%)",
            series="site_code", target=100, y_format=".0f")
    ui.table(ui.q("SELECT * FROM marts.traceability_coverage"))
elif kpi == "KPI-07":
    wip = ui.q("SELECT age_bucket, wip_value, works_orders FROM marts.wip_ageing")
    wip["label"] = [f"{ui.gbp(v)} ({n})" for v, n in zip(wip.wip_value, wip.works_orders, strict=True)]
    ui.columns_chart(wip, "age_bucket", "wip_value", "Age since work started", "WIP value (£)", label="label",
                     sort=list(wip.age_bucket))
    ui.table(ui.q("SELECT * FROM marts.wip_works_orders"), height=320)
elif kpi == "KPI-08":
    cap = ui.q("SELECT week_commencing, site_code, utilisation_pct FROM marts.capacity_utilisation "
               "WHERE utilisation_pct IS NOT NULL")
    ui.line(cap, "week_commencing", "utilisation_pct", "Week commencing", "Booked / available hours (%)",
            series="site_code", target=95, y_format=".0f")
    ui.table(ui.q("SELECT * FROM marts.capacity_utilisation_by_site"))
else:
    qc = ui.q("SELECT month, cost_of_quality_pct, ncr_cost, turnover FROM marts.quality_cost_by_month "
              "WHERE turnover > 0")
    ui.line(qc, "month", "cost_of_quality_pct", "Month", "NCR cost as % of turnover", target=2, y_format=".1f")
    ui.table(ui.q("SELECT * FROM marts.ncr_by_category"))

row = cards[cards.kpi_id == kpi].iloc[0]
st.caption(f"Caveat: {row.caveat}")
