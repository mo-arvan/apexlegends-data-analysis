import csv
import time
from argparse import ArgumentParser
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm.auto import tqdm
from difflib import SequenceMatcher

import json


def get_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def main():
    parser = ArgumentParser()
    parser.add_argument("--algs_players", default="data/algs_players.csv", help="ALGS Game List File")
    parser.add_argument("--algs_games_dir", default="data/algs_games", help="ALGS Games Directory")
    parser.add_argument("--init_data_dir", default="data/algs_games/init")

    args = parser.parse_args()
    algs_players_file = args.algs_players
    algs_games_dir = args.algs_games_dir
    init_data_dir = args.init_data_dir

    init_dict = {}
    for file_name in os.listdir(args.init_data_dir):
        with open(os.path.join(args.init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)

    hash_to_name_file = "data/player_to_hash.json"
    if os.path.exists(hash_to_name_file):
        with open(hash_to_name_file, "r") as f:
            hash_to_name_dict = json.load(f)
    else:
        hash_to_name_dict = {}

    hash_to_player_dict = {pp["nucleusHash"][:32]: pp["playerName"] for p in init_dict.values() for pp in p["players"]}

    hash_to_player_dict = {k: v for k, v in hash_to_player_dict.items() if k not in hash_to_name_dict}

    players_df = pd.read_csv(algs_players_file)

    for player_hash, player_name in hash_to_player_dict.items():
        exact_match = players_df[players_df["Player ID"] == player_name]
        if len(exact_match) == 1:
            hash_to_name_dict[player_hash] = player_name
        else:
            name_variations = []
            name_variations.extend(player_name.split(" "))
            name_variations.extend(player_name.split("_"))
            name_variations = list(set(name_variations))

            for i in range(len(player_name)):
                if len(player_name[i:]) > 3:
                    name_variations.append(player_name[i:])

            matching_players = players_df[players_df["Player ID"].isin(name_variations)]

            if len(matching_players) == 1:
                print(f"Matched {player_name} to {matching_players['Player ID'].values[0]}")
                input_choice = input("Is this correct? (y/n): ")
                if input_choice == "y":
                    hash_to_name_dict[player_hash] = matching_players["Player ID"].values[0]
                    with open(hash_to_name_file, "w") as f:
                        json.dump(hash_to_name_dict, f, indent=2)
            else:
                continue
                # print(f"Found {len(matching_players)} matching players for {player_name}")
                # for i, row in matching_players.iterrows():
                #     print(f"{i}: {row['Player ID']}")
                # input_choice = input("Enter the index of the correct player: ")
                # if input_choice.isdigit():
                #     hash_to_name_dict[player_hash] = matching_players.iloc[int(input_choice)]["Player ID"]
                # else:
                #     print("Skipping")

    with open(hash_to_name_file, "w") as f:
        json.dump(hash_to_name_dict, f, indent=2)

    print("")


if __name__ == "__main__":
    main()
