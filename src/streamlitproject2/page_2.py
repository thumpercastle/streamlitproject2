import streamlit as st

from st_config import _build_survey, init_app_state, to_csv_preserve_multiheader

ss = init_app_state()


def analysis_page() -> None:
    st.title("Analysis")
    st.markdown(
        "> Explore broadband summaries, spectra, modal values, and download-ready datasets derived from your uploaded logs."
    )

    logs_available = list(ss["logs"].keys())
    if not logs_available:
        st.warning("No logs have been uploaded yet. Use the Data Loader page to add data.")
        st.stop()

    default_selection = ss.get("analysis_selected_logs") or logs_available

    selected_logs = st.multiselect(
        "Select logs to include in the survey calculations",
        options=logs_available,
        default=default_selection,
        key="analysis_log_filter",
        help="Results update when you add or remove logs.",
    )

    if not selected_logs:
        st.warning("Select at least one log to display analysis outputs.")
        st.stop()

    ss["analysis_selected_logs"] = selected_logs

    period_times = ss.get("times")
    survey = _build_survey(times=period_times, log_names=selected_logs)
    ss["survey"] = survey

    st.subheader("Summary datasets")

    summary_tabs = st.tabs(
        [
            "Broadband summary",
            "Leq spectra",
            "Lmax spectra",
            "Modal and counts",
        ]
    )

    with summary_tabs[0]:
        st.subheader("Broadband Summary")

        c1, c2 = st.columns(2)
        with c1:
            ss["lmax_n"] = st.number_input(
                "Lmax n (nth-highest)",
                min_value=1,
                max_value=20,
                value=int(ss["lmax_n"]),
                step=1,
                key="bb_lmax_n",
            )
        with c2:
            ss["lmax_t"] = st.number_input(
                "Lmax t (minutes)",
                min_value=1,
                max_value=60,
                value=int(ss["lmax_t"]),
                step=1,
                key="bb_lmax_t",
            )

        try:
            df = survey.broadband_summary(
                lmax_n=int(ss["lmax_n"]),
                lmax_t=f"{int(ss['lmax_t'])}min",
            )
            ss["broadband_df"] = df
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No broadband summary data available for the selected logs.")
        except Exception as exc:
            st.error(f"Failed to compute broadband summary: {exc}")
            ss["broadband_df"] = None

        st.download_button(
            "Download CSV (full headers)",
            data=to_csv_preserve_multiheader(ss.get("broadband_df")),
            file_name="broadband_summary.csv",
            mime="text/csv",
            key="dl_broadband_csv",
        )

    with summary_tabs[1]:
        st.subheader("Leq Spectra")
        st.caption(
            "This computes the combined Leq for each period over the whole survey, rather than separate values by date."
        )

        try:
            df = survey.leq_spectra()
            ss["leq_df"] = df
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No Leq spectra data available for the selected logs.")
        except Exception as exc:
            st.error(f"Failed to compute Leq spectra: {exc}")
            ss["leq_df"] = None

        st.download_button(
            "Download CSV (full headers)",
            data=to_csv_preserve_multiheader(ss.get("leq_df")),
            file_name="leq_spectra.csv",
            mime="text/csv",
            key="dl_leq_csv",
        )

    with summary_tabs[2]:
        st.subheader("Lmax Spectra")
        st.caption(
            "The date shown for night-time results refers to the start date of the night period."
        )
        st.caption(
            "This uses the highest A-weighted value and returns the corresponding event data."
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            nth = st.number_input(
                "nth-highest Lmax",
                min_value=1,
                max_value=60,
                value=int(ss["lmax_n"]),
                step=1,
                key="lmax_spectra_n",
            )
        with c2:
            t_int = st.number_input(
                "Desired time-resolution of Lmax (minutes)",
                min_value=1,
                max_value=60,
                value=int(ss["lmax_t"]),
                step=1,
                key="lmax_spectra_t",
            )
        with c3:
            period_label = st.selectbox(
                "Which period to use for Lmax?",
                options=["days", "evenings", "nights"],
                index=2,
                key="lmax_spectra_period",
            )

        if period_label == "evenings" and ss["times"]["evening"] == ss["times"]["night"]:
            st.info("Evenings are currently disabled. Set different evening and night start times to enable them.")

        try:
            df = survey.lmax_spectra(
                n=int(nth),
                t=f"{int(t_int)}min",
                period=period_label,
            )
            ss["lmax_df"] = df
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No Lmax spectra data available for the selected logs and settings.")
        except Exception as exc:
            st.error(f"Failed to compute Lmax spectra: {exc}")
            ss["lmax_df"] = None

        st.download_button(
            "Download CSV (full headers)",
            data=to_csv_preserve_multiheader(ss.get("lmax_df")),
            file_name="lmax_spectra.csv",
            mime="text/csv",
            key="dl_lmax_csv",
        )

    with summary_tabs[3]:
        st.subheader("Modal and Value Counts")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            parameter = st.selectbox(
                "Which parameter to use?",
                options=["L90", "Leq", "Lmax"],
                index=0,
                key="modal_parameter",
            )
            parameter_col = (parameter, "A")
        with c2:
            day_t = f"{st.selectbox('Daytime interval (minutes)', [1, 2, 5, 10, 15, 30, 60, 120], index=6, key='modal_day_t')}min"
        with c3:
            evening_t = f"{st.selectbox('Evening interval (minutes)', [1, 2, 5, 10, 15, 30, 60, 120], index=6, key='modal_evening_t')}min"
        with c4:
            night_t = f"{st.selectbox('Night interval (minutes)', [1, 2, 5, 10, 15, 30, 60, 120], index=4, key='modal_night_t')}min"

        ss["modal_params"] = [parameter_col, day_t, evening_t, night_t]

        st.markdown("### Modal")
        try:
            modal_df = survey.modal(
                cols=[parameter_col],
                by_date=False,
                day_t=day_t,
                evening_t=evening_t,
                night_t=night_t,
            )
            ss["modal_df"] = modal_df
            if modal_df is not None and not modal_df.empty:
                st.dataframe(modal_df, use_container_width=True)
            else:
                st.info("No modal data available for the selected logs and settings.")
        except Exception as exc:
            st.error(f"Failed to compute modal values: {exc}")
            ss["modal_df"] = None

        st.download_button(
            "Download CSV (full headers)",
            data=to_csv_preserve_multiheader(ss.get("modal_df")),
            file_name="modal.csv",
            mime="text/csv",
            key="dl_modal_csv",
        )

        st.markdown("### Counts")
        try:
            counts_df = survey.counts(
                cols=[parameter_col],
                day_t=day_t,
                evening_t=evening_t,
                night_t=night_t,
            )
            ss["counts"] = counts_df
            if counts_df is not None and not counts_df.empty:
                st.dataframe(counts_df, use_container_width=True)
            else:
                st.info("No counts data available for the selected logs and settings.")
        except Exception as exc:
            st.error(f"Failed to compute counts: {exc}")
            ss["counts"] = None

        st.download_button(
            "Download CSV (full headers)",
            data=to_csv_preserve_multiheader(ss.get("counts")),
            file_name="counts.csv",
            mime="text/csv",
            key="dl_counts_csv",
        )