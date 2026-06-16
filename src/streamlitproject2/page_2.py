import pandas as pd
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
            "Peak Picker",
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
                st.dataframe(df, width='stretch')
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
                st.dataframe(df, width='stretch')
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
                st.dataframe(df, width='stretch')
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

        # Build sorted list of all available columns from loaded logs
        _all_modal_cols: set = set()
        for _log_obj in ss["logs"].values():
            try:
                for _col in _log_obj.get_data().columns:
                    if isinstance(_col, tuple):
                        if str(_col[0]).lower() != "night idx":
                            _all_modal_cols.add(_col)
                    elif str(_col).lower() != "night idx":
                        _all_modal_cols.add(_col)
            except Exception:
                pass

        def _modal_col_sort_key(col):
            _forder = {"L90": 0, "Leq": 1, "Lmax": 2}
            family = str(col[0]) if isinstance(col, tuple) else str(col).split()[0]
            band = col[1] if (isinstance(col, tuple) and len(col) > 1) else ""
            forder = _forder.get(family, 99)
            if isinstance(band, float):
                band_key = (1, band)
            elif str(band).upper() == "A":
                band_key = (0, 0.0)
            else:
                try:
                    band_key = (1, float(band))
                except (TypeError, ValueError):
                    band_key = (2, str(band))
            return (forder, family, band_key)

        def _fmt_modal_col(col):
            if isinstance(col, tuple):
                parts = []
                for p in col:
                    if str(p) in ("", "nan"):
                        continue
                    if isinstance(p, float) and p == int(p):
                        parts.append(str(int(p)))
                    else:
                        parts.append(str(p))
                return " ".join(parts)
            return str(col)

        _all_modal_cols_sorted = sorted(_all_modal_cols, key=_modal_col_sort_key)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if _all_modal_cols_sorted:
                _current_param = ss.get("modal_params", [("L90", "A")])[0]
                _default_idx = (
                    _all_modal_cols_sorted.index(_current_param)
                    if _current_param in _all_modal_cols_sorted
                    else 0
                )
                parameter_col = st.selectbox(
                    "Column",
                    options=_all_modal_cols_sorted,
                    index=_default_idx,
                    format_func=_fmt_modal_col,
                    key="modal_parameter_col",
                )
            else:
                st.caption("Upload logs to see available columns.")
                parameter_col = ("L90", "A")
        with c2:
            day_t = f"{st.selectbox('Daytime interval (minutes)', [1, 2, 5, 10, 15, 30, 60, 120], index=6, key='modal_day_t')}min"
        with c3:
            evening_t = f"{st.selectbox('Evening interval (minutes)', [1, 2, 5, 10, 15, 30, 60, 120], index=6, key='modal_evening_t')}min"
        with c4:
            night_t = f"{st.selectbox('Night interval (minutes)', [1, 2, 5, 10, 15, 30, 60, 120], index=4, key='modal_night_t')}min"

        ss["modal_params"] = [parameter_col, day_t, evening_t, night_t]

        _all_t_options = [1, 2, 5, 10, 15, 30, 60, 120]
        _inc_col, _all_t_col = st.columns(2)
        with _inc_col:
            include_all = st.toggle(
                "Include all-period summary",
                value=ss.get("counts_include_all", False),
                key="modal_include_all",
            )
            ss["counts_include_all"] = include_all
        with _all_t_col:
            if include_all:
                _cur_all_t_min = int(ss.get("counts_all_t", "15min").replace("min", ""))
                _all_t_idx = _all_t_options.index(_cur_all_t_min) if _cur_all_t_min in _all_t_options else 4
                _all_t_min = st.selectbox(
                    "All-period interval (minutes)",
                    options=_all_t_options,
                    index=_all_t_idx,
                    key="modal_all_t",
                )
                ss["counts_all_t"] = f"{_all_t_min}min"

        st.markdown("### Modal")
        try:
            modal_df = survey.modal(
                cols=[parameter_col],
                by_date=False,
                day_t=day_t,
                evening_t=evening_t,
                night_t=night_t,
                include_all=include_all,
                all_t=ss.get("counts_all_t", "15min"),
            )
            ss["modal_df"] = modal_df
            if modal_df is not None and not modal_df.empty:
                st.dataframe(modal_df, width='stretch')
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
                include_all=include_all,
                all_t=ss.get("counts_all_t", "15min"),
            )
            ss["counts"] = counts_df
            if counts_df is not None and not counts_df.empty:
                st.dataframe(counts_df, width='stretch')
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

    with summary_tabs[4]:
        st.subheader("Peak Picker")
        st.caption(
            "Select a log and pivot column to find the K highest or K lowest"
            " values and view their corresponding spectra."
        )

        log_options = list(ss["logs"].keys())
        if not log_options:
            st.info("No logs loaded.")
        else:
            selected_log = st.selectbox(
                "Select log",
                options=log_options,
                index=0,
                key="peak_picker_log",
            )

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                pivot_family = st.selectbox(
                    "Pivot column",
                    options=["Lmax", "Leq", "L90", "L10", "Lmin", "Lpeak"],
                    index=0,
                    key="peak_picker_family",
                )
            with col2:
                k_val = st.number_input(
                    "K (number of peaks)",
                    min_value=1,
                    max_value=100,
                    value=3,
                    step=1,
                    key="peak_picker_k",
                )
            with col3:
                high_low = st.radio(
                    "Direction",
                    options=["Highest", "Lowest"],
                    index=0,
                    key="peak_picker_direction",
                )
            with col4:
                exclusion_zone = st.number_input(
                    "Exclusion zone (seconds)",
                    min_value=0.0,
                    max_value=3600.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f",
                    key="peak_picker_exclusion",
                    help="If set, no two peaks can be within this many seconds of "
                         "each other. The algorithm greedily picks the best peak, "
                         "then skips any others within the exclusion window. "
                         "Accepts fractional values (e.g. 0.5, 1.6).",
                )

            try:
                log_obj = ss["logs"].get(selected_log)
                if log_obj is None:
                    st.error("Selected log not found.")
                else:
                    data = log_obj.get_data()
                    pivot_candidates = [
                        c for c in data.columns
                        if c[0] == pivot_family
                    ]
                    if not pivot_candidates:
                        st.warning(f"No columns found for family {pivot_family!r}.")
                    else:
                        band_label = st.selectbox(
                            "Band",
                            options=[str(c[1]) for c in pivot_candidates],
                            index=0,
                            key="peak_picker_band",
                        )
                        band_val = pivot_candidates[0][1]
                        for c in pivot_candidates:
                            if str(c[1]) == band_label:
                                band_val = c[1]
                                break
                        pivot_col = (pivot_family, band_val)

                        survey = ss.get("survey")
                        if survey is not None:
                            peaks_df, history = survey.peak_picker(
                                log_name=selected_log,
                                pivot_col=pivot_col,
                                k=int(k_val),
                                high=(high_low == "Highest"),
                                exclusion_zone_s=exclusion_zone,
                            )

                            if not peaks_df.empty:
                                st.subheader("Time history with peaks")
                                import plotly.graph_objects as go
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=history.index,
                                    y=history.values,
                                    mode="lines",
                                    name=str(pivot_col),
                                    line=dict(color="#1f77b4"),
                                ))
                                peak_times = peaks_df.index
                                peak_vals = history.loc[peak_times]
                                fig.add_trace(go.Scatter(
                                    x=peak_times,
                                    y=peak_vals,
                                    mode="markers",
                                    name=f"Top {int(k_val)} peaks",
                                    marker=dict(
                                        color="red",
                                        size=10,
                                        symbol="circle",
                                    ),
                                ))
                                fig.update_layout(
                                    xaxis_title="Time",
                                    yaxis_title=f"{pivot_col} [dB]",
                                    height=400,
                                    margin=dict(l=40, r=20, t=20, b=40),
                                )
                                st.plotly_chart(fig, width='stretch')

                                st.subheader("Peak spectra")
                                # Filter out internal columns
                                drop_cols_set = {("Night idx", ""), ("Time", ""), "Time", ("Night idx",)}
                                spectral_cols = [c for c in peaks_df.columns if c not in drop_cols_set]

                                # Sort columns: pivot family first, then other families
                                # alphabetically; within each family, bands sort numerically
                                # where possible (e.g. 20, 25, 31.5, 40 … not 100, 1000 …).
                                def _peak_col_sort_key(col):
                                    family = col[0] if isinstance(col, tuple) else str(col)
                                    band = col[1] if isinstance(col, tuple) and len(col) > 1 else ""
                                    # Primary: pivot family first
                                    pivot_order = 0 if family == pivot_family else 1
                                    # Secondary: band as numeric value, or string
                                    try:
                                        band_key = (0, float(band))
                                    except (ValueError, TypeError):
                                        band_key = (1, str(band))
                                    return (pivot_order, family, band_key)

                                display_cols = sorted(spectral_cols, key=_peak_col_sort_key)
                                display_df = peaks_df[display_cols] if display_cols else peaks_df
                                st.dataframe(display_df, width='stretch')

                                # Build combined peaks across ALL logs for download
                                survey_in = ss.get("survey")
                                all_peaks_list = []
                                if survey_in is not None:
                                    for name in ss["logs"].keys():
                                        try:
                                            pk, _ = survey_in.peak_picker(
                                                log_name=name,
                                                pivot_col=pivot_col,
                                                k=int(k_val),
                                                high=(high_low == "Highest"),
                                                exclusion_zone_s=exclusion_zone,
                                            )
                                            if not pk.empty:
                                                pk = pk.rename_axis("Timestamp")
                                                pk["Log"] = name
                                                all_peaks_list.append(pk)
                                        except Exception:
                                            pass

                                if all_peaks_list:
                                    combined_peaks = pd.concat(all_peaks_list)
                                else:
                                    combined_peaks = peaks_df.copy()
                                    combined_peaks = combined_peaks.rename_axis("Timestamp")
                                    combined_peaks["Log"] = selected_log

                                # Reorder combined_peaks columns to match display column order
                                # so that the CSV mirrors the table grouping.
                                existing_display = [c for c in display_cols if c in combined_peaks.columns]
                                extra_cols = [c for c in combined_peaks.columns if c not in display_cols and c not in drop_cols_set]
                                ordered_cols = existing_display + extra_cols + ["Log"]
                                combined_peaks = combined_peaks[ordered_cols]

                                st.download_button(
                                    "Download peaks CSV (all logs)",
                                    data=to_csv_preserve_multiheader(combined_peaks),
                                    file_name="peak_picker.csv",
                                    mime="text/csv",
                                    key="dl_peak_csv",
                                )
                            else:
                                st.info("No peaks found for the current selection.")
            except Exception as exc:
                st.error(f"Peak Picker failed: {exc}")
