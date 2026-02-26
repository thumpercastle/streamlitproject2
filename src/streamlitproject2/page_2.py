import streamlit as st
from st_config import to_csv_preserve_multiheader

from st_config import (
    init_app_state,
    _build_survey
)

ss = init_app_state()

def analysis_page():
    st.title("Analysis")
    st.markdown(
        "> Explore broadband summaries, spectra, modal values, and download-ready datasets derived from your uploaded logs."
    )

    logs_available = list(ss["logs"].keys())

    if not logs_available:
        st.warning("No logs have been uploaded yet. Use the Home page to add data.", icon=":material/info:")
        st.stop()

    default_selection = ss.get("analysis_selected_logs") or logs_available

    selected_logs = st.multiselect(
        "Select logs to include in the survey calculations",
        options=logs_available,
        default=default_selection,
        key="analysis_log_filter",
        help="Results update immediately when you add or remove logs.",
        on_change=st.rerun
    )

    if not selected_logs:
        st.warning("Select at least one log to display analysis outputs.", icon=":material/select_all:")
        st.stop()

    ss["analysis_selected_logs"] = selected_logs

    period_times = ss.get("period_times")
    ss["survey"] = _build_survey(times=period_times, log_names=selected_logs)

    st.subheader("Summary datasets")

    summary_tabs = st.tabs(
        [
            "Broadband summary",
            "Leq spectra",
            "Lmax spectra",
            "Modal and counts",
        ]
    )

    log_items = list(ss.get("logs", {}).items())

    if not log_items:
        st.info("No logs loaded yet.")
    else:

        # Broadband tab
        with summary_tabs[0]:
            # Compute and display broadband_summary directly from current logs
            st.subheader("Broadband Summary")



            w_cols = st.columns(2)
            with w_cols[0]:
                ss["lmax_n"] = st.number_input(
                    "Lmax n (nth-highest)",
                    min_value=1,
                    max_value=20,
                    value=int(ss["lmax_n"]),
                    step=1,
                    key="bb_lmax_n",
                )
            with w_cols[1]:
                ss["lmax_t"] = st.number_input(
                    "Lmax t (minutes)",
                    min_value=1,
                    max_value=60,
                    value=int(ss["lmax_t"]),
                    step=1,
                    key="bb_lmax_t",
                )

            broadband_container = st.container()
            with broadband_container:
                if not bool(ss["logs"]):
                    st.info("No logs loaded yet.")
                else:
                    try:
                        df = ss["survey"].broadband_summary(
                            lmax_n=int(ss["lmax_n"]),
                            lmax_t=f"{int(ss['lmax_t'])}min",
                        )
                        ss["broadband_df"] = df

                        if not ss["broadband_df"].empty:
                            st.dataframe(ss["broadband_df"], key="broadband_df", width="stretch")
                        else:
                            st.info("Run broadband_summary() to see results here.")
                    except Exception as e:
                        st.error(f"Failed to compute broadband_summary: {e}")

                st.download_button(
                    "Download CSV (full headers)",
                    data=to_csv_preserve_multiheader(ss["broadband_df"]),
                    file_name="broadband_summary.csv",
                    mime="text/csv",
                    key="dl_broadband_csv",
                )

            st.divider()

            # Leq tab
            with summary_tabs[1]:
                st.subheader("Leq Spectra")
                st.text(
                    "This function computes the combined Leq for the period in question over the entire survey (e.g. all days combined).")
                leq_container = st.container()

                with leq_container:
                    if not bool(ss["logs"]):
                        st.info("No logs loaded yet.")
                    else:
                        try:
                            df = ss["survey"].leq_spectra()  # Always a DataFrame per your note
                            ss["leq_df"] = df

                            # st.success(f"Leq spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                            # Show cached result on rerun
                            if not ss["leq_df"].empty:
                                st.dataframe(ss["leq_df"], key="leq_df", width="stretch")
                            else:
                                st.info("Run leq_spectra() to see results here.")
                        except Exception as e:
                            st.error(f"Failed to compute leqspectra: {e}")
                    st.download_button(
                        "Download CSV (full headers)",
                        data=to_csv_preserve_multiheader(ss["leq_df"]),
                        file_name="leq.csv",
                        mime="text/csv",
                        key="dl_leq_csv",
                    )

                st.divider()


        # Compute and display broadband_summary directly from current logs

        with summary_tabs[2]:
            lmax_container = st.container()

            with lmax_container:
                st.subheader("Lmax Spectra")
                st.text(
                    "Note: the timestamp in the 'Date' column shows the date when the night-time period started, not the date on which the lmax occurred. e.g. 2025-08-14 00:14 lmax would have occured in the early hours of 2025-08-15.")
                st.text(
                    "This function works by selecting the highest A-weighted value, and the corresponding octave band data.")
                col_nth, col_t, col_per = st.columns([1, 1, 1])
                with col_nth:
                    nth = st.number_input(
                        label="nth-highest Lmax",
                        min_value=1,
                        max_value=60,
                        value=ss["lmax_n"],
                        step=1,
                    )
                with col_t:
                    t_int = st.number_input(
                        label="Desired time-resolution of Lmax (min).",
                        min_value=1,
                        max_value=60,
                        value=ss["lmax_t"],
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
                        df = ss["survey"].lmax_spectra(n=nth, t=t_str, period=per)  # Always a DataFrame per your note
                        ss["lmax_df"] = df
                        # st.success(f"Lmax spectra computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                        # Show cached result on rerun
                        # Notify user if evening period disabled
                        if per == "evenings" and ss["times"]["evening"] == ss["times"]["night"]:
                            st.info("Evenings are currently disabled. Enable them by setting the times in the sidebar.")
                        if not ss["lmax_df"].empty:
                            st.dataframe(ss["lmax_df"], key="lmax_df", width="stretch")
                        else:
                            st.info("Run lmax_spectra() to see results here.")
                    except Exception as e:
                        st.error(f"Failed to compute lmax_spectra: {e}")
                st.download_button(
                    "Download CSV (full headers)",
                    data=to_csv_preserve_multiheader(ss["lmax_df"]),
                    file_name="lmax.csv",
                    mime="text/csv",
                    key="dl_lmax_csv",
                )


            st.divider()


        with summary_tabs[3]:
            st.subheader("Modal and Value Counts")
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

                ss["modal_params"] = [par_tup, day_t, eve_t, night_t]
                # Modal
                st.markdown("## Modal")
                try:
                    df = ss["survey"].modal(
                        cols=[par_tup],
                        by_date=False,
                        day_t=day_t,
                        evening_t=eve_t,
                        night_t=night_t
                    )  # Always a DataFrame per your note
                    ss["modal_df"] = df
                    # st.success(f"Modal values computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    if not ss["modal_df"].empty:
                        st.dataframe(ss["modal_df"], key="modal_df", width="stretch")
                    else:
                        st.info("Run modal() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute modal: {e}")

                st.download_button(
                    "Download CSV (full headers)",
                    data=to_csv_preserve_multiheader(ss["modal_df"]),
                    file_name="modal.csv",
                    mime="text/csv",
                    key="dl_modal_csv",
                )

                # Value counts
                st.markdown("## Counts")
                try:
                    df = ss["survey"].counts(
                        cols=[par_tup],
                        day_t=day_t,
                        evening_t=eve_t,
                        night_t=night_t
                    )
                    ss["counts"] = df
                    # st.success(f"Modal values computed: {df.shape[0]} rows, {df.shape[1]} columns.")
                    # Show cached result on rerun
                    if not ss["counts"].empty:
                        st.dataframe(ss["counts"], key="counts_df", width="stretch")
                    else:
                        st.info("Run modal() to see results here.")
                except Exception as e:
                    st.error(f"Failed to compute modal: {e}")


                # ss["counts"] = ss["survey"].counts()
                st.download_button(
                    "Download CSV (full headers)",
                    data=to_csv_preserve_multiheader(ss["counts"]),
                    file_name="counts.csv",
                    mime="text/csv",
                    key="dl_counts_csv",
                )

                st.divider()

