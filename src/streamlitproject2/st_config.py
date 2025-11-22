import os
import pandas as pd
import pycoustic as pc
import streamlit as st
import datetime as dt
from typing import Dict, Tuple


# Graph colour palette config
COLOURS = {
    "Leq A": "#FBAE18",   # light grey
    "L90 A": "#4d4d4d",   # dark grey
    "Lmax A": "#B51724",  # red
}
# Graph template config
TEMPLATE = "plotly"


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
    return ss

default_times = {"day": (7, 0), "evening": (23, 0), "night": (23, 0)}


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
