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
    _reset_workspace,
    _build_survey
)

ss = init_app_state()

def page_2():
    st.title("Analysis & Visualisation")
    st.markdown(
        "> Explore broadband summaries, spectra, modal values, and download-ready datasets derived from your uploaded logs."
    )

    logs_available = list(ss["logs"].keys())

    if not logs_available:
        st.warning("No logs have been uploaded yet. Use the Home page to add data.", icon=":material/info:")
        st.stop()

    logs_loaded = len(ss["logs"])
    # resample_options = [1, 2, 5, 10, 15, 30, 60, 120]
    # current_resample = ss.get("global_resample_period", 15)
    # if current_resample not in resample_options:
    #     current_resample = 15
    # ss["global_resample_period"] = current_resample

    default_selection = ss.get("analysis_selected_logs") or logs_available

    selected_logs = st.multiselect(
        "Select logs to include in the survey calculations",
        options=logs_available,
        default=default_selection,
        key="analysis_log_filter",
        help="Results update immediately when you add or remove logs.",
        on_change=st.rerun
    )

    if not selected_logs:
        st.warning("Select at least one log to display analysis outputs.", icon=":material/select_all:")
        st.stop()

    ss["analysis_selected_logs"] = selected_logs

    period_times = ss.get("period_times")
    ss["survey"] = _build_survey(times=period_times, log_names=selected_logs)

    st.subheader("Summary datasets")
    # filters = ss.setdefault("overview_filters", {"lmax_period": "nights"})

    # lmax_options = ["days", "evenings", "nights"]
    # default_lmax = filters.get("lmax_period", "nights")
    # if default_lmax not in lmax_options:
    #     default_lmax = "nights"
    # lmax_period = st.selectbox(
    #     "Lmax period",
    #     options=lmax_options,
    #     index=lmax_options.index(default_lmax),
    #     key="lmax_period_selector",
    # )
    # ss["overview_filters"]["lmax_period"] = lmax_period

    summary_tabs = st.tabs(
        [
            "Broadband summary",
            "Leq spectra",
            "Lmax spectra",
            "Modal and counts",
        ]
    )

    log_items = list(ss.get("logs", {}).items())

    if not log_items:
        st.info("No logs loaded yet.")
    else:

        # Broadband tab
        with summary_tabs[0]:
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

            # Leq tab
            with summary_tabs[1]:
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

        with summary_tabs[2]:
            lmax_container = st.container()

            with lmax_container:
                st.subheader("Lmax Spectra")
                st.text(
                    "Note: the timestamp in the 'Date' column shows the date when the night-time period started, not the date on which the lmax occurred. e.g. 2025-08-14 00:14 lmax would have occured in the early hours of 2025-08-15.")
                st.text(
                    "This function works by selecting the highest A-weighted value, and the corresponding octave band data.")
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


        with summary_tabs[3]:
            st.subheader("Modal and Value Counts")
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

                try:
                    df = ss["survey"].counts(
                        cols=par_tup,
                        day_t=day_t,
                        evening_t=eve_t,
                        night_t=night_t
                    )
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

                st.divider()




                # # One tab per log - assumes the same layout in each
                # for idx, (name, log) in enumerate(log_items, start=0):
                #     st.markdown(f"## {name} L90 value counts")
                #     fig = ss["counts"].loc[name].plot.bar(facet_row="variable")
                #     st.plotly_chart(fig, key=f"counts_bar_{name}", config={
                #         "y": "Occurrences",
                #         "x": "dB",
                #         "color": "Period",
                #         "theme": None
                #     })  # TODO: These kwargs don't work.


                # st.dataframe(count_graph, key="count_graph", width="stretch")
