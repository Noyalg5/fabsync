"""FabSync Streamlit entry page. All data shown is synthetic."""

import streamlit as st

st.set_page_config(page_title="FabSync", layout="wide")
st.title("FabSync")
st.caption("Systems integration, data governance and management reporting demonstrator. All data is synthetic.")
st.markdown("Run `make ingest` to build the warehouse, then open **Lineage and quarantine** in the sidebar to "
            "see where every source row went and why. After `make reconcile`, **Reconciliation** drills from "
            "each headline figure to the rows and source lines behind it.")
