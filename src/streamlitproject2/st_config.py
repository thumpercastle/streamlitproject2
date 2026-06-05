import datetime as dt
import hashlib
import io
import os
import tempfile
from typing import Dict, Iterable, Tuple
from uuid import uuid4

import pandas as pd
import pycoustic as pc
import streamlit as st

COLOURS = {
    "Leq A": "#FBAE18",
    "L90 A": "#4d4d4d",
    "Lmax A": "#B51724",
}

TEMPLATE = "plotly"

default_times = {
    "day": (7, 0),
    "evening": (23, 0),
    "night": (23, 0),
}

TEMPLATE_COLUMNS = [
    "Time",
    "Leq A",
    "Lmax A",
    "L90 A",
    "Leq 63",
    "Leq 125",
    "Leq 250",
    "Leq 500",
    "Leq 1000",
    "Leq 2000",
    "Leq 4000",
    "Leq 8000",
    "Lmax 63",
    "Lmax 125",
    "Lmax 250",
    "Lmax 500",
    "Lmax 1000",
    "Lmax 2000",
    "Lmax 4000",
    "Lmax 8000",
    "L90 63",
    "L90 125",
    "L90 250",
    "L90 500",
    "L90 1000",
    "L90 2000",
    "L90 4000",
    "L90 8000",
]


def init_app_state():
    ss = st.session_state
    ss.setdefault("lmax_n", 10)
    ss.setdefault("lmax_t", 2)
    ss.setdefault("tmp_paths", [])
    ss.setdefault("logs", {})
    ss.setdefault("broadband_df", pd.DataFrame())
    ss.setdefault("leq_df", pd.DataFrame())
    ss.setdefault("lmax_df", pd.DataFrame())
    ss.setdefault("modal_df", pd.DataFrame())
    ss.setdefault("counts", pd.DataFrame())
    ss.setdefault("survey", None)
    ss.setdefault("num_logs", 0)
    ss.setdefault("pending_uploads", [])
    ss.setdefault("last_upload_ts", None)
    ss.setdefault("times", default_times.copy())
    ss.setdefault("show_upload_modal", False)
    ss.setdefault("counts_facet_overlap", False)
    ss.setdefault("counts_include_all", False)
    ss.setdefault("counts_all_t", "15min")
    ss.setdefault("modal_params", [("L90", "A"), "60min", "60min", "15min"])
    ss.setdefault("l90_averaging", "log")
    ss.setdefault("analysis_selected_logs", [])
    ss.setdefault("weather_country", "GB")
    ss.setdefault("weather_postcode", "")
    ss.setdefault("weather_units", "metric")
    ss.setdefault("weather_interval_hours", 12)
    ss.setdefault("weather_timeout_s", 30)
    ss.setdefault("owm_api_key", "")
    ss.setdefault("weather_df", pd.DataFrame())
    ss.setdefault("weather_show_raw", False)
    pd.options.plotting.backend = "plotly"
    return ss


@st.cache_data
def get_data() -> pd.DataFrame:
    return pd.DataFrame(columns=TEMPLATE_COLUMNS)


@st.cache_data
def to_csv_preserve_multiheader(df: pd.DataFrame) -> bytes:
    if df is None:
        return b""
    return df.to_csv(index=True).encode("utf-8")


@st.cache_data
def convert_for_download(df: pd.DataFrame) -> bytes:
    if df is None:
        return b""
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data
def _convert_for_download(df: pd.DataFrame) -> bytes:
    if df is None:
        return b""
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data
def _get_template_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=TEMPLATE_COLUMNS)


def _cleanup_tmp_files(paths) -> None:
    for path in paths or []:
        try:
            os.remove(path)
        except Exception:
            pass


def parse_times(
        day_start: dt.time,
        evening_start: dt.time,
        night_start: dt.time,
) -> Dict[str, Tuple[int, int]]:
    def to_hm(value: dt.time) -> Tuple[int, int]:
        if not isinstance(value, dt.time):
            raise TypeError(f"Expected datetime.time, got {type(value).__name__}")
        return value.hour, value.minute

    return {
        "day": to_hm(day_start),
        "evening": to_hm(evening_start),
        "night": to_hm(night_start),
    }


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    size = float(num_bytes)
    for unit in ["KB", "MB", "GB", "TB"]:
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.2f} {unit}"
    return f"{size:.2f} PB"


def _update_pending_uploads(queue: list[dict]) -> None:
    st.session_state["pending_uploads"] = queue


def _render_upload_modal_contents() -> None:
    uploaded_files = st.file_uploader(
        "Select CSV files",
        type=["csv"],
        accept_multiple_files=True,
        key="modal_log_uploader",
        help="You can add multiple CSV files at once.",
    )

    ss = st.session_state
    queue = ss.get("pending_uploads", [])
    known_hashes = {item["hash"] for item in queue if "hash" in item}

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

    removal_ids: list[str] = []
    for item in queue:
        name_col, action_col = st.columns([3, 1])
        with name_col:
            item["custom_name"] = st.text_input(
                label=f"Name for {item['original_name']}",
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
        st.info("No files staged yet. Drag and drop CSV files above to begin.")

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
        succeeded_ids: list[str] = []
        added = 0

        for item in list(queue):
            default_name = os.path.splitext(os.path.basename(item["original_name"]))[0]
            custom_name = item.get("custom_name") or default_name

            if not custom_name:
                st.error(f"Name for {item['original_name']} cannot be empty.")
                continue

            final_name = custom_name
            suffix = 1
            while final_name in existing_names:
                final_name = f"{custom_name}-{suffix}"
                suffix += 1
            existing_names.add(final_name)

            tmp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
            tmp_file.write(item["data"])
            tmp_file.flush()
            tmp_file.close()
            ss["tmp_paths"].append(tmp_file.name)

            try:
                log = pc.Log(tmp_file.name)
            except Exception as exc:
                st.error(f"Failed to create log from {item['original_name']}: {exc}")
                continue

            ss["logs"][final_name] = log
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


def _reset_workspace() -> None:
    ss = st.session_state
    _cleanup_tmp_files(ss.get("tmp_paths", []))
    ss["tmp_paths"] = []
    ss["logs"] = {}
    ss["broadband_df"] = pd.DataFrame()
    ss["leq_df"] = pd.DataFrame()
    ss["lmax_df"] = pd.DataFrame()
    ss["modal_df"] = pd.DataFrame()
    ss["counts"] = pd.DataFrame()
    ss["weather_df"] = pd.DataFrame()
    ss["survey"] = None
    ss["pending_uploads"] = []
    ss["num_logs"] = 0
    ss["last_upload_ts"] = None
    ss["analysis_selected_logs"] = []
    ss["show_upload_modal"] = False
    ss["times"] = default_times.copy()
    ss["lmax_n"] = 10
    ss["lmax_t"] = 2
    ss["modal_params"] = [("L90", "A"), "60min", "60min", "15min"]
    ss["l90_averaging"] = "log"
    ss["counts_include_all"] = False
    ss["counts_all_t"] = "15min"
    st.rerun()


def _export_frames_to_excel(frames: dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, frame in frames.items():
            if frame is None or frame.empty:
                continue
            export_frame = frame.copy()
            if isinstance(export_frame.columns, pd.MultiIndex):
                export_frame.columns = [
                    " | ".join(str(level) for level in col if level not in (None, ""))
                    for col in export_frame.columns.to_flat_index()
                ]
            if isinstance(export_frame.index, pd.MultiIndex):
                export_frame = export_frame.reset_index()
            export_frame.to_excel(writer, sheet_name=(sheet_name[:31] or "Sheet1"), index=False)
    output.seek(0)
    return output.getvalue()


def _build_survey(
        times: Dict[str, Tuple[int, int]] | None = None,
        log_names: Iterable[str] | None = None,
) -> pc.Survey:
    survey = pc.Survey()
    logs = st.session_state.get("logs", {})

    if log_names:
        for name in log_names:
            if name in logs:
                survey.add_log(data=logs[name], name=name)
    else:
        for name, log in logs.items():
            survey.add_log(data=log, name=name)

    if times:
        survey.set_periods(times=times)

    return survey


def _fmt_time_value(value) -> str:
    if isinstance(value, dt.time):
        return value.strftime("%H:%M")
    if isinstance(value, tuple) and len(value) == 2:
        hh, mm = value
        return f"{int(hh):02d}:{int(mm):02d}"
    if value is None:
        return "—"
    return str(value)


def _fmt_int_value(value) -> str:
    if value is None:
        return "—"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _section_to_csv(
        title: str,
        params: list[tuple[str, str]],
        df: pd.DataFrame | None,
) -> str:
    lines: list[str] = [f"# {title}"]

    if params:
        lines.append("# Parameters")
        for key, value in params:
            lines.append(f"{key},{value}")
    else:
        lines.append("# Parameters,None")

    lines.append("")

    if df is None or getattr(df, "empty", True):
        lines.append("# (no data)")
        return "\n".join(lines)

    lines.append(df.to_csv(index=True, lineterminator="\n").rstrip("\n"))
    return "\n".join(lines)


@st.cache_data
def build_combined_csv_with_sections(
        broadband_df: pd.DataFrame | None,
        leq_df: pd.DataFrame | None,
        lmax_df: pd.DataFrame | None,
        modal_df: pd.DataFrame | None,
        counts_df: pd.DataFrame | None,
        *,
        day_start=None,
        evening_start=None,
        night_start=None,
        lmax_n=None,
        lmax_t=None,
        modal_param=None,
        day_t=None,
        evening_t=None,
        night_t=None,
) -> bytes:
    period_params = [
        ("Day start", _fmt_time_value(day_start)),
        ("Evening start", _fmt_time_value(evening_start)),
        ("Night start", _fmt_time_value(night_start)),
    ]

    lmax_params = [
        ("Lmax n (nth-highest)", _fmt_int_value(lmax_n)),
        ("Lmax t (minutes)", _fmt_int_value(lmax_t)),
    ]

    modal_params = [
        ("Parameter", "—" if modal_param is None else str(modal_param)),
        ("Daytime T", "—" if day_t is None else str(day_t)),
        ("Evening T", "—" if evening_t is None else str(evening_t)),
        ("Night T", "—" if night_t is None else str(night_t)),
    ]

    sections = [
        _section_to_csv("Broadband summary", period_params + lmax_params, broadband_df),
        _section_to_csv("Leq spectra", period_params, leq_df),
        _section_to_csv("Lmax spectra", period_params, lmax_df),
        _section_to_csv("Modal", period_params + modal_params, modal_df),
        _section_to_csv("Counts", period_params + modal_params, counts_df),
    ]

    combined = ("\n\n\n").join(sections).strip() + "\n"
    return combined.encode("utf-8")