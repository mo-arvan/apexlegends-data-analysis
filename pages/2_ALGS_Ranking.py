import logging

import numpy as np
import streamlit as st

import src.data_helper as data_helper
import src.streamtlit_helper as streamlit_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

st.set_page_config(
    page_title="ALGS Fights Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'https://www.extremelycoolapp.com/help',
        # 'Report a bug': "https://www.extremelycoolapp.com/bug",
        # 'About': "# This is a header. This is an *extremely* cool app!"
    }
)


def get_player_ranking(input_df, minimum_damage):
    higher_than_threshold_data = input_df.loc[
        damage_events_filtered_df["damage_sum"] >= minimum_damage]

    player_ranking_data = damage_events_filtered_df[["player_name", "team_name", "input", "hit_count", "damage_sum"]]

    player_hit_count = player_ranking_data.groupby(["player_name", "team_name", "input"]).agg(
        total_fights=("hit_count", "count"),
    ).reset_index()

    high_hit_count_players = player_ranking_data.loc[player_ranking_data["damage_sum"] >= minimum_damage]

    high_hit_count_players_ranking = high_hit_count_players.groupby(["player_name", "team_name", "input"]).agg(
        high_hit_count=("hit_count", "count"),
    ).reset_index()

    high_hit_count_players_ranking = high_hit_count_players_ranking.merge(player_hit_count, on=[
        "player_name",
        "team_name",
        "input"
    ], how="inner")

    high_hit_count_players_ranking["high_hit_count_percentage"] = 100 * high_hit_count_players_ranking[
        "high_hit_count"] / \
                                                                  high_hit_count_players_ranking["total_fights"]

    high_hit_count_players_ranking["high_hit_count_percentage"] = high_hit_count_players_ranking[
        "high_hit_count_percentage"].apply(
        lambda x: np.round(x, 2))
    high_hit_count_players_ranking = high_hit_count_players_ranking.sort_values(by=["high_hit_count",
                                                                                    "high_hit_count_percentage"
                                                                                    ],
                                                                                ascending=False)

    high_hit_count_players_ranking["high_hit_count_rank"] = range(1, len(high_hit_count_players_ranking) + 1)

    high_hit_count_players_ranking.rename(columns={"player_name": "Name",
                                                   "team_name": "Team",
                                                   "input": "Input",
                                                   "high_hit_count_rank": "Rank",
                                                   "high_hit_count": "Count",
                                                   "total_fights": "Total",
                                                   "high_hit_count_percentage": "Percentage"}, inplace=True)

    return high_hit_count_players_ranking[
        ["Rank", "Name", "Input", "Count", "Total", "Percentage"]], higher_than_threshold_data


def get_team_ranking():
    team_ranking_data = high_hit_count_players_ranking.groupby("team_name").agg(
        high_hit_count=("high_hit_count", "sum"),
        total_fights=("total_fights", "sum"),
    ).reset_index()

    team_ranking_data["high_hit_count_percentage"] = 100 * team_ranking_data["high_hit_count"] / team_ranking_data[
        "total_fights"]

    team_ranking_data["high_hit_count_percentage"] = team_ranking_data["high_hit_count_percentage"].apply(
        lambda x: np.round(x, 2))

    team_ranking_data = team_ranking_data.sort_values(by="high_hit_count", ascending=False)

    team_ranking_data["rank"] = range(1, len(team_ranking_data) + 1)

    team_ranking_data.rename(columns={"team_name": "Name",
                                      "rank": "Rank",
                                      "high_hit_count": "Count",
                                      "total_fights": "Total",
                                      "high_hit_count_percentage": "Percentage"}, inplace=True)


logger.info("Loading data...")
# with st.spinner("Loading data..."):
algs_games_df = data_helper.get_algs_games()
gun_stats_df, _, _ = data_helper.get_gun_stats()

logger.info("Data loaded.")

damage_events_filtered_df, selected_tournament, selected_region, selected_days, selected_weapons = streamlit_helper.common_filters(
    algs_games_df, gun_stats_df)

hit_count_median = int(damage_events_filtered_df["hit_count"].median())

# median_damage_dealt = int(damage_events_filtered_df["damage_sum"].median())

minimum_damage = st.sidebar.number_input("Minimum Damage Dealt",
                                         min_value=1,
                                         max_value=1000,
                                         value=100,
                                         key="high_hit_count")

hash_to_input_dict = data_helper.get_hash_to_input_dict()

damage_events_filtered_df["input"] = damage_events_filtered_df["player_hash"].apply(
    lambda x: hash_to_input_dict.get(x, "?"))

filter_input_nan = damage_events_filtered_df[damage_events_filtered_df["input"].isna()]

filter_input_nan_grouped = filter_input_nan.groupby(["player_name", "player_hash", "team_name"]).agg(
    count=("player_name", "count"),
).reset_index()

filter_input_nan_grouped = filter_input_nan_grouped.sort_values(by="count", ascending=False)

print(filter_input_nan_grouped[["player_name", "team_name", "count"]][:10])

high_hit_count_players_ranking, higher_than_threshold_data = get_player_ranking(damage_events_filtered_df,
                                                                                minimum_damage)

st.write("Player Rankings")
st.dataframe(high_hit_count_players_ranking,
             hide_index=True, use_container_width=True)

#
# st.write("Team Rankings")
#
# st.dataframe(team_ranking_data[["Rank", "Name", "Count", "Total", "Percentage"]]
#              , hide_index=True, use_container_width=True)

expander = st.expander(label='Raw Data')
expander.dataframe(higher_than_threshold_data[[
    "player_name",
    "input",
    "team_name",
    "tournament_full_name",
    "tournament_day",
    "game_title",
    "game_map",
    "event_start_time",
    "weapon_name",
    # "class",
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
