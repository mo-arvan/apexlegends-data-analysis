import json
import logging
import os
import re
import time
from argparse import ArgumentParser

import bs4
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm.auto import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

DGS_API_URL = "https://algs-public-outbound.apexlegendsstatus.com/"
ALS_URL = "https://apexlegendsstatus.com/"


def scrape_games_data(game_df, init_dict, algs_games_dir):
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

    players_endpoints = [
        # "getPlayerEvents"
    ]

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

    # game_df = game_df.sort_values(by=["game_timestamp"], ascending=False)

    if not os.path.exists(algs_games_dir):
        os.makedirs(algs_games_dir)

    all_api_names = list(game_endpoints.keys()) + list(players_endpoints)
    for api_name in all_api_names:
        if not os.path.exists(f"{algs_games_dir}/{api_name}"):
            os.makedirs(f"{algs_games_dir}/{api_name}")

    for api_name, endpoint in game_endpoints.items():
        api_download_dir = f"{algs_games_dir}/{api_name}"
        downloaded_files = [f.split(".")[0] for f in os.listdir(api_download_dir)]
        logger.info(f"Downloading {api_name} data")

        missing_games = game_df[~game_df["game_id"].isin(downloaded_files)]
        if len(missing_games) == 0:
            logger.info(f"No missing games for {api_name}")
            continue

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
                    logger.info(f"Unknown API: {api_name}")
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
        logger.info(f"Downloading {api_name} data")
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
    #     logger.info(f"Error: {response.status_code} for {row['game_id']}")

    return algs_data


def scrape_tournaments():
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

            tournament_row = (tournament_full_name, tournament_name, tournament_year, tournament_split,
                              tournament_region, tournament_url)

            tournament_list.append(tournament_row)  # type: ignore
        else:
            logger.info(f"Error: {tournament_full_name}")
    tournament_columns = ["tournament_full_name", "tournament_name", "tournament_year", "tournament_split",
                          "tournament_region", "tournament_url"]
    tournament_df = pd.DataFrame(tournament_list, columns=tournament_columns)

    return tournament_df


def scrape_games(tournament_df, current_game_df):
    tournament_columns = tournament_df.columns.tolist()
    game_columns = tournament_columns + ["tournament_day",
                                         "game_title",
                                         "game_map",
                                         "game_timestamp",
                                         "game_num",
                                         "game_id"]

    game_list = []
    for index, row in tournament_df.iterrows():

        tournament_full_name = row["tournament_full_name"]
        tournament_name = row["tournament_name"]
        tournament_year = row["tournament_year"]
        tournament_split = row["tournament_split"]
        tournament_region = row["tournament_region"]
        tournament_url = row["tournament_url"]

        if tournament_region == "" or pd.isna(tournament_region):
            logger.info(f"Invalid region: {tournament_full_name} - {tournament_url}")

        tournament_page_url = ALS_URL + tournament_url

        current_tournament_df = current_game_df[current_game_df["tournament_url"] == tournament_url]

        tournament_page_html = requests.get(tournament_page_url)

        if tournament_page_html.status_code != 200 or "No games found for this region" in tournament_page_html.text:
            logger.error(f"Error: {tournament_full_name} - {tournament_url}")
            continue

        soup = BeautifulSoup(tournament_page_html.text, 'html.parser')

        # algsDaysNav
        algs_days_nav = soup.find(class_='algsDaysNav')
        for day in algs_days_nav.children:
            # make sure it is a tag
            if isinstance(day, bs4.Tag) and "Overview" not in day.text and "All regions stats" not in day.text:
                tournament_day = day.text
                day_href = day["href"]

                games_matching = current_tournament_df[current_tournament_df["tournament_day"] == tournament_day]

                if not games_matching.empty:
                    continue
                day_page_url = ALS_URL + day_href
                day_page_html = requests.get(day_page_url)
                if day_page_html.status_code != 200:
                    logger.info(f"Error: {tournament_full_name} - {tournament_url} - {day_href}")
                    continue
                # all algsGameElem elements
                algs_game_elems = BeautifulSoup(day_page_html.text, 'html.parser').find_all(
                    class_='algsGameElem')

                # 'Game #7'
                game_pattern = r"Game #(?P<game_num>\d+)"

                # Day (?P<day_num>\d+) -

                for elem in algs_game_elems:
                    game_title = elem.find('p', class_='gameTitle')
                    game_map = elem.find('p', class_='gameMap')
                    if game_title.text == "All games":
                        continue
                    if game_title is None or game_map is None:
                        logger.info(f"Error: {tournament_full_name} - {tournament_url} ")
                        continue
                    game_title = game_title.text.strip()
                    game_map = game_map.text.strip()
                    game_id = elem['href'].replace("/algs/game/", "")
                    game_timestamp = elem.find("p", class_="settings-label")["data-timestamp"]

                    game_match = re.match(game_pattern, game_title)
                    if game_match:
                        game_num = game_match.group("game_num").strip()

                        r = (
                            tournament_full_name, tournament_name, tournament_year, tournament_split,
                            tournament_region, tournament_url, tournament_day,
                            game_title, game_map, game_timestamp, game_num, game_id)
                        game_list.append(r)

    game_df = pd.DataFrame(game_list, columns=game_columns)

    old_size = len(current_game_df)

    if not current_game_df.empty:
        game_df = pd.concat([current_game_df, game_df], ignore_index=True)

    game_df = game_df.sort_values(
        by=["tournament_year", "tournament_split", "tournament_region", "game_timestamp", "game_num"])

    game_df.drop_duplicates(["game_id"], inplace=True)

    game_df = game_df[game_df["game_id"] != "#"]

    new_size = len(game_df)

    if new_size > old_size:
        logger.info(f"Founds {new_size - old_size} new games")

    logger.info(f"Total games: {len(game_df)}")

    return game_df


def main():
    parser = ArgumentParser()
    parser.add_argument("--algs_game_list_file", default="data/algs_game_list.parquet", help="ALGS Game List File")
    parser.add_argument("--algs_games_dir", default="data/algs_games", help="ALGS Games Directory")
    parser.add_argument("--init_data_dir", default="data/algs_games/init")
    parser.add_argument("--init_data", default="data/init_dict.pbz2")

    args = parser.parse_args()

    algs_game_list_file = args.algs_game_list_file
    algs_games_dir = args.algs_games_dir
    init_data_dir = args.init_data_dir
    init_data = args.init_data

    if os.path.exists(algs_game_list_file):
        current_game_df = pd.read_parquet(algs_game_list_file)
    else:
        current_game_df = None

    tournament_df = scrape_tournaments()

    game_df = scrape_games(tournament_df, current_game_df)

    game_df.to_parquet(algs_game_list_file, index=False, compression="gzip")

    games_init_dict = {}
    for game_init in os.listdir(init_data_dir):
        game_init_file_path = f"{algs_games_dir}/init/{game_init}"
        with open(game_init_file_path, "r") as file:
            games_init_dict[game_init.replace(".json", "")] = json.load(file)

    scrape_games_data(game_df, games_init_dict, algs_games_dir)



if __name__ == "__main__":
    main()
