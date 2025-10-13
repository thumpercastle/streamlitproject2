import os
import tempfile
import datetime as dt
import streamlit as st
import pycoustic as pc
import pandas as pd
from typing import Dict, Tuple



st.set_page_config(page_title="pycoustic GUI", layout="wide")
st.title("pycoustic Streamlit GUI")

# Session state
ss = st.session_state
ss.setdefault("tmp_paths", [])
ss.setdefault("logs", {})          # Dict[str, pc.Log]
ss.setdefault("resi_df", pd.DataFrame())
ss.setdefault("leq_df", pd.DataFrame())
ss.setdefault("lmax_df", pd.DataFrame())
ss.setdefault("modal_df", pd.DataFrame())
ss.setdefault("times", {"day": (7, 0), "evening": (23, 0), "night": (23, 0)})
ss.setdefault("survey", pc.Survey())

col_add, col_reset = st.columns([1, 1])

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

    return {
        "day": to_hm(day_start),
        "evening": to_hm(evening_start),
        "night": to_hm(night_start),
    }


with col_add:
    st.subheader("1. Upload CSV logs")
    uploaded_files = st.file_uploader(
        "Choose one or more CSV files",
        type=["csv"],
        accept_multiple_files=True,
    )
    if st.button("Add uploaded files as Logs", disabled=not uploaded_files):
        added = 0
        for f in uploaded_files or []:
            # Persist the uploaded file to a temporary path for pycoustic to read
            tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
            tmp.write(f.getbuffer())
            tmp.flush()
            tmp.close()
            ss["tmp_paths"].append(tmp.name)

            try:
                log = pc.Log(tmp.name)
            except Exception as e:
                st.error(f"Failed to create Log from {f.name}: {e}")
                continue

            name = os.path.splitext(os.path.basename(f.name))[0]
            ss["logs"][name] = log
            added += 1

        if added:
            st.success(f"Added {added} log(s).")

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

# Build the survey
survey = pc.Survey()
for name, lg in ss["logs"].items():
    survey.add_log(data=lg, name=name)

# day_col, evening_col, night_col = st.columns([1, 1, 1])
# with day_col:
with st.sidebar:
    st.markdown("## Set Time Periods")
    day_start = st.time_input("Set Day Period Start", dt.time(7, 00))
# with evening_col:
    evening_start = st.time_input("Set Evening Period Start", dt.time(23, 00))
# with night_col:
    night_start = st.time_input("Set Night Period Start", dt.time(23, 00))
    st.text("If Evening starts at the same time as Night, Evening periods will be disabled (default). Night must cross over midnight")

# If times have changed:
new_times = parse_times(day_start, evening_start, night_start)
if new_times != ss["times"]:
    ss["times"] = new_times
    ss["survey"].set_periods(times=ss["times"])

st.divider()
# Compute and display resi_summary directly from current logs
st.subheader("Residential Summary (resi_summary)")
resi_container = st.container()
button_container = st.container()


with resi_container:
    if st.button("Run resi_summary()", key=0, disabled=len(ss["logs"]) == 0):
        try:
            # Build a Survey from the current logs right before running the summary
            # survey = ss["survey"]
            # for name, lg in ss["logs"].items():
            #     survey.add_log(data=lg, name=name)

            df = survey.resi_summary()  # Always a DataFrame per your note
            ss["resi_df"] = df

            st.success(f"resi_summary computed: {df.shape[0]} rows, {df.shape[1]} columns.")
            # Show cached result on rerun
            if not ss["resi_df"].empty:
                st.dataframe(ss["resi_df"], key="resi_df", use_container_width=True)
            else:
                st.info("Run resi_summary() to see results here.")
        except Exception as e:
            st.error(f"Failed to compute resi_summary: {e}")

with button_container:
    if st.button("Clear summary", key=1, disabled=ss["resi_df"].empty):
        ss["resi_df"] = pd.DataFrame()
        st.info("Summary cleared.")

st.divider()
# Compute and display resi_summary directly from current logs
st.subheader("Leq Spectra")
leq_container = st.container()
leq_button_container = st.container()


with leq_container:
    if st.button("Run leq_spectra()", key=2, disabled=len(ss["logs"]) == 0):
        try:
            # Build a Survey from the current logs right before running the summary
            # survey = ss["survey"]
            # for name, lg in ss["logs"].items():
            #     survey.add_log(data=lg, name=name)

            df = survey.leq_spectra()  # Always a DataFrame per your note
            ss["leq_df"] = df

            st.success(f"Leq spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
            # Show cached result on rerun
            if not ss["leq_df"].empty:
                st.dataframe(ss["leq_df"], key="leq_df", use_container_width=True)
            else:
                st.info("Run leq_spectra() to see results here.")
        except Exception as e:
            st.error(f"Failed to compute leqspectra: {e}")

with leq_button_container:
    if st.button("Clear summary", key=3, disabled=ss["leq_df"].empty):
        ss["leq_df"] = pd.DataFrame()
        st.info("Summary cleared.")


st.divider()
# Compute and display resi_summary directly from current logs
st.subheader("Lmax Spectra")
lmax_container = st.container()
lmax_button_container = st.container()


with lmax_container:
    if st.button("Run lmax_spectra()", key=4, disabled=len(ss["logs"]) == 0):
        try:
            # Build a Survey from the current logs right before running the summary
            # survey = ss["survey"]
            # for name, lg in ss["logs"].items():
            #     survey.add_log(data=lg, name=name)

            df = survey.lmax_spectra()  # Always a DataFrame per your note
            ss["lmax_df"] = df

            st.success(f"Lmax spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
            # Show cached result on rerun
            if not ss["lmax_df"].empty:
                st.dataframe(ss["lmax_df"], key="lmax_df", use_container_width=True)
            else:
                st.info("Run lmax_spectra() to see results here.")
        except Exception as e:
            st.error(f"Failed to compute lmax_spectra: {e}")

with lmax_button_container:
    if st.button("Clear summary", key=5, disabled=ss["lmax_df"].empty):
        ss["lmax_df"] = pd.DataFrame()
        st.info("Summary cleared.")


st.divider()
# Compute and display resi_summary directly from current logs
st.subheader("Modal values")
modal_container = st.container()
modal_button_container = st.container()


with modal_container:
    if st.button("Run modal()", key=6, disabled=len(ss["logs"]) == 0):
        try:
            # Build a Survey from the current logs right before running the summary
            # survey = ss["survey"]
            # for name, lg in ss["logs"].items():
            #     survey.add_log(data=lg, name=name)

            df = survey.modal()  # Always a DataFrame per your note
            ss["modal_df"] = df

            st.success(f"Modal values computed: {df.shape[0]} rows, {df.shape[1]} columns.")
            # Show cached result on rerun
            if not ss["modal_df"].empty:
                st.dataframe(ss["modal_df"], key="modal_df", use_container_width=True)
            else:
                st.info("Run modal() to see results here.")
        except Exception as e:
            st.error(f"Failed to compute modal: {e}")

with modal_button_container:
    if st.button("Clear summary", key=7, disabled=ss["modal_df"].empty):
        ss["modal_df"] = pd.DataFrame()
        st.info("Summary cleared.")