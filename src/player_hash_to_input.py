import json
import os
from argparse import ArgumentParser
from difflib import SequenceMatcher

import pandas as pd

import data_loader


def get_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def normalize_name(x):
    return x.lower().replace(" ", "").replace("_", "")


def get_player_hash_list(init_dict):
    player_name_hash_to_match = [(pp["playerName"], pp["nucleusHash"][:32])
                                 for p in init_dict.values()
                                 for pp in p["players"]]

    player_name_hash_to_match = list(set(player_name_hash_to_match))

    return player_name_hash_to_match


def match_hash_to_player(player_name_hash_to_match, esports_list):
    # players_df["player_name_normalized"] = players_df["Player ID"].apply(normalize_name)

    zero = ['ebb81458a29f44e9c2c30c75008e3223', '34a24927b4ed0332a30c1f5c854c00b6',
            'a70600ba17c5fb8a9222a4856165d6ff']

    for i, row in enumerate(esports_list):
        if not isinstance(row["hash"], list):
            esports_list[i]["hash"] = row["hash"].tolist()
        if not isinstance(row["hash"], list):
            esports_list[i]["hash"] = row["hash"].tolist()

    no_match_list = []

    for player_name, player_hash in player_name_hash_to_match:
        if player_name == "Osivien" and player_hash == "cb3a766e957858a490eb8408245b91fd":
            continue

        esport_list_match = next(filter(lambda x: player_hash in x[1]["hash"], enumerate(esports_list)), None)

        if esport_list_match is not None:
            match_index, matching_player = esport_list_match
            # if current name is not in the list, add it
            if player_name not in matching_player["alias_list"]:
                esports_list[match_index]["alias_list"].append(player_name)
        else:
            esports_list.append((None, [player_hash], [player_name]))

    for e in esports_list:
        e["alias_list"] = sorted(list(set(e["alias_list"])))


def get_missing_players(players_df, esports_list):
    missing_players = []
    name_list = [r["esport_name"] for r in esports_list]
    for i, row in players_df.iterrows():
        player_name = row["Player ID"]
        # check if it exists in the esports df, if not, add it

        if player_name not in name_list:
            missing_players.append({
                "esport_name": player_name,
                "hash": [],
                "alias_list": []
            })

    return missing_players


def approximate_match(esports_list):
    matching_list = []

    for e in esports_list:
        if e["esport_name"] is None:
            name_variations = []
            for n in e["alias_list"]:
                name_variations.extend(n.split(" "))
                name_variations.extend(n.split("_"))

                for i in range(len(n)):
                    if len(n[i:]) > 3:
                        name_variations.append(n[i:])
            name_variations = list(set(name_variations))

            matching_players = list(
                filter(lambda x: len(set([x["esport_name"]] + x["alias_list"]).intersection(name_variations)),
                       esports_list))
            if len(matching_players) > 1:
                matching_list.append((e, matching_players))

    matching_list = sorted(matching_list, key=lambda x: len(x[1][0]), reverse=True)

    for e, matching_players in matching_list:
        print(f"Matching {e['alias_list']}")
        for mp in matching_players:
            print(f"    {mp['alias_list']}")


def check_for_duplicate_hashes(esports_list):
    hash_to_player_dict = {}
    for i, row in enumerate(esports_list):
        for h in row["hash"]:
            if h in hash_to_player_dict:
                print(f"Hash {h} is already in the list")
            else:
                hash_to_player_dict[h] = row["esport_name"]

    # return hash_to_player_dict


def main():
    init_dict = data_loader.get_game_init()
    players_df = data_loader.get_liquipedia_players_df()
    esports_list = data_loader.get_esports_list()

    esports_list.extend(get_missing_players(players_df, esports_list))

    player_name_hash_to_match = get_player_hash_list(init_dict)

    match_hash_to_player(player_name_hash_to_match, esports_list)

    approximate_match(esports_list)

    check_for_duplicate_hashes(esports_list)

    data_loader.save_esports_list(esports_list)


if __name__ == "__main__":
    main()

    # player_to_hash_file = "data/player_to_hash.json"
    #
    # if os.path.exists(player_to_hash_file):
    #     with open(player_to_hash_file, "r") as f:
    #         player_to_hash_dict = json.load(f)
    #
    # player_to_hash_df = pd.DataFrame(player_to_hash_dict.items(), columns=["hash", "player_name"])
    # player_to_hash_df = player_to_hash_df.groupby("player_name").agg({"hash": lambda x: list(x)}).reset_index()
    # player_to_hash_df = player_to_hash_df.rename(columns={
    #     "player_name": "esport_name"
    # })
    # player_to_hash_df["alias_list"] = [[] for _ in range(len(player_to_hash_df))]

    # hash_to_player_dict = dict(sorted(hash_to_player_dict.items(), key=lambda x: x[1]))
