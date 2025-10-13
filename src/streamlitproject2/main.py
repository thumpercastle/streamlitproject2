import streamlit as st
import pycoustic as pc
import pandas as pd
import numpy as np

import os
import tempfile
from typing import Dict, List

import plotly.graph_objects as go


st.set_page_config(page_title="pycoustic GUI", layout="wide")
st.title("pycoustic Streamlit GUI")

# Initialize session state
ss = st.session_state
ss.setdefault("tmp_paths", [])                 # List[str] for cleanup
ss.setdefault("logs", {})                      # Dict[str, pc.Log]
# Initialize Survey eagerly as requested
if "survey" not in ss:
    ss["survey"] = pc.Survey()
ss.setdefault("resi_df", pd.DataFrame)         # Cached summary (unused here)
ss.setdefault("periods_times", {               # Default times for set_periods()
    "day": (7, 0),
    "evening": (23, 0),
    "night": (23, 0),
})
ss.setdefault("lmax_n", 10)
ss.setdefault("lmax_t", 2)
ss.setdefault("extra_kwargs_raw", "{}")

st.subheader("Upload CSV logs")
uploaded_files = st.file_uploader(
    "Choose one or more CSV files",
    type=["csv"],
    accept_multiple_files=True,
    help="Each CSV will be turned into a pycoustic.Log and added to the collection below.",
)

col_add, col_survey, col_reset = st.columns([1, 1, 1])

def _cleanup_tmp_files(paths: List[str]) -> None:
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass

with col_add:
    if st.button("Add uploaded files as Logs", disabled=not uploaded_files):
        added = 0
        for f in uploaded_files or []:
            # Save uploaded CSV to a temporary file so pycoustic can read it
            tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
            tmp.write(f.getbuffer())
            tmp.flush()
            tmp.close()
            ss["tmp_paths"].append(tmp.name)

            try:
                # Prefer a simple, explicit constructor from CSV if available
                if hasattr(pc.Log, "from_csv"):
                    log = pc.Log.from_csv(tmp.name)  # type: ignore[attr-defined]
                else:
                    # Some versions may accept a path directly
                    log = pc.Log(tmp.name)
            except Exception as e:
                st.error(f"Failed to create Log from {f.name}: {e}")
                continue

            # Use the file stem as the key/name
            name = os.path.splitext(os.path.basename(f.name))[0]
            ss["logs"][name] = log
            added += 1

        if added:
            st.success(f"Added {added} log(s).")

with col_survey:
    if st.button("Build Survey from current Logs", disabled=len(ss["logs"]) == 0):
        # Try to build in one go, fallback to adding with names
        try:
            try:
                survey = pc.Survey(list(ss["logs"].values()))
            except Exception:
                survey = pc.Survey()
                if hasattr(survey, "add"):
                    for name, lg in ss["logs"].items():
                        # Add with explicit name as requested
                        survey.add(data=lg, name=name)  # type: ignore[attr-defined]
            ss["survey"] = survey
            st.success(f"Survey created with {len(ss['logs'])} log(s).")
        except Exception as e:
            st.error(f"Failed to create Survey: {e}")

with col_reset:
    if st.button("Reset"):
        _cleanup_tmp_files(ss.get("tmp_paths", []))
        ss["tmp_paths"] = []
        ss["logs"] = {}
        ss["survey"] = pc.Survey()
        st.rerun()

st.divider()
st.subheader("Current Logs")
if ss["logs"]:
    st.write(f"{len(ss['logs'])} log(s) loaded:")
    st.write(list(ss["logs"].keys()))
else:
    st.info("No logs loaded yet.")

st.subheader("Survey")
st.success("Survey is initialized.")