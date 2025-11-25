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

from page_1 import page_1
from page_2 import page_2
from page_3 import page_3

ss = init_app_state()


#TODO: Evening periods don't work on Streamlit
#TODO: Move 'Lmax period' drop down into Lmax tab
#TODO: Add modal and counts bar chart
#TODO: Add titles to graphs
#TODO: Tidy buttons and info on graph page.
#TODO: Add option for user input for log names.
#TODO: Add option for user input for log names.



pg = st.navigation([
    st.Page(page_1, title="Data Loader"),
    st.Page(page_2, title="Survey Overview"),
    st.Page(page_3, title="Individual Logs")
])

# Sidebar menu
with st.sidebar:
    st.text("This tool is a work in progress and may produce errors. Check results manually. Use at your own risk.")

pg.run()

        # st.bar_chart(counts, use_container_width=True)