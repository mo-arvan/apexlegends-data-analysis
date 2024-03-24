import json
import os
import re
import time
from argparse import ArgumentParser
import csv
import pickle
import bs4
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")

DGS_API_URL = "https://algs-public-outbound.apexlegendsstatus.com/"
ALS_URL = "https://apexlegendsstatus.com/"


def parse_events_html(players_hash_list, game_events_html):
    soup = BeautifulSoup(game_events_html, "html.parser")
    # <p class="eventsFeedPlayerName universalLeftMargin">
    players = soup.find_all("p", class_="eventsFeedPlayerName universalLeftMargin")
    event_contents = soup.find_all("div", class_="eventsFeed_Content")
    assert len(players) == len(event_contents)
    assert len(players) == len(players_hash_list)

    events_columns = [
        "player_hash",
        "event_id", "event_type", "game_timestamp", "target", "x_position", "y_position", "pre_game_text",
        "player_connected_text"]

    player_events = []

    for player, player_hash, event_content in zip(players, players_hash_list, event_contents):
        container = event_content.find("div", class_="eventsFeedContainer")
        events = []
        for child in container.children:
            event_id = int(child['data-eventid'])
            event_type = child['data-eventtype']
            game_timestamp = int(child['data-gametimestamp'])
            target = child['data-target']
            x_position = int(child['data-x'])
            y_position = int(child['data-y'])
            event_time = child.find('div', class_='col-2').find('p', class_='eventsFeed_text').text
            events_text = child.find('div', class_='col-10').find('p', class_='eventsFeed_text').text
            events.append(
                [player_hash, event_id, event_type, game_timestamp, target, x_position, y_position, event_time,
                 events_text])
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
        if len(game_events_dict) > 10:
            break

    for file_name in os.listdir(args.init_data_dir):
        with open(os.path.join(args.init_data_dir, file_name), "r") as f:
            init_dict[file_name[:-5]] = json.load(f)

    init_df = pd.DataFrame(init_dict.values())

    events_list = []
    for game_id, game_events in game_events_dict.items():
        game_events_merged = {}
        game_events_merged["lastEventId"] = {k: v for g in game_events for k, v in g["lastEventId"].items()}
        game_events_merged["eventsLocations"] = {k: v for g in game_events for k, v in g["eventsLocations"].items()}

        game_events_merged["events"] = [player_event for g in game_events for player_event in
                                        parse_events_html(list(g["lastEventId"].keys()), g["html"])]

        row = (
            game_id, game_events_merged["events"], game_events_merged["lastEventId"],
            game_events_merged["eventsLocations"])
        events_list.append(row)

    # dump the data as pickle

    with open("data/events.pkl", "wb") as f:
        pickle.dump(events_list, f)


if __name__ == "__main__":
    main()
