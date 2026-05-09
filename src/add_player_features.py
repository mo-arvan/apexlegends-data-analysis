"""Compute per-player skill aggregates from training-set games and add
team-level features (team_avg_kpg, team_max_kpg, team_avg_dpg) to
match_state.parquet.

  team_avg_kpg = mean of the 3 rostered players' mean kills-per-game
                 (team's average per-player productivity)
  team_max_kpg = max of the 3                       (carry-player signal)
  team_avg_dpg = mean of the 3 players' mean damage-per-game

Player aggregates are computed only on training tournaments to avoid leakage.
Players unseen in training receive the train-set overall mean.

Augmented columns are written back to data/match_state.parquet in place; the
existing schema is preserved and the script is idempotent (safe to rerun).
"""

import logging
import os
from argparse import ArgumentParser
from collections import defaultdict

import pandas as pd

from train_wpa import TRAIN_TOURNAMENTS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

STATE_PARQUET = "data/match_state.parquet"
KILL_EVENTS = "data/kill_events.parquet"
GAME_LIST = "data/algs_game_list.csv"
DAMAGE_DIR = "data/tournament_damage_events"


def main():
    parser = ArgumentParser()
    parser.add_argument("--state", default=STATE_PARQUET)
    parser.add_argument("--kills", default=KILL_EVENTS)
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--game-list", default=GAME_LIST)
    args = parser.parse_args()

    logger.info(f"Loading {args.state}...")
    state = pd.read_parquet(args.state)
    in_scope_games = set(state["game_id"])

    logger.info("Identifying training games...")
    games = pd.read_csv(args.game_list)
    train_game_ids = set(games[games["tournament_full_name"].isin(TRAIN_TOURNAMENTS)]["game_id"]) & in_scope_games
    logger.info(f"  train games in match_state: {len(train_game_ids):,}")

    # Per-player kill aggregates from training games.
    logger.info("Computing per-player kills-per-game from training games...")
    kills = pd.read_parquet(args.kills)
    train_kills = kills[kills["game_id"].isin(train_game_ids)]
    player_game_kills = (
        train_kills.groupby(["attacker_hash", "game_id"]).size().reset_index(name="k")
    )
    # Players who never killed in training are missing from this table; we
    # add zero-kill games by computing per-player game-count from rosters.

    # Per-player damage aggregate + rosters: from damage events.
    logger.info("Loading damage events for training games (player_hash, team, dmg)...")
    files = sorted(f for f in os.listdir(args.damage_dir) if f.endswith(".parquet"))
    rows = []
    roster_rows = []
    for f in files:
        df = pd.read_parquet(
            os.path.join(args.damage_dir, f),
            columns=["game_id", "player_hash", "team_name", "total_damage"],
        )
        df_train = df[df["game_id"].isin(train_game_ids)]
        if not df_train.empty:
            rows.append(
                df_train.groupby(["player_hash", "game_id"])["total_damage"].sum().reset_index()
            )
        # Rosters: any (game, hash, team) that appears in damage events. We
        # need rosters across ALL games (train + val + test), not just train.
        df_in_scope = df[df["game_id"].isin(in_scope_games)]
        if not df_in_scope.empty:
            roster_rows.append(df_in_scope[["game_id", "player_hash", "team_name"]]
                               .drop_duplicates(["game_id", "player_hash"]))
    player_game_dmg = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    rosters = pd.concat(roster_rows, ignore_index=True).drop_duplicates(["game_id", "player_hash"])
    logger.info(f"  rosters: {len(rosters):,} (game, player) pairs")

    # The "true" per-player game count uses rosters (count of train games the
    # player appeared in), so a player with 0 kills in 50 games gets 0.0 KPG
    # (not undefined).
    train_rosters = rosters[rosters["game_id"].isin(train_game_ids)]
    player_train_games = train_rosters.groupby("player_hash").size()
    player_total_kills = player_game_kills.groupby("attacker_hash")["k"].sum()
    player_kpg = (player_total_kills / player_train_games).fillna(0.0).to_dict()
    # players who never killed but did play
    for p in player_train_games.index:
        if p not in player_kpg:
            player_kpg[p] = 0.0
    logger.info(f"  per-player KPG: {len(player_kpg):,} players")

    if not player_game_dmg.empty:
        player_total_dmg = player_game_dmg.groupby("player_hash")["total_damage"].sum()
        player_dpg = (player_total_dmg / player_train_games).fillna(0.0).to_dict()
    else:
        player_dpg = {}
    logger.info(f"  per-player DPG: {len(player_dpg):,} players")

    fallback_kpg = sum(player_kpg.values()) / max(len(player_kpg), 1)
    fallback_dpg = sum(player_dpg.values()) / max(len(player_dpg), 1)
    logger.info(f"  fallback KPG: {fallback_kpg:.2f}; fallback DPG: {fallback_dpg:.1f}")

    # Per-(game, team) team-level aggregates from rosters.
    logger.info("Aggregating to team level per game...")
    rosters["kpg"] = rosters["player_hash"].map(player_kpg).fillna(fallback_kpg)
    rosters["dpg"] = rosters["player_hash"].map(player_dpg).fillna(fallback_dpg)
    team_features = rosters.groupby(["game_id", "team_name"]).agg(
        team_avg_kpg=("kpg", "mean"),
        team_max_kpg=("kpg", "max"),
        team_avg_dpg=("dpg", "mean"),
    ).reset_index().rename(columns={"team_name": "team"})

    logger.info("Merging into match_state...")
    # Drop existing columns if rerunning.
    for col in ["team_avg_kpg", "team_max_kpg", "team_avg_dpg"]:
        if col in state.columns:
            state = state.drop(columns=col)
    state = state.merge(team_features, on=["game_id", "team"], how="left")
    for col, fb in [("team_avg_kpg", fallback_kpg),
                    ("team_max_kpg", fallback_kpg),
                    ("team_avg_dpg", fallback_dpg)]:
        state[col] = state[col].fillna(fb)

    state.to_parquet(args.state, index=False)
    logger.info(f"Wrote {args.state} (cols={list(state.columns)})")
    logger.info(f"team_avg_kpg distribution: {state['team_avg_kpg'].describe().round(2).to_dict()}")
    logger.info(f"team_max_kpg distribution: {state['team_max_kpg'].describe().round(2).to_dict()}")


if __name__ == "__main__":
    main()
