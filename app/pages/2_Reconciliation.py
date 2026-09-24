"""Reconciliation: every headline figure, the rows behind it, and the source line behind each row.

All data is synthetic.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

WAREHOUSE = Path(os.environ.get("FABSYNC_WAREHOUSE", "data/warehouse/fabsync.duckdb"))
TITLES = {"three_way": "Three-way match", "job_cost": "Job cost reconciliation", "stock": "Stock accuracy",
          "traceability": "Material traceability"}

st.set_page_config(page_title="FabSync · Reconciliation", layout="wide")
st.title("Reconciliation")
st.caption("All data is synthetic. Every figure on this page is recomputed from the rows shown beneath it, and "
           "every row carries the source file and line it came from.")


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()


def has_recon() -> bool:
    if not WAREHOUSE.exists():
        return False
    return bool(len(query("SELECT 1 FROM information_schema.tables WHERE table_schema = 'recon' "
                          "AND table_name = 'headline'")))


if not has_recon():
    st.warning("No reconciliation results yet. Run `make reconcile`.")
    st.stop()


def show(value: float, unit: str) -> str:
    if unit == "GBP":
        return f"-£{-value:,.0f}" if value < 0 else f"£{value:,.0f}"
    return {"percent": f"{value:.1f}%", "count": f"{int(value):,}", "tonnes": f"{value:,.1f} t",
            "kg": f"{value:,.0f} kg", "hours": f"{value:,.1f} h"}.get(unit, str(value))


exposure = query("SELECT * FROM recon.exposure")
cols = st.columns(len(exposure))
for col, r in zip(cols, exposure.itertuples(), strict=True):
    unit = "tonnes" if "tonnes" in r.exposure_label else "GBP"
    col.metric(TITLES[r.engine], show(r.exposure, unit), help=r.exposure_label)

heads = query("SELECT * FROM recon.headline ORDER BY ordinal")
engine = st.radio("Engine", list(TITLES), format_func=TITLES.get, horizontal=True)
mine = heads[heads.engine == engine].reset_index(drop=True)
st.dataframe(mine.assign(figure=[show(v, u) for v, u in zip(mine.value, mine.unit, strict=True)])
             [["label", "figure", "explanation"]], hide_index=True, width="stretch")

label = st.selectbox("Drill into", mine.label.tolist())
h = mine[mine.label == label].iloc[0]
rows = query(h.rows_sql)
recomputed = query(h.value_sql).iloc[0, 0]
st.markdown(f"**{h.label}: {show(h.value, h.unit)}** from {len(rows):,} rows in `{h.table}`. "
            f"Recomputed now: {show(float(recomputed or 0), h.unit)}.")
st.caption(h.explanation)
with st.expander("SQL"):
    st.code(f"-- the figure\n{h.value_sql};\n\n-- the rows behind it\n{h.rows_sql};", language="sql")
st.dataframe(rows, hide_index=True, width="stretch")

if {"source_file", "source_row"} <= set(rows.columns) and len(rows):
    st.subheader("Trace a row to its source line")
    traceable = rows.dropna(subset=["source_file", "source_row"])
    if len(traceable):
        pick = st.selectbox("Row", range(len(traceable)),
                            format_func=lambda i: f"{traceable.iloc[i].source_file} line "
                                                  f"{int(traceable.iloc[i].source_row)}")
        src = traceable.iloc[pick]
        system, table = str(src.source_file).removesuffix(".csv").split("/")
        raw = query(f"SELECT * EXCLUDE (_run_id, _loaded_at) FROM raw.{system}_{table} WHERE _source_row = ?",
                    [int(src.source_row)])
        st.markdown(f"As received in `{src.source_file}`, line {int(src.source_row)}:")
        st.dataframe(raw, hide_index=True, width="stretch")
