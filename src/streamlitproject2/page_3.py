import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from st_config import COLOURS, TEMPLATE, init_app_state

ss = init_app_state()

PERIOD_COLOURS = {
    "Daytime": "#FBAE18",
    "Evening": "#FF7F0E",
    "Night-time": "#4d4d4d",
    "All": "#1f77b4",
}


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


def _build_counts_figure(series: pd.Series, title: str, colour: str | None = None) -> go.Figure:
    if colour is None:
        colour = COLOURS["Leq A"]
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
            marker_color=colour,
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
        parts = []
        for part in col:
            if part in (None, ""):
                continue
            if isinstance(part, float) and part == int(part):
                parts.append(str(int(part)))
            else:
                parts.append(str(part))
        return " ".join(parts)
    return str(col)


def _prepare_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a display-ready copy: Night idx dropped, float bands shown as integers."""
    cols = [col for col in df.columns if _column_family(col) != "Night idx"]
    display = df[cols].copy()

    def _clean_col(col):
        if isinstance(col, tuple):
            return tuple(int(p) if isinstance(p, float) and p == int(p) else p for p in col)
        return col

    display.columns = [_clean_col(c) for c in display.columns]
    return display


def _split_column_parts(col) -> list[str]:
    if isinstance(col, tuple):
        return [str(part).strip() for part in col if str(part).strip()]
    return [part.strip() for part in str(col).split() if part.strip()]


def _column_family(col) -> str:
    parts = _split_column_parts(col)
    return parts[0] if parts else ""


def _column_band(col) -> str:
    parts = _split_column_parts(col)
    return parts[1] if len(parts) > 1 else ""


def _base_default_colour(col, index: int) -> str:
    label = _normalise_plot_column_name(col)
    if label in COLOURS:
        return COLOURS[label]

    family = _column_family(col)
    family_a_label = f"{family} A"
    if family_a_label in COLOURS:
        return COLOURS[family_a_label]

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


def _is_lmax_column(col) -> bool:
    return _column_family(col).lower() == "lmax"


def _column_matches_family(col, family: str) -> bool:
    family_lower = family.lower()
    parts = [part.lower() for part in _split_column_parts(col)]
    return family_lower in parts


def _default_plot_columns(available_plot_cols: list) -> list:
    selected = []

    for family in ["Leq", "Lmax", "L90"]:
        exact_a = next(
            (
                col
                for col in available_plot_cols
                if _column_matches_family(col, family) and _column_band(col).upper() == "A"
            ),
            None,
        )
        if exact_a is not None:
            selected.append(exact_a)
            continue

        fallback = next((col for col in available_plot_cols if _column_matches_family(col, family)), None)
        if fallback is not None:
            selected.append(fallback)

    return selected[:9]


def _default_trace_mode(col) -> str:
    return "point" if _is_lmax_column(col) else "line"


def _column_sort_key(col) -> tuple[int, str, str]:
    family_order = {"Leq": 0, "Lmax": 1, "L90": 2}
    family = _column_family(col)
    band = _column_band(col)
    return family_order.get(family, 99), family, band


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
                graph_df = log.as_interval(t=period, averaging=ss.get("l90_averaging", "log"))
            except Exception as exc:
                st.error(f"Failed to resample data for {name}: {exc}")
                continue

            st.subheader(f"{name} time history plot")

            if isinstance(graph_df.columns, pd.MultiIndex):
                available_cols = list(graph_df.columns.to_flat_index())
            else:
                available_cols = list(graph_df.columns)

            available_plot_cols = []
            debug_rows = []

            for col in available_cols:
                label = _normalise_plot_column_name(col)
                family = _column_family(col)
                band = _column_band(col)

                try:
                    series = pd.to_numeric(graph_df[col], errors="coerce")
                    numeric_values = int(series.notna().sum())
                except Exception:
                    series = pd.Series(dtype="float64")
                    numeric_values = 0

                include_col = numeric_values > 0
                if include_col:
                    available_plot_cols.append(col)

                debug_rows.append(
                    {
                        "Column": label,
                        "Family": family,
                        "Band": band,
                        "Numeric values": numeric_values,
                        "Available to plot": include_col,
                    }
                )

            available_plot_cols = sorted(available_plot_cols, key=_column_sort_key)
            default_selected_cols = _default_plot_columns(available_plot_cols)

            selected_cols = st.multiselect(
                "Select up to 9 columns to plot",
                options=available_plot_cols,
                default=default_selected_cols,
                format_func=_normalise_plot_column_name,
                max_selections=9,
                key=f"time_history_cols_{name}",
            )

            with st.expander("Plot column diagnostics", expanded=False):
                debug_df = pd.DataFrame(debug_rows).sort_values(
                    by=["Family", "Band", "Column"],
                    na_position="last",
                )
                st.dataframe(debug_df, use_container_width=True, hide_index=True)

                family_counts = {}
                for family in ["Leq", "Lmax", "L90"]:
                    family_counts[family] = sum(1 for col in available_plot_cols if _column_matches_family(col, family))
                st.caption(
                    f"Available plot columns by family: "
                    f"Leq={family_counts['Leq']}, "
                    f"Lmax={family_counts['Lmax']}, "
                    f"L90={family_counts['L90']}"
                )

            if selected_cols:
                st.markdown("#### Plot styling")

                for trace_index, col in enumerate(selected_cols):
                    label = _normalise_plot_column_name(col)
                    mode_key = f"time_history_mode_{name}_{label}"
                    colour_key = f"time_history_colour_{name}_{label}"

                    if mode_key not in ss:
                        ss[mode_key] = _default_trace_mode(col)
                    if colour_key not in ss:
                        ss[colour_key] = _base_default_colour(col, trace_index)

                style_columns = st.columns(3)
                for idx_col, col in enumerate(selected_cols):
                    label = _normalise_plot_column_name(col)
                    mode_key = f"time_history_mode_{name}_{label}"
                    colour_key = f"time_history_colour_{name}_{label}"

                    with style_columns[idx_col % 3]:
                        st.markdown(f"**{label}**")
                        ss[mode_key] = st.selectbox(
                            "Style",
                            options=["line", "point", "bar"],
                            index=["line", "point", "bar"].index(ss[mode_key]),
                            key=f"{mode_key}_widget",
                        )
                        ss[colour_key] = st.color_picker(
                            "Colour",
                            value=ss[colour_key],
                            key=f"{colour_key}_widget",
                        )

                fig = go.Figure()

                for trace_index, col in enumerate(selected_cols):
                    label = _normalise_plot_column_name(col)
                    series = pd.to_numeric(graph_df[col], errors="coerce")

                    if not series.notna().any():
                        continue

                    mode_value = ss.get(f"time_history_mode_{name}_{label}", _default_trace_mode(col))
                    colour_value = ss.get(f"time_history_colour_{name}_{label}", _base_default_colour(col, trace_index))

                    if mode_value == "bar":
                        fig.add_trace(
                            go.Bar(
                                x=graph_df.index,
                                y=series,
                                name=label,
                                marker_color=colour_value,
                            )
                        )
                    else:
                        scatter_mode = "lines" if mode_value == "line" else "markers"
                        fig.add_trace(
                            go.Scatter(
                                x=graph_df.index,
                                y=series,
                                name=label,
                                mode=scatter_mode,
                                line=dict(
                                    color=colour_value,
                                    width=2,
                                ) if mode_value == "line" else None,
                                marker=dict(
                                    color=colour_value,
                                    size=6 if mode_value == "point" else 4,
                                ) if mode_value == "point" else None,
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
                    barmode="overlay",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Select at least one column to display the time history plot.")

            st.subheader(f"{name} resampled data")
            st.dataframe(_prepare_display_df(graph_df), use_container_width=True)

            st.divider()

            st.subheader(f"{name} counts", divider=True)

            counts_col = modal_param
            counts_label = _normalise_plot_column_name(counts_col)

            st.caption(
                f"Column: **{counts_label}** · Day T: {day_t} · Evening T: {evening_t} · Night T: {night_t}. "
                "Change these on the **Analysis** page → **Modal and counts** tab."
            )

            stack_counts = st.toggle(
                "Overlay periods on one chart",
                value=ss.get("counts_facet_overlap", False),
                key=f"counts_stack_{name}",
            )
            ss["counts_facet_overlap"] = stack_counts

            period_defs = [("Daytime", "days", day_t), ("Night-time", "nights", night_t)]
            if log.is_evening():
                period_defs.insert(1, ("Evening", "evenings", evening_t))

            period_counts: dict = {}
            for period_label, period_key, period_t in period_defs:
                try:
                    interval_df = log.as_interval(t=period_t, averaging=ss.get("l90_averaging", "log"))
                    period_df = log.get_period(data=interval_df, period=period_key)
                    counts_series = log.counts(data=period_df, cols=[counts_col])
                    if not counts_series.empty:
                        period_counts[period_label] = counts_series
                except Exception as exc:
                    st.warning(f"Could not compute {period_label.lower()} counts: {exc}")

            if ss.get("counts_include_all", False):
                _all_t = ss.get("counts_all_t", "15min")
                try:
                    _all_interval = log.as_interval(t=_all_t, averaging=ss.get("l90_averaging", "log"))
                    _all_series = log.counts(data=_all_interval, cols=[counts_col])
                    if not _all_series.empty:
                        period_counts["All"] = _all_series
                except Exception as exc:
                    st.warning(f"Could not compute all-period counts: {exc}")

            if not period_counts:
                st.info("No counts data available for this log.")
            elif stack_counts:
                fig = go.Figure()
                for period_label, counts_series in period_counts.items():
                    plot_series = pd.to_numeric(counts_series, errors="coerce").dropna()
                    try:
                        sort_index = sorted(plot_series.index, key=lambda v: float(v))
                        plot_series = plot_series.reindex(sort_index)
                    except Exception:
                        pass
                    fig.add_trace(go.Bar(
                        x=[str(x) for x in plot_series.index],
                        y=plot_series.values,
                        name=period_label,
                        marker_color=PERIOD_COLOURS.get(period_label, "#7f7f7f"),
                        opacity=0.75,
                    ))
                fig.update_layout(
                    template=TEMPLATE,
                    title=f"{name} — {counts_label} counts by period",
                    xaxis_title="Value (dB)",
                    yaxis_title="Count",
                    margin=dict(l=0, r=0, t=48, b=0),
                    height=420,
                    barmode="overlay",
                    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="left", x=0),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": "hover", "responsive": True})
            else:
                chart_cols = st.columns(len(period_counts))
                for col_idx, (period_label, counts_series) in enumerate(period_counts.items()):
                    with chart_cols[col_idx]:
                        colour = PERIOD_COLOURS.get(period_label, COLOURS["Leq A"])
                        period_fig = _build_counts_figure(counts_series, title=period_label, colour=colour)
                        st.plotly_chart(
                            period_fig,
                            use_container_width=True,
                            config={"displayModeBar": "hover", "responsive": True},
                        )