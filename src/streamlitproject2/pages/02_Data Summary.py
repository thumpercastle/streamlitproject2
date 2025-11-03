import datetime as dt
import io

import pandas as pd
import streamlit as st

from streamlitproject2.app_state import (
    DEFAULT_PERIODS,
    build_survey,
    init_app_state,
    parse_times,
)

ss = init_app_state()


def _export_frames_to_excel(frames: dict[str, pd.DataFrame]) -> bytes:
    """Convert multiple DataFrames into a single Excel workbook."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, frame in frames.items():
            if frame.empty:
                continue
            writer_sheet = sheet_name[:31] or "Sheet1"
            export_frame = frame.copy()
            if isinstance(export_frame.columns, pd.MultiIndex):
                export_frame.columns = [
                    " | ".join(str(level) for level in col if level not in (None, ""))
                    for col in export_frame.columns.to_flat_index()
                ]
            if isinstance(export_frame.index, pd.MultiIndex):
                export_frame = export_frame.reset_index()
            export_frame.to_excel(writer, sheet_name=writer_sheet, index=False)
    output.seek(0)
    return output.getvalue()


def _to_time(hours: int, minutes: int) -> dt.time:
    return dt.time(hours, minutes)


st.title("Analysis & Visualisation")
st.markdown(
    "> Explore broadband summaries, spectra, modal values, and download-ready datasets derived from your uploaded logs."
)

logs_available = list(ss["logs"].keys())

if not logs_available:
    st.warning("No logs have been uploaded yet. Use the Home page to add data.", icon=":material/info:")
    st.stop()

logs_loaded = len(ss["logs"])
resample_options = [1, 2, 5, 10, 15, 30, 60, 120]
current_resample = ss.get("global_resample_period", 15)
if current_resample not in resample_options:
    current_resample = 15
ss["global_resample_period"] = current_resample

default_selection = ss.get("analysis_selected_logs") or logs_available

selected_logs = st.multiselect(
    "Select logs to include in the survey calculations",
    options=logs_available,
    default=default_selection,
    key="analysis_log_filter",
    help="Results update immediately when you add or remove logs.",
)

if not selected_logs:
    st.warning("Select at least one log to display analysis outputs.", icon=":material/select_all:")
    st.stop()

ss["analysis_selected_logs"] = selected_logs

period_times = ss.get("period_times")
survey = build_survey(times=period_times, log_names=selected_logs)

st.subheader("Summary datasets")
filters = ss.setdefault("overview_filters", {"lmax_period": "nights"})

lmax_options = ["days", "evenings", "nights"]
default_lmax = filters.get("lmax_period", "nights")
if default_lmax not in lmax_options:
    default_lmax = "nights"
lmax_period = st.selectbox(
    "Lmax period",
    options=lmax_options,
    index=lmax_options.index(default_lmax),
    key="lmax_period_selector",
)
ss["overview_filters"]["lmax_period"] = lmax_period

summary_tabs = st.tabs(
    [
        "Broadband summary",
        "Leq spectra",
        "Lmax spectra",
        "Modal values",
    ]
)

with summary_tabs[0]:
    try:
        df = survey.resi_summary()
        ss["resi_df"] = df
        if df.empty:
            st.info("No broadband summary rows returned for the current selection.")
        else:
            st.caption(f"{df.shape[0]} row(s)")
            st.dataframe(df, use_container_width=True)
    except Exception as exc:
        st.error(f"Failed to compute resi_summary: {exc}")

with summary_tabs[1]:
    try:
        df = survey.leq_spectra()
        ss["leq_df"] = df
        if df.empty:
            st.info("No Leq spectra data available for the chosen logs.")
        else:
            st.caption(f"{df.shape[0]} row(s)")
            st.dataframe(df, use_container_width=True)
    except Exception as exc:
        st.error(f"Failed to compute leq_spectra: {exc}")

with summary_tabs[2]:
    col_nth, col_t = st.columns([1, 1])
    with col_nth:
        nth = st.number_input(
            "nth-highest Lmax",
            min_value=1,
            max_value=60,
            value=10,
            step=1,
        )
    with col_t:
        t_resolution = st.selectbox(
            "Lmax time resolution (minutes)",
            options=[1, 2, 5, 10, 15, 30, 60, 120],
            index=2,
        )
    period_label = lmax_period
    try:
        df = survey.lmax_spectra(n=nth, t=f"{t_resolution}min", period=period_label)
        ss["lmax_df"] = df
        if df.empty:
            st.info("No Lmax spectra rows matched the current settings.")
        else:
            st.caption(f"{df.shape[0]} row(s)")
            st.dataframe(df, use_container_width=True)
        if period_label == "evenings" and period_times and period_times.get("evening") == period_times.get("night"):
            st.info("Evenings are currently disabled. Adjust the start time in the sidebar.")
    except Exception as exc:
        st.error(f"Failed to compute lmax_spectra: {exc}")

with summary_tabs[3]:
    col_par, col_day, col_eve, col_night = st.columns([1, 1, 1, 1])
    with col_par:
        parameter = st.selectbox("Parameter", options=["L90", "Leq", "Lmax"], index=0)
    with col_day:
        day_t = st.selectbox("Day resolution (minutes)", options=[1, 2, 5, 10, 15, 30, 60, 120], index=6)
    with col_eve:
        eve_t = st.selectbox("Evening resolution (minutes)", options=[1, 2, 5, 10, 15, 30, 60, 120], index=6)
    with col_night:
        night_t = st.selectbox("Night resolution (minutes)", options=[1, 2, 5, 10, 15, 30, 60, 120], index=4)
    try:
        df = survey.modal(
            cols=(parameter, "A"),
            by_date=False,
            day_t=f"{day_t}min",
            evening_t=f"{eve_t}min",
            night_t=f"{night_t}min",
        )
        ss["modal_df"] = df
        if df.empty:
            st.info("No modal values calculated for the selected parameters.")
        else:
            st.caption(f"{df.shape[0]} row(s)")
            st.dataframe(df, use_container_width=True)
    except Exception as exc:
        st.error(f"Failed to compute modal values: {exc}")

export_sources: dict[str, pd.DataFrame] = {}

if isinstance(ss.get("resi_df"), pd.DataFrame) and not ss["resi_df"].empty:
    export_sources["Broadband Summary"] = ss["resi_df"]
if isinstance(ss.get("leq_df"), pd.DataFrame) and not ss["leq_df"].empty:
    export_sources["Leq Spectra"] = ss["leq_df"]
if isinstance(ss.get("lmax_df"), pd.DataFrame) and not ss["lmax_df"].empty:
    export_sources["Lmax Spectra"] = ss["lmax_df"]
if isinstance(ss.get("modal_df"), pd.DataFrame) and not ss["modal_df"].empty:
    export_sources["Modal Values"] = ss["modal_df"]

resampled_dfs = ss.get("resampled_dfs", {})
if isinstance(resampled_dfs, dict):
    for log_name, frame in resampled_dfs.items():
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            export_sources[f"Resampled - {log_name}"] = frame

non_empty_sources = export_sources
export_bytes: bytes | None = None
if non_empty_sources:
    export_bytes = _export_frames_to_excel(non_empty_sources)
    st.caption("Download a combined Excel workbook from the sidebar, including per-log resampled sheets.")
else:
    st.caption("Generate at least one dataset above to enable Excel export from the sidebar.")


with st.sidebar:
    current_periods = ss.get("period_times", DEFAULT_PERIODS.copy())
    with st.expander("Survey periods", expanded=False):
        day_start = st.time_input(
            "Day starts",
            value=_to_time(*current_periods["day"]),
            key="analysis_time_day",
        )
        evening_start = st.time_input(
            "Evening starts",
            value=_to_time(*current_periods["evening"]),
            key="analysis_time_evening",
        )
        night_start = st.time_input(
            "Night starts",
            value=_to_time(*current_periods["night"]),
            key="analysis_time_night",
        )
        selected_periods = parse_times(day_start, evening_start, night_start)
        if selected_periods != current_periods:
            ss["period_times"] = selected_periods
            ss["survey"] = build_survey(times=selected_periods)
        if selected_periods["evening"] == selected_periods["night"]:
            st.caption("Evening outputs are currently disabled because evening matches the night start.")

    with st.expander("Resample period", expanded=True):
        resample_choice = st.selectbox(
            "Resample interval (minutes)",
            options=resample_options,
            index=resample_options.index(current_resample),
            key="global_resample_selector",
        )
        if resample_choice != current_resample:
            ss["global_resample_period"] = resample_choice
            current_resample = resample_choice
        ss["graph_resample_period"] = ss["global_resample_period"]
        st.caption("Adjust to change how log data is resampled for charts and exports.")

    with st.expander("Export", expanded=bool(export_bytes)):
        if export_bytes:
            st.download_button(
                "Export calculated data to Excel",
                data=export_bytes,
                file_name="pycoustic-analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="analysis_export_excel",
                icon=":material/download:",
            )
            st.caption("Workbook includes summary datasets plus per-log resampled sheets.")
        else:
            st.caption("Export becomes available once datasets are generated.")
