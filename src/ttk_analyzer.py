import math
import pandas as pd
import streamlit as st

import src.chart_config as chart_config


# https://fonts.google.com/specimen/Saira+Extra+Condensed
# https://www.reddit.com/r/apexlegends/comments/13rtny9/the_foundational_flaw_of_apex_legends/
# https://apexlegendsstatus.com/algs/Y3-Split2/ALGS-Championships/Global/Overview#weaponsStats
# https://docs.google.com/spreadsheets/d/1ipBvNmgK7-u2VJGlbNzsPvqydXhoRGM7Zxf6OBMvkpc/edit#gid=0
# tracking time over damage
# https://www.reddit.com/r/CrucibleGuidebook/comments/vrfvfb/ttk_simulator_based_on_your_weapon_and_estimated/
# https://www.reddit.com/r/CompetitiveApex/comments/mir49b/apex_legends_data_visualizations/
# https://public.tableau.com/app/profile/connor.murphy2369/viz/TSMCompetitiveAnalysis/TSMTeamAnalysis?publish=yes


def get_ttk_df(guns_slice_df,
               sniper_stocks_df, standard_stocks_df,
               conditions):
    ttk_dict_list = []

    for idx, weapon_primary in guns_slice_df.iterrows():
        # ttk_dict_list = get_gun_effective_ttk(weapon_primary,
        #                                       sniper_stocks_df, standard_stocks_df,
        #                                       conditions)
        # ttk_dict_list = ttk_dict_list + ttk_dict_list

        weapon_raw_damage = weapon_primary["damage"]

        mag_index = chart_config.mag_list.index(conditions["mag"])
        current_mag_size = weapon_primary[f"magazine_{mag_index + 1}"]

        # stock_index = chart_config.stock_list.index(conditions["stock"])
        # current_stock = weapon_primary[f"stock_{stock_index + 1}"]

        helmet_modifier = chart_config.helmet_dict[conditions["helmet"]]
        shot_location = chart_config.shot_location_dict[conditions["shot_location"]]

        evo_shield_amount = chart_config.evo_shield_dict[conditions["shield"]]
        health_amount = chart_config.health_values_dict[conditions["health"]]

        if conditions["ability_modifier"] == "Amped Cover (Rampart)":
            # Amped Cover boosts the damage of outgoing shots by 20%.
            # Source https://apexlegends.fandom.com/wiki/Rampart#Amped_Cover
            weapon_raw_damage = weapon_raw_damage * 1.2
        head_damage = weapon_raw_damage * shot_location[0] * (
                helmet_modifier + (1 - helmet_modifier) * weapon_primary["head_multiplier"])
        body_damage = weapon_raw_damage * shot_location[1]
        leg_damage = weapon_raw_damage * shot_location[2] * weapon_primary["leg_multiplier"]

        if conditions["ability_modifier"] == "Fortified (Gibby, Caustic, Newcastle)":
            body_damage = body_damage * 0.85
            leg_damage = leg_damage * 0.85

        damage = head_damage + body_damage + leg_damage

        effective_damage = damage

        evo_shield_effective_damage = effective_damage * weapon_primary["evo_damage_multiplier"]
        non_evo_shield_effective_damage = effective_damage * weapon_primary["non_evo_damage_multiplier"]

        if conditions["ability_modifier"] == "Forged Shadows (Revenant)":
            health_amount += 75

        if weapon_primary["class"] == "Shotgun":
            current_bolt = chart_config.mag_list.index(conditions["bolt"])
            primary_rpm = weapon_primary[f"rpm_{current_bolt + 1}"]
        else:
            primary_rpm = weapon_primary["rpm_1"]

        # if pd.isna(evo_shield_effective_damage):
        #     print(weapon_primary)

        # if weapon_primary["class"] == "Marksman" or weapon_primary["class"] == "Sniper":
        #     reload_time_modifier = weapon_primary["reload_time_4"]
        # elif weapon_primary["class"] == "Shotgun" or weapon_primary["class"] == "SMG" or weapon_primary["class"] == "AR":
        #     reload_time_modifier = weapon_primary["reload_time_4"]
        # else:
        #     reload_time_modifier =weapon_primary["reload_time_4"]

        shots_to_evo_shield = math.ceil(evo_shield_amount / evo_shield_effective_damage)
        shots_to_evo_shield = min(shots_to_evo_shield, current_mag_size)
        remaining_bullets = current_mag_size - shots_to_evo_shield

        evo_minus_dealt_damage = evo_shield_amount - shots_to_evo_shield * evo_shield_effective_damage

        health_left = health_amount + evo_minus_dealt_damage

        health_left = max(health_left, 0)
        shots_to_body = math.ceil(health_left / non_evo_shield_effective_damage)
        shots_to_body = min(shots_to_body, remaining_bullets)
        remaining_health = max(health_left - shots_to_body * non_evo_shield_effective_damage, 0)

        total_damage_dealt = shots_to_body * non_evo_shield_effective_damage + shots_to_evo_shield * evo_shield_effective_damage

        total_shots = shots_to_body + shots_to_evo_shield

        if remaining_health != 0:
            return ttk_dict_list

        for miss_shots in range(0, current_mag_size - total_shots + 1):
            miss_rate = round(miss_shots / (total_shots + miss_shots) * 100, 0)
            accuracy = round(100 - miss_rate, 0)

            hit_and_miss_shots = total_shots + miss_shots

            primary_shot_interval = 60 / primary_rpm
            ttk = primary_shot_interval * (hit_and_miss_shots - 1)
            ttk = round(ttk * 1000, 0)
            # TODO include raise and holster time

            gun_ttk_dict = {
                "miss_rate": miss_rate,
                "accuracy": accuracy,
                "weapon_name": weapon_primary["weapon_name"],
                # "remaining_health": remaining_health,
                "ttk": ttk,
                "how": f"shots hit: {total_shots}, shots missed: {miss_shots}",
                "damage_dealt": total_damage_dealt,
                # "reload time": reload_time_modifier,
            }
            gun_ttk_dict.update(conditions)
            ttk_dict_list.append(gun_ttk_dict)

            # if len(ttk_dict_list) > 0:
            #     if gun_ttk_dict["ttk"] == ttk_dict_list[-1]["ttk"]:
            #         continue
            #     else:
            #         last_ettk = ttk_dict_list[-1].copy()
            #         last_ettk["accuracy"] = row["accuracy"] + 1
            #         ttk_dict_list.append(last_ettk)

    ttk_dict_list = sorted(ttk_dict_list, key=lambda k: k['ttk'], reverse=True)
    ttk_df = pd.DataFrame(ttk_dict_list)
    return ttk_df


# def get_gun_effective_ttk(weapon_primary,
#                           weapon_secondary):
#     """
#     effective accuracy is the accuracy of the weapon
#     if the weapon is the primary weapon
#     else it is the accuracy of the weapon if it is the secondary weapon
#
#     :param weapon_primary:
#     :param weapon_secondary:
#     :return:
#     """
#     weapon_name = weapon_primary["weapon_name"]

#     #     st.sidebar.selectbox('Legend Modifier:', ["None", 'Rev (+75 Evo)', 'Fortified (0.8 body shots)', 'Rampart (0.2'],
#     ability_modifier_list = ["None",
#                             'Forged Shadows (Revenant)',
#                             'Amped Cover (Rampart)',
#                             'Fortified (Gibby, Caustic, Newcastle)']
#
#     ttk_dict_list = []
#
#     weapon_raw_damage = weapon_primary["damage"]
#
#     for shield_tuple, shot_location_tuple, mag_tuple, stock_tuple, helmet_tuple, health_tuple, \
#             ability_modifier in itertools.product(
#         *[evo_shield_dict.items(),
#           shot_location_dict.items(),
#           enumerate(mag_list),
#           enumerate(stock_list),
#           helmet_dict.items(),
#           chart_type_dict.items(),
#           ability_modifier_list
#           ]):
#
#
#             # ttk = (primary_shot_interval * (
#             #         total_shots - 1) + secondary_shot_interval * secondary_shots + deploy_lower_sum_time +
#             #        reload_time)
#     return ttk_dict_list


# def get_ttk_over_accuracy(guns_slice_df, sniper_stocks_df, standard_stocks_df, conditions):
#     ttk_dict_list = []
#
#     for idx, row in guns_slice_df.iterrows():
#         gun_ttk_dict_list = get_gun_effective_ttk(row.to_dict(), row.to_dict(),
#                                                   sniper_stocks_df, standard_stocks_df,
#                                                   conditions)
#         ttk_dict_list = ttk_dict_list + gun_ttk_dict_list
#
#     return ttk_dict_list


def get_close_range_effective_ttk_df(gun_df):
    ttk_over_accuracy = get_ttk_df(gun_df)

    ttk_over_accuracy = pd.DataFrame(ttk_over_accuracy)

    return ttk_over_accuracy


def get_damage_over_peek_time(gun_df):
    head_multiplier = 1.25
    leg_multiplier = 0.8
    head_body_leg_distribution = [0.15, 0.7, 0.15]

    # effective_accuracy = 0.75
    weapon_health_time_list = []
    for idx, row in gun_df.iterrows():

        weapon = row["weapon_name"]
        # if weapon == "Alternator Disruptor":
        #     continue

        weapon = row["weapon_name"]
        damage = row["damage"]
        rpm = row["rpm"]
        mag = row[f"magazine_{3 + 1}"]
        shot_interval = 60 / rpm
        current_weapon_damage_time_list = []
        for i in range(1, mag + 1):
            for accuracy in range(1, 101):
                effective_damage = damage * i * accuracy / 100
                if weapon == "Alternator Disruptor":
                    # the first 125 damage has a 1.2 multiplier
                    max_i = 125 / ((damage * 1.2) * accuracy / 100)
                    distrupter_damage = (damage * 0.2) * min(i, max_i) * accuracy / 100
                    effective_damage += distrupter_damage

                if effective_damage > 225:
                    effective_damage = 225
                weapon_health_time_list.append([weapon, effective_damage, accuracy, shot_interval * (i - 1) * 1000])

    return weapon_health_time_list


def plot_damage_over_peek_time(gun_df):
    damage_over_peek_time = get_damage_over_peek_time(gun_df)

    damage_over_peek_time_df = pd.DataFrame(damage_over_peek_time, columns=["weapon", "damage", "accuracy", "time"])


def visualize_gun_df(gun_df):
    st.write("Raw Data")
    st.dataframe(gun_df)


def main():
    close_gun_df = pd.read_csv("data/guns_close_range.csv")
    long_gun_df = pd.read_csv("data/guns_long_range.csv")

    get_close_range_effective_ttk_df(close_gun_df)

    # for accuracy in range(50, 101, 10):
    #     plot_remaining_health_over_time(close_gun_df, 3, 3, 1, accuracy / 100)
    #
    # plot_ttk_over_accuracy(close_gun_df, 3)
    # plot_damage_over_peek_time(close_gun_df)

    # plot_ttk_over_accuracy(close_gun_df, 2)
    # plot_ttk_over_accuracy(close_gun_df, 1)
    # plot_ttk_over_accuracy(close_gun_df, 0)


if __name__ == "__main__":
    main()
