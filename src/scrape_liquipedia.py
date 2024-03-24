import csv
import time
from argparse import ArgumentParser
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm.auto import tqdm

import json


def filter_country_representation_table(table):
    return any(["Country" in tt.text for tt in table.find_all("th")])


def filter_player_info_box(table):
    return any(["Player Information" in i.text for i in table])


def request_from_liquipedia(url):
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    # "apex-legends-data-analysis"}
    response = requests.get(url, headers=header)
    time.sleep(2)
    return response


def get_players_esports_profile():
    latest_tournament_base_url = "https://liquipedia.net/apexlegends/Apex_Legends_Global_Series/2024/Split_1/Pro_League"
    regions_list = ["North_America", "EMEA", "APAC_North", "APAC_South"]

    players_info_list = []

    for region in regions_list:
        region_url = latest_tournament_base_url + "/" + region

        tournament_page = request_from_liquipedia(region_url)

        soup = BeautifulSoup(tournament_page.text, 'html.parser')

        all_tables = soup.find_all(class_='wikitable')

        players_table = next(filter(filter_country_representation_table, all_tables), None)

        if players_table is None:
            print("No players table found")

        players_list = players_table.find_all("a")

        url_set = sorted(set([p["href"] for p in players_list if "index.php" not in p["href"]]))

        base_url = "https://liquipedia.net"

        for url in tqdm(url_set):
            file_name = f"data/players/{url.split('/')[2]}.json"
            player_info_dict = {}
            if os.path.exists(file_name):
                with open(file_name, "r") as file:
                    player_info_dict = json.load(file)
            else:
                player_page = request_from_liquipedia(base_url + url)
                player_soup = BeautifulSoup(player_page.text, 'html.parser')
                info_type = player_soup.find_all(class_="infobox-header-2")
                header = player_soup.find_all(class_="infobox-header")
                if len(info_type) == 0 or info_type[0].text != 'Player Information':
                    continue

                info_box_list = player_soup.find_all(class_="fo-nttax-infobox")

                player_info = next(filter(filter_player_info_box, info_box_list), None)

                player_info_dict["Player ID"] = (player_info.find(class_="infobox-header").text.
                                                 replace("[e][h]", "").replace("\xa0", "").strip())

                for info in player_info.find_all(class_="infobox-description"):
                    key = info.text.replace(":", "").strip()
                    value = info.find_next_sibling().text.strip()
                    player_info_dict[key] = value

                if len(list(header[0].children)) < 3:
                    continue
                with open(file_name, "w") as file:
                    json.dump(player_info_dict, file, indent=2)

            players_info_list.append(player_info_dict)


    players_df = pd.DataFrame(players_info_list)
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
