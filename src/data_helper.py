import base64
import csv
import logging
import os
from io import BytesIO

import time
import pandas as pd
import streamlit as st
from PIL import Image

import src.data_loader as data_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


@st.cache_data
def load_damage_data(selected_tournament):
    logger.debug(f"Loading damage data for {selected_tournament}")
    normalized_name = selected_tournament.lower().replace(" ", "_")

    damage_events_df = pd.read_parquet(f"data/tournament_damage_events/{normalized_name}.parquet")

    return damage_events_df


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
    algs_games_df = data_loader.get_algs_games()
    # fights_df = get_fights_data()
    gun_stats_df, sniper_stocks_df, standard_stocks_df = get_gun_stats()

    return gun_stats_df, sniper_stocks_df, standard_stocks_df, algs_games_df


@st.cache_data
def load_legends_data(resource_dir="resources"):
    logger.debug("Loading legends data")

    image_path_list = [f"{resource_dir}/{x}" for x in os.listdir(resource_dir) if x.endswith(".png")]

    def get_image(image_path):
        pil_image = Image.open(image_path)
        output = BytesIO()
        pil_image.save(output, format='PNG')

        legend_name = os.path.basename(image_path).replace("-transparent.png", "")

        data = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()

        return legend_name, data

    legends_data_list = list(map(get_image, image_path_list))

    legends_data_df = pd.DataFrame(legends_data_list, columns=["character", "image"])

    return legends_data_df


@st.cache_data
def get_fights_data():
    # not used
    logger.debug("Loading fights data")
    algs_games_df = data_loader.get_algs_games()
    # fights_df = pd.read_csv("data/weapons_data.csv")
    fights_df = pd.read_parquet("data/fights_data.parquet")

    fights_df = fights_df[~pd.isna(fights_df["weapon_name"])]
    # filter when hits > shots
    fights_df = fights_df[fights_df["hits"] <= fights_df["shots"]]

    fights_df["accuracy"] = fights_df["hits"] / fights_df["shots"] * 100

    def map_weapon_name(name):
        replace_dict = {
            # "R-99": "R99",
            "HAVOC": "HAVOC Turbo",
        }
        if name != "Charge Rifle":
            if name in replace_dict:
                name = replace_dict[name]
        return name

    invalid_weapon_names = ["Smoke Launcher", "Thermite Grenade", "Arc Star", "Frag Grenade", "Melee",
                            'Perimeter Security', 'Knuckle Cluster', 'Riot Drill', 'Defensive Bombardment']

    fights_df = fights_df[~fights_df["weapon_name"].isin(invalid_weapon_names)]
    fights_df["weapon_name"] = fights_df["weapon_name"].apply(map_weapon_name)
    fights_df = fights_df.merge(algs_games_df, on=["game_id"], how="inner")

    return fights_df
