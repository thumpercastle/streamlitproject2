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

ss = init_app_state()


def config_page():
    st.set_page_config(page_title="pycoustic GUI", layout="wide")
    # st.title("Data Loader")

    st.title("Pycoustic Acoustic Survey Analyser")
    st.markdown(
        "> Upload CSV logs, adjust survey periods below, then explore broadband insights and interactive graphs."
    )

    logs_loaded = len(ss["logs"])
    last_upload = ss["last_upload_ts"]

    stats_cols = st.columns(2)
    stats_cols[0].metric("Loaded logs", logs_loaded)
    stats_cols[1].metric(
        "Last import",
        last_upload.strftime("%Y-%m-%d %H:%M") if isinstance(last_upload, dt.datetime) else "—",
    )

    st.markdown("### Quick start")
    quick_cols = st.columns(3)
    with quick_cols[0]:
        st.markdown("**1. Upload logs**<br/>Use the primary button below or drag CSV files directly into the modal.",
                    unsafe_allow_html=True)
    with quick_cols[1]:
        st.markdown(
            "**2. Review periods**<br/>Pick survey times from the menu below, so every page shares the same schedule.",
            unsafe_allow_html=True)
    with quick_cols[2]:
        st.markdown(
            "**3. Explore outputs**<br/>Head to Survey Overview or Individual Logs once logs are ready.",
            unsafe_allow_html=True)

    if logs_loaded:
        st.success(f"{logs_loaded} log(s) ready for analysis. Jump to Analysis or Interactive Graphs when you’re set.")
    else:
        st.warning("No logs uploaded yet. Use the **Upload CSV logs** button below to get started.")

    template_df = _get_template_dataframe()
    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("Upload CSV logs", type="primary", icon=":material/upload_file:", width="stretch"):
            ss["show_upload_modal"] = True
            st.rerun()
    with action_cols[1]:
        st.download_button(
            label="Download template CSV",
            data=_convert_for_download(template_df),
            file_name="pycoustic-template.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="home_template_download",
        )
    cols = st.columns(1)
    with cols[0]:
        if st.button(
                "Reset logs and temp files",
                width="stretch",
                key="reset_logs_button",
                help="Clears loaded logs, staged files, cached temp files, and analysis outputs.",
        ):
            _reset_workspace()

    st.divider()

    # Ensure modal state exists
    ss.setdefault("show_upload_modal", False)

    # Streamlit dialog opened only when flag is True
    if ss.get("show_upload_modal", False):

        @st.dialog("Data Loader", width="large")
        def data_loader_dialog():
            col_add = st.columns(1)
            with col_add[0]:
                st.subheader("1. Upload CSV logs")
                _render_upload_modal_contents()
        data_loader_dialog()


    # Build the survey
    survey = pc.Survey()
    for name, lg in ss["logs"].items():
        survey.add_log(data=lg, name=name)

    survey.set_periods(times=default_times)
    ss["survey"] = survey
    ss["broadband_df"] = survey.broadband_summary()
    ss["leq_df"] = survey.leq_spectra()
    ss["lmax_df"] = survey.lmax_spectra()
    ss["modal_df"] = survey.modal()
    ss["counts"] = survey.counts()

    st.markdown("## Set Time Periods")
    day_col, eve_col, night_col = st.columns([1, 1, 1])
    with day_col:
        day_start = st.time_input(
            "Daytime Start",
            value=dt.time(*ss["times"]["day"]),
            key="day_start",
        )
    with eve_col:
        evening_start = st.time_input(
            "Evening Start*",
            value=dt.time(*ss["times"]["evening"]),
            key="evening_start",
        )
    with night_col:
        night_start = st.time_input(
            "Night-time Start**",
            value=dt.time(*ss["times"]["night"]),
            key="night_start",
        )
    st.text(
        "*If Evening starts at the same time as Night, Evening periods will be disabled (default). **Night-time must cross over midnight")
    times = parse_times(day_start, evening_start, night_start)
    ss["times"] = times
    survey.set_periods(times=times)

    with st.expander("Maintenance", expanded=True):

        st.markdown(
            "- If you edit CSV cells and then delete rows, create a fresh copy before exporting to avoid parsing issues.\n"
            "- Evening periods are disabled when they match night start times; adjust above to restore evening summaries.\n"
            "- Uploaded files stay queued until you add them as logs, so you can review names safely."
        )

    st.divider()
