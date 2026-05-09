"""Phase 0 sanity check: find the highest-leverage events in the test set and
inspect whether they look legitimate.

For each kill event (which is the moment we have a prediction for), compute
per-team WPA as the change in expected score caused by the event:

  WPA_team = score(pred_after) - score(pred_before)
  score   = E[final_kills] + placement_points(E[final_placement_rank])

Then sum |WPA_killer| + |WPA_victim_team| as the total leverage of the event.

The hope: top-leverage events are late-game eliminations of the leading team,
or focused-team-push kills that flipped a placement bucket. The fear: top-
leverage events are random early-game deaths with no narrative weight.

Output:
  output/wpa/top_events.md  ranked top-N events with full context
"""

import logging
import os
from argparse import ArgumentParser

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PRED_PARQUET = "data/wpa_predictions.parquet"
KILL_EVENTS = "data/kill_events.parquet"
DAMAGE_DIR = "data/tournament_damage_events"
GAME_LIST = "data/algs_game_list.csv"
OUT_MD = "output/wpa/top_events.md"

# ALGS standard placement points table. rank 1 = 12, rank 20+ = 0.
PLACEMENT_POINTS = {
    1: 12, 2: 9, 3: 7, 4: 5, 5: 4,
    6: 3, 7: 3,
    8: 2, 9: 2, 10: 2,
    11: 1, 12: 1, 13: 1, 14: 1, 15: 1,
}


def expected_placement_points(rank_pred):
    """Map a continuous predicted rank to expected placement points by linear
    interpolation between the integer-rank table values. Anything past 15
    is 0 points."""
    if pd.isna(rank_pred):
        return np.nan
    if rank_pred <= 1:
        return PLACEMENT_POINTS[1]
    if rank_pred >= 16:
        return 0.0
    lo = int(np.floor(rank_pred))
    hi = lo + 1
    pl = PLACEMENT_POINTS.get(lo, 0)
    ph = PLACEMENT_POINTS.get(hi, 0)
    frac = rank_pred - lo
    return pl + (ph - pl) * frac


def compute_wpa(pred):
    """Add per-(game, team) lagged predictions and WPA columns."""
    pred = pred.sort_values(["game_id", "team", "ts", "event_id"]).copy()
    g = pred.groupby(["game_id", "team"], sort=False)
    pred["pred_kills_before"] = g["pred_final_kills"].shift(1)
    pred["pred_rank_before"] = g["pred_final_placement_rank"].shift(1)
    # Compose into expected score.
    pred["exp_score_after"] = (
        pred["pred_final_kills"]
        + pred["pred_final_placement_rank"].apply(expected_placement_points)
    )
    pred["exp_score_before"] = (
        pred["pred_kills_before"]
        + pred["pred_rank_before"].apply(expected_placement_points)
    )
    pred["wpa_score"] = pred["exp_score_after"] - pred["exp_score_before"]
    pred["wpa_kills"] = pred["pred_final_kills"] - pred["pred_kills_before"]
    pred["wpa_rank"] = pred["pred_final_placement_rank"] - pred["pred_rank_before"]
    return pred


def main():
    parser = ArgumentParser()
    parser.add_argument("--pred", default=PRED_PARQUET)
    parser.add_argument("--kills", default=KILL_EVENTS)
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--game-list", default=GAME_LIST)
    parser.add_argument("--out-md", default=OUT_MD)
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--min-teams-alive", type=int, default=0,
                        help="Filter to events where >= this many teams remain alive "
                             "(use 10 to restrict to mid-game).")
    parser.add_argument("--max-time-in-game-s", type=int, default=None,
                        help="Filter to events at or before this many seconds in.")
    args = parser.parse_args()

    logger.info(f"Loading {args.pred}...")
    pred = pd.read_parquet(args.pred)
    logger.info(f"  test rows: {len(pred):,}")

    pred = compute_wpa(pred)
    pred = pred.dropna(subset=["wpa_score"])  # drop first event per (game, team)
    logger.info(f"  WPA-scored rows: {len(pred):,}")

    # Aggregate per (game, event_id) -- one event = one kill -- find top by total leverage.
    # Total leverage = sum |wpa_score| across all teams that moved at this event.
    per_event = (
        pred.groupby(["game_id", "event_id"])
        .agg(
            ts=("ts", "first"),
            total_leverage=("wpa_score", lambda s: s.abs().sum()),
            killer_wpa=("wpa_score", "max"),
            victim_wpa=("wpa_score", "min"),
            n_teams_moved=("wpa_score", lambda s: (s.abs() > 0.01).sum()),
        )
        .reset_index()
    )

    # Attach kill-event details: who killed whom, weapon, location.
    logger.info(f"Loading {args.kills}...")
    kills = pd.read_parquet(args.kills)[
        ["game_id", "event_id", "attacker_hash", "victim_hash",
         "weapon", "distance_m", "is_bleed_out"]
    ]
    per_event = per_event.merge(kills, on=["game_id", "event_id"], how="left")

    # Attach attacker / victim names + teams from damage events.
    logger.info("Building player name + team lookup...")
    files = sorted(f for f in os.listdir(args.damage_dir) if f.endswith(".parquet"))
    name_team_rows = []
    test_games = set(pred["game_id"])
    for f in files:
        df = pd.read_parquet(
            os.path.join(args.damage_dir, f),
            columns=["game_id", "player_hash", "player_name", "team_name"],
        )
        df = df[df["game_id"].isin(test_games)]
        if not df.empty:
            name_team_rows.append(df.drop_duplicates(["game_id", "player_hash"]))
    name_team = (pd.concat(name_team_rows, ignore_index=True)
                 .drop_duplicates(["game_id", "player_hash"]))
    name_team_idx = name_team.set_index(["game_id", "player_hash"])

    def lookup(gid, h, col):
        try:
            return name_team_idx.loc[(gid, h), col]
        except KeyError:
            return None

    per_event["attacker_name"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["attacker_hash"], "player_name"), axis=1)
    per_event["victim_name"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["victim_hash"], "player_name"), axis=1)
    per_event["attacker_team"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["attacker_hash"], "team_name"), axis=1)
    per_event["victim_team"] = per_event.apply(
        lambda r: lookup(r["game_id"], r["victim_hash"], "team_name"), axis=1)

    # Attach tournament/game metadata.
    games = pd.read_csv(args.game_list)[
        ["game_id", "tournament_full_name", "game_map", "game_num", "tournament_day"]
    ]
    per_event = per_event.merge(games, on="game_id", how="left")

    # Pull state at the event for context: how many teams alive, who was leading.
    state_at = (
        pred.groupby(["game_id", "event_id"])
        .agg(n_teams_alive=("n_teams_alive", "first"),
             time_in_game_s=("time_in_game_s", "first"))
        .reset_index()
    )
    per_event = per_event.merge(state_at, on=["game_id", "event_id"], how="left")

    # Killer's and victim's team state at moment.
    per_event = per_event.merge(
        pred[["game_id", "event_id", "team", "n_alive_team", "kills_so_far_team",
              "wpa_score", "wpa_kills", "wpa_rank"]]
        .rename(columns={"team": "attacker_team",
                         "n_alive_team": "atk_alive",
                         "kills_so_far_team": "atk_kills_after",
                         "wpa_score": "atk_wpa",
                         "wpa_kills": "atk_wpa_kills",
                         "wpa_rank": "atk_wpa_rank"}),
        on=["game_id", "event_id", "attacker_team"], how="left",
    )
    per_event = per_event.merge(
        pred[["game_id", "event_id", "team", "n_alive_team", "wpa_score", "wpa_kills", "wpa_rank"]]
        .rename(columns={"team": "victim_team",
                         "n_alive_team": "vic_alive",
                         "wpa_score": "vic_wpa",
                         "wpa_kills": "vic_wpa_kills",
                         "wpa_rank": "vic_wpa_rank"}),
        on=["game_id", "event_id", "victim_team"], how="left",
    )

    if args.min_teams_alive:
        per_event = per_event[per_event["n_teams_alive"] >= args.min_teams_alive]
    if args.max_time_in_game_s is not None:
        per_event = per_event[per_event["time_in_game_s"] <= args.max_time_in_game_s]
    logger.info(f"After filters: {len(per_event):,} events")
    top = per_event.sort_values("total_leverage", ascending=False).head(args.top_n)

    # Markdown report.
    lines = [
        "# Top WPA events (Phase 0 sanity check)",
        "",
        f"Source: `{args.pred}` (test set: ALGS Playoffs Y4 Split 2, 63 games).",
        f"Per-event WPA = score(state_after) - score(state_before), where score = "
        f"E[final_kills] + expected_placement_points(E[final_placement_rank]).",
        f"Placement points table: {PLACEMENT_POINTS}.",
        f"`total_leverage` = sum |wpa_score| across all teams at the event "
        f"(killer's gain plus victim-team's loss, broadly).",
        "",
        f"Showing top {args.top_n} of {len(per_event):,} kill events in the test set.",
        "",
        "| rank | game | day/match/map | time | victim (team, alive) | attacker (team, alive) | weapon | n_teams_alive | leverage | atk_wpa | vic_wpa |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    def _i(v):
        return int(v) if pd.notna(v) else "?"
    for i, (_, r) in enumerate(top.iterrows(), start=1):
        gid_short = r["game_id"][:8]
        time_min = int(r["time_in_game_s"]) // 60
        time_sec = int(r["time_in_game_s"]) % 60
        match_label = f"{r['tournament_day']} G{_i(r['game_num'])}"
        map_label = (r['game_map'] or '').replace('mp_rr_', '').replace('.png', '')
        vic_alive = _i(r['vic_alive'])
        vic_was = (vic_alive + 1) if isinstance(vic_alive, int) else "?"
        lines.append(
            f"| {i} | {gid_short} | {match_label} {map_label} | "
            f"{time_min}:{time_sec:02d} | "
            f"{r['victim_name']} ({r['victim_team']}, was {vic_was}->{vic_alive} alive) | "
            f"{r['attacker_name']} ({r['attacker_team']}, {_i(r['atk_alive'])} alive) | "
            f"{r['weapon']} | "
            f"{_i(r['n_teams_alive'])} | "
            f"{r['total_leverage']:.2f} | "
            f"{r['atk_wpa']:+.2f} | "
            f"{r['vic_wpa']:+.2f} |"
        )

    lines += [
        "",
        "## How to read this",
        "",
        "- **leverage** in points: total absolute swing in expected tournament points across all teams at this event. Higher = more pivotal.",
        "- **atk_wpa** / **vic_wpa**: change in expected points for the attacker's team (positive = good for them) and the victim's team (negative for the team that lost a member). The attacker team usually gains kills (+1 or so) AND climbs in placement; the victim team usually loses placement.",
        "- **n_teams_alive**: how many teams were still in the game at this moment. Late-game leverage is higher because there are fewer teams left and each kill changes placement more.",
        "- **was N+1->N alive**: the victim's team had N+1 alive before this kill, N after. Final-kill (N=0) eliminations are usually the highest-leverage events because they take a team from \"alive, contesting\" to \"out, locked-in placement.\"",
        "",
        "## What to look for",
        "",
        "- Top events should mostly be **late-game team-eliminations** (N+1->N=0): the kill that takes the last alive member of a team out.",
        "- Top events should cluster in **late-stage rings** (high time_in_game_s, low n_teams_alive).",
        "- Top events should not be early-game drop-fight knocks (low time, full lobby alive).",
        "- If top events look random or skew early-game, the model is leaning on weak signal.",
    ]

    os.makedirs(os.path.dirname(args.out_md), exist_ok=True)
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md}")

    # Also dump quick distribution: what fraction of top-100 events are late-game team-elims?
    top100 = per_event.sort_values("total_leverage", ascending=False).head(100)
    n_team_elim = (top100["vic_alive"] == 0).sum()
    median_n_teams = top100["n_teams_alive"].median()
    median_time_min = top100["time_in_game_s"].median() / 60.0
    logger.info(f"Top-100 stats: {n_team_elim}/100 are team eliminations (vic_alive==0); "
                f"median n_teams_alive={median_n_teams}; median time_in_game={median_time_min:.1f} min")


if __name__ == "__main__":
    main()
