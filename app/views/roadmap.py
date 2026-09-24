"""Roadmap: phased rollout, risk register and training plan, sized by the live findings."""

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from fabsync import ui

ui.title("Roadmap", "How to move from the demonstrator to the business: in phases, owned, with the risks and the "
         "training named up front.")
roadmap = yaml.safe_load(Path("config/roadmap.yaml").read_text(encoding="utf-8"))

st.subheader("The size of the job")
if ui.has_table("recon", "headline") and ui.has_table("governance", "dq_exceptions"):
    review_hours = ui.scalar("SELECT sum(est_minutes) / 60 FROM core.v_match_review_queue")
    certs_sql = ("SELECT grn_no, po_no, trim(material_code) AS material_code, received_date, heat_number, "
                 "mill_cert_ref, _source_file AS source_file, _source_row AS source_row "
                 "FROM staging.corvus_mrp_goods_received WHERE heat_number IS NULL OR mill_cert_ref IS NULL "
                 "ORDER BY received_date")
    aged_sql = "SELECT * FROM recon.three_way_lines WHERE is_exception AND age_days > 90 ORDER BY age_days DESC"
    critical_sql = "SELECT * FROM governance.v_dq_exception_queue WHERE severity = 'critical'"
    count = lambda sql: ui.scalar(f"SELECT count(*) FROM ({sql})")  # noqa: E731
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.headline("Master data decisions to make", f"{review_hours:.0f} hours",
                    "SELECT * FROM core.v_match_review_queue ORDER BY domain", "rm_review", note="Phase 2")
    with c2:
        ui.headline("Receipts to recover certificates for", f"{count(certs_sql):,}", certs_sql, "rm_certs",
                    note="Phase 1")
    with c3:
        ui.headline("Purchasing exceptions older than 90 days", f"{count(aged_sql):,}", aged_sql, "rm_ageing",
                    note="Phase 1")
    with c4:
        ui.headline("Critical data quality exceptions", f"{count(critical_sql):,}", critical_sql, "rm_crit",
                    note="Phases 1 and 2")
else:
    st.info("Run `make run-all` to size the work from the data.")

st.subheader("Phased rollout")
ui.table(pd.DataFrame(roadmap["phases"]).rename(columns={"exit": "exit criteria"}))

st.subheader("Risk register")
ui.table(pd.DataFrame(roadmap["risks"]))

st.subheader("Training plan")
ui.table(pd.DataFrame(roadmap["training"]))
