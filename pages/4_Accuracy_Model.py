import altair as alt
import pandas as pd
import streamlit as st
from altair import datum

from functools import partial
import src.chart_config as chart_config
from src import ttk_analyzer
import src.data_helper as data_helper
from src.dynamic_filters import DynamicFilters
import numpy as np

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="Accuracy Model",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)

with st.spinner("Loading data..."):
    guns_df, _, _ = data_helper.get_gun_stats()
    fights_df = data_helper.get_fights_data()



def plot_accuracy_models(accuracy_model_df):
    accuracy_cdf_line = alt.Chart(accuracy_model_df).mark_line().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)', labelAngle=0)),
        y=alt.Y("cdf", axis=alt.Axis(title='CDF', format=".2f")),
        color=alt.Color('model_name:N', legend=alt.Legend(title="Model"), scale=alt.Scale(scheme='category20')),

    ).properties(
        title="Single Shot Accuracy CDF",
        width=400,
        height=400,
    )

    accuracy_pdf_line = alt.Chart(accuracy_model_df).mark_line().encode(
        x=alt.X('accuracy', axis=alt.Axis(title='Accuracy (%)', labelAngle=0)),
        y=alt.Y("pdf", axis=alt.Axis(title='PDF', format=".2f")),
        color=alt.Color('model_name:N', legend=alt.Legend(title="Model"), scale=alt.Scale(scheme='category20')),
    ).properties(
        title="Single Shot Accuracy PDF",
        width=400,
        height=400,
    )

    return accuracy_cdf_line, accuracy_pdf_line



selected_estimation_method = "Expected Value"

selected_weapons_df = pd.DataFrame()

accuracy_model_df = ttk_analyzer.get_estimation_model(guns_df,
                                                      fights_df,
                                                      selected_estimation_method,
                                                      selected_weapons_df)
accuracy_plots = plot_accuracy_models(accuracy_model_df)

st.altair_chart(accuracy_plots[0], use_container_width=True)
st.altair_chart(accuracy_plots[1], use_container_width=True)

