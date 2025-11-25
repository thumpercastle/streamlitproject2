import os
import hashlib
import pandas as pd
import pycoustic as pc
import streamlit as st
import datetime as dt
from typing import Dict, Tuple
from uuid import uuid4



# Graph colour palette config
COLOURS = {
    "Leq A": "#FBAE18",   # light grey
    "L90 A": "#4d4d4d",   # dark grey
    "Lmax A": "#B51724",  # red
}
# Graph template config
TEMPLATE = "plotly"

default_times = {"day": (7, 0), "evening": (23, 0), "night": (23, 0)}

# Session state
def init_app_state() -> st.session_state:
    ss = st.session_state
    ss.setdefault("tmp_paths", [])
    ss.setdefault("logs", {})          # Dict[str, pc.Log]
    ss.setdefault("resi_df", pd.DataFrame())
    ss.setdefault("leq_df", pd.DataFrame())
    ss.setdefault("lmax_df", pd.DataFrame())
    ss.setdefault("modal_df", pd.DataFrame())
    ss.setdefault("counts", pd.DataFrame())
    ss.setdefault("survey", pc.Survey())
    ss.setdefault("num_logs", 0)
    ss.setdefault("pending_uploads", [])
    ss.setdefault("last_upload_ts", None)
    ss.setdefault("times", default_times)
    ss.setdefault("show_upload_modal", False)
    pd.options.plotting.backend = "plotly"
    return ss


@st.cache_data
def get_data():
    df = pd.DataFrame(
        columns=["Time", "Leq A", "Lmax A", "L90 A",
                 "Leq 63", "Leq 125", "Leq 250", "Leq 500", "Leq 1000", "Leq 2000", "Leq 4000", "Leq 8000",
                 "Lmax 63", "Lmax 125", "Lmax 250", "Lmax 500", "Lmax 1000", "Lmax 2000", "Lmax 4000", "Lmax 8000",
                 "L90 63", "L90 125", "L90 250", "L90 500", "L90 1000", "L90 2000", "L90 4000", "L90 8000"]
    )
    return df

@st.cache_data
def convert_for_download(df):
    return df.to_csv(index=False).encode("utf-8")


def _cleanup_tmp_files(paths):
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass

def parse_times(day_start: dt.time, evening_start: dt.time, night_start: dt.time) -> Dict[str, Tuple[int, int]]:
    """
    Convert datetime.time objects to a dict of (hour, minute) tuples.

    Example output:
        {"day": (7, 0), "evening": (23, 0), "night": (23, 0)}
    """
    def to_hm(t: dt.time) -> Tuple[int, int]:
        if not isinstance(t, dt.time):
            raise TypeError(f"Expected datetime.time, got {type(t).__name__}")
        return t.hour, t.minute

    t = {
        "day": to_hm(day_start),
        "evening": to_hm(evening_start),
        "night": to_hm(night_start),
    }
    return t

# --- Helper: format bytes nicely ---
def _format_bytes(num_bytes: int) -> str:
    """
    Convert a byte count into a human-readable string, e.g. '123 KB'.
    """
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        num_bytes /= 1024.0
        if num_bytes < 1024.0:
            return f"{num_bytes:0.2f} {unit}"
    return f"{num_bytes:0.2f} PB"


# --- Helper: central place to update queue in session state ---
def _update_pending_uploads(queue: list[dict]) -> None:
    """
    Store the pending upload queue in Streamlit session_state.
    """
    st.session_state["pending_uploads"] = queue


# --- Helper: trigger a rerun; kept as a small wrapper ---
def rerun_app() -> None:
    st.rerun()


def _render_upload_modal_contents() -> None:
    """
    Render the contents of the CSV upload modal.

    Uses session_state keys:
        pending_uploads  : list[dict] of staged uploads
        logs             : mapping of name -> pc.Log
        tmp_paths        : list of temporary file paths
        show_upload_modal: bool, whether modal is open
        last_upload_ts   : datetime of last successful upload
        num_logs         : int, number of logs loaded
    """
    ss = st.session_state

    # Ensure required keys exist
    ss.setdefault("pending_uploads", [])
    ss.setdefault("logs", {})
    ss.setdefault("tmp_paths", [])
    ss.setdefault("show_upload_modal", False)
    ss.setdefault("last_upload_ts", None)
    ss.setdefault("num_logs", 0)

    uploaded_files = st.file_uploader(
        "Select CSV files",
        type=["csv"],
        accept_multiple_files=True,
        key="modal_log_uploader",
        help="You can add multiple CSV files at once.",
    )

    # Pending uploads in session state
    queue: list[dict] = ss.get("pending_uploads", [])
    # Use content hash to avoid duplicates of the same file
    known_hashes = {item["hash"] for item in queue if "hash" in item}

    for uploaded in uploaded_files or []:
        file_bytes = uploaded.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        if file_hash in known_hashes:
            # Skip already-staged file with same content
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

    # Allow user to rename or remove staged items
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

    # Apply removals and clean any associated text inputs
    if removal_ids:
        queue = [item for item in queue if item["id"] not in removal_ids]
        for removed_id in removal_ids:
            ss.pop(f"log_name_{removed_id}", None)

    _update_pending_uploads(queue)

    # Show a simple table of staged files
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

    # Action buttons: Add + Close
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

    # When "Add" is clicked, convert staged uploads to pc.Log objects
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

            # Ensure the final log name is unique
            sanitized_name = custom_name
            suffix = 1
            while sanitized_name in existing_names:
                sanitized_name = f"{custom_name}-{suffix}"
                suffix += 1
            existing_names.add(sanitized_name)

            # Save bytes to a temporary CSV for pycoustic to read
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
            # Clear name widgets for successfully added uploads
            for upload_id in succeeded_ids:
                ss.pop(f"log_name_{upload_id}", None)
            # Keep only the ones that failed (if any)
            queue = [item for item in queue if item["id"] not in succeeded_ids]
            _update_pending_uploads(queue)
            st.success(f"Added {added} log(s).")
            if not queue:
                ss["show_upload_modal"] = False
            rerun_app()

