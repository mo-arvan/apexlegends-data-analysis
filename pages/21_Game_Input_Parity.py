import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import src.data_helper as data_helper
import src.data_loader as data_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="Game Input Parity",
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


def discrepancy_plot_builder(damage_events_a_df,
                             damage_events_b_df,
                             shots_hit_clip):
    tournament_a_name = damage_events_a_df["tournament_full_name"].unique()[0]
    tournament_b_name = damage_events_b_df["tournament_full_name"].unique()[0]
    damage_events_a_df["shots_hit_clipped"] = damage_events_a_df.shots_hit.clip(upper=shots_hit_clip)
    damage_events_b_df["shots_hit_clipped"] = damage_events_b_df.shots_hit.clip(upper=shots_hit_clip)

    plots_height = 700
    plot_width = 700

    input_to_color_dict = {
        "Mouse & Keyboard": "blue",
        "Controller": "red"
    }

    # Function to compute histogram-based EPDF and ECDF
    def compute_hist_epdf_ecdf(group):
        # Compute the histogram
        bins = list(range(1, int(max(group['shots_hit_clipped']) + 2)))  # Corrected to include max value
        density, bin_edges = np.histogram(group['shots_hit_clipped'], bins=bins, density=True)

        # Calculate the ECDF
        ecdf = np.cumsum(density * np.diff(bin_edges))
        eccdf = 1 - ecdf

        # Create a DataFrame for the EPDF and ECDF
        epdf_ecdf_df = pd.DataFrame({
            'shots_hit_clipped': bins[:-1],
            'epdf': density,
            'ecdf': ecdf,
            'eccdf': eccdf,
            'player_input': group.name
        })
        return epdf_ecdf_df

    def get_epdf_ecdf_diff(epdf_ecdf_df):
        diff_list = []

        controller_df = epdf_ecdf_df.loc[epdf_ecdf_df["player_input"] == "Controller"]
        mouse_keyboard_df = epdf_ecdf_df.loc[epdf_ecdf_df["player_input"] == "Mouse & Keyboard"]
        for shots_hit_count in range(1, shots_hit_clip + 1):
            row_dict = {
                "shots_hit_clipped": shots_hit_count,
            }
            matching_controller_row = controller_df.loc[controller_df["shots_hit_clipped"] == shots_hit_count]
            matching_mouse_keyboard_row = mouse_keyboard_df.loc[
                mouse_keyboard_df["shots_hit_clipped"] == shots_hit_count]

            row_dict["epdf_diff"] = matching_controller_row["epdf"].values[0] - \
                                    matching_mouse_keyboard_row["epdf"].values[0]
            row_dict["eccdf_diff"] = matching_controller_row["eccdf"].values[0] - \
                                     matching_mouse_keyboard_row["eccdf"].values[0]
            diff_list.append(row_dict)
        diff_df = pd.DataFrame(diff_list)
        diff_df["epdf_diff"] = diff_df["epdf_diff"].round(3)
        diff_df["eccdf_diff"] = diff_df["eccdf_diff"].round(3)
        return diff_df

    # Apply the function to each group and concatenate results, excluding group keys in the operation
    epdf_ecdf_a_df = damage_events_a_df.groupby('player_input').apply(
        compute_hist_epdf_ecdf, include_groups=False).reset_index(drop=True)
    epdf_ecdf_b_df = damage_events_b_df.groupby('player_input').apply(
        compute_hist_epdf_ecdf, include_groups=False).reset_index(drop=True)

    # def get_epdf_eccdf_plot(data_df, tournament_title):
    #     # two bar plots
    #     epdf_plot = go.Figure()
    #     ecdf_plot = go.Figure()
    #
    #     for i, player_input in enumerate(data_df["player_input"].unique()):
    #         player_df = data_df.loc[data_df["player_input"] == player_input]
    #
    #         showlegend = False
    #         # if i == 0:
    #         #     showlegend = True
    #
    #         epdf_plot.add_trace(go.Bar(
    #             x=player_df["shots_hit_clipped"],
    #             y=player_df["epdf"],
    #             name=player_input,
    #             marker_color=input_to_color_dict[player_input],
    #             legendgroup=player_input,
    #             showlegend=showlegend
    #         ))
    #         ecdf_plot.add_trace(go.Bar(
    #             x=player_df["shots_hit_clipped"],
    #             y=player_df["eccdf"],
    #             name=player_input,
    #             marker_color=input_to_color_dict[player_input],
    #             legendgroup=player_input,
    #             showlegend=showlegend
    #         ))
    #
    #     epdf_plot.update_layout(
    #         title=f"ePDF of Shots Hit - {tournament_title}",
    #         xaxis_title="Shots Hit",
    #         yaxis_title="ePDF",
    #         height=plots_height,
    #         width=plot_width,
    #         # barmode="group"
    #     )
    #
    #     ecdf_plot.update_layout(
    #         title=f"eCCDF of Shots Hit - {tournament_title}",
    #         xaxis_title="Shots Hit",
    #         yaxis_title="eCCDF",
    #         height=plots_height,
    #         width=plot_width,
    #         # barmode="group"
    #     )
    #
    #     return epdf_plot, ecdf_plot

    def epdf_eccdf_plot(data_a_df, tournament_a_name, data_b_df, tournament_b_name):

        # single figure, containing two subplots
        epdf_plot = make_subplots(rows=1,
                                  cols=2,
                                  subplot_titles=(tournament_a_name, tournament_b_name),
                                  shared_xaxes=True,
                                  horizontal_spacing=0.05
                                  )

        ecdf_plot = make_subplots(rows=1,
                                  cols=2,
                                  subplot_titles=(tournament_a_name, tournament_b_name),
                                  shared_xaxes=True,
                                  horizontal_spacing=0.05
                                  )

        for player_input in data_a_df["player_input"].unique():
            player_df = data_a_df.loc[data_a_df["player_input"] == player_input]
            legend_group = player_input
            if player_input == "Mouse & Keyboard":
                legend_group = "MnK"

            epdf_plot.add_trace(go.Bar(
                x=player_df["shots_hit_clipped"],
                y=player_df["epdf"],
                name=legend_group,
                marker_color=input_to_color_dict[player_input],
                legendgroup=legend_group,
            ), row=1, col=1)
            ecdf_plot.add_trace(go.Line(
                x=player_df["shots_hit_clipped"],
                y=player_df["eccdf"],
                name=legend_group,
                marker_color=input_to_color_dict[player_input],
                legendgroup=legend_group,
            ), row=1, col=1)

        for player_input in data_b_df["player_input"].unique():
            player_df = data_b_df.loc[data_b_df["player_input"] == player_input]
            legend_group = player_input
            if player_input == "Mouse & Keyboard":
                legend_group = "MnK"

            epdf_plot.add_trace(go.Bar(
                x=player_df["shots_hit_clipped"],
                y=player_df["epdf"],
                name=legend_group,
                marker_color=input_to_color_dict[player_input],
                legendgroup=legend_group,
                showlegend=False,
            ), row=1, col=2)
            ecdf_plot.add_trace(go.Line(
                x=player_df["shots_hit_clipped"],
                y=player_df["eccdf"],
                name=legend_group,
                marker_color=input_to_color_dict[player_input],
                legendgroup=legend_group,
                showlegend=False,
            ), row=1, col=2)

        epdf_plot.update_layout(
            title="Empirical Probability Density Function (ePDF) of Shots Hit",
            # xaxis_title="Shots Hit",
            yaxis_title="ePDF",
            height=plots_height,
            width=plot_width,
            barmode="group",
            barcornerradius=5,
        )

        ecdf_plot.update_layout(
            title="Empirical Complementary Cumulative Distribution Function (eCCDF) of Shots Hit",
            # xaxis_title="Shots Hit",
            yaxis_title="eCCDF",
            height=plots_height,
            width=plot_width,
            barmode="group",
            barcornerradius=5,
        )

        return epdf_plot, ecdf_plot

    # epdf_a_plot, eccdf_a_plot = get_epdf_eccdf_plot(epdf_ecdf_a_df, tournament_a_name)
    # epdf_b_plot, eccdf_b_plot = get_epdf_eccdf_plot(epdf_ecdf_b_df, tournament_b_name)
    epdf_ecdf_a_df["epdf"] = epdf_ecdf_a_df["epdf"].round(3)
    epdf_ecdf_a_df["eccdf"] = epdf_ecdf_a_df["eccdf"].round(3)

    epdf_ecdf_b_df["epdf"] = epdf_ecdf_b_df["epdf"].round(3)
    epdf_ecdf_b_df["eccdf"] = epdf_ecdf_b_df["eccdf"].round(3)

    epdf_merged_plot, eccdf_merged_plot = epdf_eccdf_plot(epdf_ecdf_a_df, tournament_a_name,
                                                          epdf_ecdf_b_df, tournament_b_name)

    epdf_ecdf_diff_a_df = get_epdf_ecdf_diff(epdf_ecdf_a_df)
    epdf_ecdf_diff_b_df = get_epdf_ecdf_diff(epdf_ecdf_b_df)

    epdf_ecdf_diff_a_df["epdf_diff_color"] = np.where(epdf_ecdf_diff_a_df["epdf_diff"] > 0, "goldenrod", "darkmagenta")
    epdf_ecdf_diff_b_df["epdf_diff_color"] = np.where(epdf_ecdf_diff_b_df["epdf_diff"] > 0, "goldenrod", "darkmagenta")

    epdf_ecdf_diff_a_df["eccdf_diff_color"] = np.where(epdf_ecdf_diff_a_df["eccdf_diff"] > 0, "goldenrod",
                                                       "darkmagenta")
    epdf_ecdf_diff_b_df["eccdf_diff_color"] = np.where(epdf_ecdf_diff_b_df["eccdf_diff"] > 0, "goldenrod",
                                                       "darkmagenta")

    epdf_diff_subplots = make_subplots(rows=1,
                                       cols=2,
                                       # x_title="Shots Hit",
                                       # y_title="ePDF Difference",
                                       subplot_titles=(tournament_a_name, tournament_b_name),
                                       shared_yaxes='all',
                                       horizontal_spacing=0.05
                                       )

    eccdf_diff_subplots = make_subplots(rows=1,
                                        cols=2,
                                        subplot_titles=(tournament_a_name, tournament_b_name),
                                        shared_yaxes='all',
                                        horizontal_spacing=0.01
                                        )

    epdf_diff_a_hist = go.Bar(x=epdf_ecdf_diff_a_df["shots_hit_clipped"],
                              y=epdf_ecdf_diff_a_df["epdf_diff"],
                              # name="ePDF Difference A",
                              text=epdf_ecdf_diff_a_df["epdf_diff"],
                              showlegend=False,
                              textposition="outside",
                              marker_color=epdf_ecdf_diff_a_df["epdf_diff_color"],
                              )
    epdf_diff_b_hist = go.Bar(x=epdf_ecdf_diff_b_df["shots_hit_clipped"],
                              y=epdf_ecdf_diff_b_df["epdf_diff"],
                              # name="ePDF Difference B",
                              text=epdf_ecdf_diff_b_df["epdf_diff"],
                              showlegend=False,
                              textposition="outside",
                              marker_color=epdf_ecdf_diff_b_df["epdf_diff_color"],
                              )

    eccdf_diff_a_hist = go.Bar(x=epdf_ecdf_diff_a_df["shots_hit_clipped"],
                               y=epdf_ecdf_diff_a_df["eccdf_diff"],
                               name="eCCDF Difference A",
                               text=epdf_ecdf_diff_a_df["eccdf_diff"],
                               textposition="outside",
                               showlegend=False,
                               marker_color=epdf_ecdf_diff_a_df["eccdf_diff_color"],
                               )
    eccdf_diff_b_hist = go.Bar(x=epdf_ecdf_diff_b_df["shots_hit_clipped"],
                               y=epdf_ecdf_diff_b_df["eccdf_diff"],
                               name="eCCDF Difference B",
                               text=epdf_ecdf_diff_b_df["eccdf_diff"],
                               textposition="outside",
                               showlegend=False,
                               marker_color=epdf_ecdf_diff_b_df["eccdf_diff_color"],
                               )

    epdf_diff_subplots.add_trace(epdf_diff_a_hist, row=1, col=1)
    epdf_diff_subplots.add_trace(epdf_diff_b_hist, row=1, col=2)
    epdf_diff_subplots.add_trace(go.Bar(
        x=[None],
        y=[None],
        name="Cont. - MnK >= 0",
        marker_color="goldenrod",
    ))
    epdf_diff_subplots.add_trace(go.Bar(
        x=[None],
        y=[None],
        name="Cont. - MnK < 0",
        marker_color="darkmagenta",
    ))

    eccdf_diff_subplots.add_trace(eccdf_diff_a_hist, row=1, col=1)
    eccdf_diff_subplots.add_trace(eccdf_diff_b_hist, row=1, col=2)
    eccdf_diff_subplots.add_trace(go.Bar(
        x=[None],
        y=[None],
        name="Cont. - MnK >= 0",
        marker_color="goldenrod",
    ))
    eccdf_diff_subplots.add_trace(go.Bar(
        x=[None],
        y=[None],
        name="Cont. - MnK < 0",
        marker_color="darkmagenta",
    ))

    default_plot_layout = {
        "barcornerradius": 5,
        "height": plots_height,
        "width": plot_width,
        "bargap": 0.1,
        # "xaxis" : {
        #     "showgrid" : False,
        # },
        # "yaxis" : {
        #     "showgrid" : False,
        # },
        # "margin": dict(l=150, r=150, t=50, b=50),
        "legend": dict(
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
        )
    }

    epdf_merged_plot.update_layout(
        **default_plot_layout,
    )
    eccdf_merged_plot.update_layout(
        **default_plot_layout,
    )

    plot_list = [epdf_diff_subplots, eccdf_diff_subplots]
    for plot in plot_list:
        plot.update_xaxes(showgrid=False)
        plot.update_yaxes(showgrid=False)
    epdf_diff_subplots.update_layout(
        title_text="Empirical Probability Density Function (ePDF) Difference of Shots Hit Between Game Inputs",
        **default_plot_layout,
        yaxis={
            "title": "ePDF Difference",
        }
    )
    eccdf_diff_subplots.update_layout(
        title_text="Empirical Complementary Cumulative Distribution Function (eCCDF) Difference of Shots Hit Between Game Inputs",
        **default_plot_layout,
        yaxis={
            "title": "eCCDF Difference",
        })

    plots_dict = {
        "epdf_merged_plot": epdf_merged_plot,
        "eccdf_merged_plot": eccdf_merged_plot,
        "epdf_diff_subplots": epdf_diff_subplots,
        "eccdf_diff_subplots": eccdf_diff_subplots
    }
    return plots_dict, _


filters_container = st.sidebar.container()

tournaments = (algs_games_df[['tournament_full_name', "tournament_region", 'game_timestamp']]
               .groupby(['tournament_full_name', "tournament_region"]).
               agg(max_timestamp=('game_timestamp', 'max'))).reset_index()
tournaments = tournaments.sort_values(by="max_timestamp", ascending=False)

tournaments_order = tournaments["tournament_full_name"].unique().tolist()

filters_container.write("Apply the filters in any order")

selected_tournament_a = filters_container.selectbox("Tournament A",
                                                    tournaments_order,
                                                    index=2,
                                                    key="selected_tournament_a")

selected_tournament_b = filters_container.selectbox("Tournament B",
                                                    tournaments_order,
                                                    index=0,
                                                    key="selected_tournament_b")

if selected_tournament_a is None:
    st.error("Please select at least one tournament.")
    st.stop()

#  add loading
with st.spinner("Loading data, it may take a while..."):
    damage_events_a_df = data_helper.load_damage_data(selected_tournament_a)
    damage_events_b_df = data_helper.load_damage_data(selected_tournament_b)

weapon_info = gun_stats_df[["weapon_name", "class"]].sort_values(by="weapon_name")
damage_events_a_df = damage_events_a_df.merge(weapon_info, on=["weapon_name"], how="left")
damage_events_b_df = damage_events_b_df.merge(weapon_info, on=["weapon_name"], how="left")

weapon_list = damage_events_a_df["weapon_name"].unique().tolist()

close_range_weapons = [
    "Volt SMG",
    "HAVOC Rifle",
    "R-99 SMG",
    "Volt SMG",
    "Alternator SMG",
    "C.A.R. SMG",
    "Prowler Burst PDW",
    "VK-47 Flatline",
    "R-301 Carbine",
    'Devotion LMG',
    'EVA-8 Auto',
    'L-STAR EMG',
    'M600 Spitfire',
    'Mozambique Shotgun',
    'P2020',
    'RE-45 Auto',
]

selected_guns = filters_container.multiselect("Select Weapons",
                                              weapon_list,
                                              default=close_range_weapons,
                                              key="selected_guns")

damage_events_a_df = damage_events_a_df[damage_events_a_df["weapon_name"].isin(selected_guns)]
damage_events_b_df = damage_events_b_df[damage_events_b_df["weapon_name"].isin(selected_guns)]

filter_unknown_inputs = filters_container.checkbox("Filter Unknown Inputs", value=True)

# Close Range (<40m) Shots Hit - Tournament A vs B
valid_inputs = ["Mouse & Keyboard", "Controller"]

damage_events_a_df = damage_events_a_df.loc[damage_events_a_df["player_input"].isin(valid_inputs)]
damage_events_b_df = damage_events_b_df.loc[damage_events_b_df["player_input"].isin(valid_inputs)]

shots_hit_clip = st.sidebar.number_input("Max Shots Hit",
                                         min_value=1,
                                         max_value=30,
                                         value=15,
                                         key="shots_hit_clip")

selected_distance = st.sidebar.number_input("Distance Threshold",
                                            min_value=0,
                                            max_value=1000,
                                            value=40,
                                            key="selected_distance")

distance_filter = st.sidebar.selectbox("Distance Filter",
                                       ["Less than", "Greater than"],
                                       ["Less than"],
                                       key="distance_filter")

if "Less than" in distance_filter:
    filtered_damage_events_a_df = damage_events_a_df.loc[damage_events_a_df["distance"] <= selected_distance]
    filtered_damage_events_b_df = damage_events_b_df.loc[damage_events_b_df["distance"] <= selected_distance]
else:
    filtered_damage_events_a_df = damage_events_a_df.loc[damage_events_a_df["distance"] > selected_distance]
    filtered_damage_events_b_df = damage_events_b_df.loc[damage_events_b_df["distance"] > selected_distance]

with st.spinner("Building plots..."):
    plots_dict, raw_data = discrepancy_plot_builder(filtered_damage_events_a_df,
                                                    filtered_damage_events_b_df,
                                                    shots_hit_clip)

tabs = st.tabs([
    "ePDF",
    "eCCDF",
    "ePDF Diff",
    "eCCDF Diff",
    f"Raw Data A",
    f"Raw Data B"
])

with tabs[0]:
    st.plotly_chart(plots_dict["epdf_merged_plot"], use_container_width=True)
    st.write(
        "The Empirical Probability Density Function (ePDF) of Shots Hit shows the probability density of the number of shots hit for each input type. ")

with tabs[1]:
    st.plotly_chart(plots_dict["eccdf_merged_plot"], use_container_width=True)
    st.write(
        "The Empirical Complementary Cumulative Distribution Function (eCCDF) of Shots Hit shows the probability of hitting more than a certain number of shots for each input type. ")

with tabs[2]:
    st.plotly_chart(plots_dict["epdf_diff_subplots"], use_container_width=True)
    st.write(
        "The Empirical Probability Density Function (ePDF) of Shots Hit shows the probability density of the number of shots hit for each input type. ")

with tabs[3]:
    st.plotly_chart(plots_dict["eccdf_diff_subplots"], use_container_width=True)
    st.write(
        "The Empirical Complementary Cumulative Distribution Function (eCCDF) of Shots Hit shows the probability of hitting more than a certain number of shots for each input type. ")

# st.altair_chart(plots[2], use_container_width=False)
# st.altair_chart(plots[3], use_container_width=False)
#
# row_2_cols = st.columns(2)

# with tabs[2]:
#     # st.header("ePDF of Shots Hit")
#     st.altair_chart(plots[2], use_container_width=True)

#
# with tabs[3]:
#     # st.header("eCCDF of Shots Hit")
#     st.altair_chart(plots[3], use_container_width=True)


# st.altair_chart(plots[1], use_container_width=True)

# TODO:
# interval selection
# - ePDF of damage dealt
# - eCDF of damage dealt
# - color per input

with tabs[4]:
    st.header(f"Raw Data {selected_tournament_a}")
    st.dataframe(filtered_damage_events_a_df[[
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
with tabs[5]:
    st.header(f"Raw Data {selected_tournament_b}")
    st.dataframe(filtered_damage_events_b_df[[
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
