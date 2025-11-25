import os
import tempfile
import datetime as dt
import streamlit as st
import pycoustic as pc
import pandas as pd
from typing import Dict, Tuple
import plotly.graph_objects as go


from st_config import (
    init_app_state,
    TEMPLATE,
    COLOURS,
    get_data,
    _convert_for_download,
    _cleanup_tmp_files,
    parse_times,
    default_times,
    _render_upload_modal_contents,
    _get_template_dataframe,
    _convert_for_download,
    _reset_workspace
)

from page_1 import page_1
from page_2 import page_2

ss = init_app_state()


def page_3():
    st.title("Individual Logs")
    log_items = list(ss.get("logs", {}).items())
    if not log_items:
        st.info("No logs loaded yet.")
    tab_labels = [name for name, _ in log_items]
    tabs = st.tabs(tab_labels)

    # Overview tab content

    # One tab per log - assumes the same layout in each
    for idx, (name, log) in enumerate(log_items, start=0):
        with tabs[idx]:
            period = st.selectbox(
                label="Resample period (minutes). Must be >= survey measurement period.",
                options=[1, 2, 5, 10, 15, 30, 60, 120],
                index=4,
                key=f"period_{name}"
            )
            period = str(period) + "min"
            graph_df = log.as_interval(t=period)
            st.markdown(f"## {name} time history plot")
            # TODO: Add option for user to choose which columns are required
            required_cols = [("Leq", "A"), ("Lmax", "A"), ("L90", "A")]
            if set(map(tuple, required_cols)).issubset(set(graph_df.columns.to_flat_index())):
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=graph_df.index,
                        y=graph_df[("Leq", "A")],
                        name="Leq A",
                        mode="lines",
                        line=dict(color=COLOURS["Leq A"], width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=graph_df.index,
                        y=graph_df[("L90", "A")],
                        name="L90 A",
                        mode="lines",
                        line=dict(color=COLOURS["L90 A"], width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=graph_df.index,
                        y=graph_df[("Lmax", "A")],
                        name="Lmax A",
                        mode="markers",
                        marker=dict(color=COLOURS["Lmax A"], size=3),
                    )
                )
                fig.update_layout(
                    template=TEMPLATE,
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis=dict(
                        title="Time & Date (hh:mm & dd/mm/yyyy)",
                        type="date",
                        tickformat="%H:%M<br>%d/%m/%Y",
                        tickangle=0,
                    ),
                    yaxis_title="Measured Sound Pressure Level dB(A)",
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0),
                    height=600,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"Required columns {required_cols} missing in {name}.")

            st.markdown(f"## {name} resampled data")
            st.dataframe(graph_df, key="master", width="stretch")

            # TODO: Enable value counts for other parameters
            # counts = pd.DataFrame([survey.counts().loc[name]["Daytime"], survey.counts().loc[name]["Night-time"]]).T
            # counts = survey.counts()
            st.dataframe(ss["counts"].loc[name], key=f"counts_df_{name}", width="stretch")

            st.markdown(f"## {name} L90 value counts")
            fig = ss["counts"].loc[name].plot.bar(facet_row="variable")
            st.plotly_chart(fig, key=f"counts_bar_{name}", config={
                "y": "Occurrences",
                "x": "dB",
                "color": "Period",
                "theme": None
            }) #TODO: These kwargs don't work.
