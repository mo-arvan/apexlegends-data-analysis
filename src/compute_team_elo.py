"""Compute team Elo ratings from training games (Phase 1 of the WPA model).

Pairwise placement-based Elo: walk training games in chronological order, and
for every pair of teams (A, B) in a game where A placed higher than B, run a
standard Elo update with A as the "winner". K-factor is the standard chess
default (32).

Output:
  data/team_elo_train_end.csv  one row per team with final Elo at end of train

This Elo is used as a static feature `team_elo_prior` in train/val/test of
the WPA model. Unlike the naive `team_mean_kills_train` prior (which assumes
performance is absolute), Elo encodes performance *relative to opponents
faced*, so it should generalize better across competitive contexts.
"""

import logging
from argparse import ArgumentParser
from collections import defaultdict

import pandas as pd

from train_wpa import TRAIN_TOURNAMENTS

# "Recent" Elo uses only the most-recent training tournament so the rating is
# closer to the test-time competitive context.
RECENT_TRAIN_TOURNAMENTS = {"Pro League - Year 4, Split 2"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

STATE_PARQUET = "data/match_state.parquet"
OUT_CSV = "data/team_elo_train_end.csv"
OUT_RECENT_CSV = "data/team_elo_recent_end.csv"

INITIAL_ELO = 1500.0
K_FACTOR = 32.0


def expected_score(elo_a, elo_b):
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def update_pair(elo, a, b, actual_a):
    """Standard pairwise Elo update."""
    exp_a = expected_score(elo[a], elo[b])
    elo[a] += K_FACTOR * (actual_a - exp_a)
    elo[b] += K_FACTOR * ((1 - actual_a) - (1 - exp_a))


def compute_elo(state, tournaments, rating_col):
    sub = state[state["tournament_full_name"].isin(tournaments)]
    per_game_team = sub.drop_duplicates(["game_id", "team"])[
        ["game_id", "team", "final_placement_rank", "game_timestamp"]
    ].dropna(subset=["final_placement_rank", "game_timestamp"]).copy()
    games_sorted = (per_game_team.drop_duplicates("game_id")
                    .sort_values("game_timestamp")["game_id"].tolist())

    elo = defaultdict(lambda: INITIAL_ELO)
    games_per_team = defaultdict(int)
    grouped = {gid: g for gid, g in per_game_team.groupby("game_id")}
    for gid in games_sorted:
        g = grouped[gid].sort_values("final_placement_rank")
        teams = g["team"].tolist()
        ranks = dict(zip(g["team"], g["final_placement_rank"]))
        for i, a in enumerate(teams):
            for b in teams[i + 1:]:
                actual = 0.5 if ranks[a] == ranks[b] else (1.0 if ranks[a] < ranks[b] else 0.0)
                update_pair(elo, a, b, actual)
            games_per_team[a] += 1

    return pd.DataFrame([
        {"team": t, rating_col: round(elo[t], 1), f"n_games_{rating_col}": games_per_team[t]}
        for t in elo
    ]).sort_values(rating_col, ascending=False)


def main():
    parser = ArgumentParser()
    parser.add_argument("--state", default=STATE_PARQUET)
    parser.add_argument("--out", default=OUT_CSV)
    parser.add_argument("--out-recent", default=OUT_RECENT_CSV)
    args = parser.parse_args()

    logger.info(f"Loading {args.state}...")
    state = pd.read_parquet(args.state)

    logger.info("Computing full-season Elo from all training tournaments...")
    full = compute_elo(state, TRAIN_TOURNAMENTS, "team_elo_prior")
    logger.info(f"  {len(full)} teams; range {full['team_elo_prior'].min():.0f} "
                f"-> {full['team_elo_prior'].max():.0f}")
    full.to_csv(args.out, index=False)
    logger.info(f"  wrote {args.out}")

    logger.info(f"Computing recency-weighted Elo from {RECENT_TRAIN_TOURNAMENTS}...")
    recent = compute_elo(state, RECENT_TRAIN_TOURNAMENTS, "team_elo_recent_prior")
    logger.info(f"  {len(recent)} teams; range {recent['team_elo_recent_prior'].min():.0f} "
                f"-> {recent['team_elo_recent_prior'].max():.0f}")
    recent.to_csv(args.out_recent, index=False)
    logger.info(f"  wrote {args.out_recent}")
    logger.info(f"\nTop 10 by recent Elo:\n{recent.head(10).to_string(index=False)}")


if __name__ == "__main__":
    main()
