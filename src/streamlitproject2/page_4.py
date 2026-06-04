import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from st_config import TEMPLATE, _build_survey, init_app_state

ss = init_app_state()


def _safe_get_survey_time_bounds(selected_logs: list[str]) -> tuple[object, object]:
    logs = ss.get("logs", {})
    starts = []
    ends = []

    for name in selected_logs:
        log = logs.get(name)
        if log is None:
            continue

        try:
            starts.append(log.get_start())
        except Exception:
            pass

        try:
            ends.append(log.get_end())
        except Exception:
            pass

    start = min(starts) if starts else None
    end = max(ends) if ends else None
    return start, end


def _get_weather_source(survey):
    weather_obj = getattr(survey, "_weather", None)
    if weather_obj is None:
        raise RuntimeError("Weather service is not available on the current survey object.")
    return weather_obj


def _prepare_weather_dataframe(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    prepared = df.copy()

    if "dt" in prepared.columns:
        prepared["dt"] = pd.to_datetime(prepared["dt"], errors="coerce")

    numeric_candidates = [
        "temp",
        "feels_like",
        "dew_point",
        "pressure",
        "humidity",
        "wind_speed",
        "wind_deg",
        "wind_gust",
        "clouds",
        "visibility",
        "rain",
        "snow",
    ]
    for col in numeric_candidates:
        if col in prepared.columns:
            prepared[col] = pd.to_numeric(prepared[col], errors="coerce")

    return prepared


def _line_chart(df: pd.DataFrame, x_col: str, y_cols: list[str], title: str) -> go.Figure:
    fig = go.Figure()

    for col in y_cols:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df[x_col],
                    y=df[col],
                    mode="lines+markers",
                    name=col,
                )
            )

    fig.update_layout(
        template=TEMPLATE,
        title=title,
        margin=dict(l=0, r=0, t=48, b=0),
        height=420,
        xaxis_title="Time",
        yaxis_title="Value",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def weather_page() -> None:
    st.title("Weather")
    st.markdown(
        "> Fetch weather history covering the selected survey period and compare it with your uploaded acoustic logs."
    )

    logs_available = list(ss["logs"].keys())
    if not logs_available:
        st.warning("No logs have been uploaded yet. Use the Data Loader page to add data.")
        st.stop()

    selected_logs = ss.get("analysis_selected_logs") or logs_available
    if not selected_logs:
        selected_logs = logs_available

    st.caption(f"Using {len(selected_logs)} selected log(s) for weather time bounds.")

    with st.form("weather_controls"):
        c1, c2 = st.columns(2)
        with c1:
            country = st.text_input(
                "Country code",
                value=ss.get("weather_country", "GB"),
                help="Example: GB",
            ).strip().upper()
        with c2:
            postcode = st.text_input(
                "Postcode / ZIP",
                value=ss.get("weather_postcode", ""),
                help="Example: WC1",
            ).strip()

        c3, c4 = st.columns(2)
        with c3:
            units = st.selectbox(
                "Units",
                options=["metric", "imperial", "standard"],
                index=["metric", "imperial", "standard"].index(ss.get("weather_units", "metric")),
            )
        with c4:
            interval_hours = st.selectbox(
                "History interval (hours)",
                options=[1, 2, 3, 6, 12, 24],
                index=[1, 2, 3, 6, 12, 24].index(ss.get("weather_interval_hours", 12)),
            )

        api_key = st.text_input(
            "OpenWeather API key",
            value=ss.get("owm_api_key", ""),
            type="password",
            help="Enter your API key to fetch historical weather data.",
        ).strip()

        fetch_clicked = st.form_submit_button("Fetch weather history", use_container_width=True)

    ss["weather_country"] = country
    ss["weather_postcode"] = postcode
    ss["weather_units"] = units
    ss["weather_interval_hours"] = interval_hours
    ss["owm_api_key"] = api_key

    start, end = _safe_get_survey_time_bounds(selected_logs)

    info_cols = st.columns(2)
    info_cols[0].metric("Survey start", str(start) if start is not None else "—")
    info_cols[1].metric("Survey end", str(end) if end is not None else "—")

    if fetch_clicked:
        if not api_key:
            st.error("Enter an API key before fetching weather history.")
            st.stop()

        if not postcode:
            st.error("Enter a postcode or ZIP code before fetching weather history.")
            st.stop()

        if start is None or end is None:
            st.error("Could not determine survey time bounds from the selected logs.")
            st.stop()

        survey = _build_survey(times=ss.get("times"), log_names=selected_logs)
        ss["survey"] = survey

        try:
            weather_obj = _get_weather_source(survey)
            weather_obj.reinit(
                start=start,
                end=end,
                interval=int(interval_hours),
                api_key=api_key,
                country=country,
                postcode=postcode,
                tz=country,
                units=units,
            )
            weather_df = weather_obj.compute_weather_history(drop_cols=[])
            weather_df = _prepare_weather_dataframe(weather_df)
            ss["weather_df"] = weather_df
            st.success("Weather history loaded.")
        except Exception as exc:
            ss["weather_df"] = pd.DataFrame()
            st.error(f"Failed to fetch weather history: {exc}")

    weather_df = ss.get("weather_df")
    if weather_df is None or weather_df.empty:
        st.info("No weather data loaded yet.")
        st.stop()

    st.subheader("Weather history")

    if "dt" in weather_df.columns:
        temp_cols = [col for col in ["temp", "feels_like", "dew_point"] if col in weather_df.columns]
        wind_cols = [col for col in ["wind_speed", "wind_gust"] if col in weather_df.columns]
        sky_cols = [col for col in ["humidity", "clouds", "pressure"] if col in weather_df.columns]

        if temp_cols:
            st.plotly_chart(
                _line_chart(weather_df, "dt", temp_cols, "Temperature"),
                use_container_width=True,
            )

        chart_cols = st.columns(2)
        with chart_cols[0]:
            if wind_cols:
                st.plotly_chart(
                    _line_chart(weather_df, "dt", wind_cols, "Wind"),
                    use_container_width=True,
                )
        with chart_cols[1]:
            if sky_cols:
                st.plotly_chart(
                    _line_chart(weather_df, "dt", sky_cols, "Humidity / Cloud / Pressure"),
                    use_container_width=True,
                )

    st.dataframe(weather_df, use_container_width=True)

    ss["weather_show_raw"] = st.toggle(
        "Show raw weather object output table",
        value=ss.get("weather_show_raw", False),
    )

    if ss["weather_show_raw"]:
        st.markdown("### Raw weather data")
        st.dataframe(weather_df, use_container_width=True)