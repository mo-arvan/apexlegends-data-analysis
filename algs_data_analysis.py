import json
import os
from argparse import ArgumentParser

import pandas as pd


def get_fights_data(algs_fights_data_dict):
    weapons_data = []

    no_weapon_used_count = 0
    no_damage_dealt_count = 0
    hits_more_than_used_count = 0
    total_count = 0
    for game_id, fights_list in algs_fights_data_dict.items():
        for fights in fights_list:

            start_fight_time = fights["startEventTimestamp"]

            for player, data in fights["players"].items():
                player_name = data["playerName"]
                if len(data["weaponsDamage"]["dealt"]) == 0 or "weaponsUsed" not in data:
                    # print(f"No weapons used for {player_name}")
                    no_weapon_used_count += 1
                    continue

                #

                for short_name, weapon_damage in data["weaponsDamage"]["dealt"].items():
                    weapon_name = weapon_damage["name"]
                    weapon_used = next(
                        filter(lambda x: x["name"] == weapon_name, data["weaponsUsed"]), None)
                    if weapon_used is not None:
                        shots = weapon_used["ammoUsed"]
                        damage_dealt = weapon_damage["damage"]
                        hits = weapon_damage["hits"]
                        time = weapon_used["time"]

                        if hits > shots:
                            hits_more_than_used_count += 1
                        else:
                            weapons_data.append(
                                (player_name, weapon_name, shots, hits, damage_dealt, time,
                                 game_id, start_fight_time))
                    else:
                        # invalid_weapon_used = ['Piercing Spikes']
                        # print(f"No weapon used for {weapon_name}")
                        no_damage_dealt_count += 1
                    total_count += 1

    print(f"Missing Weapons Used Info %: {no_weapon_used_count / total_count * 100:.2f}")
    print(f"Hits > Shots %: {hits_more_than_used_count / total_count * 100:.2f}")

    weapons_df = pd.DataFrame(weapons_data,
                              columns=["player_name", "weapon_name", "shots", "hits", "damage_dealt", "time",
                                       "game_id", "start_fight_time"])

    return weapons_df


def main():
    aug_parser = ArgumentParser()
    aug_parser.add_argument("--getFights_data_dir", default="data/algs_games/getFights")

    args = aug_parser.parse_args()
    get_fights_data_dir = args.getFights_data_dir

    get_fights_dict = {}

    for file_name in os.listdir(get_fights_data_dir):
        with open(os.path.join(get_fights_data_dir, file_name), "r") as f:
            get_fights_dict[file_name[:-5]] = json.load(f)

    weapons_df = get_fights_data(get_fights_dict)

    weapons_df.to_csv("data/weapons_data.csv", index=False)


if __name__ == "__main__":
    main()
