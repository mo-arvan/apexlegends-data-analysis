"""Augment kill_records.parquet with situational columns from match_state.

For each engagement, compute the attacker team's pre-engagement context by
finding the most recent match_state snapshot at or before the engagement
start. Adds:

  team_HP_sum_at_start                       attacker team's HP coming in
  team_kills_last_60s_at_start               attacker's recent momentum
  team_dmg_dealt_last_30s_at_start           offensive activity
  team_dmg_taken_last_30s_at_start           defensive pressure
  team_centroid_x_at_start, _y_at_start      attacker centroid
  team_spread_at_start                       attacker formation spread
  dist_to_nearest_alive_team_at_start        third-party / contested risk
  n_teams_alive_at_start                     global game state

Engagements before the first match_state snapshot in their game (i.e. before
the first kill happens in that game) get fallback values: HP_sum=300 (3
players * 100), momentum=0, others NaN.

Match_state is built per-year. Run `build_match_state.py --year N` for each
year that should be covered, then re-run this script with --append-year to
build up the augmentation across years. Engagements in years without
match_state coverage get NaN augmentation columns.
"""

import logging
import os
from argparse import ArgumentParser

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

KILL_RECORDS = "data/kill_records.parquet"
MATCH_STATE = "data/match_state.parquet"
DAMAGE_DIR = "data/tournament_damage_events"

AUG_COLS = [
    "team_HP_sum_at_start",
    "team_kills_last_60s_at_start",
    "team_dmg_dealt_last_30s_at_start",
    "team_dmg_taken_last_30s_at_start",
    "team_centroid_x_at_start",
    "team_centroid_y_at_start",
    "team_spread_at_start",
    "dist_to_nearest_alive_team_at_start",
    "n_teams_alive_at_start",
]

STATE_COLS = [
    "team_HP_sum",
    "team_kills_last_60s",
    "team_dmg_dealt_last_30s",
    "team_dmg_taken_last_30s",
    "team_centroid_x",
    "team_centroid_y",
    "team_spread",
    "dist_to_nearest_alive_team",
    "n_teams_alive",
]


def build_team_lookup(damage_dir, game_ids):
    """(game_id, player_hash) -> team_name lookup."""
    files = sorted(f for f in os.listdir(damage_dir) if f.endswith(".parquet"))
    rows = []
    for f in files:
        df = pd.read_parquet(os.path.join(damage_dir, f),
                             columns=["game_id", "player_hash", "team_name"])
        df = df[df["game_id"].isin(game_ids)]
        if not df.empty:
            rows.append(df.drop_duplicates(["game_id", "player_hash"]))
    full = pd.concat(rows, ignore_index=True).drop_duplicates(["game_id", "player_hash"])
    return full.set_index(["game_id", "player_hash"])["team_name"].to_dict()


def main():
    parser = ArgumentParser()
    parser.add_argument("--kill-records", default=KILL_RECORDS)
    parser.add_argument("--match-state", default=MATCH_STATE)
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--out", default=KILL_RECORDS)
    args = parser.parse_args()

    logger.info(f"Loading {args.kill_records}...")
    kr = pd.read_parquet(args.kill_records)
    n_total = len(kr)
    logger.info(f"  engagements: {n_total:,}")

    logger.info(f"Loading {args.match_state}...")
    state = pd.read_parquet(args.match_state)[
        ["game_id", "ts", "team"] + STATE_COLS
    ]
    state_games = set(state["game_id"])
    logger.info(f"  state rows: {len(state):,} across {len(state_games)} games")

    overlap = set(kr["game_id"]) & state_games
    logger.info(f"  kill_records rows in covered games: "
                f"{kr['game_id'].isin(state_games).sum():,} of {n_total:,}")

    logger.info("Building (game, player) -> team lookup for attackers...")
    team_lookup = build_team_lookup(args.damage_dir, overlap)
    kr["attacker_team"] = kr.apply(
        lambda r: team_lookup.get((r["game_id"], r["top_attacker_hash"])), axis=1
    )

    # If augmentation cols already exist (from a prior year run), keep them
    # and only fill rows that are currently NaN. This lets the script run
    # once per year of match_state, accumulating coverage across years.
    accumulate = all(c in kr.columns for c in AUG_COLS)
    if accumulate:
        prev_n = kr["team_HP_sum_at_start"].notna().sum()
        logger.info(f"  pre-existing augmentation: {prev_n:,} rows already filled")
    else:
        for c in AUG_COLS:
            kr[c] = pd.NA

    # Per-(game, team) merge_asof on engagement start.
    logger.info("Merging state at engagement start via merge_asof...")
    kr_sub = kr[kr["game_id"].isin(state_games) & kr["attacker_team"].notna()].copy()
    kr_sub = kr_sub[["game_id", "attacker_team", "start_ts"]].rename(
        columns={"attacker_team": "team", "start_ts": "ts"}
    ).reset_index().sort_values("ts")
    state_sorted = state.sort_values("ts")

    merged = pd.merge_asof(
        kr_sub, state_sorted,
        by=["game_id", "team"],
        on="ts",
        direction="backward",
        allow_exact_matches=True,
    )
    merged = merged.set_index("index")
    rename = dict(zip(STATE_COLS, AUG_COLS))
    merged = merged[STATE_COLS].rename(columns=rename)

    # Fill only rows currently NaN; preserve any prior-year augmentation.
    for src_col, dst_col in zip(STATE_COLS, AUG_COLS):
        new_vals = merged[dst_col]
        existing = kr[dst_col]
        kr[dst_col] = existing.where(existing.notna(), new_vals)

    # Sanity stats.
    n_with_aug = kr["team_HP_sum_at_start"].notna().sum()
    logger.info(f"Augmented {n_with_aug:,} of {n_total:,} engagements "
                f"({n_with_aug / n_total:.1%})")
    if n_with_aug:
        logger.info("HP_sum_at_start: " + str(kr["team_HP_sum_at_start"].describe().round(0).to_dict()))
        logger.info("kills_last_60s_at_start: " + str(
            kr["team_kills_last_60s_at_start"].describe().round(2).to_dict()))
        logger.info("dist_to_nearest_alive_team_at_start: " + str(
            kr["dist_to_nearest_alive_team_at_start"].describe().round(0).to_dict()))

    kr.to_parquet(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
