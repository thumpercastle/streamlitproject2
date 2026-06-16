import streamlit as st

from st_config import build_combined_csv_with_sections, init_app_state
from page_1 import config_page
from page_2 import analysis_page
from page_3 import vis_page
from page_4 import weather_page

ss = init_app_state()

st.set_page_config(page_title="Pycoustic Acoustic Survey Analyser", layout="wide")

pg = st.navigation(
    [
        st.Page(config_page, title="Data Loader"),
        st.Page(analysis_page, title="Analysis"),
        st.Page(vis_page, title="Visualisation"),
        st.Page(weather_page, title="Weather"),
    ]
)

with st.sidebar:
    st.caption(
        "This tool is a work in progress and may produce errors. "
        "Check results manually and use with care."
    )

    any_data = bool(ss.get("logs"))

    times = ss.get("times") or {}
    modal_params = ss.get("modal_params") or [("L90", "A"), "60min", "60min", "15min"]

    csv_bytes = build_combined_csv_with_sections(
        ss.get("broadband_df"),
        ss.get("leq_df"),
        ss.get("lmax_df"),
        ss.get("modal_df"),
        ss.get("counts"),
        day_start=times.get("day"),
        evening_start=times.get("evening"),
        night_start=times.get("night"),
        lmax_n=ss.get("lmax_n"),
        lmax_t=ss.get("lmax_t"),
        modal_param=modal_params[0],
        day_t=modal_params[1],
        evening_t=modal_params[2],
        night_t=modal_params[3],
    )

    st.download_button(
        label="Download all tables (CSV)",
        data=csv_bytes,
        file_name="pycoustic-analysis-tables.csv",
        mime="text/csv",
        key="dl_all_tables_csv",
        disabled=not any_data,
        width='stretch',
        help=(
            "Exports all summary tables into one CSV file with section headers "
            "and full multi-row column headers where applicable."
        ),
    )

pg.run()