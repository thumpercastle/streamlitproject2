import os
import tempfile
import datetime as dt
import streamlit as st
import pycoustic as pc
import pandas as pd
from typing import Dict, Tuple
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
with st.sidebar:
    st.text("This tool is a work in progress and may produce errors. Check results manually. Use at your own risk.")

pg.run()

