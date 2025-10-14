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
ss.setdefault("survey", pc.Survey())

times = {"day": (7, 0), "evening": (23, 0), "night": (23, 0)}

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

    t = {
        "day": to_hm(day_start),
        "evening": to_hm(evening_start),
        "night": to_hm(night_start),
    }
    return t

#TODO: Add option for user input for log names.
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

survey.set_periods(times=times)

# Sidebar menu
with st.sidebar:
    st.text("This tool is a work in progress and may produce errors. Check results manually. Use at your own risk.")
    st.markdown("# Survey Config")
    st.markdown("## Set Time Periods")
    day_start = st.time_input("Set Day Period Start", dt.time(7, 00))
    evening_start = st.time_input("Set Evening Period Start", dt.time(23, 00))
    night_start = st.time_input("Set Night Period Start", dt.time(23, 00))
    st.text("If Evening starts at the same time as Night, Evening periods will be disabled (default). Night must cross over midnight")
    times = parse_times(day_start, evening_start, night_start)
    survey.set_periods(times=times)


st.divider()
#TODO: Implement tabs with graphs for each log.

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
st.text("Note: Ignore the 'Date' column.")
modal_container = st.container()

with modal_container:
    col_cols, col_by_date, col_day_t, col_eve_t, col_night_t = st.columns([1, 1, 1, 1, 1])
    with col_cols:
        par = st.selectbox(
            label="Which parameter to use for modal?",
            options=["L90", "Leq", "Lmax"],
            index=0
        )
        par_tup = (par, "A")
    with col_by_date:
        by_date = st.selectbox(
            label="Overall modal, or by date?",
            options=["Overall", "By date"],
            index=0
        )
        if by_date == "By date":
            by_date = True
        else:
            by_date = False
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
                by_date=by_date,
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