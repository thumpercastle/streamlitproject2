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
)

ss = init_app_state()


#TODO: Evening periods don't work on Streamlit
#TODO: Move 'Lmax period' drop down into Lmax tab
#TODO: Add modal and counts bar chart
#TODO: Add titles to graphs
#TODO: Tidy buttons and info on graph page.
#TODO: Add option for user input for log names.
#TODO: Add option for user input for log names.


def page_1():
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
        if st.button("Upload CSV logs", type="primary", icon=":material/upload_file:", use_container_width=True):
            ss["show_upload_modal"] = True
            st.rerun()
    with action_cols[1]:
        st.download_button(
            label="Download template CSV",
            data=_convert_for_download(template_df),
            file_name="pycoustic-template.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True,
            key="home_template_download",
        )

    st.divider()

    # Ensure modal state exists
    ss.setdefault("show_upload_modal", False)

    # Streamlit dialog opened only when flag is True
    if ss.get("show_upload_modal", False):

        @st.dialog("Data Loader", width="large")
        def data_loader_dialog():
            col_add, col_reset = st.columns([1, 1])
            with col_add:
                st.subheader("1. Upload CSV logs")
                _render_upload_modal_contents()

            with col_reset:
                st.subheader("2. Current Logs")
                if ss["logs"]:
                    st.write(f"{len(ss['logs'])} log(s) loaded:")
                    st.write(list(ss["logs"].keys()))
                else:
                    st.info("No logs loaded yet.")
                if st.button("Reset"):
                    _cleanup_tmp_files(ss.get("tmp_paths", []))
                    ss["tmp_paths"] = []
                    ss["logs"] = {}
                    ss["resi_df"] = pd.DataFrame()
                    ss["pending_uploads"] = []
                    ss["num_logs"] = 0
                    st.rerun()

        data_loader_dialog()


    # Build the survey
    survey = pc.Survey()
    for name, lg in ss["logs"].items():
        survey.add_log(data=lg, name=name)

    survey.set_periods(times=default_times)
    ss["survey"] = survey

    st.divider()
    st.markdown("# Survey Config")
    st.markdown("## Set Time Periods")
    day_col, eve_col, night_col = st.columns([1, 1, 1])
    with day_col:
        day_start = st.time_input("Daytime Start", dt.time(7, 00), on_change=st.rerun)
    with eve_col:
        evening_start = st.time_input("Evening Start*", dt.time(23, 00), on_change=st.rerun)
    with night_col:
        night_start = st.time_input("Night-time Start**", dt.time(23, 00), on_change=st.rerun)
    st.text(
        "*If Evening starts at the same time as Night, Evening periods will be disabled (default). **Night-time must cross over midnight")
    times = parse_times(day_start, evening_start, night_start)
    ss["times"] = times
    survey.set_periods(times=times)

    with st.expander("Maintenance", expanded=True):
        if st.button(
                "Reset logs and temp files",
                use_container_width=True,
                key="reset_logs_button",
                help="Clears loaded logs, staged files, cached temp files, and analysis outputs.",
        ):
            _reset_workspace()
        st.markdown(
            "- If you edit CSV cells and then delete rows, create a fresh copy before exporting to avoid parsing issues.\n"
            "- Evening periods are disabled when they match night start times; adjust above to restore evening summaries.\n"
            "- Uploaded files stay queued until you add them as logs, so you can review names safely."
        )

    st.divider()

    # Line 151: create tabs dynamically for each log in ss["logs"], with an Overview tab first

def page_2():
    st.title("Survey Overview")
    # st.header("Overview")
    log_items = list(ss.get("logs", {}).items())
    # if not log_items:
    #     st.info("No logs loaded yet.")
    # else:
    #     # Compute and display resi_summary directly from current logs
    #     st.subheader("Broadband Summary")
    #     resi_container = st.container()
    #
    #     with resi_container:
    #         if not bool(ss["logs"]):
    #             st.info("No logs loaded yet.")
    #         else:
    #             try:
    #                 df = ss["survey"].resi_summary()  # Always a DataFrame per your note
    #                 ss["resi_df"] = df
    #
    #                 st.success(f"resi_summary computed: {df.shape[0]} rows, {df.shape[1]} columns.")
    #                 # Show cached result on rerun
    #                 if not ss["resi_df"].empty:
    #                     st.dataframe(ss["resi_df"], key="resi_df", width="stretch")
    #                 else:
    #                     st.info("Run resi_summary() to see results here.")
    #             except Exception as e:
    #                 st.error(f"Failed to compute resi_summary: {e}")
    #
    #     st.divider()




    st.header("Overview")
    if not log_items:
        st.info("No logs loaded yet.")
    else:
        # Compute and display resi_summary directly from current logs
        st.subheader("Broadband Summary")
        resi_container = st.container()

        with resi_container:
            if not bool(ss["logs"]):
                st.info("No logs loaded yet.")
            else:
                try:
                    df = ss["survey"].resi_summary()  # Always a DataFrame per your note
                    ss["resi_df"] = df

                    st.success(f"resi_summary computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    if not ss["resi_df"].empty:
                        st.dataframe(ss["resi_df"], key="resi_df", width="stretch")
                    else:
                        st.info("Run resi_summary() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute resi_summary: {e}")

        st.divider()


        # Compute and display resi_summary directly from current logs
        st.subheader("Leq Spectra")
        st.text(
            "This function computes the combined Leq for the period in question over the entire survey (e.g. all days combined).")
        leq_container = st.container()

        with leq_container:
            if not bool(ss["logs"]):
                st.info("No logs loaded yet.")
            else:
                try:
                    df = ss["survey"].leq_spectra()  # Always a DataFrame per your note
                    ss["leq_df"] = df

                    st.success(f"Leq spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    if not ss["leq_df"].empty:
                        st.dataframe(ss["leq_df"], key="leq_df", width="stretch")
                    else:
                        st.info("Run leq_spectra() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute leqspectra: {e}")

        st.divider()


        # Compute and display resi_summary directly from current logs
        st.subheader("Lmax Spectra")
        st.text("Note: the timestamp in the 'Date' column shows the date when the night-time period started, not the date on which the lmax occurred. e.g. 2025-08-14 00:14 lmax would have occured in the early hours of 2025-08-15.")
        st.text("This function works by selecting the highest A-weighted value, and the corresponding octave band data.")
        lmax_container = st.container()

        with lmax_container:
            col_nth, col_t, col_per = st.columns([1, 1, 1])
            with col_nth:
                nth = st.number_input(
                    label="nth-highest Lmax",
                    min_value=1,
                    max_value=60,
                    value=10,
                    step=1,
                )
            with col_t:
                t_int = st.number_input(
                    label="Desired time-resolution of Lmax (min).",
                    min_value=1,
                    max_value=60,
                    value=2,
                    step=1,
                )
                t_str = str(t_int) + "min"
            with col_per:
                per = st.selectbox(
                    label="Which period to use for Lmax?",
                    options=["Days", "Evenings", "Nights"],
                    index=2
                )
                per = per.lower()
            if not bool(ss["logs"]):
                st.info("No logs loaded yet.")
            else:
                try:
                    df = ss["survey"].lmax_spectra(n=nth, t=t_str, period=per)  # Always a DataFrame per your note
                    ss["lmax_df"] = df
                    st.success(f"Lmax spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    # Notify user if evening period disabled
                    if per == "evenings" and ss["times"]["evening"] == ss["times"]["night"]:
                        st.info("Evenings are currently disabled. Enable them by setting the times in the sidebar.")
                    if not ss["lmax_df"].empty:
                        st.dataframe(ss["lmax_df"], key="lmax_df", width="stretch")
                    else:
                        st.info("Run lmax_spectra() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute lmax_spectra: {e}")

        st.divider()


        # Compute and display resi_summary directly from current logs
        st.subheader("Modal and Value Counts")
        st.text("Note: Ignore the 'Date' label.")
        modal_container = st.container()

        with modal_container:
            col_cols, col_day_t, col_eve_t, col_night_t = st.columns([1, 1, 1, 1])
            with col_cols:
                par = st.selectbox(
                    label="Which parameter to use for modal?",
                    options=["L90", "Leq", "Lmax"],
                    index=0
                )
                par_tup = (par, "A")
            # TODO:
            # with col_by_date:
            #     by_date = st.selectbox(
            #         label="Overall modal, or by date?",
            #         options=["Overall", "By date"],
            #         index=0
            #     )
            #     if by_date == "By date":
            #         by_date = True
            #     else:
            #         by_date = False
            with col_day_t:
                day_t = st.selectbox(
                    label="Desired time-resolution of Daytime modal.",
                    options=[1, 2, 5, 10, 15, 30, 60, 120],
                    index=6
                )
                day_t = str(day_t) + "min"
            with col_eve_t:
                eve_t = st.selectbox(
                    label="Desired time-resolution of Evening modal.",
                    options=[1, 2, 5, 10, 15, 30, 60, 120],
                    index=6
                )
                eve_t = str(eve_t) + "min"
            with col_night_t:
                night_t = st.selectbox(
                    label="Desired time-resolution of Night modal.",
                    options=[1, 2, 5, 10, 15, 30, 60, 120],
                    index=4
                )
                night_t = str(night_t) + "min"
            if not bool(ss["logs"]):
                st.info("No logs loaded yet.")
            else:
                try:
                    df = ss["survey"].modal(
                        cols=par_tup,
                        by_date=False,
                        day_t=day_t,
                        evening_t=eve_t,
                        night_t=night_t
                    )  # Always a DataFrame per your note
                    ss["modal_df"] = df
                    st.success(f"Modal values computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    if not ss["modal_df"].empty:
                        st.dataframe(ss["modal_df"], key="modal_df", width="stretch")
                    else:
                        st.info("Run modal() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute modal: {e}")

            # st.markdown("Counts")
            ss["counts"] = ss["survey"].counts()

                # st.dataframe(count_graph, key="count_graph", width="stretch")

def page_3():
    st.title("Individual Logs")
    log_items = list(ss.get("logs", {}).items())
    tab_labels = [name for name, _ in log_items]
    tabs = st.tabs(tab_labels)

    # Overview tab content

    # One tab per log - assumes the same layout in each
    for idx, (name, log) in enumerate(log_items, start=0):
        with tabs[idx]:
            period = st.selectbox(
                label="Resample period (minutes). Must be >= survey measurement period.",
                options=[1, 2, 5, 10, 15, 30, 60, 120],
                index=4,
                key=f"period_{name}"
            )
            period = str(period) + "min"
            graph_df = log.as_interval(t=period)
            st.markdown(f"## {name} time history plot")
            # TODO: Add option for user to choose which columns are required
            required_cols = [("Leq", "A"), ("Lmax", "A"), ("L90", "A")]
            if set(map(tuple, required_cols)).issubset(set(graph_df.columns.to_flat_index())):
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=graph_df.index,
                        y=graph_df[("Leq", "A")],
                        name="Leq A",
                        mode="lines",
                        line=dict(color=COLOURS["Leq A"], width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=graph_df.index,
                        y=graph_df[("L90", "A")],
                        name="L90 A",
                        mode="lines",
                        line=dict(color=COLOURS["L90 A"], width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=graph_df.index,
                        y=graph_df[("Lmax", "A")],
                        name="Lmax A",
                        mode="markers",
                        marker=dict(color=COLOURS["Lmax A"], size=3),
                    )
                )
                fig.update_layout(
                    template=TEMPLATE,
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis=dict(
                        title="Time & Date (hh:mm & dd/mm/yyyy)",
                        type="date",
                        tickformat="%H:%M<br>%d/%m/%Y",
                        tickangle=0,
                    ),
                    yaxis_title="Measured Sound Pressure Level dB(A)",
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0),
                    height=600,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"Required columns {required_cols} missing in {name}.")

            st.markdown(f"## {name} resampled data")
            st.dataframe(graph_df, key="master", width="stretch")

            # TODO: Enable value counts for other parameters
            # counts = pd.DataFrame([survey.counts().loc[name]["Daytime"], survey.counts().loc[name]["Night-time"]]).T
            # counts = survey.counts()
            st.dataframe(ss["counts"].loc[name], key=f"counts_df_{name}", width="stretch")

            st.markdown(f"## {name} L90 value counts")
            fig = ss["counts"].loc[name].plot.bar(facet_row="variable")
            st.plotly_chart(fig, key=f"counts_bar_{name}", config={
                "y": "Occurrences",
                "x": "dB",
                "color": "Period",
                "theme": None
            }) #TODO: These kwargs don't work.

pg = st.navigation([
    st.Page(page_1, title="Data Loader"),
    st.Page(page_2, title="Survey Overview"),
    st.Page(page_3, title="Individual Logs")
])

# Sidebar menu
with st.sidebar:
    st.text("This tool is a work in progress and may produce errors. Check results manually. Use at your own risk.")
    st.markdown("# Download Template CSV")
    df = get_data()
    csv = _convert_for_download(df)
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="pycoustic.csv",
        mime="text/csv",
        icon=":material/download:",
    )
    st.text(" ")
    st.text(
        "Known error: If you add data to your csv, and then delete some cells before uploading, the app may not like it. Fix: Once you have deleted the cells you need to, create a copy of your tab in Excel, and then delete the old tab. This makes a fresh CSV that the app can handle.")

pg.run()

        # st.bar_chart(counts, use_container_width=True)