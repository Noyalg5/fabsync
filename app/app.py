"""FabSync demonstrator: entry point for `make app`.

Pages run in the order that tells the story: the problem, the mess, the
quality, the fix, the money, the performance, the governance and the plan.
All data is synthetic.
"""

import streamlit as st

from fabsync import ui

st.set_page_config(page_title="FabSync", layout="wide")
ui.page_setup()

PAGES = [
    st.Page("views/overview.py", title="Overview", url_path="overview", default=True),
    st.Page("views/source_systems.py", title="Source systems", url_path="source-systems"),
    st.Page("views/data_quality.py", title="Data quality", url_path="data-quality"),
    st.Page("views/master_data.py", title="Master data", url_path="master-data"),
    st.Page("views/reconciliation.py", title="Reconciliation", url_path="reconciliation"),
    st.Page("views/performance.py", title="Performance", url_path="performance"),
    st.Page("views/governance.py", title="Governance", url_path="governance"),
    st.Page("views/roadmap.py", title="Roadmap", url_path="roadmap"),
]

st.navigation(PAGES).run()
