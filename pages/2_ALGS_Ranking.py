import logging

import numpy as np
import streamlit as st

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

logger.info("Loading data...")
# with st.spinner("Loading data..."):
algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

logger.info("Data loaded.")

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

# weapons_filtered = dynamic_filters.filter_df()
damage_events_filtered_df = damage_events_df[damage_events_df["weapon_name"].isin(selected_weapons)]

hit_count_median = int(damage_events_filtered_df["hit_count"].median())

high_hit_threshold = st.sidebar.number_input("Ranking Minimum Hit Count",
                                             min_value=1,
                                             max_value=100,
                                             value=hit_count_median,
                                             key="high_hit_count")

higher_than_threshold_data = damage_events_filtered_df.loc[damage_events_filtered_df["hit_count"] >= high_hit_threshold]

player_ranking_data = damage_events_filtered_df[["player_name", "team_name", "hit_count"]]

player_hit_count = player_ranking_data.groupby(["player_name", "team_name"]).agg(
    total_fights=("hit_count", "count"),
).reset_index()

high_hit_count_players = player_ranking_data.loc[player_ranking_data["hit_count"] >= high_hit_threshold]

high_hit_count_players_ranking = high_hit_count_players.groupby(["player_name", "team_name"]).agg(
    high_hit_count=("hit_count", "count"),
).reset_index()

high_hit_count_players_ranking = high_hit_count_players_ranking.sort_values(by="high_hit_count", ascending=False)

high_hit_count_players_ranking = high_hit_count_players_ranking.merge(player_hit_count, on=[
    "player_name",
    "team_name"], how="inner")

high_hit_count_players_ranking["high_hit_count_percentage"] = 100 * high_hit_count_players_ranking["high_hit_count"] / \
                                                              high_hit_count_players_ranking["total_fights"]

high_hit_count_players_ranking["high_hit_count_percentage"] = high_hit_count_players_ranking[
    "high_hit_count_percentage"].apply(
    lambda x: np.round(x, 2))
team_ranking_data = high_hit_count_players_ranking.groupby("team_name").agg(
    high_hit_count=("high_hit_count", "sum"),
    total_fights=("total_fights", "sum"),
).reset_index()

team_ranking_data["high_hit_count_percentage"] = 100 * team_ranking_data["high_hit_count"] / team_ranking_data[
    "total_fights"]

team_ranking_data["high_hit_count_percentage"] = team_ranking_data["high_hit_count_percentage"].apply(
    lambda x: np.round(x, 2))

team_ranking_data = team_ranking_data.sort_values(by="high_hit_count", ascending=False)

hao_right_data = damage_events_filtered_df.loc[damage_events_filtered_df["player_name"] == "HAO Right"]

high_hit_count_players_ranking["high_hit_count_rank"] = range(1, len(high_hit_count_players_ranking) + 1)

high_hit_count_players_ranking.rename(columns={"player_name": "Name",
                                               "high_hit_count_rank": "Rank",
                                               "high_hit_count": "Count",
                                               "total_fights": "Total",
                                               "high_hit_count_percentage": "Percentage"}, inplace=True)

st.write("Player Rankings")
st.dataframe(high_hit_count_players_ranking[
                 ["Rank", "Name", "Count", "Total", "Percentage"]],
             hide_index=True, use_container_width=True)

team_ranking_data["rank"] = range(1, len(team_ranking_data) + 1)

team_ranking_data.rename(columns={"team_name": "Name",
                                  "rank": "Rank",
                                  "high_hit_count": "Count",
                                  "total_fights": "Total",
                                  "high_hit_count_percentage": "Percentage"}, inplace=True)

st.write("Team Rankings")

st.dataframe(team_ranking_data[["Rank", "Name", "Count", "Total", "Percentage"]]
             , hide_index=True, use_container_width=True)

expander = st.expander(label='Raw Data')
expander.dataframe(higher_than_threshold_data[[
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
