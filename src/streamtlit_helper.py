import logging

import numpy as np
import pandas as pd
import streamlit as st

import src.chart_config as chart_config
import src.data_helper as data_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


def get_gun_filters(gun_stats_df,
                    filter_container,
                    select_text="Weapon",
                    mag_bolt_selection=False,
                    include_hop_ups=False,
                    include_ordnance=False,
                    include_reworks=False,
                    enable_tabs=False,
                    ):
    default_selection = {
        "weapon_name": [
            "R-99 SMG",
            "Volt SMG",
            # "Alternator SMG",
            # "C.A.R. SMG",
            # "Prowler Burst PDW"
        ],
    }

    base_weapon_condition = np.logical_or(pd.isna(gun_stats_df["secondary_class"]),
                                          gun_stats_df["secondary_class"] == "Care Package")

    child_container = filter_container.container()
    post_child_container = filter_container.container()
    if include_hop_ups:
        base_weapon_condition = np.logical_or(base_weapon_condition, gun_stats_df["secondary_class"] == "Hop-Up")
    if include_reworks:
        include_reworked_weapons = post_child_container.checkbox("Include Future Reworks", value=False)

        if include_reworked_weapons:
            base_weapon_condition = np.logical_or(base_weapon_condition,
                                                  gun_stats_df["secondary_class"] == "Future Reworks")

    base_weapons_df = gun_stats_df[base_weapon_condition]

    weapon_class_list = sorted(base_weapons_df["class"].unique().tolist())

    if "selected_weapons" not in st.session_state:
        preselected_weapons = default_selection["weapon_name"]
    else:
        preselected_weapons = st.session_state["selected_weapons"]

    with child_container.container():
        st.write("Batch Add Weapon Class")
        row_0_cols = st.columns(3)
        with row_0_cols[0]:
            batch_add_smg = st.button("SMG", use_container_width=True, type="primary")
            if batch_add_smg:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "SMG"][
                    "weapon_name"].unique().tolist()

        with row_0_cols[1]:
            batch_add_pistol = st.button("Pistol", use_container_width=True, type="primary")
            if batch_add_pistol:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "Pistol"][
                    "weapon_name"].unique().tolist()

        with row_0_cols[2]:
            batch_add_shotgun = st.button("Shotgun", use_container_width=True, type="primary")
            if batch_add_shotgun:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "Shotgun"][
                    "weapon_name"].unique().tolist()

        row_1_cols = st.columns(2)
        with row_1_cols[0]:
            batch_add_ar = st.button("AR", use_container_width=True, type="primary")
            if batch_add_ar:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "AR"][
                    "weapon_name"].unique().tolist()

        with row_1_cols[1]:
            batch_add_lmg = st.button("LMG", use_container_width=True, type="primary")

            if batch_add_lmg:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "LMG"][
                    "weapon_name"].unique().tolist()

        row_2_cols = st.columns(2)

        with row_2_cols[0]:
            batch_add_marksman = st.button("Marksman", use_container_width=True, type="primary")
            if batch_add_marksman:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "Marksman"][
                    "weapon_name"].unique().tolist()
        with row_2_cols[1]:
            batch_add_sniper = st.button("Sniper", use_container_width=True, type="primary")
            if batch_add_sniper:
                preselected_weapons += base_weapons_df[base_weapons_df["class"] == "Sniper"][
                    "weapon_name"].unique().tolist()

    preselected_weapons = list(sorted(set(preselected_weapons)))
    logger.debug(f"Preselected Weapons: {preselected_weapons}")

    all_weapons = base_weapons_df["weapon_name"].unique().tolist()

    if include_ordnance:
        ordnance_list = ["Frag Grenade", "Arc Star", "Thermite Grenade"]
        all_weapons += ordnance_list

    for w in preselected_weapons:
        if w not in all_weapons:
            logger.warning(f"Preselected weapon {w} not found in the dataset. Removing from preselected weapons.")
            preselected_weapons.remove(w)

    selected_weapons = child_container.multiselect(select_text,
                                                   all_weapons,
                                                   default=preselected_weapons,
                                                   key="selected_weapons")

    if mag_bolt_selection:
        selected_mag = child_container.selectbox('Mag (if applicable):',
                                                 chart_config.mag_list,
                                                 index=3,
                                                 key='mag')

        selected_bolt = child_container.selectbox('Shotgun Bolt (if applicable):',
                                                  ['White', 'Blue', 'Purple'],
                                                  index=2,
                                                  key='bolt')
        selected_stocks = child_container.selectbox('Stock (if applicable):',
                                                    chart_config.stock_list,
                                                    index=3,
                                                    key='stock')
    else:
        selected_mag = None
        selected_bolt = None
        selected_stocks = None

    return selected_weapons, selected_mag, selected_bolt, selected_stocks


def get_tournament_filters(algs_games_df, gun_stats_df, filters_container):
    # find the largest timestamp for each tournament
    tournaments = (algs_games_df[['tournament_full_name', "tournament_region", 'game_timestamp']]
                   .groupby(['tournament_full_name', "tournament_region"]).
                   agg(max_timestamp=('game_timestamp', 'max'))).reset_index()
    tournaments = tournaments.sort_values(by="max_timestamp", ascending=False)

    tournaments_order = tournaments["tournament_full_name"].unique().tolist()

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

    filters_container.write("Apply the filters in any order")

    selected_tournament = filters_container.selectbox("Tournament",
                                                      tournaments_order,
                                                      index=0,
                                                      key="selected_tournaments")

    if selected_tournament is None:
        st.error("Please select at least one tournament.")
        st.stop()

    damage_events_df = data_helper.load_damage_data(selected_tournament)

    region_list = algs_games_df[algs_games_df["tournament_full_name"] == selected_tournament][
        "tournament_region"].unique().tolist()

    region_list = sorted(region_list)

    selected_region = filters_container.multiselect("Region",
                                                    region_list,
                                                    key="selected_region")

    if len(selected_region) != 0:
        damage_events_df = damage_events_df[damage_events_df["tournament_region"].isin(selected_region)]

    game_days = sorted(damage_events_df["tournament_day"].unique().tolist())

    selected_days = filters_container.multiselect("Day",
                                                  game_days,
                                                  key="selected_days")

    if len(selected_days) != 0:
        damage_events_df = damage_events_df[damage_events_df["tournament_day"].isin(selected_days)]

    weapon_info = gun_stats_df[["weapon_name", "class"]].sort_values(by="weapon_name")
    damage_events_df = damage_events_df.merge(weapon_info, on=["weapon_name"], how="left")

    weapon_list = damage_events_df["weapon_name"].unique().tolist()

    selected_weapons, selected_mag, selected_bolt, selected_stock = get_gun_filters(gun_stats_df,
                                                                                    filters_container,
                                                                                    include_ordnance=True,
                                                                                    )

    if len(selected_weapons) != 0:
        damage_events_df = damage_events_df[damage_events_df["weapon_name"].isin(selected_weapons)]

    return damage_events_df, selected_tournament, selected_region, selected_days, selected_weapons
