import json
import logging
import os
from argparse import ArgumentParser

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


def get_fights_data(algs_fights_data_dict, players_in_games):
    weapons_data = []

    no_weapon_used_count = 0
    no_damage_dealt_count = 0
    hits_more_than_used_count = 0
    total_count = 0
    for game_id, fights_list in algs_fights_data_dict.items():
        players_in_current_game = players_in_games[game_id]

        for fights in fights_list:

            start_fight_time = int(fights["startEventTimestamp"])

            for player, data in fights["players"].items():
                player_name = data["playerName"]
                player_info = next(filter(lambda x: x["playerName"] == player_name, players_in_current_game), None)

                if player_info is None:
                    logger.info(f"Player {player_name} not found in players_in_current_game")
                    continue

                player_hash = player_info["nucleusHash"][:32]
                # player_team = player_info["team"]
                if len(data["weaponsDamage"]["dealt"]) == 0 or "weaponsUsed" not in data:
                    # logger.info(f"No weapons used for {player_name}")
                    no_weapon_used_count += 1
                    continue

                for short_name, weapon_damage in data["weaponsDamage"]["dealt"].items():
                    weapon_name = weapon_damage["name"]
                    weapon_used = next(
                        filter(lambda x: x["name"] == weapon_name, data["weaponsUsed"]), None)
                    if weapon_used is not None:
                        shots = int(weapon_used["ammoUsed"])
                        damage_dealt = int(weapon_damage["damage"])
                        hits = int(weapon_damage["hits"])
                        time = int(weapon_used["time"])

                        if hits > shots:
                            hits_more_than_used_count += 1
                        else:
                            weapons_data.append(
                                (player_name, player_hash,
                                 weapon_name, shots, hits, damage_dealt, time,
                                 game_id, start_fight_time))
                    else:
                        # invalid_weapon_used = ['Piercing Spikes']
                        # logger.info(f"No weapon used for {weapon_name}")
                        no_damage_dealt_count += 1
                    total_count += 1

    logger.info(f"Missing Weapons Used Info %: {no_weapon_used_count / total_count * 100:.2f}")
    logger.info(f"Hits > Shots %: {hits_more_than_used_count / total_count * 100:.2f}")

    weapons_df = pd.DataFrame(weapons_data,
                              columns=["player_name", "player_hash",
                                       "weapon_name", "shots", "hits", "damage_dealt", "time",
                                       "game_id", "start_fight_time"])

    # time is in iso chron format
    weapons_df["time"] = pd.to_datetime(weapons_df["time"].astype(int), unit="s")

    players_list = weapons_df[["player_hash", "time"]].groupby("player_hash").agg(
        time=("time", "max")).reset_index()

    players_list_left_join_with_name = players_list.merge(weapons_df[["player_hash", "time", "player_name"]],
                                                          on=["player_hash", "time"], how="left")

    players_with_latest_name = players_list_left_join_with_name[["player_hash", "player_name"]].drop_duplicates(
        keep="last")

    weapons_df.drop(columns=["player_name"], inplace=True)

    weapons_df = weapons_df.merge(players_with_latest_name, on="player_hash", how="left")

    return weapons_df


def main():
    aug_parser = ArgumentParser()
    aug_parser.add_argument("--getFights_data_dir", default="data/algs_games/getFights")
    aug_parser.add_argument("--init_data_dir", default="data/algs_games/init")

    args = aug_parser.parse_args()
    get_fights_data_dir = args.getFights_data_dir

    get_fights_dict = {}
    init_dict = {}

    for file_name in os.listdir(get_fights_data_dir):
        with open(os.path.join(get_fights_data_dir, file_name), "r") as f:
            get_fights_dict[file_name[:-5]] = json.load(f)

    for file_name in os.listdir(args.init_data_dir):
        with open(os.path.join(args.init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)

    players_in_games = {k: v["players"] for k, v in init_dict.items()}

    fights_data_df = get_fights_data(get_fights_dict, players_in_games)

    fights_data_df.to_parquet("data/fights_data.parquet")


if __name__ == "__main__":
    main()
