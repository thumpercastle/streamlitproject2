import datetime as dt
import hashlib
import os
import tempfile
from typing import List
from uuid import uuid4

import pandas as pd
import pycoustic as pc
import streamlit as st

from streamlitproject2.app_state import (
    DEFAULT_PERIODS,
    build_survey,
    cleanup_tmp_files,
    convert_for_download,
    get_template_dataframe,
    init_app_state,
    parse_times,
    rerun_app,
)

st.set_page_config(page_title="pycoustic GUI", layout="wide")

ss = init_app_state()

st.title("Pycoustic Time History Calulator")
st.markdown(
    "> Upload CSV logs, adjust survey periods from the sidebar, then explore broadband insights and interactive graphs."
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
    st.markdown("**1. Upload logs**<br/>Use the primary button below or drag CSV files directly into the modal.", unsafe_allow_html=True)
with quick_cols[1]:
    st.markdown("**2. Review periods**<br/>Pick survey times from the sidebar so every page shares the same schedule.", unsafe_allow_html=True)
with quick_cols[2]:
    st.markdown("**3. Explore outputs**<br/>Head to Analysis & Visualisation or Interactive Graphs once logs are ready.", unsafe_allow_html=True)

if logs_loaded:
    st.success(f"{logs_loaded} log(s) ready for analysis. Jump to Analysis or Interactive Graphs when you’re set.")
else:
    st.warning("No logs uploaded yet. Use the **Upload CSV logs** button below to get started.")

template_df = get_template_dataframe()
action_cols = st.columns(2)
with action_cols[0]:
    if st.button("Upload CSV logs", type="primary", icon=":material/upload_file:", use_container_width=True):
        ss["show_upload_modal"] = True
        rerun_app()
with action_cols[1]:
    st.download_button(
        label="Download template CSV",
        data=convert_for_download(template_df),
        file_name="pycoustic-template.csv",
        mime="text/csv",
        icon=":material/download:",
        use_container_width=True,
        key="home_template_download",
    )

st.divider()


def _to_time(hours: int, minutes: int) -> dt.time:
    return dt.time(hours, minutes)


def _format_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {units[-1]}"


def _update_pending_uploads(new_entries: List[dict]) -> None:
    ss["pending_uploads"] = new_entries


def _reset_workspace() -> None:
    cleanup_tmp_files(ss.get("tmp_paths", []))
    ss["tmp_paths"] = []
    ss["logs"] = {}
    ss["resi_df"] = pd.DataFrame()
    ss["leq_df"] = pd.DataFrame()
    ss["lmax_df"] = pd.DataFrame()
    ss["modal_df"] = pd.DataFrame()
    ss["resampled_df"] = pd.DataFrame()
    ss["resampled_dfs"] = {}
    ss["pending_uploads"] = []
    ss["num_logs"] = 0
    ss["last_upload_ts"] = None
    ss["global_resample_period"] = 15
    rerun_app()


dialog_decorator = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)


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
        st.info("No files staged yet. Drag-and-drop CSV files above to begin.", icon=":material/upload_file:")

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
            rerun_app()

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
            rerun_app()


if dialog_decorator:
    def _upload_dialog_decorator():
        try:
            return dialog_decorator("Upload CSV logs", width="large")
        except TypeError:
            return dialog_decorator("Upload CSV logs")

    @_upload_dialog_decorator()
    def show_upload_modal() -> None:
        _render_upload_modal_contents()
else:
    def show_upload_modal() -> None:
        st.info("This Streamlit version does not support modal dialogs; showing the uploader inline instead.")
        with st.container():
            _render_upload_modal_contents()


if ss.get("show_upload_modal"):
    show_upload_modal()

with st.expander("Quick tips", expanded=False):
    st.markdown(
        """
- Upload and rename logs above before importing them into the workspace.
- Adjust survey periods from the sidebar; evening outputs disable automatically if they match night start times.
- Visit **Analysis & Visualisation** for broadband summaries, spectra, and modal datasets.
- Jump to **Interactive Graphs** to tailor colours and resampling across all logs.
"""
    )

with st.sidebar:
    current_periods = ss.get("period_times", DEFAULT_PERIODS.copy())
    with st.expander("Survey periods", expanded=False):
        day_start = st.time_input(
            "Day starts",
            value=_to_time(*current_periods["day"]),
            key="sidebar_time_day",
        )
        evening_start = st.time_input(
            "Evening starts",
            value=_to_time(*current_periods["evening"]),
            key="sidebar_time_evening",
        )
        night_start = st.time_input(
            "Night starts",
            value=_to_time(*current_periods["night"]),
            key="sidebar_time_night",
        )
        selected_periods = parse_times(day_start, evening_start, night_start)
        if selected_periods != current_periods:
            ss["period_times"] = selected_periods
            ss["survey"] = build_survey(times=selected_periods)
        if selected_periods["evening"] == selected_periods["night"]:
            st.caption("Evening outputs are currently disabled because evening matches the night start.")

    resample_options = [1, 2, 5, 10, 15, 30, 60, 120]
    current_resample = ss.get("global_resample_period", 15)
    with st.expander("Resample period", expanded=True):
        resample_choice = st.selectbox(
            "Resample interval (minutes)",
            options=resample_options,
            index=resample_options.index(current_resample),
            key="global_resample_selector",
        )
        if resample_choice != current_resample:
            ss["global_resample_period"] = resample_choice
            ss["graph_resample_period"] = resample_choice

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
