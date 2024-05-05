import json
import logging
import os
import pickle
import re
from argparse import ArgumentParser

import numpy as np
import pandas as pd
from tqdm import tqdm

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
        logger.debug(f"Event text {event_text} did not match the pattern")
        return None, None, None, None


def normalize_weapon_name(weapon):
    return weapon.lower().replace(" ", "")


def process_events(game_hash, game_data_dict, init_data_dict, output_dir):
    game_events = game_data_dict["events"]
    last_event_id = game_data_dict["lastEventId"]
    events_location = game_data_dict["eventsLocations"]

    if len(game_events) != len(events_location):
        game_events = [p for g in game_events for p in g]

        if len(game_events) != len(events_location):
            logger.debug(f"Mismatch in the number of events and events location for {game_hash}")

    weapon_set = set()

    #

    ammo_type_to_weapon_dict_base = {"Light": ["P2020", "RE-45", "Alternator", "R-99", "CAR", "R-301", 'G7 Scout'],
                                     "Heavy": ["Hemlok", "Flatline", "Spitfire", "CAR", "30-30", 'Rampage', "Prowler"],
                                     "Energy": ["Triple Take", "L-Star", "Volt", 'HAVOC', "Devotion", 'Nemesis',
                                                'L-STAR'],
                                     "Shotgun": ["Mastiff", "EVA-8", "Peacekeeper", "Mozambique"],
                                     "Sniper": ["Kraber", "Sentinel", "Wingman", "Longbow", "Charge Rifle"],
                                     "Special": ["Kraber", 'Bocek', 'Minigun', "Sniper's Mark"]
                                     }
    invalid_weapons_base = ["Drone EMP", "Caustic Gas", 'Mobile Minigun "Sheila"', 'War Club Melee',
                            'Rolling Thunder', 'Defensive Bombardment', 'Frag Grenade', 'Missile Swarm',
                            'Energy Barricade', 'Thermite Grenade', 'Arc Star', 'Smoke Launcher', 'Creeping Barrage',
                            'Smoke Launcher', 'Suzaku Melee', 'Perimeter Security', 'Piercing Spikes', 'The Motherlode',
                            'Knuckle Cluster', 'Cold Steel Melee', 'Melee', 'Gravity Maw', 'Riot Drill',
                            'Wrecking Ball', 'Castle Wall', 'Biwon Blade Melee', 'Showstoppers Melee', 'Killed',
                            'Garra De Alanza Melee', 'Problem Solver Melee', "Arc Snare", "Raven's Bite Melee",
                            'Gravity Maw Melee', "Showstoppers", 'Silence', 'Mobile Shield', 'Strongest Link']

    invalid_weapons = []
    for i_w in invalid_weapons_base:
        invalid_weapons.append(i_w)
        invalid_weapons.append(normalize_weapon_name(i_w))

    ammo_type_to_weapon_dict = {}
    for ammo_type, weapons in ammo_type_to_weapon_dict_base.items():
        ammo_type_to_weapon_dict[ammo_type] = []
        for weapon in weapons:
            ammo_type_to_weapon_dict[ammo_type].append(weapon)
            ammo_type_to_weapon_dict[ammo_type].append(normalize_weapon_name(weapon))

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

                    if weapon in invalid_weapons or normalize_weapon_name(
                            weapon) in invalid_weapons or "Melee" in weapon:
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
                                    # logger.warning(f"Time difference between events is {time_diff} for {weapon}")
                                    pass
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
                                # logger.warning(f"Time difference between events is {time_diff} for {ammo_type}")
                                pass

        game_damage_events.extend(merged_damage_events)

    game_damage_df = pd.DataFrame(game_damage_events)

    game_damage_df["game_hash"] = game_hash

    game_damage_df.to_parquet(os.path.join(output_dir, f"{game_hash}.parquet"))

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

    all_weapons = [w for ww in ammo_type_to_weapon_dict.values() for w in ww]
    weapon_set = list(
        filter(lambda x: x not in all_weapons and normalize_weapon_name(x) not in all_weapons, weapon_set))
    if len(weapon_set) > 0:
        logger.debug(f"weapon_set: {weapon_set}")
    # return game_damage_events


def read_events(event_files, events_dir):
    for file_name in event_files:
        with open(os.path.join(events_dir, file_name), "rb") as f:
            yield file_name[:-4], pickle.load(f)


def main():
    aug_parser = ArgumentParser()
    aug_parser.add_argument("--events_dir", default="data/events")
    aug_parser.add_argument("--init_data_dir", default="data/algs_games/init")
    aug_parser.add_argument("--output_dir", default="data/events_processed")
    aug_parser.add_argument("--damage_events_dir", default="data/tournament_damage_events")
    aug_parser.add_argument("--debug", action="store_true", default=True)

    args = aug_parser.parse_args()
    events_dir = args.events_dir
    output_dir = args.output_dir
    damage_events_dir = args.damage_events_dir
    debug = args.debug

    event_files = os.listdir(events_dir)
    logger.info(f"Reading events from {events_dir}")

    existing_files = os.listdir(output_dir)
    existing_files = [f.split(".")[0] for f in existing_files]

    event_files = [f for f in event_files if f[:-4] not in existing_files]
    num_events = len(event_files)
    # 52dd387d9d52ec001940a8c175437335

    init_dict = {}
    for file_name in os.listdir(args.init_data_dir):
        with open(os.path.join(args.init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)

    if num_events > 0:
        events_gen = read_events(event_files, events_dir)

        logger.info(f"Read {num_events} events")

        logger.info(f"Reading init data from {args.init_data_dir}")
        init_dict = {}
        for file_name in os.listdir(args.init_data_dir):
            with open(os.path.join(args.init_data_dir, file_name), "r") as f:
                init_dict[file_name[:-5]] = json.load(f)
        #
        # init_df = pd.DataFrame(init_dict.values())

        logger.info(f"Read {len(init_dict)} init files")

        # events_list = sorted(events_list, key=lambda x: int(init_dict[x[0]]["timestamp"]), reverse=True)

        logger.info("Processing events")
        for e in tqdm(events_gen, total=num_events):
            if e[0] in init_dict:
                game_hash, game_data_tuple = e
                process_events(game_hash, game_data_tuple, init_dict[e[0]], output_dir)

    logger.info("Merging all the parquet files into one file per tournament")

    # merging all the parquet files into a single file
    all_files = os.listdir(output_dir)
    all_files = [f for f in all_files if f.endswith(".parquet")]
    all_files = [os.path.join(output_dir, f) for f in all_files]
    all_files = [pd.read_parquet(f) for f in all_files]
    damage_df = pd.concat(all_files)

    algs_games_df = pd.read_parquet("data/algs_game_list.parquet")
    gun_stats_df = pd.read_csv("data/guns_stats.csv")

    def fix_weapon_name(name):
        relpace_dict = {
            # "R-99": "R99",
            "Alternator": "Alternator SMG",
            'EVA-8': "EVA-8 Auto",
            'CAR': "C.A.R. SMG",
            "Prowler": "Prowler Burst PDW",
            "Volt": "Volt SMG",
            "R-99": "R-99 SMG",
            '30-30': "30-30 Repeater",
            'Hemlok': "Hemlok Burst AR",
            'R-301': "R-301 Carbine",
            'Flatline': "VK-47 Flatline",
            'Mastiff': "Mastiff Shotgun",
            'Mozambique': "Mozambique Shotgun",
            'Rampage': "Rampage LMG",
            'RE-45': "RE-45 Auto",
            "Spitfire": "M600 Spitfire",
            'HAVOC': "HAVOC Rifle",
            'Nemesis': 'Nemesis Burst AR',
            'Bocek': 'Bocek Compound Bow',
            "Longbow": "Longbow DMR",
            "Kraber": "Kraber .50-Cal Sniper",
            "Devotion": "Devotion LMG",
            'ChargeRifle': "Charge Rifle",
            "TripleTake": "Triple Take",
            "L-STAR": "L-STAR EMG",
            "G7Scout": "G7 Scout",
            "Sniper'sMark": "Sniper's Mark",
        }
        if name in relpace_dict:
            name = relpace_dict[name]
        return name

    damage_df["weapon"] = damage_df["weapon"].apply(fix_weapon_name)

    damage_weapon_names = damage_df["weapon"].unique().tolist()

    stats_weapon_names = gun_stats_df["weapon_name"].unique().tolist()

    missing_weapon_names = [w for w in damage_weapon_names if w not in stats_weapon_names]

    logger.debug(f"Missing weapon names: {missing_weapon_names}")
    # print(missing_weapon_names)
    # print(stats_weapon_names)

    damage_df.rename(columns={"weapon": "weapon_name",
                              "game_hash": "game_id"},
                     inplace=True)

    damage_df["distance_median"] = damage_df["distance"].apply(lambda x: np.median(x))
    damage_df["hit_count"] = damage_df["damage"].apply(lambda x: len(x))
    damage_df["damage_sum"] = damage_df["damage"].apply(lambda x: sum(x))

    player_hash_to_name = [(game["gameID"],
                            player["nucleusHash"][:32],
                            player["playerName"],
                            player["teamName"],
                            # game["timestamp"]
                            ) for
                           game in init_dict.values() for player in game["players"]]
    player_hash_df = pd.DataFrame(player_hash_to_name, columns=["game_id", "player_hash", "player_name", "team_name",
                                                                # "timestamp"
                                                                ])

    damage_df = damage_df.merge(algs_games_df,
                                on=["game_id"], how="inner")

    damage_df = damage_df.merge(player_hash_df,
                                on=["game_id", "player_hash"], how="inner")

    tournaments_list = damage_df["tournament_full_name"].unique().tolist()
    for tournament in tournaments_list:
        normalized_name = tournament.lower().replace(" ", "_")
        tournament_df = damage_df[damage_df["tournament_full_name"] == tournament]
        tournament_df.to_parquet(os.path.join(damage_events_dir, f"{normalized_name}.parquet"))

    # damage_df.to_parquet(damage_events_file, index=False, compression="gzip")

    logger.info("Done")


if __name__ == "__main__":
    main()
