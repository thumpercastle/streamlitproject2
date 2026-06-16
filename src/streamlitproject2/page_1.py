import datetime as dt

import streamlit as st

from st_config import (
    _build_survey,
    _convert_for_download,
    _get_template_dataframe,
    _render_upload_modal_contents,
    _reset_workspace,
    default_times,
    init_app_state,
    parse_times,
)

ss = init_app_state()


def config_page() -> None:
    st.title("Pycoustic Acoustic Survey Analyser")
    st.markdown(
        "> Upload CSV logs, adjust survey periods below, then explore broadband insights and interactive graphs."
    )

    logs_loaded = len(ss["logs"])
    last_upload = ss["last_upload_ts"]

    stats_cols = st.columns(2)
    stats_cols[0].metric("Loaded logs", logs_loaded)
    stats_cols[1].metric(
        "Last import",
        last_upload.strftime("%Y-%m-%d %H:%M") if isinstance(last_upload, dt.datetime) else "—",
    )

    st.markdown("### Quick start")
    quick_cols = st.columns(3)
    with quick_cols[0]:
        st.markdown(
            "**1. Upload logs**<br/>Use the primary button below to stage and import CSV files.",
            unsafe_allow_html=True,
        )
    with quick_cols[1]:
        st.markdown(
            "**2. Review periods**<br/>Pick survey times here so every page uses the same schedule.",
            unsafe_allow_html=True,
        )
    with quick_cols[2]:
        st.markdown(
            "**3. Explore outputs**<br/>Head to Analysis or Visualisation once logs are loaded.",
            unsafe_allow_html=True,
        )

    if logs_loaded:
        st.success(f"{logs_loaded} log(s) ready for analysis.")
    else:
        st.warning("No logs uploaded yet. Use the **Upload CSV logs** button below to get started.")

    template_df = _get_template_dataframe()

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("Upload CSV logs", type="primary", icon=":material/upload_file:", width='stretch'):
            ss["show_upload_modal"] = True
            st.rerun()
    with action_cols[1]:
        st.download_button(
            label="Download template CSV",
            data=_convert_for_download(template_df),
            file_name="pycoustic-template.csv",
            mime="text/csv",
            icon=":material/download:",
            width='stretch',
            key="home_template_download",
        )

    if st.button(
            "Reset logs and temp files",
            width='stretch',
            key="reset_logs_button",
            help="Clears loaded logs, staged files, cached temp files, and analysis outputs.",
    ):
        _reset_workspace()

    st.divider()

    ss.setdefault("show_upload_modal", False)

    if ss.get("show_upload_modal", False):

        @st.dialog("Data Loader", width="large")
        def data_loader_dialog() -> None:
            st.subheader("Upload CSV logs")
            _render_upload_modal_contents()

        data_loader_dialog()

    st.markdown("## Set Time Periods")

    current_times = ss.get("times", default_times)

    day_col, eve_col, night_col = st.columns(3)
    with day_col:
        day_start = st.time_input(
            "Daytime Start",
            value=dt.time(*current_times["day"]),
            key="day_start",
        )
    with eve_col:
        evening_start = st.time_input(
            "Evening Start*",
            value=dt.time(*current_times["evening"]),
            key="evening_start",
        )
    with night_col:
        night_start = st.time_input(
            "Night-time Start**",
            value=dt.time(*current_times["night"]),
            key="night_start",
        )

    st.caption(
        "* If Evening starts at the same time as Night, evening periods are disabled. "
        "** Night-time must cross over midnight."
    )

    averaging_choice = st.radio(
        "L90 averaging method",
        options=["Logarithmic (energy)", "Arithmetic (simple mean)"],
        index=0 if ss.get("l90_averaging", "log") == "log" else 1,
        horizontal=True,
        help=(
            "Controls how L90 values are combined when resampling to longer intervals. "
            "**Logarithmic** treats each measurement as acoustic energy — appropriate for energy-equivalent metrics. "
            "**Arithmetic** takes a plain numerical average of the dB values — conventional for statistical noise descriptors such as L90."
        ),
    )
    ss["l90_averaging"] = "log" if averaging_choice.startswith("Log") else "arithmetic"

    times = parse_times(day_start, evening_start, night_start)
    ss["times"] = times

    selected_logs = ss.get("analysis_selected_logs") or list(ss["logs"].keys())
    if not selected_logs:
        selected_logs = list(ss["logs"].keys())

    survey = _build_survey(times=times, log_names=selected_logs)
    ss["survey"] = survey

    if ss["logs"]:
        try:
            ss["broadband_df"] = survey.broadband_summary(
                lmax_n=int(ss["lmax_n"]),
                lmax_t=f"{int(ss['lmax_t'])}min",
            )
        except Exception:
            ss["broadband_df"] = None

        try:
            ss["leq_df"] = survey.leq_spectra()
        except Exception:
            ss["leq_df"] = None

        try:
            ss["lmax_df"] = survey.lmax_spectra(
                n=int(ss["lmax_n"]),
                t=f"{int(ss['lmax_t'])}min",
                period="nights",
            )
        except Exception:
            ss["lmax_df"] = None

        try:
            modal_param, day_t, evening_t, night_t = ss["modal_params"]
            ss["modal_df"] = survey.modal(
                cols=[modal_param],
                by_date=False,
                day_t=day_t,
                evening_t=evening_t,
                night_t=night_t,
                averaging=ss.get("l90_averaging", "log"),
                ln_averaging=ss.get("l90_averaging", "log"),
            )
        except Exception:
            ss["modal_df"] = None

        try:
            modal_param, day_t, evening_t, night_t = ss["modal_params"]
            ss["counts"] = survey.counts(
                cols=[modal_param],
                day_t=day_t,
                evening_t=evening_t,
                night_t=night_t,
                averaging=ss.get("l90_averaging", "log"),
                ln_averaging=ss.get("l90_averaging", "log"),
            )
        except Exception:
            ss["counts"] = None
    else:
        ss["broadband_df"] = None
        ss["leq_df"] = None
        ss["lmax_df"] = None
        ss["modal_df"] = None
        ss["counts"] = None

    with st.expander("Maintenance", expanded=True):
        st.markdown(
            "- If you edit CSV cells and then delete rows, create a fresh copy before exporting to avoid parsing issues.\n"
            "- Evening periods are disabled when they match night start times.\n"
            "- Uploaded files remain staged until you add them as logs."
        )