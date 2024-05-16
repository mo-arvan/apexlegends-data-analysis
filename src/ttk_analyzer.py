import logging

import math
import pandas as pd

import src.chart_config as chart_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


def get_estimation_model(guns_df, fights_df, estimation_method, selected_weapons_df):
    accuracy_model_df = None
    if estimation_method == "Expected Value":
        single_shot_weapons_list = guns_df[guns_df["firing_mode"] == "single shot"]["weapon_name"].unique().tolist()
        burst_fire_weapons_list = guns_df[guns_df["firing_mode"] == "burst"]["weapon_name"].unique().tolist()
        auto_weapon_list = guns_df[guns_df["firing_mode"] == "auto"]["weapon_name"].unique().tolist()

        single_shot_weapons_list.extend(burst_fire_weapons_list)

        single_shot_fights_df = fights_df.loc[fights_df["weapon_name"].isin(single_shot_weapons_list)].copy()
        remaining_fights_df = fights_df.loc[~fights_df["weapon_name"].isin(single_shot_weapons_list)]
        auto_weapon_fights_df = remaining_fights_df.loc[
            remaining_fights_df["weapon_name"].isin(auto_weapon_list)].copy()

        accuracy_bins = list(range(0, 101, 5))

        single_shot_fights_df["binned"] = pd.cut(single_shot_fights_df["accuracy"], accuracy_bins)
        auto_weapon_fights_df["binned"] = pd.cut(auto_weapon_fights_df["accuracy"], accuracy_bins)

        single_shot_accuracy_df = single_shot_fights_df[["binned"]].groupby("binned", observed=False).agg(
            frequency=("binned", "size")).reset_index()
        single_shot_accuracy_df["pdf"] = single_shot_accuracy_df["frequency"] / single_shot_accuracy_df[
            "frequency"].sum()
        single_shot_accuracy_df["cdf"] = single_shot_accuracy_df["pdf"].cumsum()

        auto_weapon_accuracy_df = auto_weapon_fights_df[["binned"]].groupby("binned", observed=False).agg(
            frequency=("binned", "size")).reset_index()
        auto_weapon_accuracy_df["pdf"] = auto_weapon_accuracy_df["frequency"] / auto_weapon_accuracy_df[
            "frequency"].sum()
        auto_weapon_accuracy_df["cdf"] = auto_weapon_accuracy_df["pdf"].cumsum()

        auto_weapon_accuracy_df["accuracy"] = auto_weapon_accuracy_df["binned"].apply(lambda x: x.right)
        single_shot_accuracy_df["accuracy"] = single_shot_accuracy_df["binned"].apply(lambda x: x.right)

        auto_weapon_accuracy_df["accuracy"] = auto_weapon_accuracy_df["accuracy"].astype(int)
        single_shot_accuracy_df["accuracy"] = single_shot_accuracy_df["accuracy"].astype(int)

        single_shot_accuracy_df["model_name"] = "Single Shot"
        auto_weapon_accuracy_df["model_name"] = "Auto"
        single_shot_accuracy_df["guns"] = [single_shot_weapons_list for _ in range(len(single_shot_accuracy_df))]
        auto_weapon_accuracy_df["guns"] = [auto_weapon_list for _ in range(len(auto_weapon_accuracy_df))]

        accuracy_model_df = pd.concat([single_shot_accuracy_df, auto_weapon_accuracy_df])

    return accuracy_model_df


def get_e_dps_df(selected_weapons,
                 guns_df,
                 sniper_stocks_df,
                 standard_stocks_df,
                 fights_df,
                 conditions):
    dps_dict_list = []

    selected_weapons_df = guns_df[guns_df["weapon_name"].isin(selected_weapons)]

    mag_index = chart_config.mag_list.index(conditions["mag"])
    helmet_modifier = chart_config.helmet_dict[conditions["helmet"]]
    shot_location = chart_config.shot_location_dict[conditions["shot_location"]]
    evo_shield_amount = chart_config.evo_shield_dict[conditions["shield"]]
    health_amount = chart_config.health_values_dict[conditions["health"]]
    peek_time_in_ms = conditions["peek_time"]
    estimation_method = conditions["estimation_method"]

    total_health = health_amount + evo_shield_amount

    # accuracy_model_df = get_estimation_model(selected_weapons_df,
    #                                          fights_df,
    #                                          estimation_method,
    #                                          selected_weapons_df)

    for idx, weapon in selected_weapons_df.iterrows():

        # if weapon["weapon_name"] in accuracy_model_df["guns"]
        # gun_accuracy_model_df = accuracy_model_df[accuracy_model_df["guns"].apply(lambda x: weapon["weapon_name"] in x)]
        weapon_raw_damage = weapon["damage"]
        current_mag_size = weapon[f"magazine_{mag_index + 1}"]

        stock_index = chart_config.stock_list.index(conditions["stock"])
        # current_stock = weapon[f"stock_{stock_index + 1}"]

        if conditions["ability_modifier"] == "Amped Cover (Rampart)":
            # Amped Cover boosts the damage of outgoing shots by 20%.
            # Source https://apexlegends.fandom.com/wiki/Rampart#Amped_Cover
            weapon_raw_damage = weapon_raw_damage * 1.2
        head_damage = weapon_raw_damage * shot_location[0] * (
                helmet_modifier + (1 - helmet_modifier) * weapon["head_multiplier"])
        body_damage = weapon_raw_damage * shot_location[1]
        leg_damage = weapon_raw_damage * shot_location[2] * weapon["leg_multiplier"]

        if conditions["ability_modifier"] == "Fortified (Gibby, Caustic, Newcastle)":
            body_damage = body_damage * 0.85
            leg_damage = leg_damage * 0.85

        damage = head_damage + body_damage + leg_damage

        effective_damage = damage

        evo_shield_effective_damage = effective_damage * weapon["evo_damage_multiplier"]
        non_evo_shield_effective_damage = effective_damage * weapon["non_evo_damage_multiplier"]

        if conditions["ability_modifier"] == "Forged Shadows (Revenant)":
            health_amount += 75
        if weapon["class"] == "Shotgun":
            current_bolt = chart_config.mag_list.index(conditions["bolt"])
            gun_rpm = weapon[f"rpm_{current_bolt + 1}"]
        else:
            gun_rpm = weapon["rpm_1"]

        # if weapon["class"] == "Marksman" or weapon["class"] == "Sniper":
        #     reload_time_modifier = weapon["reload_time_4"]
        # elif weapon["class"] == "Shotgun" or weapon["class"] == "SMG" or weapon["class"] == "AR":
        #     reload_time_modifier = weapon["reload_time_4"]
        # else:
        #     reload_time_modifier =weapon["reload_time_4"]

        charge_time = weapon.get("charge_time")
        if pd.isna(charge_time):
            charge_time = 0

        charge_time_in_ms = charge_time * 1000

        shot_interval = 60 / gun_rpm

        burst_fire_delay = weapon.get("burst_fire_delay")
        bullets_per_burst = weapon.get("bullets_per_burst")
        if pd.isna(burst_fire_delay) or pd.isna(bullets_per_burst):
            shots_during_peek = math.floor((peek_time_in_ms - charge_time_in_ms) / 1000 / shot_interval) + 1
            shots_during_peek = min(shots_during_peek, current_mag_size)
        else:
            bullets_per_burst = int(bullets_per_burst)
            max_burst = current_mag_size // bullets_per_burst
            max_shot_burst = -1
            for i in range(1, max_burst + 1):
                max_possible_shots = bullets_per_burst * i
                burst_time = burst_fire_delay * (i - 1)
                burst_time_in_ms = burst_time * 1000
                remaining_peek_time_ms = peek_time_in_ms - charge_time_in_ms - burst_time_in_ms
                if remaining_peek_time_ms < 0:
                    break
                shots_during_peek = math.floor(remaining_peek_time_ms / 1000 / shot_interval) + 1
                shots_during_peek = min(shots_during_peek, max_possible_shots)
                if shots_during_peek > max_shot_burst:
                    max_shot_burst = shots_during_peek
            shots_during_peek = max_shot_burst

        pellets_per_shot = weapon.get("pellets_per_shot")
        if pd.isna(pellets_per_shot):
            pellets_per_shot = 1

        for miss_shots in range(shots_during_peek):
            miss_rate = round(miss_shots / shots_during_peek * 100, 0)
            hit_shots = shots_during_peek - miss_shots
            accuracy = round(100 - miss_rate, 0)

            hit_pellets = hit_shots * pellets_per_shot

            hit_and_miss_shots = shots_during_peek
            damage_dealt = hit_pellets * evo_shield_effective_damage
            uncapped_damage_dealt = damage_dealt

            if damage_dealt > evo_shield_amount:
                shots_to_evo_shield = math.ceil(evo_shield_amount / evo_shield_effective_damage)
                remaining_bullets = hit_pellets - shots_to_evo_shield

                evo_shield_damage_dealt = shots_to_evo_shield * evo_shield_effective_damage

                evo_minus_dealt_damage = evo_shield_amount - evo_shield_damage_dealt

                health_left = health_amount + evo_minus_dealt_damage

                health_left = max(health_left, 0)
                shots_to_body = math.ceil(health_left / non_evo_shield_effective_damage)
                shots_to_body = min(shots_to_body, remaining_bullets)

                non_evo_damage_dealt = shots_to_body * non_evo_shield_effective_damage

                damage_dealt = evo_shield_damage_dealt + non_evo_damage_dealt

                second_target_bullets = remaining_bullets - shots_to_body
                uncapped_damage_dealt = damage_dealt + second_target_bullets * evo_shield_effective_damage

                damage_dealt = min(damage_dealt, total_health)

            ammo_left = current_mag_size - hit_shots - miss_shots
            # cdf = gun_accuracy_model_df[gun_accuracy_model_df["accuracy"] <= accuracy]["cdf"].max()
            #
            # model_name = gun_accuracy_model_df["model_name"].unique().tolist()
            # assert len(model_name) == 1
            # accuracy_model = model_name[0]

            dps = damage_dealt / peek_time_in_ms * 1000
            uncapped_dps = uncapped_damage_dealt / peek_time_in_ms * 1000

            # TODO include raise and holster time, reload time
            gun_ttk_dict = {
                "miss_rate": miss_rate,
                "accuracy": accuracy,
                "weapon_name": weapon["weapon_name"],
                # "remaining_health": remaining_health,
                "damage_dealt": damage_dealt,
                "uncapped_damage_dealt": uncapped_damage_dealt,
                "dps": dps,
                "uncapped_dps": uncapped_dps,
                # "cdf": cdf,
                "how": f"shots hit: {hit_shots}, shots missed: {miss_shots}",
                "ammo_left": ammo_left,
                # "accuracy_model": accuracy_model,
                # "reload time": reload_time_modifier,
            }
            gun_ttk_dict.update(conditions)
            dps_dict_list.append(gun_ttk_dict)

    # # adding ranking for weapons based on eDPS for each accuracy value
    # accuracy_value = sorted(set([dps_dict["accuracy"] for dps_dict in dps_dict_list]), reverse=True)
    # weapons_set  =  set([dps_dict["weapon_name"] for dps_dict in dps_dict_list])
    #
    # ranking_dict = {}
    # matching_weapons = [dps_dict for dps_dict in dps_dict_list if dps_dict["accuracy"] == 100]
    # matching_weapons = sorted(matching_weapons, key=lambda k: k['dps'], reverse=True)
    # weapon_names = [dps_dict["weapon_name"] for dps_dict in matching_weapons]
    # for i, weapon in enumerate(weapon_names):
    #     ranking_dict[weapon] = i + 1
    # #
    # for accuracy in accuracy_value:
    #     matching_weapons = [dps_dict for dps_dict in dps_dict_list if dps_dict["accuracy"] == accuracy]
    #     matching_weapons = sorted(matching_weapons, key=lambda k: k['dps'], reverse=True)
    #     for weapon in weapons_set:

    dps_dict_list = sorted(dps_dict_list, key=lambda k: k['dps'], reverse=True)
    dps_df = pd.DataFrame(dps_dict_list)
    plot_dict = {
        "dps_df": dps_df,
    }
    return plot_dict


def get_gun_meta_df(selected_weapons,
                    guns_df,
                    sniper_stocks_df,
                    standard_stocks_df,
                    fights_df,
                    conditions):
    dps_list = []

    peek_time_list = [50]
    peek_time_list += [(t + 1) * 500 for t in range(10)]

    for peek_time in peek_time_list:
        conditions["peek_time"] = peek_time
        plot_dict = get_e_dps_df(selected_weapons,
                                 guns_df,
                                 sniper_stocks_df,
                                 standard_stocks_df,
                                 fights_df,
                                 conditions)
        dps_df = plot_dict["dps_df"]
        dps_df["peek_time"] = peek_time
        dps_list.append(dps_df)

    dps_df = pd.concat(dps_list)

    accuracy_list = [a * 10 for a in range(3, 11)]

    weapon_list = selected_weapons

    best_dps_list = []
    # for each accuracy and peek time, find the worst dps for each weapon
    for max_accuracy in accuracy_list:
        accuracy_df = dps_df[dps_df["accuracy"] <= max_accuracy]
        for peek_time in peek_time_list:
            peek_time_df = accuracy_df[accuracy_df["peek_time"] == peek_time]
            # for weapon in weapon_list:

            best_dps = peek_time_df.groupby("weapon_name", observed=False).agg(
                uncapped_dps=("uncapped_dps", "max"),
                uncapped_damage_dealt=("uncapped_damage_dealt", "max"),
            ).reset_index()

            best_dps = best_dps.sort_values(by=["uncapped_dps"], ascending=False).reset_index(drop=True)

            # rank the weapons based on the worst dps, use the same rank for weapons with the same dps
            last_rank = 0
            last_dps = None
            for i, row in best_dps.iterrows():
                if row["uncapped_dps"] != last_dps:
                    rank = i + 1
                    last_dps = row["uncapped_dps"]
                else:
                    rank = last_rank
                best_dps.at[i, "rank"] = rank
                last_rank = rank
            best_dps["peek_time"] = peek_time
            best_dps["max_accuracy"] = max_accuracy

            best_dps_list.append(best_dps)

    dps_grid_df = pd.concat(best_dps_list)

    return dps_grid_df
