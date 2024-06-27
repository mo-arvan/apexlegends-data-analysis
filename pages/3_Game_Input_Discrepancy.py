import logging

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import gaussian_kde

import src.data_helper as data_helper
import src.streamtlit_helper as streamlit_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="ALGS Fights Explorer",
    page_icon="📊",
    # layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)
st.markdown('<style>#vg-tooltip-element{z-index: 1000051}</style>',
            unsafe_allow_html=True)

logger.info("Loading data...")
# with st.spinner("Loading data..."):
algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

logger.info("Data loaded.")


def damage_plot_builder(damage_data_df,
                        hit_count_clip,
                        min_distance,
                        max_distance):
    data_df = damage_data_df.copy()
    data_df = data_df.loc[(data_df["distance_median"] >= min_distance) & (data_df["distance_median"] <= max_distance)]
    # data_df = data_df.loc[data_df["hit_count"] <= max_hit_count]
    data_df["hit_count"] = data_df["hit_count"].clip(upper=hit_count_clip)

    bin_count = int(len(data_df["hit_count"].unique()) / 2)

    plots_height = 500
    plot_width = 700

    color_scale = alt.Scale(
        # scheme='dark2',
        domain=["Mouse & Keyboard", "Controller"],
        range=['red', 'blue'],
    )

    hit_count_distance_heatmap = (alt.Chart(data_df).mark_rect().encode(
        x=alt.X('distance_median:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Distance (m)')),
        y=alt.Y('hit_count:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Hit Count')),
        color=alt.Color('count()', scale=alt.Scale(scheme='viridis'))
    ).properties(
        title={"text": f"Hit Count vs Distance Heatmap",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,
    )
    )

    hit_count_duration_heatmap = (alt.Chart(data_df).mark_rect().encode(
        x=alt.X('event_duration:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Duration (s)')),
        y=alt.Y('hit_count:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Hit Count')),
        color=alt.Color('count()', scale=alt.Scale(scheme='viridis'))
    ).properties(
        title={"text": f"Hit Count vs Duration Heatmap",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,

    )
    )

    def compute_epdf(group):
        # Fit the KDE to the data
        kde = gaussian_kde(group['hit_count'])

        # Create a range of values for hit_count over which to evaluate the KDE
        x = np.linspace(group['hit_count'].min(), group['hit_count'].max(), 100)

        # Evaluate the KDE over this range to get the EPDF values
        epdf = kde.evaluate(x)

        # Return a DataFrame with the hit_count values, EPDF values, and player_input group
        return pd.DataFrame({'hit_count': x, 'epdf': epdf, 'player_input': group.name})

    def compute_hist_epdf(group):
        # Compute the histogram

        bin_centers = list(range(1, max(group['hit_count'])))
        bins = len(bin_centers)
        counts, bin_edges = np.histogram(group['hit_count'], bins=bins, density=True)

        # Calculate the bin centers
        # bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        # Create a DataFrame for the EPDF
        epdf_df = pd.DataFrame({'hit_count': bin_centers, 'epdf': counts, 'player_input': group.name})
        return epdf_df

    # Function to compute histogram-based EPDF and ECDF
    def compute_hist_epdf_ecdf(group):
        # Compute the histogram
        bins = list(range(1, max(group['hit_count']) + 2))  # Corrected to include max value
        density, bin_edges = np.histogram(group['hit_count'], bins=bins, density=True)

        # Calculate the ECDF
        ecdf = np.cumsum(density * np.diff(bin_edges))
        eccdf = 1 - ecdf

        # Create a DataFrame for the EPDF and ECDF
        epdf_ecdf_df = pd.DataFrame({
            'hit_count': bins[:-1],
            'epdf': density,
            'ecdf': ecdf,
            'eccdf': eccdf,
            'player_input': group.name
        })
        return epdf_ecdf_df

    # Apply the function to each group and concatenate results, excluding group keys in the operation
    epdf_ecdf_df = data_df.groupby('player_input').apply(compute_hist_epdf_ecdf, include_groups=False).reset_index(
        drop=True)

    base_chart = alt.Chart(epdf_ecdf_df)

    columns = data_df["player_input"].unique()

    epdf_line = base_chart.mark_line(interpolate="basis",
                                     strokeWidth=5,
                                     ).encode(
        x=alt.X('hit_count:Q',
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)
                ),
        y="epdf:Q",
        color=alt.Color('player_input:N',
                        # scale=alt.Scale(scheme='dark2'),
                        scale=color_scale,
                        ),
    ).properties(
        title={"text": f"ePDF of Hit Count",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,
    )

    # Create a selection that chooses the nearest point & selects based on x-value
    epdf_nearest = alt.selection_point(nearest=True,
                                       on="mouseover",
                                       fields=["hit_count"],
                                       empty=False)

    # Draw points on the line, and highlight based on selection
    epdf_points = base_chart.mark_point(
        filled=True,
        size=100,
        color="white",
    ).encode(
        x=alt.X('hit_count:Q',
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)
                ),
        y="epdf:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0))
    )

    # Draw a rule at the location of the selection
    epdf_rules = base_chart.transform_pivot(
        "player_input",
        value="epdf",
        groupby=["hit_count"]
    ).mark_rule(
        color="gray",
        strokeWidth=2,
    ).encode(
        x="hit_count:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip(c, type="quantitative", format=".2f") for c in columns],
    ).add_params(epdf_nearest)

    # Put the five layers into a chart and bind the data
    epdf_plot = alt.layer(
        epdf_line, epdf_points, epdf_rules,
    )

    epdf_plot = epdf_plot.interactive()

    eccdf_line = base_chart.mark_line(interpolate="basis",
                                      strokeWidth=5,
                                      ).encode(
        x=alt.X('hit_count:Q',
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)
                ),
        y="eccdf:Q",
        color=alt.Color('player_input:N',
                        # scale=alt.Scale(scheme='dark2'),
                        scale=color_scale,
                        ),
    ).properties(
        title={"text": f"eCCDF of Hit Count",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,
    )

    # Draw points on the line, and highlight based on selection
    eccdf_points = base_chart.mark_point(
        filled=True,
        size=100,
        color="white",
    ).encode(
        x=alt.X('hit_count:Q',
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)
                ),
        y="eccdf:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0))
    )

    # Draw a rule at the location of the selection
    eccdf_rules = base_chart.transform_pivot(
        "player_input",
        value="eccdf",
        groupby=["hit_count"]
    ).mark_rule(
        color="gray",
        strokeWidth=2,
    ).encode(
        x="hit_count:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip(c, type="quantitative", format=".2f") for c in columns],
    ).add_params(epdf_nearest)

    # Put the five layers into a chart and bind the data
    eccdf_plot = alt.layer(
        eccdf_line, eccdf_points, eccdf_rules,
    )

    eccdf_plot = eccdf_plot.interactive()

    plot_list = [hit_count_distance_heatmap, hit_count_duration_heatmap, epdf_plot, eccdf_plot]

    return plot_list, data_df


filters_container = st.sidebar.container()

damage_events_filtered_df, selected_tournament, selected_region, selected_days, selected_weapons = streamlit_helper.get_tournament_filters(
    algs_games_df, gun_stats_df, filters_container)

filter_unknown_inputs = filters_container.checkbox("Filter Unknown Inputs", value=True)

if filter_unknown_inputs:
    valid_inputs = ["Mouse & Keyboard", "Controller"]
    damage_events_filtered_df = damage_events_filtered_df.loc[
        damage_events_filtered_df["player_input"].isin(valid_inputs)]

hit_count_clip = st.sidebar.number_input("Hit Count Clip",
                                         min_value=1,
                                         max_value=30,
                                         value=15,
                                         key="hit_count_clip")

min_distance = st.sidebar.number_input("Minimum Distance",
                                       min_value=1,
                                       max_value=1000,
                                       value=1,
                                       key="min_distance")
max_distance = st.sidebar.number_input("Maximum Distance",
                                       min_value=1,
                                       max_value=1000,
                                       value=1000,
                                       key="max_distance")

plots, raw_data = damage_plot_builder(damage_events_filtered_df, hit_count_clip, min_distance, max_distance)

row_1_cols = st.columns(2)

st.altair_chart(plots[2], use_container_width=False)
st.altair_chart(plots[3], use_container_width=False)

row_2_cols = st.columns(2)

st.altair_chart(plots[1], use_container_width=False)
st.altair_chart(plots[0], use_container_width=False)

# st.altair_chart(plots[1], use_container_width=True)

# TODO:
# interval selection
# - ePDF of damage dealt
# - eCDF of damage dealt
# - color per input

expander = st.expander(label='Raw Data')
expander.dataframe(raw_data[[
    "player_name",
    "team_name",
    "tournament_full_name",
    "tournament_day",
    "game_title",
    "game_map",
    "weapon_name",
    "class",
    "target",
    "distance_median",
    "hit_count",
    "damage_sum",
    "ammo_used",
    "distance",
    "damage",
    "event_time",

    "player_hash",
    "game_id",

]]
                   )
