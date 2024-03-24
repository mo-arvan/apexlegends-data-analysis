import json
import os
import re
import time
from argparse import ArgumentParser
import csv

from datetime import datetime

import bs4
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm.auto import tqdm

DGS_API_URL = "https://algs-public-outbound.apexlegendsstatus.com/"
ALS_URL = "https://apexlegendsstatus.com/"


def get_game_data(game_df, init_dict, algs_games_dir):
    # with open(dgs_token_file, "r") as f:
    #     dgs_auth = f.read()

    headers = {
        "Content-Type": "application/json",
        # "DGS-Authorization": dgs_auth
    }
    # API Endpoints with names
    game_endpoints = {
        "init": "qt=init",
        "getFights": "qt=getFights",
        "getReplay": "getReplay",

        # "getRankings": "qt=getRankings&rankingsBy=some_value&statsType=some_value",
        # "getRings": "qt=getRings&stage=some_value",
        # "getAllRings": "qt=getAllRings&stage=some_value",
        # "getStateAtTime": "qt=getStateAtTime&time=some_value",
        # "getHeatmap": "qt=getHeatmap&et=some_value",
        # "getWeaponsUsage": "qt=getWeaponsUsage",
        # "getAbilitiesUsage": "qt=getAbilitiesUsage",
        # "getPlayerEvents": "qt=getPlayerEvents&nucleusHash=",
    }

    players_endpoints = ["getPlayerEvents"]

    algs_data = []

    # downloaded_replay_file = "data/algs_downloaded_replays.csv"
    # replays_dir = algs_games_dir + "/getReplay"
    # downloaded_replays = []
    # if os.path.exists(replays_dir):
    #     downloaded_replays = os.listdir(algs_games_dir + "/getReplay")
    #
    # downloaded_replays = [replay.replace(".json", "") for replay in downloaded_replays]
    # downloaded_replays_df = pd.DataFrame(downloaded_replays, columns=["game_id"])
    #
    # if os.path.exists(downloaded_replay_file):
    #     current_downloaded_replays = pd.read_csv(downloaded_replay_file)
    #     downloaded_replays_df = pd.concat([current_downloaded_replays, downloaded_replays_df], ignore_index=True)
    # downloaded_replays_df = downloaded_replays_df.drop_duplicates(subset=["game_id"])
    # downloaded_replays_df.to_csv(downloaded_replay_file, index=False)

    game_df = game_df[game_df["game_id"] != "#"]
    game_df["game_timestamp"] = game_df["game_id"].apply(
        lambda x: datetime.fromtimestamp(int(init_dict[x]["timestamp"])))
    game_df = game_df.sort_values(by=["game_timestamp"], ascending=False)

    if not os.path.exists(algs_games_dir):
        os.makedirs(algs_games_dir)
    all_api_names = list(game_endpoints.keys()) + list(players_endpoints)
    for api_name in all_api_names:
        if not os.path.exists(f"{algs_games_dir}/{api_name}"):
            os.makedirs(f"{algs_games_dir}/{api_name}")

    # games_sorted_by_timestamp = game_df.sort_values(by=["game_timestamp"], ascending=True)
    results_dict = {}
    for api_name, endpoint in game_endpoints.items():
        api_download_dir = f"{algs_games_dir}/{api_name}"
        downloaded_files = [f.split(".")[0] for f in os.listdir(api_download_dir)]

        missing_games = game_df[~game_df["game_id"].isin(downloaded_files)]
        if len(missing_games) == 0:
            continue
        print(f"Downloading {api_name} data")
        progress_bar = tqdm(total=len(missing_games), desc=f"Downloading {api_name} data")
        for index, row in missing_games.iterrows():
            game_id = row["game_id"]
            game_data_file = f"{algs_games_dir}/{api_name}/{game_id}.json"
            if not os.path.exists(game_data_file):
                if api_name == "getReplay":
                    full_endpoint_url = DGS_API_URL + f"{endpoint}?gameID={row['game_id']}"
                elif api_name == "init" or api_name == "getFights":
                    full_endpoint_url = DGS_API_URL + f"api?gameID={game_id}&{endpoint}"
                else:
                    print(f"Unknown API: {api_name}")
                    continue

                response = requests.get(full_endpoint_url, headers=headers)
                # time for debugging purposes
                if response.status_code == 200:
                    result_json = {}
                    if len(response.text) > 0:
                        result_json = response.json()
                    file_name = f"{algs_games_dir}/{api_name}/{game_id}.json"
                    with open(file_name, "w") as file:
                        json.dump(result_json, file, indent=2)
                time.sleep(1)

            # sleep for 1 second
            progress_bar.update(1)
            # Check the response status and save to file

    for api_name in players_endpoints:

        api_download_dir = f"{algs_games_dir}/{api_name}"
        downloaded_files = [f.split(".")[0] for f in os.listdir(api_download_dir)]
        missing_games = game_df[~game_df["game_id"].isin(downloaded_files)]
        if len(missing_games) == 0:
            continue
        print(f"Downloading {api_name} data")
        progress_bar = tqdm(total=len(missing_games), desc=f"Downloading {api_name} data")
        for index, row in missing_games.iterrows():
            game_id = row["game_id"]
            players_hash_list = [player["nucleusHash"] for player in init_dict[row["game_id"]]["players"]]
            file_name = f"{algs_games_dir}/{api_name}/{row['game_id']}.json"
            all_players_list = []
            for i in range(0, len(players_hash_list), 3):
                player_hash_str = ",".join(players_hash_list[i:i + 3])
                # DGS_API_URL+"api?gameID="+gameId+"&qt=getPlayerEvents&nucleusHash="+e
                full_endpoint_url = (DGS_API_URL +
                                     f"api?gameID={game_id}&qt={api_name}&nucleusHash={player_hash_str}")
                response = requests.get(full_endpoint_url, headers=headers)
                if response.status_code == 200:
                    if len(response.text) > 0:
                        result_json = response.json()
                        all_players_list.append(result_json)
                time.sleep(1)
            with open(file_name, "w") as file:
                json.dump(all_players_list, file, indent=2)
            progress_bar.update(1)

    # with open(f"{algs_games_dir}/init/{row['game_id']}.json", "r") as file:
    #     init_data = json.load(file)
    # players_hash_list = [player["nucleusHash"] for player in init_data["players"]]
    #
    # full_endpoint_list = [DGS_API_URL + f"api?gameID={row['game_id']}&{endpoint}{h}" for h in
    #                       players_hash_list]

    # for name, player_endpoint_api in players_endpoints.items():

    # if response.status_code == 200 and len(response.text) > 0:
    #     result_json = response.json()
    #     with open(game_data_file, "w") as file:
    #         json.dump(result_json, file, indent=2)
    # else:
    #     print(f"Error: {response.status_code} for {row['game_id']}")

    return algs_data


def filter_country_representation_table(table):
    return any(["Country" in tt.text for tt in table.find_all("th")])


def filter_player_info_box(table):
    return any(["Player Information" in i.text for i in table])


def get_players_esports_profile():
    # tournament_columns = ["tournament_full_name", "tournament_name", "tournament_year", "tournament_split",
    #                       "tournament_region", "tournament_url", "tournament_day"]
    #
    # game_columns = tournament_columns + ["game_title", "game_map", "game_timestamp", "game_num", "game_id"]
    #
    # if os.path.exists("data/algs_games.csv"):
    #     current_game_df = pd.read_csv("data/algs_games.csv", na_filter=False)
    # else:
    #     current_game_df = pd.DataFrame(columns=game_columns)

    liquipedia_pages = "https://liquipedia.net/apexlegends/Apex_Legends_Global_Series/2024/Split_1/Pro_League/North_America"

    dgs_algs_page_html = requests.get(liquipedia_pages)

    soup = BeautifulSoup(dgs_algs_page_html.text, 'html.parser')

    all_tables = soup.find_all(class_='wikitable')

    players_table = next(filter(filter_country_representation_table, all_tables), None)

    if players_table is None:
        print("No players table found")

    players_list = players_table.find_all("a")

    url_set = sorted(set([p["href"] for p in players_list if "index.php" not in p["href"]]))

    base_url = "https://liquipedia.net"

    players_into_list = []
    for url in tqdm(url_set):
        player_page = requests.get(base_url + url)
        player_soup = BeautifulSoup(player_page.text, 'html.parser')
        info_type = player_soup.find_all(class_="infobox-header-2")
        header = player_soup.find_all(class_="infobox-header")
        if len(info_type) == 0 or info_type[0].text != 'Player Information':
            continue

        info_box_list = player_soup.find_all(class_="fo-nttax-infobox")

        player_info = next(filter(filter_player_info_box, info_box_list), None)

        player_info_dict = {}

        player_info_dict["Player ID"] = player_info.find(class_="infobox-header").text.replace("[e][h]", "").replace(
            "\xa0", "").strip()

        for info in player_info.find_all(class_="infobox-description"):
            key = info.text.replace(":", "").strip()
            value = info.find_next_sibling().text.strip()
            player_info_dict[key] = value

        if len(list(header[0].children)) < 3:
            continue
        players_into_list.append(player_info_dict)

    players_df = pd.DataFrame(players_into_list)
    players_df.to_csv("data/algs_players.csv", index=False, quoting=csv.QUOTE_ALL)


def main():
    parser = ArgumentParser()
    parser.add_argument("--dgs_token_file", default="data/local/dgs_token.txt", help="DGS Token File")
    parser.add_argument("--algs_game_list_file", default="data/algs_game_list.csv", help="ALGS Game List File")
    parser.add_argument("--algs_games_dir", default="data/algs_games", help="ALGS Games Directory")
    parser.add_argument("--init_data_dir", default="data/algs_games/init")

    args = parser.parse_args()
    dgs_token_file = args.dgs_token_file
    algs_game_list_file = args.algs_game_list_file
    algs_games_dir = args.algs_games_dir
    init_data_dir = args.init_data_dir

    game_df = get_players_esports_profile()
    # game_data = get_game_data(game_df, init_dict, dgs_token_file, algs_games_dir)
    # game_data = get_game_data(game_df)

    # file_name = f"data/algs_data.json"
    # with open(file_name, "w") as file:
    #     json.dump(game_data, file, indent=2)


if __name__ == "__main__":
    main()
