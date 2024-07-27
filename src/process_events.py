import datetime
import logging
import os
import pickle
import re
from argparse import ArgumentParser

import numpy as np
import pandas as pd
from tqdm import tqdm

import src.data_helper as data_helper
import src.data_loader as data_loader

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
    player_hash_game_dict = {}
    for i, player_event in enumerate(game_events):
        player_hash = player_event["player_hash"][0][:32]

        if player_hash in player_hash_game_dict:
            if len(player_event) > len(player_hash_game_dict[player_hash]):
                player_hash_game_dict[player_hash] = player_event
            else:
                continue
        else:
            player_hash_game_dict[player_hash] = player_event

    if len(game_events) != len(events_location):
        logger.debug(f"Mismatch in the number of events and events location for {game_hash}")

    game_id = init_data_dict["gameID"]

    players_hash_to_name_dict = {p["nucleusHash"][:32]: p["playerName"] for p in init_data_dict["players"]}

    weapon_set = set()

    #

    ammo_type_to_weapon_dict_base = {"Light": ["P2020", "RE-45", "Alternator", "R-99", "CAR", "R-301", 'G7 Scout'],
                                     "Heavy": ["Hemlok", "Flatline", "Spitfire", "CAR", "30-30", 'Rampage', "Prowler"],
                                     "Energy": ["Triple Take", "L-Star", "Volt", 'HAVOC', "Devotion", 'Nemesis',
                                                'L-STAR'],
                                     "Shotgun": ["Mastiff", "EVA-8", "Peacekeeper", "Mozambique"],
                                     "Sniper": ["Kraber", "Sentinel", "Wingman", "Longbow", "Charge Rifle"],
                                     "Special": ["Kraber", 'Bocek', 'Minigun', "Sniper's Mark"],
                                     "Ordinance": ["Frag Grenade", "Thermite Grenade", "Arc Star", ]
                                     }
    invalid_weapons_base = ["Drone EMP", "Caustic Gas", 'Mobile Minigun "Sheila"', 'War Club Melee',
                            'Rolling Thunder', 'Defensive Bombardment', 'Missile Swarm',
                            'Energy Barricade', 'Smoke Launcher', 'Creeping Barrage',
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
    ammo_used_pattern = (r"Used x(?P<ammo_count>\d+) \s*(?P<ammo_type>.+?) (Ammo|Rounds|Shells) \(\d+ ➟ \d+\)")

    game_damage_events = []

    # hao_right_hash_id = "e8708d6c9f5cc598c97556fd2ec26091"
    # dup_hashes = ["f72b99ddd0331ba9b6e8a62ead8560f1",
    #               "db044f64168fd3cdb5372e81e1abafe5",
    #               "0f7fa9ba55559a43d58327bf0661170a"]
    #
    # concat_events = pd.concat(game_events)
    # concat_events = concat_events[concat_events["event_type"] == "playerDamaged"]
    # concat_events = concat_events[concat_events["player_hash"].isin(dup_hashes)]
    # concat_events.sort_values("event_id", inplace=True)
    # concat_events.reset_index(drop=True, inplace=True)
    selected_player_hash = "ebb81458a29f44e9c2c30c75008e3223"
    for player_hash, player_events_df in player_hash_game_dict.items():
        player_name = players_hash_to_name_dict[player_events_df["player_hash"][0][:32]]
        if player_hash == selected_player_hash:
            logger.debug(f"Processing events for {player_name}")

        used_damaged_events = player_events_df[
            np.logical_or(np.logical_and(player_events_df["event_type"] == "playerDamaged",
                                         player_events_df["target"] == "attacker"),
                          player_events_df["event_type"] == "ammoUsed")
        ].copy()

        # if player_hash in dup_hashes:
        #     pass

        used_damaged_events.drop_duplicates(subset=["event_id"], inplace=True)

        used_damaged_events = used_damaged_events.sort_values("event_timestamp")
        used_damaged_events = used_damaged_events.reset_index(drop=True)
        # used_damaged_events = used_damaged_events.sort_values("event_timestamp")
        # damage_dealt = player_events_df[player_events_df["event_type"] == "playerDamaged"]
        # damage_dealt = damage_dealt[damage_dealt["target"] == "attacker"]
        #
        # ammo_used_events = player_events_df[player_events_df["event_type"] == "ammoUsed"]

        max_damage_time_diff = 5
        max_ammo_used_time_diff = 99
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

                    if player_name == target:
                        # logger.debug(f"Player {player_name} is the target of the damage event")
                        continue

                    merge_with_last = False

                    if weapon in invalid_weapons or normalize_weapon_name(
                            weapon) in invalid_weapons or "Melee" in weapon:
                        continue
                    weapon_set.add(weapon)

                    if len(merged_damage_events) > 0:

                        last_row = used_damaged_events.iloc[i - 1]

                        last_event = merged_damage_events[-1]

                        if last_event["ammo_used"] is None:
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
                        damage_dict["target_arr"].append(target)
                        damage_dict["distance_arr"].append(distance)
                        damage_dict["damage_arr"].append(damage)
                    else:
                        damage_dict = row.to_dict()
                        damage_dict.pop("event_text")
                        damage_dict["event_id"] = [row["event_id"]]
                        damage_dict["event_time"] = [row["event_time"]]
                        damage_dict["event_timestamp"] = [row["event_timestamp"]]
                        damage_dict["target_arr"] = [target]
                        damage_dict["weapon"] = weapon
                        damage_dict["distance_arr"] = [distance]
                        damage_dict["damage_arr"] = [damage]
                        damage_dict["ammo_used"] = None

                        merged_damage_events.append(damage_dict)
                else:
                    logger.error(f"Event text {event_text} did not match the pattern")

            elif row["event_type"] == "ammoUsed":

                if len(merged_damage_events) > 0:
                    match = re.match(ammo_used_pattern, event_text)

                    if match:
                        # check whether it matches the ammo type of the last damage dealt event
                        ammo_type = match.group("ammo_type")
                        ammo_count = int(match.group("ammo_count"))
                        last_damage_event = merged_damage_events[-1]
                        last_weapon = last_damage_event["weapon"]

                        if last_damage_event[
                            "ammo_used"] is None and ammo_type in ammo_type_to_weapon_dict and last_weapon in \
                                ammo_type_to_weapon_dict[ammo_type]:
                            time_diff = row["event_timestamp"] - last_damage_event["event_timestamp"][-1]
                            if time_diff <= max_ammo_used_time_diff:
                                last_damage_event["ammo_used"] = ammo_count
                            else:
                                # logger.warning(f"Time difference between events is {time_diff} for {ammo_type}")
                                pass
                        else:
                            matching_weapon_list = ammo_type_to_weapon_dict[ammo_type]
                            last_matching_event = next(
                                filter(lambda x: x["weapon"] in matching_weapon_list, merged_damage_events[::-1]), None)
                            # two_to_last_damage_event = merged_damage_events[-2]
                            # two_to_last_weapon = two_to_last_damage_event["weapon"]

                            if last_matching_event is None or last_matching_event["ammo_used"] is not None:
                                continue

                            time_diff = row["event_timestamp"] - last_matching_event["event_timestamp"][-1]
                            if time_diff <= max_ammo_used_time_diff:
                                last_matching_event["ammo_used"] = ammo_count
                            else:
                                # logger.warning(f"Time difference between events is {time_diff} for {ammo_type}")
                                pass

                    else:
                        logger.debug(f"Event text {event_text} did not match the pattern")

        game_damage_events.extend(merged_damage_events)

    if len(game_damage_events) == 0:
        logger.debug(f"No damage events found for {game_hash}")
        return

    game_damage_df = pd.DataFrame(game_damage_events)

    game_damage_df.sort_values(by=["event_timestamp"], inplace=True)

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


def post_process(damage_events_dir, output_dir, init_dict):
    # merging all the parquet files into a single file
    all_files = os.listdir(output_dir)
    all_files = [f for f in all_files if f.endswith(".parquet")]
    all_files = [os.path.join(output_dir, f) for f in all_files]
    all_files = [pd.read_parquet(f) for f in all_files]
    damage_df = pd.concat(all_files)

    algs_games_df = data_loader.get_algs_games()
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

    shots_hit_list = []
    for i, row in damage_df.iterrows():
        shots_hit = len(row["damage_arr"])
        if row["ammo_used"] is not None:
            if row["ammo_used"] < shots_hit:
                shots_hit = row["ammo_used"]

        shots_hit_list.append(shots_hit)
    damage_df["shots_hit"] = shots_hit_list
    damage_df["shots_hit"] = damage_df["shots_hit"].astype(int)

    damage_df["distance"] = damage_df["distance_arr"].apply(lambda x: np.median(x))
    # damage_df["shots_hit"] = damage_df[["damage_arr", "target_arr"]].apply(calculate_shots_hit)
    damage_df["total_damage"] = damage_df["damage_arr"].apply(lambda x: sum(x))
    # damage_df["event_start_time"] = damage_df["event_time"].apply(lambda x: x[0])
    # damage_df["event_end_time"] = damage_df["event_time"].apply(lambda x: x[-1])
    # get mintues and seconds from event timestamp
    damage_df["event_start_time"] = damage_df["event_timestamp"].apply(
        lambda x: datetime.datetime.fromtimestamp(x[0]).strftime('%M:%S'))
    damage_df["event_end_time"] = damage_df["event_timestamp"].apply(
        lambda x: datetime.datetime.fromtimestamp(x[-1]).strftime('%M:%S'))
    damage_df["event_duration"] = damage_df["event_timestamp"].apply(lambda x: max(x) - min(x))

    damage_df = damage_df.sort_values(by=["game_id", "event_duration"], ascending=[True, False])

    player_hash_to_name = [(game["gameID"],
                            player["nucleusHash"][:32],
                            player["playerName"],
                            player["teamName"],
                            player["character"],
                            # game["timestamp"]
                            ) for
                           game in init_dict.values() for player in game["players"]]
    player_hash_df = pd.DataFrame(player_hash_to_name, columns=["game_id",
                                                                "player_hash",
                                                                "player_name",
                                                                "team_name",
                                                                "character",
                                                                # "timestamp"
                                                                ])

    player_hash_df = player_hash_df.sort_values(by=["player_hash", "player_name", "team_name", "game_id"])

    player_hash_df = player_hash_df.drop_duplicates(subset=["game_id", "player_hash"], keep="first")

    damage_df = damage_df.merge(algs_games_df,
                                on=["game_id"], how="inner")

    damage_df["player_hash"] = damage_df["player_hash"].apply(lambda x: x[:32])

    # left = damage_df.merge(player_hash_df,
    #                        on=["game_id", "player_hash"], how="left")
    #
    # left_missing = left[left["player_name"].isnull()]

    damage_df = damage_df.merge(player_hash_df,
                                on=["game_id", "player_hash"], how="inner")

    hash_to_input_df = data_loader.get_hash_to_player_info_df()
    damage_df = damage_df.merge(hash_to_input_df,
                                              on="player_hash",
                                              how="left")
    def get_id_or_name(x):
        id = x["player_id"]
        name = x["player_name"]
        if not pd.isna(id):
            return id
        else:
            return name

    damage_df["player_id"] = damage_df[["player_id", "player_name"]].apply(get_id_or_name, axis=1)


    # damage_df["target_unique"] = damage_df["target_arr"].apply(lambda x: set(x))
    #
    # # finding items that player is in the target list
    # damage_df["is_target"] = damage_df.apply(lambda x: x["player_name"] in x["target_unique"], axis=1)
    #
    # incorrect_target = damage_df[damage_df["is_target"]]

    tournaments_list = damage_df["tournament_full_name"].unique().tolist()
    for tournament in tournaments_list:
        normalized_name = tournament.lower().replace(" ", "_")
        tournament_df = damage_df[damage_df["tournament_full_name"] == tournament]
        tournament_df.to_parquet(os.path.join(damage_events_dir, f"{normalized_name}.parquet"))


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

    if num_events > 0:
        events_gen = read_events(event_files, events_dir)

        logger.info(f"Read {num_events} events")

        logger.info(f"Reading init data from {args.init_data_dir}")
        # os.path.join(args.init_data_dir, file_name)
        init_dict = data_loader.get_game_init(args.init_data_dir)
        #
        # init_df = pd.DataFrame(init_dict.values())

        logger.info(f"Read {len(init_dict)} init files")

        # events_list = sorted(events_list, key=lambda x: int(init_dict[x[0]]["timestamp"]), reverse=True)
        # selected_gamez = "78656cba121dadc281fd1001a5a24233"
        #
        # selected_game_df = damage_events_filtered_df.loc[damage_events_filtered_df["game_id"] == selected_gamez]
        #
        # selected_game_df.to_csv("selected_game.csv", index=False)

        logger.info("Processing events")
        for e in tqdm(events_gen, total=num_events):
            if e[0] in init_dict:
                game_hash, game_data_tuple = e
                process_events(game_hash, game_data_tuple, init_dict[e[0]], output_dir)

        logger.info("Performing post processing")

        # damage_df.to_parquet(damage_events_file, index=False, compression="gzip")
        post_process(damage_events_dir, output_dir, init_dict)

        logger.info("Done")


if __name__ == "__main__":
    main()
