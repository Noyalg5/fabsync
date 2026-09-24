"""Lineage and quarantine: where every row went, and why. All data is synthetic."""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

WAREHOUSE = Path(os.environ.get("FABSYNC_WAREHOUSE", "data/warehouse/fabsync.duckdb"))

st.set_page_config(page_title="FabSync · Lineage and quarantine", layout="wide")
st.title("Lineage and quarantine")
st.caption("All data is synthetic. Nothing is dropped silently and nothing is edited in place: every row that "
           "leaves the raw layer is either staged or quarantined with its original values.")

if not WAREHOUSE.exists():
    st.warning("No warehouse yet. Run `make ingest`.")
    st.stop()


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()


run = query("SELECT * FROM governance.run").iloc[0]
balance = query("""SELECT source_file, data_lines, raw_rows, staged_rows, quarantined_rows, core_rows, balanced
                   FROM governance.table_balance ORDER BY source_system, source_table""")
steps = int(query("SELECT count(*) AS n FROM governance.lineage").n[0])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rows received", f"{run.rows_raw:,}")
c2.metric("Rows staged", f"{run.rows_staged:,}")
c3.metric("Rows quarantined", f"{run.rows_quarantined:,}")
c4.metric("Lineage steps", f"{steps:,}")
c5.metric("Every file balances", "Yes" if balance.balanced.all() else "No")
st.caption(f"Run {run.run_id} · status {run.status}")

tab_balance, tab_lineage, tab_quarantine, tab_trace, tab_rules = st.tabs(
    ["Balance", "Lineage flow", "Quarantine", "Trace a row", "Rules and contracts"])

with tab_balance:
    st.markdown("Lines in the file = rows staged + rows quarantined, and core holds every staged row.")
    st.dataframe(balance, hide_index=True, width="stretch")

with tab_lineage:
    targets = query("SELECT DISTINCT target_table FROM governance.lineage ORDER BY 1").target_table.tolist()
    default = targets.index("staging.shop_floor_time_bookings") if "staging.shop_floor_time_bookings" in targets else 0
    target = st.selectbox("Table", targets, index=default)
    flow = query("""SELECT step_id, rule_id, rule_description, rows_in, rows_out, rows_rejected, rows_affected, detail
                    FROM governance.lineage WHERE target_table = ? ORDER BY step_id""", [target])
    st.dataframe(flow, hide_index=True, width="stretch")
    with st.expander("Full lineage log"):
        st.dataframe(query("SELECT * EXCLUDE (run_id) FROM governance.lineage ORDER BY step_id"),
                     hide_index=True, width="stretch")

with tab_quarantine:
    summary = query("SELECT * FROM governance.v_quarantine_summary")
    st.dataframe(summary, hide_index=True, width="stretch")
    files = ["All"] + sorted(summary.source_table.unique().tolist())
    rules = ["All"] + sorted(summary.rule_id.unique().tolist())
    f1, f2 = st.columns(2)
    pick_table = f1.selectbox("Source table", files)
    pick_rule = f2.selectbox("Rule", rules)
    where, params = ["1 = 1"], []
    if pick_table != "All":
        where.append("source_table = ?")
        params.append(pick_table)
    if pick_rule != "All":
        where.append("rule_id = ?")
        params.append(pick_rule)
    rows = query(f"""SELECT quarantine_id, source_file, source_row, rule_id, failing_column, failing_value,
                            original_record, status
                     FROM governance.quarantine WHERE {' AND '.join(where)} ORDER BY quarantine_id""", params)
    st.dataframe(rows, hide_index=True, width="stretch")
    if len(rows):
        qid = st.selectbox("Inspect", rows.quarantine_id.tolist())
        rec = rows[rows.quarantine_id == qid].iloc[0]
        st.markdown(f"**{rec.rule_id}** on `{rec.source_file}` line {rec.source_row}, column "
                    f"`{rec.failing_column or '(whole row)'}`")
        st.json(json.loads(rec.original_record))

with tab_trace:
    st.markdown("Pick a file and line number to see that row in every layer it reached.")
    t1, t2 = st.columns(2)
    source_file = t1.selectbox("Source file", balance.source_file.tolist(),
                               index=balance.source_file.tolist().index("shop_floor/time_bookings.csv"))
    system, table = source_file.removesuffix(".csv").split("/")
    lo, hi = query(f"SELECT min(_source_row) AS lo, max(_source_row) AS hi FROM raw.{system}_{table}").iloc[0]
    line = t2.number_input("Line in file", min_value=int(lo), max_value=int(hi), value=int(lo))
    core_table = query("""SELECT DISTINCT target_table FROM governance.lineage
                          WHERE layer = 'core' AND source_file = ? AND rule_id = 'CO-06'""", [source_file])
    layers = {
        "raw": f"SELECT * EXCLUDE (_run_id, _loaded_at) FROM raw.{system}_{table} WHERE _source_row = ?",
        "staging": f"SELECT * EXCLUDE (_run_id) FROM staging.{system}_{table} WHERE _source_row = ?",
        "quarantine": """SELECT quarantine_id, rule_id, rule_description, failing_column, failing_value
                         FROM governance.quarantine WHERE source_file = ? AND source_row = ?""",
    }
    if len(core_table):
        layers["core"] = f"SELECT * FROM {core_table.target_table[0]} WHERE _source_row = ?"
    for layer, sql in layers.items():
        params = [source_file, int(line)] if layer == "quarantine" else [int(line)]
        found = query(sql, params)
        st.markdown(f"**{layer}**" + ("" if len(found) else " · not present"))
        if len(found):
            st.dataframe(found, hide_index=True, width="stretch")

with tab_rules:
    st.dataframe(query("SELECT * FROM governance.rule ORDER BY rule_id"), hide_index=True, width="stretch")
    st.markdown("Schema contracts, declared in code separately from the data:")
    st.dataframe(query("SELECT * FROM governance.contract ORDER BY source_system, source_table, ordinal"),
                 hide_index=True, width="stretch")
