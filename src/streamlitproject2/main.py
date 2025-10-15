import os
import tempfile
import datetime as dt
import streamlit as st
import pycoustic as pc
import pandas as pd
from typing import Dict, Tuple
import plotly.graph_objects as go



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
ss.setdefault("num_logs", 0)

times = {"day": (7, 0), "evening": (23, 0), "night": (23, 0)}

col_add, col_reset = st.columns([1, 1])

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

#TODO: Add option for user input for log names.
with col_add:
    st.subheader("1. Upload CSV logs")
    uploaded_files = st.file_uploader(
        "Choose one or more CSV files",
        type=["csv"],
        accept_multiple_files=True,
    )

    # Let the user assign a custom name for each uploaded file
    for i, f in enumerate(uploaded_files or []):
        default_name = os.path.splitext(os.path.basename(f.name))[0]
        st.text_input(
            label=f"Name for {f.name}",
            value=default_name,
            key=f"log_name_{i}",
            help="Enter a unique name for this log",
        )

    if st.button("Add uploaded files as Logs", disabled=not uploaded_files):
        added = 0
        existing_names = set(ss["logs"].keys())

        for i, f in enumerate(uploaded_files or []):
            # Resolve user-provided name (fallback to default if missing)
            default_name = os.path.splitext(os.path.basename(f.name))[0]
            new_name = st.session_state.get(f"log_name_{i}", default_name).strip()
            if not new_name:
                st.error(f"Name for {f.name} cannot be empty.")
                continue

            # Ensure uniqueness among existing and new names
            base = new_name
            suffix = 1
            while new_name in existing_names:
                new_name = f"{base}-{suffix}"
                suffix += 1
            existing_names.add(new_name)

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

            ss["logs"][new_name] = log
            added += 1

        if added:
            st.success(f"Added {added} log(s).")
            ss["num_logs"] = added

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
    day_start = st.time_input("Set Day Period Start", dt.time(7, 00))
    evening_start = st.time_input("Set Evening Period Start", dt.time(23, 00))
    night_start = st.time_input("Set Night Period Start", dt.time(23, 00))
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
        st.caption(f"Log: {name}")
        st.dataframe(log.master, key="master", width="stretch")

        # TODO: Time history of plots for each log.
        # log = logs.get(uf.name)
        # if log is None:
        #     st.error(f"Log for `{uf.name}` not found.")
        #     continue
        #
        # # Decide whether to show raw or aggregated data
        # if st.session_state["apply_agg"]:
        #     # 1) Re-aggregate / resample using the chosen period
        #     try:
        #         df_used = log.as_interval(t=period)
        #         df_used = df_used.reset_index().rename(
        #             columns={df_used.index.name or "index": "Timestamp"}
        #         )
        #         subheader = "Integrated Survey Data"
        #     except Exception as e:
        #         st.error(f"Failed to apply integration period for `{uf.name}`: {e}")
        #         continue
        # else:
        #     # 2) Show the raw data (from log._master) if available
        #     try:
        #         raw_master = log._master  # original DataFrame, indexed by Timestamp
        #         df_used = raw_master.reset_index().rename(columns={"Time": "Timestamp"})
        #         subheader = "Raw Survey Data"
        #     except Exception as e:
        #         st.error(f"Failed to load raw data for `{uf.name}`: {e}")
        #         continue
        #
        # # Prepare a flattened‐column header copy JUST FOR PLOTTING
        # df_plot = df_used.copy()
        # if isinstance(df_plot.columns, pd.MultiIndex):
        #     flattened_cols = []
        #     for lvl0, lvl1 in df_plot.columns:
        #         lvl0_str = str(lvl0)
        #         lvl1_str = str(lvl1) if lvl1 is not None else ""
        #         flattened_cols.append(f"{lvl0_str} {lvl1_str}".strip())
        #     df_plot.columns = flattened_cols
        #
        # #  Time‐history Graph (Leq A, L90 A, Lmax A) using df_plot
        # required_cols = {"Leq A", "L90 A", "Lmax A"}
        # if required_cols.issubset(set(df_plot.columns)):
        #     fig = go.Figure()
        #     fig.add_trace(
        #         go.Scatter(
        #             x=df_plot["Timestamp"],
        #             y=df_plot["Leq A"],
        #             name="Leq A",
        #             mode="lines",
        #             line=dict(color=COLOURS["Leq A"], width=1),
        #         )
        #     )
        #     fig.add_trace(
        #         go.Scatter(
        #             x=df_plot["Timestamp"],
        #             y=df_plot["L90 A"],
        #             name="L90 A",
        #             mode="lines",
        #             line=dict(color=COLOURS["L90 A"], width=1),
        #         )
        #     )
        #     fig.add_trace(
        #         go.Scatter(
        #             x=df_plot["Timestamp"],
        #             y=df_plot["Lmax A"],
        #             name="Lmax A",
        #             mode="markers",
        #             marker=dict(color=COLOURS["Lmax A"], size=3),
        #         )
        #     )
        #     fig.update_layout(
        #         template=TEMPLATE,
        #         margin=dict(l=0, r=0, t=0, b=0),
        #         xaxis=dict(
        #             title="Time & Date (hh:mm & dd/mm/yyyy)",
        #             type="date",
        #             tickformat="%H:%M<br>%d/%m/%Y",
        #             tickangle=0,
        #         ),
        #         yaxis_title="Measured Sound Pressure Level dB(A)",
        #         legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0),
        #         height=600,
        #     )
        #     st.plotly_chart(fig, use_container_width=True)
        # else:
        #     st.warning(f"Required columns {required_cols} missing in {subheader}.")
        #
        # # --- Finally, display the TABLE with MultiIndex intact ---
        # st.subheader(subheader)
        # st.dataframe(df_used, hide_index=True)
