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


def calculate_max_shots_given_peak_time(weapon, conditions):
    peek_time_in_ms = conditions["peek_time"]
    mag_index = chart_config.mag_list.index(conditions["mag"])
    current_mag_size = weapon[f"magazine_{mag_index + 1}"]

    charge_time = weapon.get("charge_time")
    if pd.isna(charge_time):
        charge_time = 0

    charge_time_in_ms = charge_time * 1000

    if weapon["class"] == "Shotgun":
        current_bolt = chart_config.mag_list.index(conditions["bolt"])
        gun_rpm = weapon[f"rpm_{current_bolt + 1}"]
    else:
        gun_rpm = weapon["rpm_1"]

    shot_interval = 60 / gun_rpm
    shot_interval_in_ms = shot_interval * 1000

    burst_fire_delay = weapon.get("burst_fire_delay")
    bullets_per_burst = weapon.get("bullets_per_burst")

    if pd.isna(burst_fire_delay) or pd.isna(bullets_per_burst):
        shots_during_peek = math.floor((peek_time_in_ms - charge_time_in_ms) / shot_interval_in_ms) + 1
        shots_during_peek = min(shots_during_peek, current_mag_size)

        firing_time = (shots_during_peek - 1) * shot_interval

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
            shots_during_peek = math.floor(remaining_peek_time_ms / shot_interval_in_ms) + i  # + bullets_per_burst
            shots_during_peek = min(shots_during_peek, max_possible_shots)
            if shots_during_peek > max_shot_burst:
                max_shot_burst = shots_during_peek
        shots_during_peek = max_shot_burst
        burst_shots_fired = math.ceil(shots_during_peek / bullets_per_burst)
        firing_time = (shots_during_peek - burst_shots_fired) * shot_interval + burst_fire_delay * max(
            (burst_shots_fired - 1), 0)

    return shots_during_peek, firing_time


def calculate_damage_dealt(weapon, hit_shots, sniper_stocks_df, standard_stocks_df, conditions):
    mag_index = chart_config.mag_list.index(conditions["mag"])
    helmet_modifier = chart_config.helmet_dict[conditions["helmet"]]
    shot_location = chart_config.shot_location_dict[conditions["shot_location"]]
    evo_shield_amount = chart_config.evo_shield_dict[conditions["shield"]]
    base_health_amount = chart_config.health_values_dict[conditions["health"]]
    peek_time_in_ms = conditions["peek_time"]

    weapon_raw_damage = weapon["damage"]
    current_mag_size = weapon[f"magazine_{mag_index + 1}"]

    if conditions["ability_modifier"] == "Amped Cover (Rampart)":
        # Amped Cover boosts the damage of outgoing shots by 20%.
        # Source https://apexlegends.fandom.com/wiki/Rampart#Amped_Cover
        weapon_raw_damage = weapon_raw_damage * 1.2
    head_damage = weapon_raw_damage * (
            helmet_modifier + (1 - helmet_modifier) * weapon["head_multiplier"])
    body_damage = weapon_raw_damage
    leg_damage = weapon_raw_damage * weapon["leg_multiplier"]

    if conditions["ability_modifier"] == "Fortified (Gibby, Caustic, Newcastle)":
        body_damage = body_damage * 0.85
        leg_damage = leg_damage * 0.85

    damage = head_damage * shot_location[0] + body_damage * shot_location[1] + leg_damage * shot_location[2]

    effective_damage = damage

    evo_shield_effective_damage = effective_damage * weapon["evo_damage_multiplier"]
    non_evo_shield_effective_damage = effective_damage * weapon["non_evo_damage_multiplier"]

    if conditions["ability_modifier"] == "Forged Shadows (Revenant)":
        health_amount = base_health_amount + 75
    else:
        health_amount = base_health_amount

    if weapon["class"] == "Shotgun":
        current_bolt = chart_config.mag_list.index(conditions["bolt"])
        gun_rpm = weapon[f"rpm_{current_bolt + 1}"]
    else:
        gun_rpm = weapon["rpm_1"]

    total_health = health_amount + evo_shield_amount

    # adding +1 to the stock level to match the index in the stock list
    stock_index = chart_config.stock_list.index(conditions["stock"])
    stock_level = stock_index + 1

    reload_time = weapon[f"reload_time_{stock_level}"]
    holster_time = weapon["holster_time"]
    deploy_time = weapon["deploy_time"]

    if stock_index > 0:
        # care package and pistols do not have a stock level
        if weapon["class"] not in ["Care Package", "Pistol"]:
            if weapon["class"] in ["Sniper", "Marksman"]:
                stock_level_name = sniper_stocks_df.columns[stock_index]
                deploy_holster_modifier = \
                    sniper_stocks_df.loc[sniper_stocks_df["Statistic"] == "Deploy/Holster Time"][
                        stock_level_name].item()
            else:
                stock_level_name = standard_stocks_df.columns[stock_index]
                deploy_holster_modifier = \
                    standard_stocks_df.loc[standard_stocks_df["Statistic"] == "Deploy/Holster Time"][
                        stock_level_name].item()
            holster_time = holster_time + holster_time * deploy_holster_modifier / 100
            deploy_time = deploy_time + deploy_time * deploy_holster_modifier / 100

    shot_interval = 60 / gun_rpm
    shot_interval_in_ms = shot_interval * 1000

    shots_during_peek, firing_time = calculate_max_shots_given_peak_time(weapon, conditions)

    pellets_per_shot = weapon.get("pellets_per_shot")
    if pd.isna(pellets_per_shot):
        pellets_per_shot = 1

    # for miss_shots in range(shots_during_peek):
    # miss_rate = 1 - accuracy
    miss_shots = shots_during_peek - hit_shots
    # hit_shots = shots_during_peek - miss_shots
    miss_rate = miss_shots / shots_during_peek
    accuracy = 1 - miss_rate

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

    target_neutralized = False
    if damage_dealt == total_health:
        target_neutralized = True

    ammo_left = current_mag_size - hit_shots - miss_shots
    # cdf = gun_accuracy_model_df[gun_accuracy_model_df["accuracy"] <= accuracy]["cdf"].max()
    #
    # model_name = gun_accuracy_model_df["model_name"].unique().tolist()
    # assert len(model_name) == 1
    # accuracy_model = model_name[0]

    dps = damage_dealt / peek_time_in_ms * 1000
    uncapped_dps = uncapped_damage_dealt / peek_time_in_ms * 1000

    # if damage_dealt > 275:
    #     pass

    damage_dict = {
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
        "shot_interval": shot_interval * 1000,
        "firing_time": firing_time * 1000,
        "ammo_left": ammo_left,
        "headshot_damage": head_damage,
        "body_damage": body_damage,
        "leg_damage": leg_damage,
        # "accuracy_model": accuracy_model,
        "reload_time": reload_time * 1000,
        "holster_time": holster_time * 1000,
        "deploy_time": deploy_time * 1000,
        "target_neutralized": target_neutralized,
    }
    damage_dict.update(conditions)
    return damage_dict


def get_e_dps_df(selected_weapons_df,
                 sniper_stocks_df,
                 standard_stocks_df,
                 conditions):
    dps_dict_list = []

    for idx, weapon in selected_weapons_df.iterrows():
        shots_during_peek, _ = calculate_max_shots_given_peak_time(weapon, conditions)

        for hit_shots in range(shots_during_peek):
            damage_dict = calculate_damage_dealt(weapon, hit_shots, sniper_stocks_df, standard_stocks_df, conditions)

            dps_dict_list.append(damage_dict.copy())
            if damage_dict["target_neutralized"]:
                break

    dps_df = pd.DataFrame(dps_dict_list)
    dps_df = dps_df.sort_values(by=["weapon_name", "accuracy"], ascending=False).reset_index(drop=True)

    dps_full_list = []
    max_x_value = int(dps_df["damage_dealt"].max())
    weapon_list = dps_df["weapon_name"].unique().tolist()
    for min_x_value in range(0, max_x_value + 1, 5):
        for weapon in weapon_list:
            sub_df = dps_df[(dps_df["weapon_name"] == weapon) & (dps_df["damage_dealt"] >= min_x_value)]

            if len(sub_df) > 0:
                sub_df = sub_df.sort_values(by=["damage_dealt", "accuracy"], ascending=True)
                row = sub_df.iloc[0].to_dict()
                row[f"min_damage_dealt"] = min_x_value
                dps_full_list.append(row)
    dps_full_df = pd.DataFrame(dps_full_list)

    pivot_df = (dps_full_df.pivot_table(index=[f"min_damage_dealt"], columns=["weapon_name"], values="accuracy")
                .reset_index())

    plot_dict = {
        "dps_df": dps_df,
        "dps_full_df": dps_full_df,
        "pivot_df": pivot_df,
    }
    return plot_dict


def get_gun_meta_df(selected_weapons,
                    guns_df,
                    sniper_stocks_df,
                    standard_stocks_df,
                    conditions):
    dps_list = []

    peek_time_list = [100]
    peek_time_list += [t * 500 + 250 for t in range(1, 10)]

    selected_guns_df = guns_df[guns_df["weapon_name"].isin(selected_weapons)]

    for peek_time in peek_time_list:
        conditions["peek_time"] = peek_time
        plot_dict = get_e_dps_df(selected_guns_df,
                                 sniper_stocks_df,
                                 standard_stocks_df,
                                 conditions)
        dps_df = plot_dict["dps_df"]
        dps_df["peek_time"] = peek_time
        dps_list.append(dps_df)

    dps_df = pd.concat(dps_list)

    accuracy_list = [a * 10 + 25 for a in range(7)] + [100]

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
