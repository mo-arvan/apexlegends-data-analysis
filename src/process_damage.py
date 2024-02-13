import json
import os
import re
import time
from argparse import ArgumentParser
import csv

import bs4
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

DGS_API_URL = "https://algs-public-outbound.apexlegendsstatus.com/"
ALS_URL = "https://apexlegendsstatus.com/"


def parse_events_html(events_html):
    soup = BeautifulSoup(events_html, "html.parser")
    # <p class="eventsFeedPlayerName universalLeftMargin">
    players = soup.find_all("p", class_="eventsFeedPlayerName universalLeftMargin")
    event_contents = soup.find_all("div", class_="eventsFeed_Content")
    assert len(players) == len(event_contents)

    events_columns = ["event_id", "event_type", "game_timestamp", "target", "x_position", "y_position", "pre_game_text",
                      "player_connected_text"]

    player_events = []

    for player, event_content in zip(players, event_contents):
        container = event_content.find("div", class_="eventsFeedContainer")
        events = []
        for child in container.children:
            event_id = int(child['data-eventid'])
            event_type = child['data-eventtype']
            game_timestamp = child['data-gametimestamp']
            target = child['data-target']
            x_position = int(child['data-x'])
            y_position = int(child['data-y'])
            pre_game_text = child.find('div', class_='col-2').find('p', class_='eventsFeed_text').text
            player_connected_text = child.find('div', class_='col-10').find('p',class_='eventsFeed_text').text
            events.append([event_id, event_type, game_timestamp, target, x_position, y_position, pre_game_text,
                           player_connected_text])
        player_events.append(events)

    return player_events


def main():
    aug_parser = ArgumentParser()
    aug_parser.add_argument("--events_data_dir", default="data/algs_games/getPlayerEvents")
    aug_parser.add_argument("--init_data_dir", default="data/algs_games/init")

    args = aug_parser.parse_args()
    events_data_dir = args.events_data_dir

    game_events_dict = {}
    init_dict = {}

    for file_name in os.listdir(events_data_dir):
        with open(os.path.join(events_data_dir, file_name), "r") as f:
            game_events_dict[file_name[:-5]] = json.load(f)

    for file_name in os.listdir(args.init_data_dir):
        with open(os.path.join(args.init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)

    init_df = pd.DataFrame(init_dict.values())

    for game_id, game_events in game_events_dict.items():
        html = game_events.pop("html")
        game_events["events"] = parse_events_html(html)

    players_in_games = {k: v["players"] for k, v in init_dict.items()}

    weapons_df.to_csv("data/weapons_data.csv", index=False)


if __name__ == "__main__":
    main()
