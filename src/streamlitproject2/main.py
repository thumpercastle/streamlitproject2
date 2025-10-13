import streamlit as st
import pycoustic as pc
import pandas as pd
import os
import tempfile

st.set_page_config(page_title="pycoustic GUI", layout="wide")
st.title("pycoustic Streamlit GUI")

# Session state
ss = st.session_state
ss.setdefault("tmp_paths", [])
ss.setdefault("logs", {})          # Dict[str, pc.Log]
ss.setdefault("resi_df", pd.DataFrame())

st.subheader("Upload CSV logs")
uploaded_files = st.file_uploader(
    "Choose one or more CSV files",
    type=["csv"],
    accept_multiple_files=True,
)

col_add, col_reset = st.columns([1, 1])

def _cleanup_tmp_files(paths):
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass

with col_add:
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
    if st.button("Reset"):
        _cleanup_tmp_files(ss.get("tmp_paths", []))
        ss["tmp_paths"] = []
        ss["logs"] = {}
        ss["resi_df"] = pd.DataFrame()
        st.rerun()

st.divider()
st.subheader("Current Logs")
if ss["logs"]:
    st.write(f"{len(ss['logs'])} log(s) loaded:")
    st.write(list(ss["logs"].keys()))
else:
    st.info("No logs loaded yet.")

# Compute and display resi_summary directly from current logs
st.subheader("Residential Summary (resi_summary)")
col_run, col_clear = st.columns([1, 1])

with col_run:
    if st.button("Run resi_summary()", disabled=len(ss["logs"]) == 0):
        try:
            # Build a Survey from the current logs right before running the summary
            survey = pc.Survey()
            for name, lg in ss["logs"].items():
                survey.add(data=lg, name=name)

            df = survey.resi_summary()  # Always a DataFrame per your note
            ss["resi_df"] = df

            st.success(f"resi_summary computed: {df.shape[0]} rows, {df.shape[1]} columns.")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to compute resi_summary: {e}")

with col_clear:
    if st.button("Clear summary", disabled=ss["resi_df"].empty):
        ss["resi_df"] = pd.DataFrame()
        st.info("Summary cleared.")

# Show cached result on rerun
if not ss["resi_df"].empty:
    st.dataframe(ss["resi_df"], use_container_width=True)
else:
    st.info("Run resi_summary() to see results here.")