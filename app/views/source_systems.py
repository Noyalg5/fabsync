"""Source systems: each raw extract exactly as received, with its conventions and defects marked."""

import streamlit as st

from fabsync import ui
from fabsync.ingest.pipeline import SOURCES

ui.title("Source systems", "Each extract exactly as it arrived, before anything was cleaned. The conventions "
         "each system follows, and the problems profiling and staging found, are marked against every file.")
ui.require("governance", "profile_anomaly", "make ingest")

by_system = {s.system: s for s in SOURCES}
system = st.radio("System", list(by_system), format_func=ui.SYSTEM_LABELS.get, horizontal=True)
source = by_system[system]
st.html(f'<div style="font-size:1.1rem;font-weight:600">{ui.system_swatch(system)}</div>')
st.markdown("  \n".join(f"**{k.capitalize()}:** {v}" for k, v in source.conventions))

tables = {t.name: t for t in source.tables}
name = st.selectbox("Extract", list(tables), format_func=lambda n: f"{tables[n].file}: {tables[n].description}")
contract = tables[name]
raw_table = f"raw.{system}_{name}"

received = ui.scalar(f"SELECT count(*) FROM {raw_table}")
quarantined = ui.scalar("SELECT count(*) FROM governance.quarantine WHERE source_file = ?", (contract.file,))
anomalies = ui.q("SELECT column_name, anomaly, affected_values, sample_values FROM governance.profile_anomaly "
                 "WHERE source_system = ? AND source_table = ? ORDER BY column_name, anomaly", (system, name))
c1, c2, c3 = st.columns(3)
with c1:
    ui.headline("Rows received", f"{received:,}",
                f"SELECT _source_row AS line, * EXCLUDE (_source_row, _run_id, _loaded_at) FROM {raw_table} "
                "ORDER BY _source_row", f"src_rows_{system}_{name}")
with c2:
    ui.headline("Rows quarantined by staging", f"{quarantined:,}",
                "SELECT quarantine_id, source_file, source_row, rule_id, rule_description, failing_column, "
                f"failing_value, original_record FROM governance.quarantine WHERE source_file = '{contract.file}' "
                "ORDER BY source_row", f"src_quar_{system}_{name}",
                note="Kept with their original values; never deleted")
with c3:
    ui.headline("Problems profiling found", f"{len(anomalies):,}",
                "SELECT column_name, anomaly, affected_values, sample_values FROM governance.profile_anomaly "
                f"WHERE source_system = '{system}' AND source_table = '{name}' ORDER BY column_name",
                f"src_anom_{system}_{name}")

st.subheader("What is wrong with this file")
if anomalies.empty:
    st.markdown("Profiling found nothing wrong with this extract.")
else:
    ui.table(anomalies.rename(columns={"column_name": "column", "affected_values": "values affected",
                                       "sample_values": "examples, quoted to show spacing"}))

st.subheader("The extract as received")
only_bad = st.checkbox("Only rows that failed a staging rule", value=False)
rows = ui.q(f"""
    SELECT r._source_row AS line, q.rule_id || ' ' || coalesce(q.failing_column, 'whole row') AS problem,
           r.* EXCLUDE (_source_row, _source_file, _run_id, _loaded_at)
    FROM {raw_table} r
    LEFT JOIN governance.quarantine q ON q.source_file = r._source_file AND q.source_row = r._source_row
    {'WHERE q.quarantine_id IS NOT NULL' if only_bad else ''}
    ORDER BY r._source_row""")
st.caption(f"{len(rows):,} rows. Line is the line number in the file; the first two lines are the SYNTHETIC DATA "
           "header and the column names. Text is shown exactly as sent, including trailing spaces.")
ui.table(rows, height=420)

with st.expander("The schema contract this file is checked against"):
    ui.table(ui.q("SELECT ordinal, column_name, declared_type, required, is_key, formats, domain, pattern, "
                  "description FROM governance.contract WHERE source_file = ? ORDER BY ordinal", (contract.file,)))
