import datetime as dt
import os
from typing import Dict, Iterable, Tuple

import pandas as pd
import pycoustic as pc
import streamlit as st


DEFAULT_PERIODS: Dict[str, Tuple[int, int]] = {
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


def init_app_state() -> st.session_state:
    """Seed Streamlit session state keys used across multipage app."""
    ss = st.session_state
    ss.setdefault("tmp_paths", [])
    ss.setdefault("logs", {})  # Dict[str, pc.Log]
    ss.setdefault("resi_df", pd.DataFrame())
    ss.setdefault("leq_df", pd.DataFrame())
    ss.setdefault("lmax_df", pd.DataFrame())
    ss.setdefault("modal_df", pd.DataFrame())
    ss.setdefault("resampled_df", pd.DataFrame())
    ss.setdefault("resampled_dfs", {})
    ss.setdefault("num_logs", 0)
    ss.setdefault("show_upload_modal", False)
    ss.setdefault("pending_uploads", [])
    ss.setdefault("last_upload_ts", None)
    ss.setdefault("period_times", DEFAULT_PERIODS.copy())
    ss.setdefault("analysis_selected_logs", [])
    ss.setdefault("survey", pc.Survey())
    ss.setdefault("overview_filters", {"lmax_period": "nights"})
    ss.setdefault("global_resample_period", 15)
    return ss


def rerun_app() -> None:
    """Compatibility wrapper to rerun irrespective of Streamlit version."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def cleanup_tmp_files(paths: Iterable[str]) -> None:
    """Remove cached temp files guarding against missing files."""
    for path in paths:
        try:
            os.remove(path)
        except Exception:
            pass


def parse_times(
    day_start: dt.time,
    evening_start: dt.time,
    night_start: dt.time,
) -> Dict[str, Tuple[int, int]]:
    """Convert datetime.time objects to a dict of (hour, minute) tuples."""

    def to_hm(time_value: dt.time) -> Tuple[int, int]:
        if not isinstance(time_value, dt.time):
            raise TypeError(f"Expected datetime.time, got {type(time_value).__name__}")
        return time_value.hour, time_value.minute

    return {
        "day": to_hm(day_start),
        "evening": to_hm(evening_start),
        "night": to_hm(night_start),
    }


def build_survey(
    times: Dict[str, Tuple[int, int]] | None = None,
    log_names: Iterable[str] | None = None,
) -> pc.Survey:
    """Create a Survey populated with logs currently in session state."""
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


@st.cache_data
def get_template_dataframe() -> pd.DataFrame:
    """Return a template DataFrame for the CSV download."""
    return pd.DataFrame(columns=TEMPLATE_COLUMNS)


@st.cache_data
def convert_for_download(df: pd.DataFrame) -> bytes:
    """Convert a DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode("utf-8")
