import json
import logging
import os
import pickle
from argparse import ArgumentParser

import pandas as pd
from bs4 import BeautifulSoup

import parallel_helper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"Running {__file__}")


def parse_events_html(players_hash_list, game_events_html):
    soup = BeautifulSoup(game_events_html, "html.parser")
    # <p class="eventsFeedPlayerName universalLeftMargin">
    players = soup.find_all("p", class_="eventsFeedPlayerName universalLeftMargin")
    event_contents = soup.find_all("div", class_="eventsFeed_Content")
    assert len(players) == len(event_contents)
    assert len(players) == len(players_hash_list)

    events_columns = [
        "player_hash",
        "event_id", "event_type", "event_timestamp", "target", "x_position", "y_position",
        "event_time",
        "event_text"]

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
            events_text = (child.find('div', class_='col-10').find('p', class_='eventsFeed_text').text.
                           replace(u'\xa0', u' '))
            events.append(
                [player_hash, event_id, event_type, game_timestamp, target, x_position, y_position, event_time,
                 events_text])
        events_df = pd.DataFrame(events, columns=events_columns)

        player_events.append(events_df)

    return player_events


def parse_events(game_data_tuple):
    game_id, game_events = game_data_tuple
    game_events_merged = {}
    game_events_merged["lastEventId"] = {k: v for g in game_events for k, v in g["lastEventId"].items()}
    game_events_merged["eventsLocations"] = {k: v for g in game_events for k, v in g["eventsLocations"].items()}

    game_events_merged["events"] = [player_event for g in game_events for player_event in
                                    parse_events_html(list(g["lastEventId"].keys()), g["html"])]

    row = (game_id,
           game_events_merged["events"],
           game_events_merged["lastEventId"],
           game_events_merged["eventsLocations"])

    return row


def read_event(base_dir_file_name_tuple):
    base_dir, file_name = base_dir_file_name_tuple
    file_path = os.path.join(base_dir, file_name)
    with open(file_path, "r") as f:
        file_content = json.load(f)

    base_file_name = file_name[:-5]

    return base_file_name, file_content


def read_events(events_data_dir):
    for file_name in os.listdir(events_data_dir):
        with open(os.path.join(events_data_dir, file_name), "r") as f:
            yield file_name[:-5], json.load(f)


def main():
    aug_parser = ArgumentParser()
    aug_parser.add_argument("--events_data_dir", default="data/algs_games/getPlayerEvents")
    aug_parser.add_argument("--init_data_dir", default="data/algs_games/init")
    aug_parser.add_argument("--debug", action="store_true", default=True)

    args = aug_parser.parse_args()
    events_data_dir = args.events_data_dir

    debug = args.debug

    init_dict = {}

    # for file_name in os.listdir(events_data_dir):
    #     with open(os.path.join(events_data_dir, file_name), "r") as f:
    #         game_events_dict[file_name[:-5]] = json.load(f)
    #     if len(game_events_dict) > 10:
    #         break
    #
    event_file_path_list = [(events_data_dir, file_name) for file_name in os.listdir(events_data_dir)]
    events_total = len(event_file_path_list)
    logger.info(f"Building events generator")
    # game_events_dict = parallel_helper.run_in_parallel_io_bound(read_event,
    #                                                             event_file_path_list,
    #                                                             max_workers=16)

    game_events_list = read_events(events_data_dir)

    # init_dict = {}
    # for file_name in os.listdir(args.init_data_dir):
    #     with open(os.path.join(args.init_data_dir, file_name), "r") as f:
    #         init_dict[file_name[:-5]] = json.load(f)
    #
    # init_df = pd.DataFrame(init_dict.values())
    logger.info(f"Processing {events_total} games")
    events_list = parallel_helper.run_in_parallel_cpu_bound(parse_events,
                                                            game_events_list,
                                                            total=events_total,
                                                            max_workers=12)
    logger.info(f"Processed {len(events_list)} games")
    logger.info(f"Saving events to data/events.pkl")
    with open("data/events.pkl", "wb") as f:
        pickle.dump(events_list, f)


if __name__ == "__main__":
    main()
