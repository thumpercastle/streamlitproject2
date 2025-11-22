import os
import tempfile
import datetime as dt
import streamlit as st
import pycoustic as pc
import pandas as pd
from typing import Dict, Tuple
import plotly.graph_objects as go

# NEW imports for modal uploader
import hashlib
from uuid import uuid4
from typing import List

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

st.set_page_config(page_title="pycoustic GUI", layout="wide")
st.title("pycoustic Streamlit GUI")

#TODO: Evening periods don't work on Streamlit
#TODO: Move 'Lmax period' drop down into Lmax tab
#TODO: Add modal and counts bar chart
#TODO: Add titles to graphs
#TODO: Tidy buttons and info on graph page.


#TODO: Add option for user input for log names.
# ---------------------------------------------------------------------------
# Modal uploader helpers
# ---------------------------------------------------------------------------

def _update_pending_uploads(queue: List[Dict]) -> None:
    ss["pending_uploads"] = queue


def _format_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


_dialog_decorator = getattr(st, "experimental_dialog", None)


def _render_upload_modal_contents() -> None:
    uploaded_files = st.file_uploader(
        "Select CSV files",
        type=["csv"],
        accept_multiple_files=True,
        key="modal_log_uploader",
        help="You can add multiple CSV files at once.",
    )

    queue = ss.get("pending_uploads", [])
    known_hashes = {item["hash"] for item in queue}

    for uploaded in uploaded_files or []:
        file_bytes = uploaded.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        if file_hash in known_hashes:
            continue
        known_hashes.add(file_hash)
        queue.append(
            {
                "id": uuid4().hex,
                "original_name": uploaded.name,
                "hash": file_hash,
                "data": file_bytes,
                "custom_name": os.path.splitext(os.path.basename(uploaded.name))[0],
                "size": len(file_bytes),
            }
        )

    removal_ids: List[str] = []
    for item in queue:
        name_col, action_col = st.columns([3, 1])
        with name_col:
            label = f"Name for {item['original_name']}"
            item["custom_name"] = st.text_input(
                label=label,
                value=item.get("custom_name", ""),
                key=f"log_name_{item['id']}",
                help="Enter a unique name for this log.",
            ).strip()
        with action_col:
            if st.button("Remove", key=f"remove_{item['id']}", use_container_width=True):
                removal_ids.append(item["id"])

    if removal_ids:
        queue = [item for item in queue if item["id"] not in removal_ids]
        for removed_id in removal_ids:
            st.session_state.pop(f"log_name_{removed_id}", None)

    _update_pending_uploads(queue)

    if queue:
        table_data = [
            {
                "Original name": item["original_name"],
                "Custom name": item.get("custom_name", ""),
                "Size": _format_bytes(item["size"]),
            }
            for item in queue
        ]
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
    else:
        st.info("No files staged yet. Drag-and-drop CSV files above to begin.")

    add_col, close_col = st.columns([3, 1])
    with add_col:
        add_clicked = st.button(
            f"Add {len(queue)} file(s) as logs" if queue else "Add files as logs",
            disabled=not queue,
            use_container_width=True,
            key="modal_add_logs",
        )
    with close_col:
        if st.button("Close", use_container_width=True, key="modal_close_logs"):
            ss["show_upload_modal"] = False
            st.rerun()

    if add_clicked and queue:
        existing_names = set(ss["logs"].keys())
        succeeded_ids: List[str] = []
        added = 0

        for item in list(queue):
            default_name = os.path.splitext(os.path.basename(item["original_name"]))[0]
            custom_name = item.get("custom_name") or default_name
            if not custom_name:
                st.error(f"Name for {item['original_name']} cannot be empty.")
                continue

            sanitized_name = custom_name
            suffix = 1
            while sanitized_name in existing_names:
                sanitized_name = f"{custom_name}-{suffix}"
                suffix += 1
            existing_names.add(sanitized_name)

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
            succeeded_ids.append(item["id"])
            added += 1

        if added:
            ss["last_upload_ts"] = dt.datetime.now()
            ss["num_logs"] = len(ss["logs"])
            for upload_id in succeeded_ids:
                st.session_state.pop(f"log_name_{upload_id}", None)
            queue = [item for item in queue if item["id"] not in succeeded_ids]
            _update_pending_uploads(queue)
            st.success(f"Added {added} log(s).")
            if not queue:
                ss["show_upload_modal"] = False
            st.rerun()


if _dialog_decorator:
    def _upload_dialog_decorator():
        try:
            return _dialog_decorator("Upload CSV logs", width="large")
        except TypeError:
            return _dialog_decorator("Upload CSV logs")

    @_upload_dialog_decorator()
    def show_upload_modal() -> None:
        _render_upload_modal_contents()
else:
    def show_upload_modal() -> None:
        st.info("This Streamlit version does not support modal dialogs; showing the uploader inline instead.")
        with st.container():
            _render_upload_modal_contents()


# ---------------------------------------------------------------------------
# Main-page uploader launcher + current logs as pill tags
# ---------------------------------------------------------------------------

upload_col, logs_col = st.columns([1.2, 1])

with upload_col:
    st.subheader("Upload CSV logs")
    st.write("Add one or more CSV files as pycoustic logs.")

    if st.button("Open CSV upload dialog", use_container_width=True):
        ss["show_upload_modal"] = True
        st.rerun()

    if ss.get("last_upload_ts"):
        st.caption(f"Last upload: {ss['last_upload_ts']}")

with logs_col:
    st.subheader("Current Logs")

    logs = ss.get("logs", {})
    num_logs = len(logs)

    if num_logs:
        tags_html = """
        <style>
        .log-tags-container {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-bottom: 0.5rem;
        }
        .log-tag {
            display: inline-flex;
            align-items: center;
            padding: 0.15rem 0.5rem;
            border-radius: 999px;
            background-color: #f0f2f6;
            color: #262730;
            font-size: 0.8rem;
            border: 1px solid rgba(49, 51, 63, 0.15);
            white-space: nowrap;
        }
        .log-tag-count {
            font-size: 0.85rem;
            margin-bottom: 0.25rem;
            color: #4b4b4b;
        }
        </style>
        """

        tags_html += '<div class="log-tag-count">'
        tags_html += f"{num_logs} log{'s' if num_logs != 1 else ''} loaded:"
        tags_html += "</div>"

        tags_html += '<div class="log-tags-container">'
        for name in logs.keys():
            safe_name = str(name).replace("<", "&lt;").replace(">", "&gt;")
            tags_html += f'<span class="log-tag">{safe_name}</span>'
        tags_html += "</div>"

        st.markdown(tags_html, unsafe_allow_html=True)
    else:
        st.info("No logs loaded yet.")

    if st.button("Reset", use_container_width=True):
        _cleanup_tmp_files(ss.get("tmp_paths", []))
        ss["tmp_paths"] = []
        ss["logs"] = {}
        ss["resi_df"] = pd.DataFrame()
        ss["leq_df"] = pd.DataFrame()
        ss["lmax_df"] = pd.DataFrame()
        ss["modal_df"] = pd.DataFrame()
        ss["pending_uploads"] = []
        ss["num_logs"] = 0
        ss["last_upload_ts"] = None
        st.rerun()

if ss.get("show_upload_modal"):
    show_upload_modal()

# Build the survey
survey = pc.Survey()
for name, lg in ss["logs"].items():
    survey.add_log(data=lg, name=name)

survey.set_periods(times=default_times)

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
    st.markdown("# Survey Config")
    st.markdown("## Set Time Periods")
    day_start = st.time_input("Set Day Period Start", dt.time(7, 00), on_change=st.rerun)
    evening_start = st.time_input("Set Evening Period Start", dt.time(23, 00), on_change=st.rerun)
    night_start = st.time_input("Set Night Period Start", dt.time(23, 00), on_change=st.rerun)
    st.text("If Evening starts at the same time as Night, Evening periods will be disabled (default). Night must cross over midnight")
    times = parse_times(day_start, evening_start, night_start)
    survey.set_periods(times=times)
    st.text(" ")
    st.text("Known error: If you add data to your csv, and then delete some cells before uploading, the app may not like it. Fix: Once you have deleted the cells you need to, create a copy of your tab in Excel, and then delete the old tab. This makes a fresh CSV that the app can handle.")


st.divider()
#TODO: Implement tabs with graphs for each log.

# Line 151: create tabs dynamically for each log in ss["logs"], with an Overview tab first
log_items = list(ss.get("logs", {}).items())

tab_labels = ["Overview"] + [name for name, _ in log_items]
tabs = st.tabs(tab_labels)

# Overview tab content
with tabs[0]:
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
                    df = survey.resi_summary()  # Always a DataFrame per your note
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
                    df = survey.leq_spectra()  # Always a DataFrame per your note
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
                    df = survey.lmax_spectra(n=nth, t=t_str, period=per)  # Always a DataFrame per your note
                    ss["lmax_df"] = df
                    st.success(f"Lmax spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    # Notify user if evening period disabled
                    if per == "evenings" and times["evening"] == times["night"]:
                        st.info("Evenings are currently disabled. Enable them by setting the times in the sidebar.")
                    if not ss["lmax_df"].empty:
                        st.dataframe(ss["lmax_df"], key="lmax_df", width="stretch")
                    else:
                        st.info("Run lmax_spectra() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute lmax_spectra: {e}")

        st.divider()


        # Compute and display resi_summary directly from current logs
        st.subheader("Modal values")
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
                    df = survey.modal(
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


# One tab per log - assumes the same layout in each
for idx, (name, log) in enumerate(log_items, start=1):
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

        # TODO: Value counts
        # counts = pd.DataFrame([survey.counts().loc[name]["Daytime"], survey.counts().loc[name]["Night-time"]]).T
        # st.bar_chart(counts, use_container_width=True)