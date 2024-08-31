import json
import os

import pandas as pd


def get_game_init(init_data_dir="data/algs_games/init", file_list=None):
    init_dict = {}
    for file_name in os.listdir(init_data_dir):
        base_file_name = os.path.basename(file_name).split(".")[0]
        if file_list is not None and base_file_name not in file_list:
            continue
        with open(os.path.join(init_data_dir, file_name), "r") as f:
            json_data = json.load(f)
            if isinstance(json_data, dict) and len(json_data) > 0:
                init_dict[file_name[:-5]] = json_data
    return init_dict


def get_esports_list(esport_hash_file="data/esports_name_to_hash.json"):
    esports_list = []
    if os.path.exists(esport_hash_file):
        with open(esport_hash_file, "r") as f:
            esports_list = json.load(f)
    return esports_list


def save_esports_list(esports_list, esport_hash_file="data/esports_name_to_hash.json"):
    esports_list = sorted(esports_list,
                          key=lambda x: str(x["esport_name"] if x["esport_name"] is not None else "ZZ"),
                          reverse=False)

    with open(esport_hash_file, "w") as f:
        json.dump(esports_list, f, indent=2)


def get_liquipedia_players_df(file_path="data/algs_players.csv"):
    players_df = pd.read_csv(file_path)
    return players_df


def get_hash_to_player_info_df():
    liquipedia_players_df = get_liquipedia_players_df()
    players_df = liquipedia_players_df[["Player ID", "Input"]].copy()
    esports_list = get_esports_list()

    player_id_to_hash = [(p["esport_name"].lower(), hash)
                         for p in esports_list
                         for hash in p["hash"] if isinstance(p["esport_name"], str)]

    player_id_to_hash_df = pd.DataFrame(player_id_to_hash, columns=["player_name", "hash"])

    players_df["player_name"] = players_df["Player ID"].apply(lambda x: x.lower())

    hash_to_input_df = player_id_to_hash_df.merge(players_df, on="player_name", how="left")

    hash_to_input_df.rename(columns={"hash": "player_hash",
                                     "Input": "player_input",
                                     "Player ID": "player_id",
                                     }, inplace=True)
    hash_to_input_df.drop(columns=["player_name"], inplace=True)
    # hash_to_input_dict = hash_to_input.set_index("hash")["Input"].to_dict()
    # match = next((e for e in player_id_to_hash if desired_hash in e[1]), None)

    return hash_to_input_df


def get_algs_games():
    # logger.debug("Loading algs games data")
    algs_games_df = pd.read_csv("data/algs_game_list.csv",
                                # ignore NA values
                                na_filter=False,
                                )

    return algs_games_df