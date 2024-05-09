import csv
import logging

import pandas as pd
import streamlit as st

import src.data_loader as data_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


@st.cache_data
def get_fights_data():
    logger.debug("Loading fights data")
    algs_games_df = get_algs_games()
    # fights_df = pd.read_csv("data/weapons_data.csv")
    fights_df = pd.read_parquet("data/fights_data.parquet")

    fights_df = fights_df[~pd.isna(fights_df["weapon_name"])]
    # filter when hits > shots
    fights_df = fights_df[fights_df["hits"] <= fights_df["shots"]]

    fights_df["accuracy"] = fights_df["hits"] / fights_df["shots"] * 100

    def map_weapon_name(name):
        relpace_dict = {
            # "R-99": "R99",
            "HAVOC": "HAVOC Turbo",
        }
        if name != "Charge Rifle":
            if name in relpace_dict:
                name = relpace_dict[name]
        return name

    invalid_weapon_names = ["Smoke Launcher", "Thermite Grenade", "Arc Star", "Frag Grenade", "Melee",
                            'Perimeter Security', 'Knuckle Cluster', 'Riot Drill', 'Defensive Bombardment']

    fights_df = fights_df[~fights_df["weapon_name"].isin(invalid_weapon_names)]
    fights_df["weapon_name"] = fights_df["weapon_name"].apply(map_weapon_name)
    fights_df = fights_df.merge(algs_games_df, on=["game_id"], how="inner")

    return fights_df


@st.cache_data
def get_damage_data(selected_tournament):
    logger.debug("Loading damage data")
    normalized_name = selected_tournament.lower().replace(" ", "_")

    damage_events_df = pd.read_parquet(f"data/tournament_damage_events/{normalized_name}.parquet")

    return damage_events_df


@st.cache_data
def get_algs_games():
    logger.debug("Loading algs games data")
    algs_games_df = pd.read_parquet("data/algs_game_list.parquet")

    return algs_games_df


# @st.cache_data
# def load_data_2():
#     gun_stats_df = pd.read_csv("data/guns_stats.csv")
#
#     # pd interprets "NA" as NaN (Not a Number) and removes it, therefore we need to use na_filter=False to avoid this
#
#     weapons_data_df = pd.read_csv("data/weapons_data.csv")
#
#     gun_stats_df = gun_stats_df.sort_values(by=["weapon_name", "class"])
#     # gun_stats_df.to_csv("data/guns_stats.csv", index=False)
#
#     weapons_data_df = weapons_data_df[~pd.isna(weapons_data_df["weapon_name"])]
#     # filter when hits > shots
#     weapons_data_df = weapons_data_df[weapons_data_df["hits"] <= weapons_data_df["shots"]]
#
#     weapons_data_df["accuracy"] = weapons_data_df["hits"] / weapons_data_df["shots"] * 100
#
#     # def map_weapon_name(name):
#     #     relpace_dict = {
#     #         # "R-99": "R99",
#     #         "HAVOC": "HAVOC Turbo",
#     #     }
#     #     if name != "Charge Rifle":
#     #         if name in relpace_dict:
#     #             name = relpace_dict[name]
#     #     return name
#     # weapons_data_df["weapon_name"] = weapons_data_df["weapon_name"].apply(map_weapon_name)
#
#     weapons_data_df = weapons_data_df[~weapons_data_df["weapon_name"].isin(invalid_weapon_names)]
#     weapons_data_df = weapons_data_df.merge(algs_games_df, on=["game_id"], how="inner")
#
#     return gun_stats_df, weapons_data_df  # , algs_games_df


def get_gun_stats():
    logger.debug("Loading gun stats data")
    gun_stats_df = pd.read_csv("data/guns_stats.csv")
    sniper_stocks_df = pd.read_csv("data/sniper_stocks.csv")
    standard_stocks_df = pd.read_csv("data/standard_stocks.csv")

    current_gun_df = gun_stats_df

    gun_stats_df = gun_stats_df.sort_values(by=["secondary_class", "class", "weapon_name"])
    for col in gun_stats_df.columns:
        if 'magazine' in col or "rpm" in col:
            gun_stats_df[col] = gun_stats_df[col].fillna(-1).astype(int)

    if current_gun_df.equals(gun_stats_df):
        logger.debug("gun_stats_df is the same as the current one")
    else:
        logger.debug("Updating gun_stats_df")
        gun_stats_df.to_csv("data/guns_stats.csv", index=False,
                            quoting=csv.QUOTE_NONNUMERIC)

    return gun_stats_df, sniper_stocks_df, standard_stocks_df


@st.cache_data
def load_data():
    algs_games_df = get_algs_games()
    fights_df = get_fights_data()
    gun_stats_df, sniper_stocks_df, standard_stocks_df = get_gun_stats()

    return gun_stats_df, sniper_stocks_df, standard_stocks_df, fights_df, algs_games_df


@st.cache_data
def get_hash_to_input_dict():
    liquipedia_players_df = data_loader.get_liquipedia_players_df()
    players_df = liquipedia_players_df[["Player ID", "Input"]]
    esports_list = data_loader.get_esports_list()

    desired_hash = "c47c3a177fce49fc512d3edffcd6fa99"

    player_id_to_hash = [(p["esport_name"].lower(), hash) for p in esports_list for hash in
                         p["hash"] if isinstance(p["esport_name"], str)]

    player_id_to_hash_df = pd.DataFrame(player_id_to_hash, columns=["player_name", "hash"])

    players_df["player_name"] = players_df["Player ID"].apply(lambda x: x.lower())

    hash_to_input = player_id_to_hash_df.merge(players_df, on="player_name", how="left")

    hash_to_input_dict = hash_to_input.set_index("hash")["Input"].to_dict()

    # match = next((e for e in player_id_to_hash if desired_hash in e[1]), None)

    return hash_to_input_dict
