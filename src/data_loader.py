import json
import os

import pandas as pd


def get_game_init(init_data_dir="data/algs_games/init"):
    init_dict = {}
    for file_name in os.listdir(init_data_dir):
        with open(os.path.join(init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)
    return init_dict


def get_esports_list(esport_hash_file="data/esports_name_to_hash.json"):
    esports_list = []
    if os.path.exists(esport_hash_file):
        with open(esport_hash_file, "r") as f:
            esports_list = json.load(f)
    return esports_list


def save_esports_list(esports_list, esport_hash_file="data/esports_name_to_hash.json"):
    esports_list = sorted(esports_list, key=lambda x: str(x["esport_name"] if x["esport_name"] is not None else "ZZ"),
                          reverse=False)

    with open(esport_hash_file, "w") as f:
        json.dump(esports_list, f, indent=2)


def get_liquipedia_players_df(file_path="data/algs_players.csv"):
    players_df = pd.read_csv(file_path)
    return players_df
