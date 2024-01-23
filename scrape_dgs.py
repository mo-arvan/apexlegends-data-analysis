import json
import os
import re
import time
from argparse import ArgumentParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

DGS_API_URL = "https://algs-public-outbound.apexlegendsstatus.com/"
ALS_URL = "https://apexlegendsstatus.com/"


def get_game_data(game_df, dgs_token_file, algs_games_dir):
    # with open(dgs_token_file, "r") as f:
    #     dgs_auth = f.read()

    headers = {
        "Content-Type": "application/json",
        # "DGS-Authorization": dgs_auth
    }
    # API Endpoints with names
    endpoints = {
        "init": "qt=init",
        "getFights": "qt=getFights",
        # "getRankings": "qt=getRankings&rankingsBy=some_value&statsType=some_value",
        # "getRings": "qt=getRings&stage=some_value",
        # "getAllRings": "qt=getAllRings&stage=some_value",
        # "getStateAtTime": "qt=getStateAtTime&time=some_value",
        # "getHeatmap": "qt=getHeatmap&et=some_value",
        # "getWeaponsUsage": "qt=getWeaponsUsage",
        # "getAbilitiesUsage": "qt=getAbilitiesUsage",
        # "getReplay": "getReplay",
        # "getInventory": "qt=getInventory&nucleusHash=some_value&atGameTimestamp=9999999",
        # "getPlayerEvents": "qt=getPlayerEvents&nucleusHash=some_value",

    }
    algs_data = []

    if not os.path.exists(algs_games_dir):
        os.makedirs(algs_games_dir)

    downloaded_replay_file = "data/algs_downloaded_replays.csv"
    replays_dir = algs_games_dir + "/getReplay"
    downloaded_replays = []
    if os.path.exists(replays_dir):
        downloaded_replays = os.listdir(algs_games_dir + "/getReplay")

    downloaded_replays = [replay.replace(".json", "") for replay in downloaded_replays]
    downloaded_replays_df = pd.DataFrame(downloaded_replays, columns=["game_id"])

    if os.path.exists(downloaded_replay_file):
        current_downloaded_replays = pd.read_csv(downloaded_replay_file)
        downloaded_replays_df = pd.concat([current_downloaded_replays, downloaded_replays_df], ignore_index=True)
    downloaded_replays_df = downloaded_replays_df.drop_duplicates(subset=["game_id"])
    downloaded_replays_df.to_csv(downloaded_replay_file, index=False)

    game_df = game_df[game_df["game_id"] != "#"]

    total_items = len(game_df) * len(endpoints)

    progress_bar = tqdm(total=total_items)
    for api_name, endpoint in endpoints.items():

        if not os.path.exists(f"{algs_games_dir}/{api_name}"):
            os.makedirs(f"{algs_games_dir}/{api_name}")

        current_api_data = []
        for index, row in game_df.iterrows():

            game_data_file = f"{algs_games_dir}/{api_name}/{row['game_id']}.json"

            if not os.path.exists(game_data_file):
                if api_name == "getReplay":
                    if row["game_id"] in downloaded_replays:
                        continue
                    full_endpoint = DGS_API_URL + f"{endpoint}?gameID={row['game_id']}"
                else:
                    full_endpoint = DGS_API_URL + f"api?gameID={row['game_id']}&{endpoint}"

                response = requests.get(full_endpoint, headers=headers)

                if response.status_code == 200 and len(response.text) > 0:
                    result_json = response.json()
                    with open(game_data_file, "w") as file:
                        json.dump(result_json, file, indent=2)
                else:
                    print(f"Error: {response.status_code} for {row['game_id']}")
                time.sleep(1)
            # sleep for 1 second
            progress_bar.update(1)
            # Check the response status and save to file

    return algs_data


def get_game_list(algs_game_list_file):
    tournament_columns = ["tournament_full_name", "tournament_name", "tournament_year", "tournament_split",
                          "tournament_region", "tournament_url"]

    game_columns = tournament_columns + ["game_title", "game_map", "game_day", "game_num", "game_id"]

    if os.path.exists("data/algs_games.csv"):
        current_game_df = pd.read_csv("data/algs_games.csv")
    else:
        current_game_df = pd.DataFrame(columns=game_columns)

    dgs_algs_page_url = "https://apexlegendsstatus.com/algs/"

    dgs_algs_page_html = requests.get(dgs_algs_page_url)

    soup = BeautifulSoup(dgs_algs_page_html.text, 'html.parser')

    # all algsRegionElem elements
    algs_region_elems = soup.find_all(class_='algsRegionElem')

    # example of the pattern usage: 'ALGS Playoffs - Year 3, Split 2'
    tournament_pattern = r"(?P<name>[^-]*) - Year (?P<year>\d+), Split (?P<split_num>\d+)"

    tournament_list = []
    for tournament in algs_region_elems:
        tournament_full_name = tournament.find(class_='listText').text.strip()
        tournament_url = tournament["href"]
        tournament_match = re.match(tournament_pattern, tournament_full_name)
        if tournament_match:
            tournament_name = tournament_match.group("name").strip()
            tournament_year = tournament_match.group("year").strip()
            tournament_split = tournament_match.group("split_num").strip()
            tournament_region = tournament_url.split("/")[-2]

            if pd.isna(tournament_region):
                print(f"Error: {tournament_full_name}")

            r = (tournament_full_name, tournament_name, tournament_year,
                 tournament_split, tournament_region, tournament_url)
            tournament_list.append(r)
        else:
            print(f"Error: {tournament_full_name}")

    tournament_df = pd.DataFrame(tournament_list, columns=tournament_columns)

    game_list = []
    for index, row in tournament_df.iterrows():
        tournament_full_name = row["tournament_full_name"]
        tournament_name = row["tournament_name"]
        tournament_year = row["tournament_year"]
        tournament_split = row["tournament_split"]
        tournament_region = row["tournament_region"]
        tournament_url = row["tournament_url"]

        if not current_game_df.empty:
            if tournament_url in current_game_df["tournament_url"].values:
                continue

        print(f"Getting data for {tournament_name} {tournament_year} {tournament_split} {tournament_region}")
        tournament_page_url = ALS_URL + tournament_url

        tournament_page_html = requests.get(tournament_page_url)
        soup = BeautifulSoup(tournament_page_html.text, 'html.parser')

        # all algsGameElem elements
        algs_game_elems = soup.find_all(class_='algsGameElem')

        # 'Day 4 - Game #7'
        game_pattern = r"Day (?P<day_num>\d+) - Game #(?P<game_num>\d+)"

        for elem in algs_game_elems:
            game_title = elem.find('p', class_='gameTitle').text.strip()
            game_map = elem.find('p', class_='gameMap').text.strip()
            game_url = elem['href'].replace("/algs/game/", "")

            game_match = re.match(game_pattern, game_title)
            if game_match:
                game_day = game_match.group("day_num").strip()
                game_num = game_match.group("game_num").strip()

                r = (tournament_full_name, tournament_name, tournament_year, tournament_split, tournament_region,
                     tournament_url,
                     game_title, game_map, game_day, game_num, game_url)
                game_list.append(r)

        # algsGameElem

    game_df = pd.DataFrame(game_list, columns=game_columns)

    if not current_game_df.empty:
        game_df = pd.concat([current_game_df, game_df], ignore_index=True)

    game_df = game_df.sort_values(
        by=["tournament_year", "tournament_split", "tournament_region", "game_day", "game_num"])

    game_df.to_csv("data/algs_games.csv", index=False)

    return game_df


def main():
    parser = ArgumentParser()
    parser.add_argument("--dgs_token_file", default="data/local/dgs_token.txt", help="DGS Token File")
    parser.add_argument("--algs_game_list_file", default="data/algs_game_list.csv", help="ALGS Game List File")
    parser.add_argument("--algs_games_dir", default="data/algs_games", help="ALGS Games Directory")

    args = parser.parse_args()
    dgs_token_file = args.dgs_token_file
    algs_game_list_file = args.algs_game_list_file
    algs_games_dir = args.algs_games_dir
    game_df = get_game_list(algs_game_list_file)
    game_data = get_game_data(game_df, dgs_token_file, algs_games_dir)

    # game_data = get_game_data(game_df)

    # file_name = f"data/algs_data.json"
    # with open(file_name, "w") as file:
    #     json.dump(game_data, file, indent=2)


if __name__ == "__main__":
    main()
