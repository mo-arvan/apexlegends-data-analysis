import json
import logging
import os
import pickle
import re
from argparse import ArgumentParser
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


def merge_damage(event_text):
    event_pattern = r"Dealt (?P<damage>\d+) damage to (?P<target>.+?) with\s+(?P<weapon>.+?)\s+— ([\s\S]+?) — (?P<distance>\d+(\.\d+)?)"
    match = re.match(event_pattern, event_text)
    if match:
        damage = int(match.group("damage"))
        target = match.group("target")
        weapon = match.group("weapon")
        distance = float(match.group("distance"))
        return damage, target, weapon, distance
    else:
        logger.warning(f"Event text {event_text} did not match the pattern")
        return None, None, None, None


def process_events(game_data_tuple, init_data_dict):
    game_id, game_events, last_event_id, events_location = game_data_tuple

    weapon_set = set()

    ammo_type_to_weapon_dict = {"Light": ["P2020", "RE-45", "Alternator", "R-99", "C.A.R.", "R-301"],
                                "Heavy": ["Hemlok", "Flatline", "G7", "Spitfire", "C.A.R.", "30-30"],
                                "Energy": ["Triple Take", "L-Star", "Volt", "Havoc", "Devotion"],
                                "Shotgun": ["Mastiff", "EVA-8", "Peacekeeper", "Mozambique"],
                                "Sniper": ["Kraber", "Sentinel", "Wingman", "Longbow", "Charge Rifle", ]}
    invalid_weapons = ["Drone EMP", "Caustic Gas", 'Mobile Minigun "Sheila"', 'War Club Melee',
                       'Rolling Thunder', 'Defensive Bombardment', 'Frag Grenade', 'Missile Swarm',
                       'Energy Barricade', 'Thermite Grenade', 'Arc Star', ]

    # Used x26  Energy Ammo (137 ➟ 111)
    # player id, event id, event name, event time, event detail, event x, event y, event time in minutes and seconds
    # event text
    damage_dealt_pattern = r"Dealt (?P<damage>\d+) damage to (?P<target>.+?) with\s+(?P<weapon>.+?)\s+— ([\s\S]+?) — (?P<distance>\d+(\.\d+)?)"
    ammo_used_pattern = (r"Used x(?P<ammo_count>\d+) \s*(?P<ammo_type>.+?) Ammo \(\d+ ➟ \d+\)")

    game_damage_events = []

    for player_events_df in game_events:
        used_damaged_events = player_events_df[
            np.logical_or(np.logical_and(player_events_df["event_type"] == "playerDamaged",
                                         player_events_df["target"] == "attacker"),
                          player_events_df["event_type"] == "ammoUsed")]

        used_damaged_events = used_damaged_events.sort_values("event_timestamp")
        used_damaged_events = used_damaged_events.reset_index(drop=True)
        # used_damaged_events = used_damaged_events.sort_values("event_timestamp")
        # damage_dealt = player_events_df[player_events_df["event_type"] == "playerDamaged"]
        # damage_dealt = damage_dealt[damage_dealt["target"] == "attacker"]
        #
        # ammo_used_events = player_events_df[player_events_df["event_type"] == "ammoUsed"]


        max_damage_time_diff = 10
        max_ammo_used_time_diff = 10
        merged_damage_events = []
        for i, row in used_damaged_events.iterrows():
            event_text = row["event_text"]
            if row["event_type"] == "playerDamaged" and row["target"] == "attacker":
                match = re.match(damage_dealt_pattern, event_text)
                if match:
                    damage = int(match.group("damage"))
                    target = match.group("target")
                    weapon = match.group("weapon")
                    distance = float(match.group("distance"))

                    merge_with_last = False

                    if weapon in invalid_weapons:
                        continue
                    weapon_set.add(weapon)

                    if len(merged_damage_events) > 0:

                        last_row = used_damaged_events.iloc[i - 1]

                        last_event = merged_damage_events[-1]

                        if last_event["weapon"] == weapon:
                            if last_row["event_type"] == "playerDamaged" or last_row["target"] == "attacker":
                                time_diff = row["event_timestamp"] - last_event["event_timestamp"][-1]
                                if time_diff <= max_damage_time_diff:
                                    merge_with_last = True
                                elif time_diff < 2 * max_damage_time_diff:
                                    logger.warning(f"Time difference between events is {time_diff} for {weapon}")
                            else:
                                # logger.warning(f"Last event is not a damage event for {weapon}")
                                pass

                    if merge_with_last:
                        damage_dict = merged_damage_events[-1]
                        damage_dict["event_id"].append(row["event_id"])
                        damage_dict["event_time"].append(row["event_time"])
                        damage_dict["event_timestamp"].append(row["event_timestamp"])
                        damage_dict["target"].append(target)
                        damage_dict["distance"].append(distance)
                        damage_dict["damage"].append(damage)
                    else:
                        damage_dict = row.to_dict()
                        damage_dict.pop("event_text")
                        damage_dict["event_id"] = [row["event_id"]]
                        damage_dict["event_time"] = [row["event_time"]]
                        damage_dict["event_timestamp"] = [row["event_timestamp"]]
                        damage_dict["target"] = [target]
                        damage_dict["weapon"] = weapon
                        damage_dict["distance"] = [distance]
                        damage_dict["damage"] = [damage]
                        damage_dict["ammo_used"] = None

                        merged_damage_events.append(damage_dict)
                else:
                    logger.warning(f"Event text {event_text} did not match the pattern")

            elif row["event_type"] == "ammoUsed":

                if len(merged_damage_events) > 0 and merged_damage_events[-1]["ammo_used"] == None:
                    match = re.match(ammo_used_pattern, event_text)

                    if match:
                        # check whether it matches the ammo type of the last damage dealt event
                        ammo_type = match.group("ammo_type")
                        ammo_count = int(match.group("ammo_count"))
                        last_damage_event = merged_damage_events[-1]
                        last_weapon = last_damage_event["weapon"]

                        if ammo_type in ammo_type_to_weapon_dict and last_weapon in ammo_type_to_weapon_dict[ammo_type]:
                            time_diff = row["event_timestamp"] - last_damage_event["event_timestamp"][-1]
                            if time_diff <= max_ammo_used_time_diff:
                                last_damage_event["ammo_used"] = ammo_count
                            else:
                                logger.warning(f"Time difference between events is {time_diff} for {ammo_type}")

        game_damage_events.extend(merged_damage_events)

    # game_damage_events = pd.DataFrame(game_damage_events)
    #
    # ammo_not_available = game_damage_events[game_damage_events["ammo_used"].isnull()]
    # ratio_ammo_not_available = len(ammo_not_available) / len(game_damage_events)
    # logger.info(f"Ratio of ammo not available: {ratio_ammo_not_available}")
    #
    # player_hash = "bee67822cdff6f11440cdf58bda0c60f"
    #
    # player_data_index = [p["player_hash"][0] for p in game_events].index(player_hash)
    #
    # player_data = game_events[player_data_index]

    logger.info(f"weapon_set: {weapon_set}")
    return game_damage_events


def main():
    aug_parser = ArgumentParser()
    aug_parser.add_argument("--events_path", default="data/events.pkl")
    aug_parser.add_argument("--init_data_dir", default="data/algs_games/init")
    aug_parser.add_argument("--debug", action="store_true", default=True)

    args = aug_parser.parse_args()
    events_path = args.events_path
    debug = args.debug

    logger.info(f"Reading events from {events_path}")
    with open(events_path, "rb") as f:
        events_list = pickle.load(f)
    logger.info(f"Read {len(events_list)} events")

    logger.info(f"Reading init data from {args.init_data_dir}")
    init_dict = {}
    for file_name in os.listdir(args.init_data_dir):
        with open(os.path.join(args.init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)
    #
    # init_df = pd.DataFrame(init_dict.values())

    logger.info(f"Read {len(init_dict)} init files")

    events_list = sorted(events_list, key=lambda x: int(init_dict[x[0]]["timestamp"]), reverse=True)

    logger.info("Processing events")
    for e in events_list:
        if e[0] in init_dict:
            process_events(e, init_dict[e[0]])


if __name__ == "__main__":
    main()
