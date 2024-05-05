import logging

import altair as alt
import numpy as np
import streamlit as st
import plotly.express as px

import src.data_helper as data_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="ALGS Fights Explorer",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)


@st.cache_data
def get_data():
    logger.info("Cache miss. Loading data from disk...")
    return data_helper.get_damage_data()


logger.info("Loading data...")
# with st.spinner("Loading data..."):
algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

logger.info("Data loaded.")


def damage_plot_builder(damage_data_df):
    bin_count = int(len(damage_data_df["hit_count"].unique()) / 2)
    histogram_plot = alt.Chart(damage_data_df).mark_bar().encode(
        x=alt.X('hit_count',
                bin=alt.Bin(maxbins=bin_count),
                axis=alt.Axis(title='Hit Count'),
                scale=alt.Scale(zero=False)),
        y='count()',
        # color=alt.Color('player_name', legend=None, scale=alt.Scale(scheme='category20')),
        # tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],
    ).properties(
        title={"text": f"Hit Count Histogram",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        # height=700,
    )
    point = alt.selection_point(encodings=['x', 'y'])
    heatmap = alt.Chart(damage_data_df).mark_rect().encode(
        x=alt.X('distance_median:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Distance (m)')),
        y=alt.Y('hit_count:Q', bin=alt.Bin(maxbins=bin_count), axis=alt.Axis(title='Hit Count')),
        color=alt.Color('count()', scale=alt.Scale(scheme='viridis'))
    ).properties(
        title={"text": f"Hit Count vs Distance Heatmap",
               # "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },
        height=700,

    ).add_params(
        point
    )
    # , color_continuous_scale="Viridis"
    #  nbinsx=20, nbinsy=20
    density_heatmap_plotly = px.density_heatmap(damage_data_df,
                                                x="distance_median",
                                                y="hit_count",
                                                marginal_x="histogram",
                                                marginal_y="histogram",
                                                # color_continuous_scale="Viridis",
                                                color_continuous_scale=px.colors.sequential.Plasma,
                                                nbinsx=10,
                                                nbinsy=12,
                                                # color="count()",
                                                title="Hit Count vs Distance Heatmap",
                                                labels={"distance_median": "Distance (m)", "hit_count": "Hit Count"},
                                                histfunc="sum",
                                                width=800,
                                                height=800,
                                                )

    return [histogram_plot, heatmap, density_heatmap_plotly], damage_data_df

    plot_df = players_grouped_df.sort_values(by="median_accuracy", ascending=False)
    plot_df["median_accuracy_rank"] = range(1, len(plot_df) + 1)

    fights_and_stats_data_df = weapons_data_df.merge(plot_df,
                                                     on=["player_hash", "player_name"],
                                                     how="inner")
    fights_and_stats_data_df = fights_and_stats_data_df.sort_values(by=["median_accuracy_rank"], ascending=True)

    median_accuracy_rank_top_k = fights_and_stats_data_df[
        fights_and_stats_data_df["median_accuracy_rank"] <= min(top_k, len(players_grouped_df))]
    box_plot_color = "gray"

    box_plot = (alt.Chart(median_accuracy_rank_top_k).mark_boxplot(
        extent="min-max",
        color=box_plot_color,
    ).encode(
        alt.X("accuracy:Q", axis=alt.Axis(title='Accuracy (%)'), scale=alt.Scale(zero=False)),
        alt.Y("player_name:N", axis=alt.Axis(title=''), sort=None),
        color=alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),
        fill=alt.Color("player_name:N", legend=None, scale=alt.Scale(scheme='category20')),

    ).properties(
        title={"text": f"Accuracy Box Plot",
               "subtitle": f"Median Fight Count: {fights_count_median}",
               "subtitleColor": "gray",
               },

        # width=800,
        # height=700,
    ))

    median_overall_accuracy = weapons_data_df["accuracy"].median()

    high_accuracy_fights = weapons_data_df[weapons_data_df["accuracy"] >= median_overall_accuracy]

    high_accuracy_count_rank = high_accuracy_fights.groupby(["player_hash", "player_name"]).agg(
        high_accuracy_count=("accuracy", "count"),
        sum_opening_damage=("damage_dealt", "sum"),
    ).reset_index()

    high_accuracy_count_rank_merged = high_accuracy_count_rank.merge(players_grouped_df,
                                                                     on=["player_hash",
                                                                         "player_name"],
                                                                     how="left")

    high_accuracy_count_rank_merged["high_accuracy_ratio"] = high_accuracy_count_rank_merged["high_accuracy_count"] / \
                                                             high_accuracy_count_rank_merged["total_fights"]

    high_accuracy_count_rank_merged = high_accuracy_count_rank_merged.sort_values(
        by=["high_accuracy_count", "sum_opening_damage"], ascending=False)

    high_accuracy_count_rank_merged["high_accuracy_count_rank"] = range(1, len(high_accuracy_count_rank_merged) + 1)

    high_accuracy_fights = high_accuracy_fights.merge(high_accuracy_count_rank_merged,
                                                      on=["player_hash", "player_name"],
                                                      how="inner")

    high_accuracy_top_k = high_accuracy_fights[high_accuracy_fights["high_accuracy_count_rank"] <= top_k]

    high_accuracy_top_k = high_accuracy_top_k.sort_values(by=["high_accuracy_count", "sum_opening_damage"],
                                                          ascending=False)

    high_accuracy_top_k["one"] = 1

    players = high_accuracy_top_k["player_name"].unique().tolist()

    players = sorted(players, key=lambda x: x.lower())

    bar_plot = alt.Chart(high_accuracy_top_k).mark_bar().encode(
        alt.Y("player_name:N", axis=alt.Axis(title=''), sort=None),
        alt.X("one:Q", axis=alt.Axis(title="Count"), scale=alt.Scale(zero=False)),
        alt.Color("damage_dealt:N", legend=None, scale=alt.Scale(scheme='yelloworangered')),
        tooltip=alt.Tooltip(
            ['player_name', "weapon_name", "damage_dealt", 'shots', 'hits', "accuracy", "high_accuracy_count",
             "total_fights",
             "tournament_full_name", "tournament_region", "tournament_day", "game_title"
             ]),
    ).properties(

        title={"text": f"Number of Fights with Higher than Median Accuracy ({median_overall_accuracy:.2f})%",
               "subtitle": f"Text and color encode the damage dealt in the fight",
               "subtitleColor": "gray",
               },

        # width=100,
        # height=500,
    )

    bar_plot_text = bar_plot.mark_text(align="left",
                                       baseline="middle",
                                       color="white",
                                       dx=-20).encode(
        alt.X("one:Q", stack="zero"),
        text="damage_dealt:Q",
        color=alt.value("black")
    )

    bar_plot = bar_plot + bar_plot_text

    high_accuracy_count_rank_merged = high_accuracy_count_rank_merged.sort_values(
        by=["high_accuracy_ratio", "sum_opening_damage"],
        ascending=False)
    high_accuracy_count_rank_merged["high_accuracy_percent"] = high_accuracy_count_rank_merged[
                                                                   "high_accuracy_ratio"] * 100

    high_accuracy_count_rank_merged["high_accuracy_ratio_rank"] = range(1, len(high_accuracy_count_rank_merged) + 1)

    high_accuracy_top_k_ratio = high_accuracy_count_rank_merged[
        high_accuracy_count_rank_merged["high_accuracy_ratio_rank"] <= top_k]

    bar_plot_2 = alt.Chart(high_accuracy_top_k_ratio).mark_bar().encode(
        alt.Y("player_name:N", axis=alt.Axis(title=''), sort=None),
        alt.X("high_accuracy_percent:Q", axis=alt.Axis(title="%"), scale=alt.Scale(zero=False)),
        alt.Color("high_accuracy_count:N", legend=None, scale=alt.Scale(scheme='yelloworangered')),
        tooltip=alt.Tooltip(
            ['player_name', "sum_opening_damage", "high_accuracy_count",
             "total_fights",
             "mean_accuracy", "median_accuracy", "sum_shots", "sum_hits"
             ]),
    ).properties(
        title={"text": f"% Fights with Higher than Median Accuracy ({median_overall_accuracy:.2f})%",
               "subtitle": f"Text encode the damage dealt in the fight, color encode the number of fights with higher than median accuracy",
               "subtitleColor": "gray",
               },

    )

    sum_opening_damage_text = bar_plot_2.mark_text(align="left",
                                                   baseline="middle",
                                                   color="white",
                                                   dx=-25).encode(
        alt.X("high_accuracy_percent:Q", stack="zero"),
        text="sum_opening_damage:Q",
        color=alt.value("black")
    )

    bar_plot_2 = bar_plot_2 + sum_opening_damage_text

    altair_scatter_2 = alt.Chart(weapons_data_df).mark_circle(size=25).encode(
        alt.Y("shots", axis=alt.Axis(title='Shots'), scale=alt.Scale(zero=True)),
        alt.X('damage_dealt', axis=alt.Axis(title='Damage Dealt'), scale=alt.Scale(zero=True)),
        color=alt.Color('accuracy', legend=None, scale=alt.Scale(scheme='redyellowgreen')),
        tooltip=['player_name', "weapon_name", 'shots', 'hits', "accuracy"],
        # opacity=alt.Opacity("accuracy", legend=None, scale=alt.Scale(scheme='viridis')),
    ).properties(
        title="Accuracy Scatter Plot",
        # width=800,
        # height=700,
    )

    plot_list = [histogram_plot.interactive(), bar_plot, bar_plot_2, box_plot, altair_scatter_2]
    return plot_list, weapons_data_df


# find the largest timestamp for each tournament
tournaments = (algs_games_df[['tournament_full_name', "tournament_region", 'game_timestamp']]
               .groupby(['tournament_full_name', "tournament_region"]).
               agg(max_timestamp=('game_timestamp', 'max'))).reset_index()
tournaments = tournaments.sort_values(by="max_timestamp", ascending=False)

tournaments_order = tournaments["tournament_full_name"].tolist()

# order_dict = {
#     "tournament_full_name": [
#         'Pro League - Year 4, Split 1',
#         'ALGS Championship - Year 3, Split 2',
#         'LCQ - Year 3, Split 2',
#         'ALGS Playoffs - Year 3, Split 2',
#         'Pro League - Year 3, Split 2',
#         'ALGS Playoffs - Year 3, Split 1',
#         'Pro League - Year 3, Split 1',
#     ],
# }
weapon_class_list = sorted(gun_stats_df["class"].unique().tolist())

default_selection = {
    "tournament_full_name": tournaments_order[0],
    # "tournament_region": ["NA"],
    "weapon_name": ["R-99 SMG", "Volt SMG", "Alternator SMG", "C.A.R. SMG", "Prowler Burst PDW"],
    # "accuracy": (0, 100),
    # "top_k": 20,
    # "fights": 1,
}
# st.session_state["filters"] = default_selection

filters_dict = {
    "tournament_full_name": "Tournament",
    # "tournament_region": "Region",
    "tournament_day": "Day",
    "player_name": "Player",
    "weapon_name": "Weapon",
    # "shots": "Shots",
    # "hits": "Hits",
    # "accuracy": "Accuracy",
    "game_num": "Game #",
}

# dynamic_filters = DynamicFilters(fights_df_slice,
#                                  filters_name="algs_filters",
#                                  filters_dict=filters_dict,
#                                  order_dict=order_dict,
#                                  default_filters=default_selection, )

st.sidebar.write("Apply the filters in any order")
# dynamic_filters.display_filters(location="sidebar")

selected_tournament = st.sidebar.selectbox("Tournament",
                                           tournaments_order,
                                           index=0,
                                           key="selected_tournaments")

if selected_tournament is None:
    st.error("Please select at least one tournament.")
    st.stop()

damage_events_df = data_helper.get_damage_data(selected_tournament)

game_days = sorted(damage_events_df["tournament_day"].unique().tolist())

selected_days = st.sidebar.multiselect("Day",
                                       game_days,
                                       key="selected_days")

if len(selected_days) != 0:
    damage_events_df = damage_events_df[damage_events_df["tournament_day"].isin(selected_days)]

weapon_info = gun_stats_df[["weapon_name", "class"]].sort_values(by="weapon_name")
damage_events_df = damage_events_df.merge(weapon_info, on=["weapon_name"], how="inner")

weapon_list = damage_events_df["weapon_name"].unique().tolist()

preselected_weapons = []

if "selected_weapons" not in st.session_state:
    preselected_weapons = default_selection["weapon_name"]
else:
    preselected_weapons = st.session_state["selected_weapons"]

with st.sidebar.container():
    st.write("Batch Add Weapon Class")
    row_0_cols = st.columns(3)
    with row_0_cols[0]:
        batch_add_smg = st.button("SMG", use_container_width=True, type="primary")
        if batch_add_smg:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "SMG"]["weapon_name"].unique().tolist()

    with row_0_cols[1]:
        batch_add_pistol = st.button("Pistol", use_container_width=True, type="primary")
        if batch_add_pistol:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "Pistol"][
                "weapon_name"].unique().tolist()

    with row_0_cols[2]:
        batch_add_shotgun = st.button("Shotgun", use_container_width=True, type="primary")
        if batch_add_shotgun:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "Shotgun"][
                "weapon_name"].unique().tolist()

    row_1_cols = st.columns(2)
    with row_1_cols[0]:
        batch_add_ar = st.button("AR", use_container_width=True, type="primary")
        if batch_add_ar:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "AR"]["weapon_name"].unique().tolist()

    with row_1_cols[1]:
        batch_add_lmg = st.button("LMG", use_container_width=True, type="primary")

        if batch_add_lmg:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "LMG"]["weapon_name"].unique().tolist()

    row_2_cols = st.columns(2)

    with row_2_cols[0]:
        batch_add_marksman = st.button("Marksman", use_container_width=True, type="primary")
        if batch_add_marksman:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "Marksman"][
                "weapon_name"].unique().tolist()
    with row_2_cols[1]:
        batch_add_sniper = st.button("Sniper", use_container_width=True, type="primary")
        if batch_add_sniper:
            preselected_weapons += damage_events_df[damage_events_df["class"] == "Sniper"][
                "weapon_name"].unique().tolist()

preselected_weapons = list(set(preselected_weapons))
logger.info(f"Preselected Weapons: {preselected_weapons}")

all_weapons = damage_events_df["weapon_name"].unique().tolist()

for w in preselected_weapons:
    if w not in all_weapons:
        logger.warning(f"Preselected weapon {w} not found in the dataset. Removing from preselected weapons.")
        preselected_weapons.remove(w)

selected_weapons = st.sidebar.multiselect("Weapon",
                                          all_weapons,
                                          default=preselected_weapons,
                                          key="selected_weapons")

if len(selected_weapons) == 0:
    st.error("Please select at least one weapon.")
    st.stop()

damage_events_filtered_df = damage_events_df[damage_events_df["weapon_name"].isin(selected_weapons)]



markdown_message_list = [f"**Warning**: attempting to load {len(damage_events_filtered_df)} rows. \n",
                         "Loading this many rows may take a long time. Please apply more filters to reduce the number of rows.\n",
                         "Alternatively, check the 'Force Load Data' checkbox to load the data."]


plots, raw_data = damage_plot_builder(damage_events_filtered_df)

st.altair_chart(plots[1], use_container_width=True)


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
