import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from st_config import COLOURS, TEMPLATE, init_app_state

ss = init_app_state()


def _counts_series_for_log(counts_df, log_name: str) -> pd.Series:
    if counts_df is None:
        return pd.Series(dtype="float64")

    if isinstance(counts_df, pd.Series):
        if isinstance(counts_df.index, pd.MultiIndex):
            try:
                subset = counts_df.loc[log_name]
                if isinstance(subset, pd.Series):
                    return subset
            except Exception:
                return pd.Series(dtype="float64")
        return counts_df

    if isinstance(counts_df, pd.DataFrame):
        try:
            subset = counts_df.loc[log_name]
            if isinstance(subset, pd.Series):
                return subset
            if isinstance(subset, pd.DataFrame) and subset.shape[1] >= 1:
                return subset.iloc[:, 0]
        except Exception:
            return pd.Series(dtype="float64")

    return pd.Series(dtype="float64")


def _build_counts_figure(series: pd.Series, title: str) -> go.Figure:
    plot_series = pd.to_numeric(series, errors="coerce").dropna()
    if not plot_series.empty:
        try:
            sort_index = sorted(plot_series.index, key=lambda value: float(value))
            plot_series = plot_series.reindex(sort_index)
        except Exception:
            pass

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[str(x) for x in plot_series.index],
            y=plot_series.values,
            marker_color=COLOURS["Leq A"],
            name="Count",
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title=title,
        xaxis_title="Value (dB)",
        yaxis_title="Count",
        margin=dict(l=0, r=0, t=48, b=0),
        height=420,
        showlegend=False,
    )
    return fig


def _normalise_plot_column_name(col) -> str:
    if isinstance(col, tuple):
        return " ".join(str(part) for part in col if part not in (None, ""))
    return str(col)


def _time_history_colour(label: str, index: int) -> str:
    if label in COLOURS:
        return COLOURS[label]

    fallback_colours = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    return fallback_colours[index % len(fallback_colours)]


def vis_page() -> None:
    st.header("Visualisation", divider=True)

    log_items = list(ss["logs"].items())
    if not log_items:
        st.warning("No logs have been uploaded yet. Use the Data Loader page to add data.")
        st.stop()

    tabs = st.tabs([name for name, _ in log_items])

    modal_params = ss.get("modal_params") or [("L90", "A"), "60min", "60min", "15min"]
    modal_param = modal_params[0]
    day_t = modal_params[1]
    evening_t = modal_params[2]
    night_t = modal_params[3]

    default_plot_cols = [("Leq", "A"), ("Lmax", "A"), ("L90", "A")]

    for idx, (name, log) in enumerate(log_items):
        with tabs[idx]:
            period_minutes = st.selectbox(
                label="Resample period (minutes). Must be greater than or equal to the survey measurement period.",
                options=[1, 2, 5, 10, 15, 30, 60, 120],
                index=4,
                key=f"period_{name}",
            )
            period = f"{period_minutes}min"

            try:
                graph_df = log.as_interval(t=period)
            except Exception as exc:
                st.error(f"Failed to resample data for {name}: {exc}")
                continue

            st.subheader(f"{name} time history plot")

            if isinstance(graph_df.columns, pd.MultiIndex):
                available_cols = list(graph_df.columns.to_flat_index())
            else:
                available_cols = list(graph_df.columns)

            available_plot_cols = []
            for col in available_cols:
                series = pd.to_numeric(graph_df[col], errors="coerce")
                if series.notna().any():
                    available_plot_cols.append(col)

            default_selected_cols = [col for col in default_plot_cols if col in available_plot_cols]

            selected_cols = st.multiselect(
                "Select up to 9 columns to plot",
                options=available_plot_cols,
                default=default_selected_cols,
                format_func=_normalise_plot_column_name,
                max_selections=9,
                key=f"time_history_cols_{name}",
            )

            if selected_cols:
                fig = go.Figure()

                for trace_index, col in enumerate(selected_cols):
                    label = _normalise_plot_column_name(col)
                    series = pd.to_numeric(graph_df[col], errors="coerce")

                    if not series.notna().any():
                        continue

                    is_lmax = label == "Lmax A"

                    fig.add_trace(
                        go.Scatter(
                            x=graph_df.index,
                            y=series,
                            name=label,
                            mode="markers" if is_lmax else "lines",
                            line=dict(
                                color=_time_history_colour(label, trace_index),
                                width=2,
                            ) if not is_lmax else None,
                            marker=dict(
                                color=_time_history_colour(label, trace_index),
                                size=4,
                            ) if is_lmax else None,
                        )
                    )

                fig.update_layout(
                    template=TEMPLATE,
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis=dict(
                        title="Time & Date",
                        type="date",
                        tickformat="%H:%M<br>%d/%m/%Y",
                        tickangle=0,
                    ),
                    yaxis_title="Measured Sound Pressure Level dB(A)",
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.2,
                        xanchor="left",
                        x=0,
                    ),
                    height=600,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Select at least one column to display the time history plot.")

            st.subheader(f"{name} resampled data")
            st.dataframe(graph_df, use_container_width=True)

            st.divider()

            st.subheader(f"{name} counts", divider=True)
            st.info(
                f"Values = {modal_param[0]} {modal_param[1]}, "
                f"Daytime T = {day_t}, "
                f"Evening T = {evening_t}, "
                f"Night T = {night_t}"
            )
            st.caption("Change these settings on the Analysis page under the Modal and counts tab.")

            try:
                counts_df = ss["survey"].counts(
                    cols=[modal_param],
                    day_t=day_t,
                    evening_t=evening_t,
                    night_t=night_t,
                )
                ss["counts"] = counts_df
            except Exception as exc:
                st.error(f"Failed to compute counts for {name}: {exc}")
                continue

            log_counts = _counts_series_for_log(ss.get("counts"), name)
            if log_counts.empty:
                st.info("No counts data available for this log.")
            else:
                counts_fig = _build_counts_figure(log_counts, title=f"{name} value counts")
                st.plotly_chart(
                    counts_fig,
                    use_container_width=True,
                    config={
                        "displayModeBar": False,
                        "responsive": True,
                    },
                )