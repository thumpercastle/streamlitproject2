import datetime as dt

import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from streamlitproject2.app_state import (
    DEFAULT_PERIODS,
    build_survey,
    init_app_state,
    parse_times,
    rerun_app,
)

ss = init_app_state()

DEFAULT_PLOT_STYLES = {
    "Leq A": {"color": "#FBAE18", "dash": "solid", "width": 1, "mode": "lines"},
    "L90 A": {"color": "#4D4D4D", "dash": "solid", "width": 1, "mode": "lines"},
    "Lmax A": {"color": "#B51724", "dash": "solid", "width": 1, "mode": "markers"},
}
CHART_COLUMNS = {
    "Leq A": ("Leq", "A"),
    "L90 A": ("L90", "A"),
    "Lmax A": ("Lmax", "A"),
}
DASH_OPTIONS = ["solid", "dash", "dot", "dashdot"]
MODE_LABELS = {
    "lines": "Lines",
    "lines+markers": "Lines + markers",
    "markers": "Markers",
}

dialog_decorator = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

if "plot_styles" not in ss or not ss["plot_styles"]:
    ss["plot_styles"] = {metric: style.copy() for metric, style in DEFAULT_PLOT_STYLES.items()}
ss.setdefault("plot_template", "plotly")
ss.setdefault("graph_selected_log", "")
ss.setdefault("graph_resample_period", 15)
ss.setdefault("show_chart_style_modal", False)
ss.setdefault("resampled_dfs", {})


def _to_time(hours: int, minutes: int) -> dt.time:
    return dt.time(hours, minutes)


def _render_style_controls() -> None:
    st.caption("Adjust colours, line styles, and marker options for each metric.")
    style_columns = st.columns(len(DEFAULT_PLOT_STYLES))
    mode_options = list(MODE_LABELS.keys())

    for idx, metric in enumerate(DEFAULT_PLOT_STYLES):
        col = style_columns[idx]
        defaults = DEFAULT_PLOT_STYLES[metric]
        current_style = ss["plot_styles"].get(metric, defaults.copy())

        color_key = f"style_{metric.replace(' ', '_').lower()}_color"
        dash_key = f"style_{metric.replace(' ', '_').lower()}_dash"
        width_key = f"style_{metric.replace(' ', '_').lower()}_width"
        mode_key = f"style_{metric.replace(' ', '_').lower()}_mode"

        color_default = current_style.get("color", defaults["color"])
        dash_default = current_style.get("dash", defaults["dash"])
        if dash_default not in DASH_OPTIONS:
            dash_default = DASH_OPTIONS[0]
        width_default = int(current_style.get("width", defaults["width"]))
        width_default = min(max(width_default, 1), 6)
        mode_default = current_style.get("mode", defaults["mode"])
        if mode_default not in mode_options:
            mode_default = mode_options[0]

        color_value = col.color_picker(
            f"{metric} colour",
            color_default,
            key=color_key,
        )
        dash_value = col.selectbox(
            f"{metric} line style",
            options=DASH_OPTIONS,
            index=DASH_OPTIONS.index(dash_default),
            key=dash_key,
        )
        width_value = col.slider(
            f"{metric} width",
            min_value=1,
            max_value=6,
            value=width_default,
            key=width_key,
        )
        mode_value = col.selectbox(
            f"{metric} display",
            options=mode_options,
            index=mode_options.index(mode_default),
            format_func=lambda option: MODE_LABELS.get(option, option),
            key=mode_key,
        )

        ss["plot_styles"][metric] = {
            "color": color_value,
            "dash": dash_value,
            "width": width_value,
            "mode": mode_value,
        }

    reset_col, close_col = st.columns([1, 1])
    with reset_col:
        if st.button("Reset to defaults", key="chart_style_reset"):
            ss["plot_styles"] = {metric: style.copy() for metric, style in DEFAULT_PLOT_STYLES.items()}
            for metric in DEFAULT_PLOT_STYLES:
                base = metric.replace(" ", "_").lower()
                st.session_state[f"style_{base}_color"] = DEFAULT_PLOT_STYLES[metric]["color"]
                st.session_state[f"style_{base}_dash"] = DEFAULT_PLOT_STYLES[metric]["dash"]
                st.session_state[f"style_{base}_width"] = DEFAULT_PLOT_STYLES[metric]["width"]
                st.session_state[f"style_{base}_mode"] = DEFAULT_PLOT_STYLES[metric]["mode"]
            rerun_app()
    with close_col:
        if st.button("Done", type="primary", key="chart_style_close"):
            ss["show_chart_style_modal"] = False
            rerun_app()


def _build_log_figure(log_name: str, frame: pd.DataFrame, template: str) -> go.Figure:
    fig = go.Figure()
    for metric, column in CHART_COLUMNS.items():
        style = ss["plot_styles"].get(metric, DEFAULT_PLOT_STYLES[metric])
        mode = style.get("mode", "lines")
        trace_kwargs = {
            "x": frame.index,
            "y": frame[column],
            "name": metric,
            "mode": mode,
        }
        if "lines" in mode:
            trace_kwargs["line"] = {
                "color": style.get("color"),
                "width": style.get("width", 3),
                "dash": style.get("dash", "solid"),
            }
        if "markers" in mode:
            trace_kwargs["marker"] = {"color": style.get("color"), "size": 6}
        fig.add_trace(go.Scatter(**trace_kwargs))

    fig.update_layout(
        template=template,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(
            title="Time & Date (hh:mm & dd/mm/yyyy)",
            type="date",
            tickformat="%H:%M<br>%d/%m/%Y",
        ),
        yaxis_title="Measured Sound Pressure Level dB(A)",
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="left", x=0),
        height=520,
    )
    return fig


def _export_frames_to_excel(frames: dict[str, pd.DataFrame]) -> bytes | None:
    if not frames:
        return None

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, frame in frames.items():
            if frame.empty:
                continue
            safe_sheet = sheet_name[:31] or "Sheet1"
            export_frame = frame.copy()
            if isinstance(export_frame.columns, pd.MultiIndex):
                export_frame.columns = [
                    " | ".join(str(level) for level in col if level not in (None, ""))
                    for col in export_frame.columns.to_flat_index()
                ]
            if isinstance(export_frame.index, pd.MultiIndex):
                export_frame = export_frame.reset_index()
            export_frame.to_excel(writer, sheet_name=safe_sheet, index=False)
    output.seek(0)
    data = output.getvalue()
    return data if data else None


def _show_style_modal() -> None:
    if dialog_decorator:
        try:
            decorator = dialog_decorator("Customise chart appearance", width="large")
        except TypeError:
            decorator = dialog_decorator("Customise chart appearance")

        @decorator
        def _modal() -> None:
            _render_style_controls()

        _modal()
    else:
        st.markdown("### Customise chart appearance")
        _render_style_controls()


st.title("Interactive Graphs")
st.markdown("> Inspect log time histories with tailor-made styling and resampling options.")

logs_available = list(ss["logs"].keys())
if not logs_available:
    st.warning("No logs have been uploaded yet. Use the Home page to add data.", icon=":material/info:")
    st.stop()

resample_options = [1, 2, 5, 10, 15, 30, 60, 120]
current_resample = ss.get("global_resample_period", ss.get("graph_resample_period", 15))
if current_resample not in resample_options:
    current_resample = 15
ss["global_resample_period"] = current_resample

with st.sidebar:
    current_periods = ss.get("period_times", DEFAULT_PERIODS.copy())
    with st.expander("Survey periods", expanded=False):
        day_start = st.time_input(
            "Day starts",
            value=_to_time(*current_periods["day"]),
            key="graphs_time_day",
        )
        evening_start = st.time_input(
            "Evening starts",
            value=_to_time(*current_periods["evening"]),
            key="graphs_time_evening",
        )
        night_start = st.time_input(
            "Night starts",
            value=_to_time(*current_periods["night"]),
            key="graphs_time_night",
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
        st.caption("Updates apply immediately to the chart and the downloadable datasets.")

resample_period = ss.get("global_resample_period", 15)
ss["graph_resample_period"] = resample_period
if logs_available:
    ss["graph_selected_log"] = logs_available[0]

resampled_frames: dict[str, pd.DataFrame] = {}
export_frames: dict[str, pd.DataFrame] = {}

for log_name, log in ss["logs"].items():
    frame = log.as_interval(t=f"{resample_period}min")
    frame.index.name = "Timestamp"
    resampled_frames[log_name] = frame

    export_df = frame.reset_index()
    export_df.insert(1, "Log", log_name)
    export_frames[log_name] = export_df

ss["resampled_dfs"] = export_frames
ss["resampled_df"] = export_frames.get(logs_available[0], pd.DataFrame())

if ss.get("show_chart_style_modal"):
    _show_style_modal()

required_columns = set(CHART_COLUMNS.values())
plot_template = ss.get("plot_template", "plotly")
log_tabs = st.tabs(logs_available)
for tab, log_name in zip(log_tabs, logs_available):
    frame = resampled_frames.get(log_name)
    if frame is None:
        continue

    with tab:
        available_flat = set(frame.columns.to_flat_index())
        if required_columns.issubset(available_flat):
            fig = _build_log_figure(log_name, frame, plot_template)
            st.plotly_chart(fig, use_container_width=True)
        else:
            missing = sorted(required_columns - available_flat)
            st.warning(
                f"Cannot render the chart because expected columns {missing} are missing from {log_name}.",
                icon=":material/insights:",
            )

        indicator_cols = st.columns([2, 1, 1, 1])
        with indicator_cols[0]:
            if st.button(
                "Customise chart",
                key=f"open_chart_style_modal_{log_name}",
                use_container_width=True,
            ):
                ss["show_chart_style_modal"] = True
                rerun_app()
        with indicator_cols[1]:
            st.metric("Selected log", log_name)
        with indicator_cols[2]:
            st.metric("Resample (min)", str(resample_period))
        with indicator_cols[3]:
            st.metric("Records", f"{len(frame):,}")

        if frame.empty:
            st.caption("Time window: no data points available.")
        else:
            start_ts = frame.index.min()
            end_ts = frame.index.max()
            if isinstance(start_ts, (pd.Timestamp, dt.datetime)):
                start_text = start_ts.strftime("%d %b %Y %H:%M")
            else:
                start_text = str(start_ts)
            if isinstance(end_ts, (pd.Timestamp, dt.datetime)):
                end_text = end_ts.strftime("%d %b %Y %H:%M")
            else:
                end_text = str(end_ts)
            st.caption(f"Time window: {start_text} to {end_text}")

        st.markdown("#### Resampled data")
        st.dataframe(frame, use_container_width=True)
        st.caption("Resampled values appear in the Data summary export workbook.")

export_sources: dict[str, pd.DataFrame] = {}

if isinstance(ss.get("resi_df"), pd.DataFrame) and not ss["resi_df"].empty:
    export_sources["Broadband Summary"] = ss["resi_df"]
if isinstance(ss.get("leq_df"), pd.DataFrame) and not ss["leq_df"].empty:
    export_sources["Leq Spectra"] = ss["leq_df"]
if isinstance(ss.get("lmax_df"), pd.DataFrame) and not ss["lmax_df"].empty:
    export_sources["Lmax Spectra"] = ss["lmax_df"]
if isinstance(ss.get("modal_df"), pd.DataFrame) and not ss["modal_df"].empty:
    export_sources["Modal Values"] = ss["modal_df"]

for log_name, frame in export_frames.items():
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        export_sources[f"Resampled - {log_name}"] = frame

export_bytes = _export_frames_to_excel(export_sources) if export_sources else None

with st.sidebar:
    with st.expander("Export", expanded=bool(export_bytes)):
        if export_bytes:
            st.download_button(
                "Export calculated data to Excel",
                data=export_bytes,
                file_name="pycoustic-analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="graphs_export_excel",
                icon=":material/download:",
            )
            st.caption("Workbook includes summary datasets plus per-log resampled sheets.")
        else:
            st.caption("Export becomes available once datasets are generated.")
