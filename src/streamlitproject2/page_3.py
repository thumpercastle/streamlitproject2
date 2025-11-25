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
)

ss = init_app_state()


def vis_page():
    st.title("Visualisation")

    log_items = list(ss["logs"].items())

    if not log_items:
        st.warning("No logs have been uploaded yet. Use the Home page to add data.", icon=":material/info:")
        st.stop()

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
                st.plotly_chart(fig, width="stretch")
            else:
                st.warning(f"Required columns {required_cols} missing in {name}.")

            st.markdown(f"## {name} resampled data")
            st.dataframe(graph_df, key="master", width="stretch")

            # TODO: Enable value counts for other parameters
            # Suppose you computed this somewhere:
            counts_df = ss["survey"].counts()

            # Make a Streamlit‑friendly copy
            df_counts_plot = counts_df.copy()

            # 1) If columns are a MultiIndex, flatten them
            if isinstance(df_counts_plot.columns, pd.MultiIndex):
                flat_cols = []
                for tpl in df_counts_plot.columns:
                    # tpl may have length 1, 2, or more – join all levels into a string
                    flat_cols.append(" ".join(str(x) for x in tpl if x is not None))
                df_counts_plot.columns = flat_cols

            # 2) Ensure all column names are strings (handles any leftover non‑str labels)
            df_counts_plot.columns = [str(c) for c in df_counts_plot.columns]

            # 3) Now show it in Streamlit
            fig = ss["counts"].loc[name].plot.bar(facet_row="variable")
            st.plotly_chart(fig, key=f"counts_bar_{name}", config={
                "y": "Occurrences",
                "x": "dB",
                "color": "Period",
                "theme": None
            }) #TODO: These kwargs don't work.
            st.dataframe(df_counts_plot)

            # TODO: Enable value counts for other parameters
            # st.dataframe(ss["counts"].loc[name], key=f"counts_df_{name}", width="stretch")


            # st.dataframe(ss["counts"].loc[name], key=f"counts_df_{name}", width="stretch")
