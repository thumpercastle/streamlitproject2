import streamlit as st
import pandas as pd
import plotly.express as px

from st_config import init_app_state
from st_config import _build_survey

ss = init_app_state()


def weather_page():
    st.header("Weather history", divider=True)
    st.markdown(
        "Fetch historic weather snapshots using the survey’s overall time range "
        "(earliest log start → latest log end) via OpenWeather One Call 3.0 Time Machine."
    )

    # Need logs and a survey that contains those logs
    if not ss.get("logs"):
        st.warning("No logs uploaded yet. Upload logs first to define the survey start/end.", icon=":material/info:")
        st.stop()

    # replace the "Survey is not ready" guard with:
    period_times = ss.get("period_times") or ss.get("times")
    ss["survey"] = _build_survey(times=period_times)
    survey = ss["survey"]

    # Session defaults (local, so you don't have to change init_app_state if you don't want to)
    ss.setdefault("weather_country", "GB")
    ss.setdefault("weather_postcode", "")
    ss.setdefault("weather_units", "metric")
    ss.setdefault("weather_interval_hours", 12)
    ss.setdefault("weather_timeout_s", 30)
    ss.setdefault("owm_api_key", "")
    ss.setdefault("weather_df", pd.DataFrame())
    ss.setdefault("weather_show_raw", False)

    with st.form("weather_form", border=True):
        c1, c2, c3 = st.columns([1, 2, 2])

        with c1:
            country = st.text_input(
                "Country code",
                value=ss["weather_country"],
                help='Two-letter ISO country code, e.g. "GB", "FR".',
                max_chars=2,
            ).strip().upper()

        with c2:
            postcode = st.text_input(
                "Postcode",
                value=ss["weather_postcode"],
                help="Postal code used to resolve lat/lon.",
            ).strip()

        with c3:
            api_key = st.text_input(
                "OpenWeatherMap API key",
                value=ss["owm_api_key"],
                type="password",
                help="Kept in session state for this app session only.",
            ).strip()

        adv1, adv2, adv3, adv4 = st.columns([1, 1, 1, 1])
        with adv1:
            interval_hours = st.number_input(
                "Interval (hours)",
                min_value=1,
                max_value=48,
                step=1,
                value=int(ss["weather_interval_hours"]),
                help="How often to fetch a snapshot between survey start/end.",
            )
        with adv2:
            units = st.selectbox(
                "Units",
                options=["metric", "imperial", "standard"],
                index=["metric", "imperial", "standard"].index(ss["weather_units"]),
            )
        with adv3:
            timeout_s = st.number_input(
                "Timeout (s)",
                min_value=5,
                max_value=120,
                step=5,
                value=int(ss["weather_timeout_s"]),
            )
        with adv4:
            recompute = st.toggle(
                "Recompute",
                value=False,
                help="If on, forces a fresh fetch even if cached.",
            )

        drop_default = ["sunrise", "sunset", "feels_like", "dew_point", "visibility"]
        drop_cols = st.multiselect(
            "Drop columns",
            options=[
                "sunrise",
                "sunset",
                "feels_like",
                "dew_point",
                "visibility",
                # allow users to drop additional common fields if they exist
                "pressure",
                "humidity",
                "clouds",
                "uvi",
                "wind_gust",
            ],
            default=[c for c in drop_default],
            help="Columns to remove from the returned table (only dropped if present).",
        )

        show_raw = st.checkbox("Show raw response count", value=bool(ss["weather_show_raw"]))

        submitted = st.form_submit_button("Fetch weather history", use_container_width=True)

    # Persist inputs
    ss["weather_country"] = country
    ss["weather_postcode"] = postcode
    ss["owm_api_key"] = api_key
    ss["weather_units"] = units
    ss["weather_interval_hours"] = int(interval_hours)
    ss["weather_timeout_s"] = int(timeout_s)
    ss["weather_show_raw"] = bool(show_raw)

    if not submitted:
        # If cached data exists, show it
        if isinstance(ss.get("weather_df"), pd.DataFrame) and not ss["weather_df"].empty:
            st.subheader("Last fetched weather history")
            st.dataframe(ss["weather_df"], use_container_width=True)
        else:
            st.info("Enter details above and click **Fetch weather history**.")
        return

    # Validate inputs
    if len(country) != 2:
        st.error("Country code must be 2 letters (e.g. GB).")
        return
    if not postcode:
        st.error("Please enter a postcode.")
        return
    if not api_key:
        st.error("Please enter an OpenWeatherMap API key.")
        return

    # Compute
    with st.spinner("Fetching weather history from OpenWeather…"):
        try:
            # Configure (explicitly) so user settings are applied even if previously configured
            survey.weather_config(
                interval_hours=int(interval_hours),
                api_key=api_key,
                country=country,
                postcode=postcode,
                units=units,
                recompute=recompute,
            )
            df = survey.weather_compute(
                drop_cols=list(drop_cols) if drop_cols else None,
                recompute=recompute,
                timeout_s=int(timeout_s),
            )
        except Exception as e:
            st.error(f"Failed to fetch weather history: {e}")
            return

    if df is None or df.empty:
        st.warning("No weather data returned.")
        ss["weather_df"] = pd.DataFrame()
        return

    ss["weather_df"] = df

    st.subheader("Weather history")
    st.dataframe(df, use_container_width=True)

    if show_raw:
        try:
            raw = survey.get_weather_raw()
            st.caption(f"Raw payloads cached: {0 if raw is None else len(raw)}")
        except Exception:
            st.caption("Raw payloads unavailable.")

    # Quick plots (only if the columns exist)
    st.subheader("Quick charts")
    chart_cols = st.columns(2)

    if "dt" in df.columns:
        plot_df = df.copy()
        plot_df["dt"] = pd.to_datetime(plot_df["dt"], errors="coerce")
        plot_df = plot_df.dropna(subset=["dt"])

        if "temp" in plot_df.columns:
            with chart_cols[0]:
                fig = px.line(plot_df, x="dt", y="temp", title="Temperature")
                st.plotly_chart(fig, use_container_width=True)
        else:
            with chart_cols[0]:
                st.info("No `temp` column available to plot.")

        wind_col = "wind_speed" if "wind_speed" in plot_df.columns else None
        if wind_col:
            with chart_cols[1]:
                fig = px.line(plot_df, x="dt", y=wind_col, title="Wind speed")
                st.plotly_chart(fig, use_container_width=True)
        else:
            with chart_cols[1]:
                st.info("No `wind_speed` column available to plot.")
    else:
        st.info("No `dt` column available for time-series plotting.")