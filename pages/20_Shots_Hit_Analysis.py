import logging

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import gaussian_kde

import src.data_helper as data_helper
import src.data_loader as data_loader
import src.streamtlit_helper as streamlit_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="Shots Hit Analysis",
    page_icon="📊",
    layout="wide",
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
algs_games_df = data_loader.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

logger.info("Data loaded.")


def damage_plot_builder(damage_data_df,
                        shots_hit_clip,
                        min_distance,
                        max_distance):
    data_df = damage_data_df.copy()
    data_df = data_df.loc[(data_df.distance >= min_distance) & (data_df.distance <= max_distance)]
    # data_df = data_df.loc[data_df.shots_hit <= max_shots_hit]
    data_df.shots_hit = data_df.shots_hit.clip(upper=shots_hit_clip)

    bin_count = int(len(data_df.shots_hit.unique()) / 2)

    plots_height = 500
    plot_width = 700

    color_scale = alt.Scale(
        # scheme='dark2',
        domain=["Mouse & Keyboard", "Controller"],
        range=['red', 'blue'],
    )

    shots_hit_distance_heatmap = (alt.Chart(data_df).mark_rect().encode(
        x=alt.X('distance:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Distance (m)')),
        y=alt.Y('shots_hit:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Shots Hit')),
        color=alt.Color('count()', scale=alt.Scale(scheme='viridis'))
    ).properties(
        title={"text": f"Shots Hit vs Distance Heatmap",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,
    )
    )

    shots_hit_duration_heatmap = (alt.Chart(data_df).mark_rect().encode(
        x=alt.X('event_duration:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Duration (s)')),
        y=alt.Y('shots_hit:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Shots Hit')),
        color=alt.Color('count()', scale=alt.Scale(scheme='viridis'))
    ).properties(
        title={"text": f"Shots Hit vs Duration Heatmap",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,

    )
    )

    def compute_epdf(group):
        # Fit the KDE to the data
        kde = gaussian_kde(group['shots_hit'])

        # Create a range of values for shots_hit over which to evaluate the KDE
        x = np.linspace(group['shots_hit'].min(), group['shots_hit'].max(), 100)

        # Evaluate the KDE over this range to get the EPDF values
        epdf = kde.evaluate(x)

        # Return a DataFrame with the shots_hit values, EPDF values, and player_input group
        return pd.DataFrame({'shots_hit': x, 'epdf': epdf, 'player_input': group.name})

    def compute_hist_epdf(group):
        # Compute the histogram

        bin_centers = list(range(1, max(group['shots_hit'])))
        bins = len(bin_centers)
        counts, bin_edges = np.histogram(group['shots_hit'], bins=bins, density=True)

        # Calculate the bin centers
        # bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        # Create a DataFrame for the EPDF
        epdf_df = pd.DataFrame({'shots_hit': bin_centers, 'epdf': counts, 'player_input': group.name})
        return epdf_df

    # Function to compute histogram-based EPDF and ECDF
    def compute_hist_epdf_ecdf(group):
        # Compute the histogram
        bins = list(range(1, int(max(group['shots_hit']) + 2)))  # Corrected to include max value
        density, bin_edges = np.histogram(group['shots_hit'], bins=bins, density=True)

        # Calculate the ECDF
        ecdf = np.cumsum(density * np.diff(bin_edges))
        eccdf = 1 - ecdf

        # Create a DataFrame for the EPDF and ECDF
        epdf_ecdf_df = pd.DataFrame({
            'shots_hit': bins[:-1],
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
        x=alt.X('shots_hit:Q',
                axis=alt.Axis(title='Shots Hit'),
                scale=alt.Scale(zero=False)
                ),
        y="epdf:Q",
        color=alt.Color('player_input:N',
                        # scale=alt.Scale(scheme='dark2'),
                        scale=color_scale,
                        ),
    ).properties(
        title={"text": f"ePDF of Shots Hit",
               "subtitleColor": "gray",
               },
        height=plots_height,
        width=plot_width,
    )

    # Create a selection that chooses the nearest point & selects based on x-value
    epdf_nearest = alt.selection_point(nearest=True,
                                       on="mouseover",
                                       fields=["shots_hit"],
                                       empty=False)

    # Draw points on the line, and highlight based on selection
    epdf_points = base_chart.mark_point(
        filled=True,
        size=100,
        color="white",
    ).encode(
        x=alt.X('shots_hit:Q',
                axis=alt.Axis(title='Shots Hit'),
                scale=alt.Scale(zero=False)
                ),
        y="epdf:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0))
    )

    # Draw a rule at the location of the selection
    epdf_rules = base_chart.transform_pivot(
        "player_input",
        value="epdf",
        groupby=["shots_hit"]
    ).mark_rule(
        color="gray",
        strokeWidth=2,
    ).encode(
        x="shots_hit:Q",
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
        x=alt.X('shots_hit:Q',
                axis=alt.Axis(title='Shots Hit'),
                scale=alt.Scale(zero=False)
                ),
        y="eccdf:Q",
        color=alt.Color('player_input:N',
                        # scale=alt.Scale(scheme='dark2'),
                        scale=color_scale,
                        ),
    ).properties(
        title={"text": f"eCCDF of Shots Hit",
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
        x=alt.X('shots_hit:Q',
                axis=alt.Axis(title='Shots Hit'),
                scale=alt.Scale(zero=False)
                ),
        y="eccdf:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0))
    )

    # Draw a rule at the location of the selection
    eccdf_rules = base_chart.transform_pivot(
        "player_input",
        value="eccdf",
        groupby=["shots_hit"]
    ).mark_rule(
        color="gray",
        strokeWidth=2,
    ).encode(
        x="shots_hit:Q",
        opacity=alt.condition(epdf_nearest, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip(c, type="quantitative", format=".2f") for c in columns],
    ).add_params(epdf_nearest)

    # Put the five layers into a chart and bind the data
    eccdf_plot = alt.layer(
        eccdf_line, eccdf_points, eccdf_rules,
    )

    eccdf_plot = eccdf_plot.interactive()

    plot_list = [shots_hit_distance_heatmap, shots_hit_duration_heatmap, epdf_plot, eccdf_plot]

    return plot_list, data_df


filters_container = st.sidebar.container()

damage_events_filtered_df, selected_tournament, selected_region, selected_days, selected_weapons = streamlit_helper.get_tournament_filters(
    algs_games_df, gun_stats_df, filters_container, base_weapons_only=True)

filter_unknown_inputs = filters_container.checkbox("Filter Unknown Inputs", value=True)

if filter_unknown_inputs:
    valid_inputs = ["Mouse & Keyboard", "Controller"]
    damage_events_filtered_df = damage_events_filtered_df.loc[
        damage_events_filtered_df["player_input"].isin(valid_inputs)]

shots_hit_clip = st.sidebar.number_input("Max Shots Hit",
                                         min_value=1,
                                         max_value=30,
                                         value=15,
                                         key="shots_hit_clip")

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

with st.spinner("Building plots..."):
    plots, raw_data = damage_plot_builder(damage_events_filtered_df, shots_hit_clip, min_distance, max_distance)

tabs = st.tabs(["Shots Hit vs Distance Heatmap",
                "Shots Hit vs Duration Heatmap",
                "ePDF of Shots Hit",
                "eCCDF of Shots Hit",
                "Raw Data"])

with tabs[0]:
    # st.header("Shots Hit vs Distance Heatmap")
    st.altair_chart(plots[0], use_container_width=True)
    st.write("The Shots Hit vs Distance Heatmap shows the number of shots hit at different distances. ")

with tabs[1]:
    # st.header("Shots Hit vs Duration Heatmap")
    st.altair_chart(plots[1], use_container_width=True)
    st.write("The Shots Hit vs Duration Heatmap shows the number of shots hit at different durations. ")

# st.altair_chart(plots[2], use_container_width=False)
# st.altair_chart(plots[3], use_container_width=False)
#
# row_2_cols = st.columns(2)

with tabs[2]:
    # st.header("ePDF of Shots Hit")
    st.altair_chart(plots[2], use_container_width=True)
    st.write(
        "The Empirical Probability Density Function (ePDF) of Shots Hit shows the probability density of the number of shots hit for each input type. ")

with tabs[3]:
    # st.header("eCCDF of Shots Hit")
    st.altair_chart(plots[3], use_container_width=True)
    st.write(
        "The Empirical Complementary Cumulative Distribution Function (eCCDF) of Shots Hit shows the probability of hitting at least a certain number of shots for each input type. ")

# st.altair_chart(plots[1], use_container_width=True)

# TODO:
# interval selection
# - ePDF of damage dealt
# - eCDF of damage dealt
# - color per input

with tabs[4]:
    st.dataframe(raw_data[[
        "player_name",
        "team_name",
        "tournament_full_name",
        "tournament_day",
        "game_title",
        "game_map",
        "weapon_name",
        "class",
        "target",
        "distance",
        "shots_hit",
        "total_damage",
        "ammo_used",
        "distance_arr",
        "damage_arr",
        "event_time",
        "player_hash",
        "game_id",

    ]]
                 )
