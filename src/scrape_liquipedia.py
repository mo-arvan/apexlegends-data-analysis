import csv
import json
import logging
import os
import time
from argparse import ArgumentParser

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm.auto import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


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


def filter_invalid_url(url):
    if not url.startswith("/apexlegends/"):
        return False

    if "index.php" in url:
        return False

    invalid_starts = ["/apexlegends/File:", "/apexlegends/Category:", "/apexlegends/Template:", "/apexlegends/Help:", ]

    if any([url.startswith(start) for start in invalid_starts]):
        return False

    return True


def get_players_esports_profile():
    """


    :return:
    """
    data_dir = "data/liquidpedia"
    # regions_list = ["North_America", "EMEA", "APAC_North", "APAC_South"]

    url_set = []

    for data_file in os.listdir(data_dir):
        with open(os.path.join(data_dir, data_file), "r") as file:
            players_table = file.read()

        # <span class="mw-headline" id="Participants">Participants</span>
        soup = BeautifulSoup(players_table, 'html.parser')

        all_items = soup.find_all("a")

        all_urls = [p["href"] for p in all_items if "href" in p.attrs]

        all_urls = list(filter(filter_invalid_url, all_urls))

        url_set.extend(all_urls)

    url_set = sorted(list(set(url_set)))

    base_url = "https://liquipedia.net"

    if os.path.exists("data/misc_urls.csv"):
        misc_url_df = pd.read_csv("data/misc_urls.csv")
        misc_url_list = misc_url_df["url"].tolist()
    else:
        misc_url_list = []

    url_set = list(filter(lambda x: x not in misc_url_list, url_set))

    players_info_list = []
    for file in os.listdir("data/players"):
        with open(os.path.join("data/players", file), "r") as f:
            players_info_list.append(json.load(f))

    for url in tqdm(url_set):
        file_name = f"data/players/{url.split('/')[2]}.json"
        player_info_dict = {}
        if not os.path.exists(file_name):
            player_page = request_from_liquipedia(base_url + url)
            player_soup = BeautifulSoup(player_page.text, 'html.parser')
            # info_type = player_soup.find_all(class_="infobox-header-2")
            # header = player_soup.find_all(class_="infobox-header")
            info_box_list = player_soup.find_all(class_="fo-nttax-infobox")
            player_info = next(filter(filter_player_info_box, info_box_list), None)

            if player_info is None:
                misc_url_list.append(url)
                continue

            player_info_dict["Player ID"] = (player_info.find(class_="infobox-header").text.
                                             replace("[e][h]", "").replace("\xa0", "").strip())

            for info in player_info.find_all(class_="infobox-description"):
                key = info.text.replace(":", "").strip()
                value = info.find_next_sibling().text.strip()
                player_info_dict[key] = value

            # if len(list(header[0].children)) < 3:
            #     continue
            with open(file_name, "w") as file:
                json.dump(player_info_dict, file, indent=2)

            players_info_list.append(player_info_dict)

    misc_url_df = pd.DataFrame({"url": misc_url_list})
    misc_url_df.to_csv("data/misc_urls.csv", index=False)
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
