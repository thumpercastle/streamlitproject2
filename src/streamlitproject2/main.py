import os
import tempfile
import datetime as dt
import streamlit as st
import pycoustic as pc
import pandas as pd
from typing import Dict, Tuple
from st_config import build_combined_csv_with_sections
import plotly.graph_objects as go


from st_config import (
    init_app_state,
    TEMPLATE,
    COLOURS,
    get_data,
    _convert_for_download,
    _cleanup_tmp_files,
    parse_times,
    default_times,
    _render_upload_modal_contents,
    _get_template_dataframe,
    _convert_for_download,
    _reset_workspace
)

from page_1 import config_page
from page_2 import analysis_page
from page_3 import vis_page

ss = init_app_state()


#TODO: Add modal and counts bar chart
#TODO: Add titles to graphs
#TODO: Tidy buttons and info on graph page.


pg = st.navigation([
    st.Page(config_page, title="Data Loader"),
    st.Page(analysis_page, title="Analysis"),
    st.Page(vis_page, title="Visualisation")
])

# Sidebar menu
from st_config import build_combined_csv_with_sections

# Sidebar menu
with st.sidebar:
    st.text("This tool is a work in progress and may produce errors. Check results manually. Use at your own risk.")

    # Grey out until data exists (either logs loaded, or any output df non-empty)
    any_data = bool(ss.get("logs"))

    # Pull parameters from session_state (use .get to avoid KeyError on first run)
    times = ss.get("times") or {}
    modal_params = ss.get("modal_params") or [None, None, None, None]

    csv_bytes = build_combined_csv_with_sections(
        ss.get("broadband_df"),
        ss.get("leq_df"),
        ss.get("lmax_df"),
        ss.get("modal_df"),
        ss.get("counts"),
        day_start=times.get("day"),
        evening_start=times.get("evening"),
        night_start=times.get("night"),
        lmax_n=int(ss.get("lmax_n")),
        lmax_t=int(ss.get("lmax_t")),
        modal_param=modal_params[0],
        day_t=modal_params[1],
        evening_t=modal_params[2],
        night_t=modal_params[3],
    )

    st.download_button(
        label="Download all tables (CSV)",
        data=csv_bytes,
        file_name="pycoustic-analysis-tables.csv",
        mime="text/csv",
        key="dl_all_tables_csv",
        disabled=not any_data,
        use_container_width=True,
        help="Exports all summary tables into one CSV file with section headers and full (multi-row) column headers.",
    )

pg.run()

