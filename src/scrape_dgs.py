import csv
import json
import logging
import os
import re
import time
from argparse import ArgumentParser
from datetime import datetime, timezone

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


def _get_with_retry(url, headers, attempts=5, timeout=(5, 60)):
    """GET with exponential-backoff retry on transient network errors.

    Returns the Response on the first successful attempt, or None after
    all attempts fail. Does not retry on non-200 status; only on
    ConnectionError / ReadTimeout. Caller is responsible for inspecting
    .status_code and parsing the body.
    """
    for attempt in range(attempts):
        try:
            return requests.get(url, headers=headers, timeout=timeout)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError) as e:
            wait = 2 ** attempt  # 1, 2, 4, 8, 16s
            logger.warning(
                f"transient {type(e).__name__} on {url} "
                f"(attempt {attempt + 1}/{attempts}); retrying in {wait}s"
            )
            time.sleep(wait)
    logger.error(f"giving up on {url} after {attempts} retries")
    return None


def scrape_game_endpoints(game_df, algs_games_dir, sleep_duration=2):
    headers = {
        "Content-Type": "application/json",
        # "DGS-Authorization": dgs_auth
    }
    # API Endpoints with names
    game_endpoints = {
        "init": "qt=init",
        # "getFights": "qt=getFights",
        # "getReplay": "getReplay",

        # "getRankings": "qt=getRankings&rankingsBy=some_value&statsType=some_value",
        # "getRings": "qt=getRings&stage=some_value",
        # "getAllRings": "qt=getAllRings&stage=some_value",
        # "getStateAtTime": "qt=getStateAtTime&time=some_value",
        # "getHeatmap": "qt=getHeatmap&et=some_value",
        # "getWeaponsUsage": "qt=getWeaponsUsage",
        # "getAbilitiesUsage": "qt=getAbilitiesUsage",
        # "getPlayerEvents": "qt=getPlayerEvents&nucleusHash=",
    }

    algs_data = []

    if not os.path.exists(algs_games_dir):
        os.makedirs(algs_games_dir)

    all_api_names = list(game_endpoints.keys())
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

                response = _get_with_retry(full_endpoint_url, headers)
                if response is None:
                    logger.error(f"skipping {api_name} for {game_id}; init JSON not written")
                    progress_bar.update(1)
                    continue
                logger.debug(f"GET {full_endpoint_url} -> {response.status_code}")
                if response.status_code == 200:
                    result_json = {}
                    if len(response.text) > 0:
                        try:
                            result_json = response.json()
                        except ValueError as e:
                            logger.warning(
                                f"JSONDecodeError on {full_endpoint_url}: {e}; "
                                f"first 200 chars of body: {response.text[:200]!r}"
                            )
                            progress_bar.update(1)
                            continue
                    file_name = f"{algs_games_dir}/{api_name}/{game_id}.json"
                    with open(file_name, "w") as file:
                        json.dump(result_json, file, indent=2)
                else:
                    logger.warning(f"Non-200 for {full_endpoint_url}: {response.status_code} {response.text[:200]}")
                time.sleep(sleep_duration)

            progress_bar.update(1)


def scrape_players_endpoints(game_df, init_dict, algs_games_dir, sleep_duration=2):
    headers = {
        "Content-Type": "application/json",
        # "DGS-Authorization": dgs_auth
    }

    players_endpoints = [
        "getPlayerEvents"
    ]

    all_api_names = list(players_endpoints)
    for api_name in all_api_names:
        if not os.path.exists(f"{algs_games_dir}/{api_name}"):
            os.makedirs(f"{algs_games_dir}/{api_name}")

    for api_name in players_endpoints:
        api_download_dir = f"{algs_games_dir}/{api_name}"
        downloaded_files = [f.split(".")[0] for f in os.listdir(api_download_dir)]
        missing_games = game_df.loc[~game_df["game_id"].isin(downloaded_files)].copy()
        if len(missing_games) == 0:
            continue

        invalid_game_timestamps = missing_games["game_timestamp"].apply(lambda x: isinstance(x, str))
        if any(invalid_game_timestamps):
            invalid_list = missing_games[invalid_game_timestamps]["game_timestamp"].tolist()
            logger.info(f"Found invalid timestamps {invalid_list}")
            # ensure game_timestamp is an integer
            missing_games = missing_games[~invalid_game_timestamps]
        missing_games.sort_values("game_timestamp", inplace=True, ascending=False)
        logger.info(f"Downloading {api_name} data")
        progress_bar = tqdm(total=len(missing_games), desc=f"Downloading {api_name} data")
        for index, row in missing_games.iterrows():
            game_id = row["game_id"]
            try:
                if len(init_dict[game_id]) == 0:
                    progress_bar.update(1)
                    continue
                if "players" not in init_dict[game_id]:
                    progress_bar.update(1)
                    continue

                players_hash_list = [player["nucleusHash"] for player in init_dict[row["game_id"]]["players"]]
                file_name = f"{algs_games_dir}/{api_name}/{row['game_id']}.json"
                all_players_list = []
                for player_hash_str in players_hash_list:
                    full_endpoint_url = (DGS_API_URL +
                                         f"api?gameID={game_id}&qt={api_name}&nucleusHash={player_hash_str}")
                    response = _get_with_retry(full_endpoint_url, headers)
                    if response is None:
                        # Game JSON will still be written with the players that did succeed.
                        continue
                    logger.debug(f"GET {full_endpoint_url} -> {response.status_code}")
                    if response.status_code == 200:
                        if len(response.text) > 0:
                            try:
                                result_json = response.json()
                            except ValueError as e:
                                # Malformed JSON from upstream — log and skip the
                                # player so a single bad response doesn't kill the run.
                                logger.warning(
                                    f"JSONDecodeError on {full_endpoint_url}: {e}; "
                                    f"first 200 chars of body: {response.text[:200]!r}"
                                )
                                time.sleep(sleep_duration)
                                continue
                            all_players_list.append(result_json)
                    else:
                        logger.warning(f"Non-200 for {full_endpoint_url}: {response.status_code} {response.text[:200]}")
                    time.sleep(sleep_duration)
                with open(file_name, "w") as file:
                    json.dump(all_players_list, file, indent=2)
            except Exception as e:
                # Catch-all so a single bad game (malformed init dict, bad
                # nucleusHash, etc.) doesn't tear down the whole multi-hour run.
                # The crash mode we hit twice on 2026-04-27 left no traceback in
                # the log because tqdm's stderr buffering ate it; explicit
                # logging here surfaces what failed and on which game.
                logger.exception(f"unhandled error while scraping {api_name} for game {game_id}: {e}; "
                                 f"skipping this game and continuing")
            finally:
                progress_bar.update(1)


def scrape_games_data(game_df, algs_games_dir, init_data_dir):
    scrape_game_endpoints(game_df, algs_games_dir)

    games_init_dict = {}
    for game_init in os.listdir(init_data_dir):
        game_init_file_path = f"{algs_games_dir}/init/{game_init}"
        with open(game_init_file_path, "r") as file:
            games_init_dict[game_init.replace(".json", "")] = json.load(file)

    scrape_players_endpoints(game_df, games_init_dict, algs_games_dir)


# URL path pattern for a tournament landing link, e.g.
#   /algs/Y5-Split2/ALGS-Championships/Global/Overview
TOURNAMENT_URL_PATTERN = re.compile(
    r'^/algs/Y(?P<year>\d+)-Split(?P<split>\d+)/(?P<type>[^/]+)/(?P<region>[^/]+)/'
)

# Game URL nested under a tournament:
#   /algs/Y5-Split2/ALGS-Championships/Global/Day1/AvB/<32-char-hex>
GAME_NESTED_URL_PATTERN = re.compile(
    r'^/algs/Y\d+-Split\d+/[^/]+/[^/]+/(?P<day>[^/]+)/(?P<match>[^/]+)/(?P<game_id>[a-f0-9]{32})/?$'
)

# Raw game URL:
#   /algs/game/<32-char-hex>
GAME_RAW_URL_PATTERN = re.compile(r'^/algs/game/(?P<game_id>[a-f0-9]{32})/?$')

NON_ALGS_TOURNAMENT_TYPES = {"Solos-Showdown"}


def scrape_tournaments():
    dgs_algs_page_url = "https://apexlegendsstatus.com/algs/"

    dgs_algs_page_html = requests.get(dgs_algs_page_url, timeout=(5, 30))
    logger.debug(f"GET {dgs_algs_page_url} -> {dgs_algs_page_html.status_code}")

    if dgs_algs_page_html.status_code != 200:
        logger.error(f"Error: {dgs_algs_page_url}, {dgs_algs_page_html.status_code}, {dgs_algs_page_html.text[:200]}")
        return None

    soup = BeautifulSoup(dgs_algs_page_html.text, 'html.parser')

    tournament_items = soup.find_all('a', class_='tournament-item')
    if not tournament_items:
        logger.error("Found 0 tournament-item elements on landing page. ALS HTML structure may have changed again.")
        return None

    tournament_list = []
    for item in tournament_items:
        tournament_url = item.get('href', '')
        name_el = item.find(class_='tournament-name')
        tournament_full_name = name_el.text.strip() if name_el else ''

        url_match = TOURNAMENT_URL_PATTERN.match(tournament_url)
        if not url_match:
            logger.info(f"Skipping tournament with unrecognised URL: {tournament_url!r} ({tournament_full_name!r})")
            continue

        tournament_type = url_match.group("type")
        if tournament_type in NON_ALGS_TOURNAMENT_TYPES:
            continue

        tournament_year = url_match.group("year")
        tournament_split = url_match.group("split")
        tournament_region = url_match.group("region")
        # tournament_name is a human-ish label derived from the URL type slug.
        tournament_name = tournament_type.replace("-", " ")

        tournament_list.append((
            tournament_full_name,
            tournament_name,
            tournament_year,
            tournament_split,
            tournament_region,
            tournament_url,
        ))

    tournament_columns = ["tournament_full_name", "tournament_name", "tournament_year", "tournament_split",
                          "tournament_region", "tournament_url"]
    tournament_df = pd.DataFrame(tournament_list, columns=tournament_columns)
    logger.info(f"Parsed {len(tournament_df)} tournaments from landing page")

    return tournament_df


def scrape_games(tournament_df, current_game_df):
    """Discover per-tournament game_ids by parsing each Overview page.

    The new ALS site lists every game directly on the tournament Overview page
    as anchors of the form:
        /algs/{year_split}/{type}/{region}/{day}/{match}/{game_id}     (nested)
        /algs/game/{game_id}                                            (raw)

    We extract game_id, tournament_day, and match_slug from the nested form,
    falling back to raw links that lack day/match context. Game metadata that
    is no longer on the Overview page (timestamp, map, game_num) is populated
    later from init JSONs by enrich_games_from_init().
    """
    tournament_columns = tournament_df.columns.tolist()
    game_columns = tournament_columns + ["tournament_day",
                                         "game_title",
                                         "game_map",
                                         "game_timestamp",
                                         "game_num",
                                         "game_id"]
    game_list = []
    for _, row in tournament_df.iterrows():
        tournament_url = row["tournament_url"]
        tournament_page_url = ALS_URL.rstrip("/") + tournament_url

        tournament_page_html = requests.get(tournament_page_url, timeout=(5, 30))
        logger.debug(f"GET {tournament_page_url} -> {tournament_page_html.status_code}")

        if tournament_page_html.status_code != 200:
            logger.error(f"Tournament page failed: {tournament_url} (status={tournament_page_html.status_code})")
            continue
        if "No games found for this region" in tournament_page_html.text:
            logger.info(f"No games for tournament: {tournament_url}")
            continue

        soup = BeautifulSoup(tournament_page_html.text, 'html.parser')

        game_meta = {}  # game_id -> (tournament_day, match_slug)
        # Pass 1: nested URLs (carry day + match context).
        for a in soup.find_all('a', href=True):
            m = GAME_NESTED_URL_PATTERN.match(a['href'])
            if m:
                gid = m.group('game_id')
                if gid not in game_meta:
                    game_meta[gid] = (m.group('day'), m.group('match'))
        # Pass 2: raw game links for any games the nested pass missed.
        for a in soup.find_all('a', href=True):
            m = GAME_RAW_URL_PATTERN.match(a['href'])
            if m:
                gid = m.group('game_id')
                if gid not in game_meta:
                    game_meta[gid] = ("", "")

        logger.info(f"{tournament_url}: found {len(game_meta)} games")

        for game_id, (tournament_day, match_slug) in game_meta.items():
            game_list.append((
                row["tournament_full_name"],
                row["tournament_name"],
                row["tournament_year"],
                row["tournament_split"],
                row["tournament_region"],
                tournament_url,
                tournament_day,
                match_slug,  # was game_title; we now store match_slug here until enrichment fills it.
                "",          # game_map (enriched from init)
                0,           # game_timestamp (enriched from init)
                "",          # game_num (no longer available from HTML)
                game_id,
            ))

    game_df = pd.DataFrame(game_list, columns=game_columns)

    old_size = 0 if current_game_df is None else len(current_game_df)
    if current_game_df is not None and not current_game_df.empty:
        game_df = pd.concat([current_game_df, game_df], ignore_index=True)

    game_df = game_df.sort_values(
        by=["tournament_year", "tournament_split", "tournament_region", "game_timestamp", "game_num"])
    game_df.drop_duplicates(["game_id"], inplace=True)
    game_df = game_df[game_df["game_id"] != "#"]

    new_size = len(game_df)
    if new_size > old_size:
        logger.info(f"Found {new_size - old_size} new games")
    logger.info(f"Total games: {len(game_df)}")

    return game_df


def enrich_games_from_init(game_df, init_data_dir):
    """Populate game_timestamp and game_map from downloaded init JSONs.

    scrape_games() leaves these columns unfilled because the new ALS Overview
    page no longer carries per-game metadata. The DGS init endpoint does, so
    once scrape_game_endpoints() has written the JSONs we can fold them in.

    Builds a {game_id -> (timestamp, map)} dict in one pass over the JSONs,
    then applies via pd.Series.map — avoids the per-row .at[] writes that
    are O(rows) in pandas.
    """
    if not os.path.exists(init_data_dir):
        logger.warning(f"Init data dir missing, cannot enrich: {init_data_dir}")
        return game_df

    init_meta = {}
    for game_id in game_df["game_id"]:
        init_path = f"{init_data_dir}/{game_id}.json"
        if not os.path.exists(init_path):
            continue
        try:
            with open(init_path, "r") as fh:
                init = json.load(fh)
        except json.JSONDecodeError:
            logger.warning(f"Corrupt init JSON for {game_id}")
            continue
        if not init:
            continue
        ts = init.get("timestamp")
        try:
            ts = int(ts) if ts is not None else None
        except (ValueError, TypeError):
            ts = None
        init_meta[game_id] = (ts, init.get("mapImg") or "")

    if not init_meta:
        logger.warning("No init JSONs available for enrichment")
        return game_df

    ts_map = {gid: meta[0] for gid, meta in init_meta.items() if meta[0] is not None}
    map_map = {gid: meta[1] for gid, meta in init_meta.items() if meta[1]}
    if ts_map:
        game_df["game_timestamp"] = game_df["game_id"].map(ts_map).fillna(game_df["game_timestamp"])
    if map_map:
        game_df["game_map"] = game_df["game_id"].map(map_map).fillna(game_df["game_map"])

    logger.info(f"Enriched {len(init_meta)}/{len(game_df)} games from init JSONs")
    return game_df


def main():
    parser = ArgumentParser()
    parser.add_argument("--algs_game_list_file", default="data/algs_game_list.csv", help="ALGS Game List File")
    parser.add_argument("--algs_games_dir", default="data/algs_games", help="ALGS Games Directory")
    parser.add_argument("--init_data_dir", default="data/algs_games/init")
    parser.add_argument("--debug", action="store_true",
                        help="Smoke test: verbose logs, first 2 tournaments and 5 games, writes to data/debug/ so the real cache is not touched.")
    parser.add_argument("--min-year", type=int, default=None,
                        help="Only scrape tournaments with tournament_year >= this value (e.g. 6 for Y6+). Filters before any per-tournament HTTP.")
    parser.add_argument("--since", type=str, default=None,
                        help="Only run the (expensive) players-endpoint scrape for games with init timestamp on/after this date (YYYY-MM-DD).")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        args.algs_game_list_file = "data/debug/algs_game_list.csv"
        args.algs_games_dir = "data/debug/algs_games"
        args.init_data_dir = "data/debug/algs_games/init"
        os.makedirs("data/debug", exist_ok=True)
        logger.info("DEBUG mode: writing to data/debug/, limiting to 2 tournaments and 5 games")

    since_ts = None
    if args.since:
        since_ts = int(datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        logger.info(f"--since {args.since}: will skip players-endpoint scrape for games before unix ts {since_ts}")

    algs_game_list_file = args.algs_game_list_file
    algs_games_dir = args.algs_games_dir
    init_data_dir = args.init_data_dir

    if os.path.exists(algs_game_list_file):
        current_game_df = pd.read_csv(algs_game_list_file, na_filter=False)
    else:
        current_game_df = None

    tournament_df = scrape_tournaments()
    if tournament_df is None:
        return

    if args.min_year is not None:
        before = len(tournament_df)
        tournament_df = tournament_df[tournament_df["tournament_year"].astype(int) >= args.min_year].reset_index(drop=True)
        logger.info(f"--min-year {args.min_year}: kept {len(tournament_df)}/{before} tournaments")

    if args.debug:
        tournament_df = tournament_df.head(2)
        logger.info(f"DEBUG: truncated to {len(tournament_df)} tournaments: {tournament_df['tournament_full_name'].tolist()}")

    game_df = scrape_games(tournament_df, current_game_df)

    if args.debug:
        game_df = game_df.head(5)
        logger.info(f"DEBUG: truncated to {len(game_df)} games")

    # Save the un-enriched list first so a Ctrl-C between phases doesn't lose
    # enumeration work. The second to_csv below overwrites it with the
    # enriched version once init JSONs land.
    game_df.to_csv(algs_game_list_file, index=False, quoting=csv.QUOTE_NONNUMERIC)

    # Phase 1: init endpoint (cheap, 1 call per game).
    scrape_game_endpoints(game_df, algs_games_dir)

    # Enrich from init so we have real timestamps before deciding which games to pull player events for.
    game_df = enrich_games_from_init(game_df, init_data_dir)
    game_df = game_df.sort_values(
        by=["tournament_year", "tournament_split", "tournament_region", "game_timestamp", "game_num"])
    game_df.to_csv(algs_game_list_file, index=False, quoting=csv.QUOTE_NONNUMERIC)

    # Phase 2: players endpoint (expensive, ~60 calls per game). Filter first if --since was set.
    players_game_df = game_df
    if since_ts is not None:
        before = len(players_game_df)
        players_game_df = players_game_df[players_game_df["game_timestamp"].astype(int) >= since_ts]
        logger.info(f"--since filter: pulling player events for {len(players_game_df)}/{before} games")

    games_init_dict = {}
    for game_init in os.listdir(init_data_dir):
        with open(f"{init_data_dir}/{game_init}", "r") as fh:
            games_init_dict[game_init.replace(".json", "")] = json.load(fh)

    scrape_players_endpoints(players_game_df, games_init_dict, algs_games_dir)


if __name__ == "__main__":
    main()
