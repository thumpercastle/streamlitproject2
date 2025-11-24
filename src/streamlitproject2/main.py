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
    convert_for_download,
    _cleanup_tmp_files,
    parse_times,
    default_times
)

ss = init_app_state()


#TODO: Evening periods don't work on Streamlit
#TODO: Move 'Lmax period' drop down into Lmax tab
#TODO: Add modal and counts bar chart
#TODO: Add titles to graphs
#TODO: Tidy buttons and info on graph page.


#TODO: Add option for user input for log names.
# TODO: Add option for user input for log names.



def page_1():
    st.set_page_config(page_title="pycoustic GUI", layout="wide")
    st.title("Data Loader")


    # Button to open the Data Loader dialog
    if st.button("Open Data Loader"):
        open_loader = True
    else:
        open_loader = False

    if open_loader:

        @st.dialog("Data Loader", width="large")
        def data_loader_dialog():
            col_add, col_reset = st.columns([1, 1])
            with col_add:
                st.subheader("1. Upload CSV logs")

                # Stage files into a "pending uploads" queue with custom names and removal support
                uploaded_files = st.file_uploader(
                    "Choose one or more CSV files",
                    type=["csv"],
                    accept_multiple_files=True,
                    help="You can add multiple CSV files at once.",
                    key="inline_log_uploader",
                )

                # Initialise or retrieve current queue
                queue = ss.get("pending_uploads", [])
                # Track names already in queue to avoid simple duplicates by original name
                known_original_names = {item["original_name"] for item in queue}

                for uploaded in uploaded_files or []:
                    if uploaded.name in known_original_names:
                        # Skip if an item with the same original name is already staged
                        continue
                    known_original_names.add(uploaded.name)
                    file_bytes = uploaded.getvalue()
                    default_name = os.path.splitext(os.path.basename(uploaded.name))[0]
                    queue.append(
                        {
                            "original_name": uploaded.name,
                            "data": file_bytes,
                            "custom_name": default_name,
                            "size": len(file_bytes),
                        }
                    )

                # Allow user to edit names and remove staged files
                removal_indices = []
                for idx, item in enumerate(queue):
                    name_col, action_col = st.columns([3, 1])
                    with name_col:
                        label = f"Name for {item['original_name']}"
                        item["custom_name"] = st.text_input(
                            label=label,
                            value=item.get("custom_name", ""),
                            key=f"log_name_pending_{idx}",
                            help="Enter a unique name for this log.",
                        ).strip()
                    with action_col:
                        if st.button("Remove", key=f"remove_pending_{idx}", use_container_width=True):
                            removal_indices.append(idx)

                # Apply removals from queue and clean up any associated text inputs
                if removal_indices:
                    for idx in sorted(removal_indices, reverse=True):
                        st.session_state.pop(f"log_name_pending_{idx}", None)
                        queue.pop(idx)

                # Persist updated queue back to session state
                ss["pending_uploads"] = queue

                # Final action: add staged files as logs
                add_clicked = st.button(
                    f"Add {len(queue)} file(s) as logs" if queue else "Add files as logs",
                    disabled=not queue,
                    use_container_width=True,
                    key="inline_add_logs",
                )

                if add_clicked and queue:
                    existing_names = set(ss["logs"].keys())
                    added = 0

                    # Work on a copy because we may clear queue after success
                    for item in list(queue):
                        default_name = os.path.splitext(os.path.basename(item["original_name"]))[0]
                        custom_name = item.get("custom_name") or default_name
                        if not custom_name:
                            st.error(f"Name for {item['original_name']} cannot be empty.")
                            continue

                        # Ensure uniqueness
                        sanitized_name = custom_name
                        suffix = 1
                        while sanitized_name in existing_names:
                            sanitized_name = f"{custom_name}-{suffix}"
                            suffix += 1
                        existing_names.add(sanitized_name)

                        # Persist the uploaded file to a temporary path for pycoustic to read
                        tmp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
                        tmp_file.write(item["data"])
                        tmp_file.flush()
                        tmp_file.close()
                        ss["tmp_paths"].append(tmp_file.name)

                        try:
                            log = pc.Log(tmp_file.name)
                        except Exception as exc:
                            st.error(f"Failed to create Log from {item['original_name']}: {exc}")
                            continue

                        ss["logs"][sanitized_name] = log
                        added += 1

                    if added:
                        ss["last_upload_ts"] = dt.datetime.now()
                        ss["num_logs"] = len(ss["logs"])
                        ss["pending_uploads"] = []
                        # Clear name inputs for a clean state next time
                        for key in list(st.session_state.keys()):
                            if key.startswith("log_name_pending_"):
                                st.session_state.pop(key, None)
                        st.success(f"Added {added} log(s).")
                        st.rerun()

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
    day_start = st.time_input("Set Day Period Start", dt.time(7, 00), on_change=st.rerun)
    evening_start = st.time_input("Set Evening Period Start", dt.time(23, 00), on_change=st.rerun)
    night_start = st.time_input("Set Night Period Start", dt.time(23, 00), on_change=st.rerun)
    st.text(
        "If Evening starts at the same time as Night, Evening periods will be disabled (default). Night must cross over midnight")
    times = parse_times(day_start, evening_start, night_start)
    ss["times"] = times
    survey.set_periods(times=times)

    # Sidebar menu
    with st.sidebar:
        st.text("This tool is a work in progress and may produce errors. Check results manually. Use at your own risk.")
        st.markdown("# Download Template CSV")
        df = get_data()
        csv = convert_for_download(df)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="pycoustic.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        st.text(" ")
        st.text("Known error: If you add data to your csv, and then delete some cells before uploading, the app may not like it. Fix: Once you have deleted the cells you need to, create a copy of your tab in Excel, and then delete the old tab. This makes a fresh CSV that the app can handle.")

    st.divider()
    #TODO: Implement tabs with graphs for each log.

    # Line 151: create tabs dynamically for each log in ss["logs"], with an Overview tab first

def page_2():
    st.title("Survey Overview")
    st.header("Overview")
    log_items = list(ss.get("logs", {}).items())
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
pg.run()

        # st.bar_chart(counts, use_container_width=True)