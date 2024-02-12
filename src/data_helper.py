import csv

import pandas as pd
import streamlit as st


@st.cache_data
def load_data():
    print("loading data")
    gun_stats_df = pd.read_csv("data/guns_stats.csv")
    sniper_stocks_df = pd.read_csv("data/sniper_stocks.csv")
    standard_stocks_df = pd.read_csv("data/standard_stocks.csv")
    weapons_data_df = pd.read_csv("data/weapons_data.csv")
    algs_games_df = pd.read_csv("data/algs_games.csv")

    gun_stats_df = gun_stats_df.sort_values(by=["secondary_class", "class", "weapon_name"])

    for col in gun_stats_df.columns:
        if 'magazine' in col or "rpm" in col:
            gun_stats_df[col] = gun_stats_df[col].fillna(-1).astype(int)

    gun_stats_df.to_csv("data/guns_stats.csv", index=False,
                        quoting=csv.QUOTE_NONNUMERIC)

    weapons_data_df = weapons_data_df[~pd.isna(weapons_data_df["weapon_name"])]
    # filter when hits > shots
    weapons_data_df = weapons_data_df[weapons_data_df["hits"] <= weapons_data_df["shots"]]

    weapons_data_df["accuracy"] = weapons_data_df["hits"] / weapons_data_df["shots"] * 100

    def map_weapon_name(name):
        relpace_dict = {
            # "R-99": "R99",
            "HAVOC": "HAVOC Turbo",
        }
        if name != "Charge Rifle":
            if name in relpace_dict:
                name = relpace_dict[name]
        return name

    invalid_weapon_names = ["Smoke Launcher", "Thermite Grenade", "Arc Star", "Frag Grenade", "Melee"]

    weapons_data_df = weapons_data_df[~weapons_data_df["weapon_name"].isin(invalid_weapon_names)]
    weapons_data_df["weapon_name"] = weapons_data_df["weapon_name"].apply(map_weapon_name)

    algs_games_df.loc[pd.isna(algs_games_df["tournament_region"]), "tournament_region"] = "NA"

    weapons_data_df = weapons_data_df.merge(algs_games_df, on=["game_id"], how="inner")

    return gun_stats_df, sniper_stocks_df, standard_stocks_df, weapons_data_df, algs_games_df
