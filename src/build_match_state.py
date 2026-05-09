"""Phase 0 of the WPA model: per-kill-event match state snapshots.

For each game, snapshot every team's state at the moment of every kill event
in that game. Each row is a (game_id, ts, team) tuple with five features
derivable from kill_events alone (no HP tracking yet):

  n_alive_team           team members still alive after this event
  kills_so_far_team      team's running kill count after this event
  n_teams_alive          global teams-alive count after this event
  time_in_game_s         seconds since game start
  kills_minus_leader     team's kills minus the current leader's kills

Plus two per-team targets that don't depend on the tournament's scoring rule:

  final_kills            team's total kills at game end
  final_placement_rank   1 = team won, 20 = first eliminated

WPA in any tournament's currency can be computed post-hoc by composing
predictions of E[final_kills | state] and E[final_placement_rank | state]
through that tournament's scoring function.

Output:
  data/match_state.parquet
"""

import logging
import os
from argparse import ArgumentParser
from collections import deque

import numpy as np
import pandas as pd

DMG_DEALT_WINDOW_S = 30
DMG_TAKEN_WINDOW_S = 30
KILLS_WINDOW_S = 60
TIME_SINCE_DMG_CAP = 600  # cap for "never dealt damage" sentinel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

KILL_EVENTS = "data/kill_events.parquet"
DOWN_EVENTS = "data/down_events.parquet"
HEAL_EVENTS = "data/heal_events.parquet"
DAMAGE_DIR = "data/tournament_damage_events"
GAME_LIST = "data/algs_game_list.csv"
OUT_PARQUET = "data/match_state.parquet"

HP_INITIAL = 100
HP_HARD_CAP = 225

# EVO shield model (current Apex, S20+). All players spawn with a white-tier
# shield and evolve through damage dealt. There are no separately-looted
# body shields in this patch — evolution is the only mechanism.
#   tier         shield_max   damage_dealt_to_unlock
#   white (0)    50            0
#   blue  (1)    75           50
#   purple(2)   100          125
#   red   (3)   125          250
SHIELD_MAX_BY_TIER = (50, 75, 100, 125)
EVO_THRESHOLDS = (0, 50, 125, 250)


def shield_tier_for(evo_dmg):
    tier = 0
    for t, thresh in enumerate(EVO_THRESHOLDS):
        if evo_dmg >= thresh:
            tier = t
    return tier


def build_team_lookup(damage_dir, game_ids=None):
    """(game_id, player_hash) -> team_name from damage events.
    Also returns a per-game name -> hash lookup (damage events use names for
    targets, but we hash-index everything else)."""
    logger.info("Building (game_id, player_hash) -> team_name lookup...")
    files = sorted(f for f in os.listdir(damage_dir) if f.endswith(".parquet"))
    rows = []
    for f in files:
        df = pd.read_parquet(os.path.join(damage_dir, f),
                             columns=["game_id", "player_hash", "player_name", "team_name"])
        if game_ids is not None:
            df = df[df["game_id"].isin(game_ids)]
        if not df.empty:
            rows.append(df.drop_duplicates(["game_id", "player_hash"]))
    full = pd.concat(rows, ignore_index=True).drop_duplicates(["game_id", "player_hash"])
    logger.info(f"  {len(full):,} (game, player) pairs across {full['game_id'].nunique()} games")
    team = full.set_index(["game_id", "player_hash"])["team_name"].to_dict()
    name_to_hash = {(gid, n): h for gid, h, n in
                    zip(full["game_id"], full["player_hash"], full["player_name"])}
    return team, name_to_hash


def load_damage_for_games(damage_dir, game_ids):
    """Lightweight per-game damage events. player_hash is the attacker;
    target_arr / damage_arr describe victims; x_position/y_position is
    attacker location at the moment of the burst."""
    logger.info("Loading damage events for in-scope games...")
    files = sorted(f for f in os.listdir(damage_dir) if f.endswith(".parquet"))
    rows = []
    for f in files:
        df = pd.read_parquet(
            os.path.join(damage_dir, f),
            columns=["game_id", "player_hash", "event_start_timestamp",
                     "target_arr", "damage_arr",
                     "x_position", "y_position"],
        )
        df = df[df["game_id"].isin(game_ids)]
        if not df.empty:
            rows.append(df)
    full = pd.concat(rows, ignore_index=True)
    logger.info(f"  damage events in scope: {len(full):,}")
    return full


def state_for_game(game_id, kills_g, team_lookup, name_to_hash,
                   damage_g=None, heals_g=None, downs_g=None):
    """For one game, walk all events in time order maintaining per-player HP
    (initialized at HP_INITIAL, capped at HP_HARD_CAP). At each kill event,
    snapshot every team's state including team_HP_sum (sum of HP across alive
    teammates). Returns state rows + per-team summary.
    """
    if kills_g.empty:
        return [], {}

    players = set(kills_g["attacker_hash"].dropna()) | set(kills_g["victim_hash"].dropna())
    player_to_team = {p: team_lookup.get((game_id, p)) for p in players}
    rosters = {}
    for p, t in player_to_team.items():
        if t is None:
            continue
        rosters.setdefault(t, set()).add(p)
    if len(rosters) < 2:
        return [], {}

    teams = list(rosters)
    alive = {t: set(rosters[t]) for t in teams}
    kills_so_far = {t: 0 for t in teams}
    last_killed_ts = {t: None for t in teams}
    all_players = {q for r in rosters.values() for q in r}
    # EVO shield model: track body, shield, shield_max, and cumulative evo dmg.
    body_hp = {p: HP_INITIAL for p in all_players}
    shield_hp = {p: SHIELD_MAX_BY_TIER[0] for p in all_players}  # white at start
    shield_max = {p: SHIELD_MAX_BY_TIER[0] for p in all_players}
    evo_dmg = {p: 0 for p in all_players}

    def total_hp(p):
        return body_hp[p] + shield_hp[p]

    def apply_damage_to(victim, dmg):
        """Damage hits shield first, then body."""
        if victim not in body_hp:
            return
        remaining = dmg
        absorbed = min(shield_hp[victim], remaining)
        shield_hp[victim] -= absorbed
        remaining -= absorbed
        body_hp[victim] = max(0, body_hp[victim] - remaining)

    def update_evo(attacker, dmg_dealt):
        if attacker not in evo_dmg:
            return
        evo_dmg[attacker] += dmg_dealt
        new_tier = shield_tier_for(evo_dmg[attacker])
        new_max = SHIELD_MAX_BY_TIER[new_tier]
        if new_max > shield_max[attacker]:
            # Tier-up bonus: bump current shield up to new max (no carryover).
            shield_hp[attacker] = new_max
            shield_max[attacker] = new_max
    # Momentum trackers: rolling deques of (ts, value) and last-event ts per team.
    recent_dmg_dealt = {t: deque() for t in teams}     # (ts, dmg)
    recent_dmg_taken = {t: deque() for t in teams}     # (ts, dmg)
    recent_kills_q = {t: deque() for t in teams}       # ts only
    last_dmg_dealt_ts = {t: None for t in teams}
    # Positional state: last known x/y per player (from damage events). NaN
    # means we haven't observed this player's position yet.
    last_x = {p: float("nan") for p in all_players}
    last_y = {p: float("nan") for p in all_players}

    game_start_ts = int(kills_g["gametimestamp"].min())

    def trim(dq, ts, window):
        while dq and ts - dq[0][0] > window:
            dq.popleft()

    # Build a unified event timeline. (priority controls within-second order.)
    timeline = []
    for k in kills_g.itertuples(index=False):
        timeline.append((int(k.gametimestamp), 3, "kill", k))  # kill last
    if damage_g is not None and not damage_g.empty:
        for d in damage_g.itertuples(index=False):
            timeline.append((int(d.event_start_timestamp), 0, "damage", d))
    if heals_g is not None and not heals_g.empty:
        for h in heals_g.itertuples(index=False):
            timeline.append((int(h.gametimestamp), 1, "heal", h))
    if downs_g is not None and not downs_g.empty:
        for dn in downs_g.itertuples(index=False):
            timeline.append((int(dn.gametimestamp), 2, "down", dn))
    timeline.sort(key=lambda x: (x[0], x[1]))

    rows = []
    for ts, _prio, etype, payload in timeline:
        if etype == "damage":
            target_arr = payload.target_arr
            damage_arr = payload.damage_arr
            if target_arr is None or len(target_arr) == 0:
                continue
            atk_team = player_to_team.get(payload.player_hash)
            atk_hash = payload.player_hash
            # Update attacker position from this damage event.
            if atk_hash in last_x and pd.notna(payload.x_position):
                last_x[atk_hash] = float(payload.x_position)
                last_y[atk_hash] = float(payload.y_position)
            burst_total = 0
            for v_name, dmg in zip(target_arr, damage_arr):
                d_int = int(dmg)
                burst_total += d_int
                vh = name_to_hash.get((game_id, v_name))
                apply_damage_to(vh, d_int)
                vt = player_to_team.get(vh)
                if vt in recent_dmg_taken:
                    recent_dmg_taken[vt].append((ts, d_int))
            # Attacker's EVO progress accrues from the burst total.
            update_evo(atk_hash, burst_total)
            if atk_team in recent_dmg_dealt:
                recent_dmg_dealt[atk_team].append((ts, burst_total))
                last_dmg_dealt_ts[atk_team] = ts
        elif etype == "heal":
            ph = payload.player_hash
            if ph in body_hp:
                shield_hp[ph] = min(shield_max[ph],
                                    shield_hp[ph] + int(payload.shield_restore))
                body_hp[ph] = min(HP_INITIAL,
                                  body_hp[ph] + int(payload.health_restore))
        elif etype == "down":
            vh = payload.victim_hash
            if vh in body_hp:
                body_hp[vh] = 0
                shield_hp[vh] = 0
        elif etype == "kill":
            event_id = int(payload.event_id)
            attacker = payload.attacker_hash
            victim = payload.victim_hash
            atk_team = player_to_team.get(attacker)
            vic_team = player_to_team.get(victim)
            if atk_team in kills_so_far:
                kills_so_far[atk_team] += 1
                recent_kills_q[atk_team].append(ts)
            if vic_team in alive and victim in alive[vic_team]:
                alive[vic_team].discard(victim)
                if not alive[vic_team]:
                    last_killed_ts[vic_team] = ts
            if victim in body_hp:
                body_hp[victim] = 0
                shield_hp[victim] = 0
            n_teams_alive = sum(1 for t in teams if alive[t])
            leader_kills = max(kills_so_far.values())
            # Pre-compute team centroids (mean of alive players' last positions).
            centroids = {}
            for t in teams:
                pts = [(last_x[p], last_y[p]) for p in alive[t]
                       if not np.isnan(last_x[p])]
                if not pts:
                    centroids[t] = (np.nan, np.nan, np.nan)
                    continue
                xs = np.array([p[0] for p in pts])
                ys = np.array([p[1] for p in pts])
                cx, cy = float(xs.mean()), float(ys.mean())
                spread = float(np.sqrt(((xs - cx) ** 2 + (ys - cy) ** 2).mean()))
                centroids[t] = (cx, cy, spread)
            for t in teams:
                trim(recent_dmg_dealt[t], ts, DMG_DEALT_WINDOW_S)
                trim(recent_dmg_taken[t], ts, DMG_TAKEN_WINDOW_S)
                while recent_kills_q[t] and ts - recent_kills_q[t][0] > KILLS_WINDOW_S:
                    recent_kills_q[t].popleft()
                team_hp_sum = sum(total_hp(p) for p in alive[t])
                team_dmg_dealt_30s = sum(d for _, d in recent_dmg_dealt[t])
                team_dmg_taken_30s = sum(d for _, d in recent_dmg_taken[t])
                team_kills_60s = len(recent_kills_q[t])
                if last_dmg_dealt_ts[t] is None:
                    time_since_dmg = TIME_SINCE_DMG_CAP
                else:
                    time_since_dmg = min(TIME_SINCE_DMG_CAP, ts - last_dmg_dealt_ts[t])
                cx, cy, spread = centroids[t]
                # Distance to nearest other ALIVE team's centroid.
                if np.isnan(cx):
                    dist_nearest = np.nan
                else:
                    others = [(ox, oy) for ot, (ox, oy, _) in centroids.items()
                              if ot != t and alive[ot] and not np.isnan(ox)]
                    if others:
                        dists = [np.sqrt((cx - ox) ** 2 + (cy - oy) ** 2)
                                 for ox, oy in others]
                        dist_nearest = float(min(dists))
                    else:
                        dist_nearest = np.nan
                rows.append({
                    "game_id": game_id,
                    "event_id": event_id,
                    "ts": ts,
                    "time_in_game_s": ts - game_start_ts,
                    "team": t,
                    "n_alive_team": len(alive[t]),
                    "kills_so_far_team": kills_so_far[t],
                    "n_teams_alive": n_teams_alive,
                    "kills_minus_leader": kills_so_far[t] - leader_kills,
                    "team_HP_sum": team_hp_sum,
                    "team_dmg_dealt_last_30s": team_dmg_dealt_30s,
                    "team_dmg_taken_last_30s": team_dmg_taken_30s,
                    "team_kills_last_60s": team_kills_60s,
                    "time_since_last_dmg_dealt_s": time_since_dmg,
                    "team_centroid_x": cx,
                    "team_centroid_y": cy,
                    "team_spread": spread,
                    "dist_to_nearest_alive_team": dist_nearest,
                    "atk_team": atk_team,
                    "vic_team": vic_team,
                })

    # Per-team summary. Teams with no last_killed_ts survived (highest rank).
    # Rank teams by (alive_at_end desc, last_killed_ts desc): teams still
    # alive at game end get rank 1; among eliminated teams, latest-eliminated
    # is rank n_alive_at_end + 1, etc.
    final_kills = dict(kills_so_far)
    eliminated = sorted(
        [(t, last_killed_ts[t]) for t in teams if last_killed_ts[t] is not None],
        key=lambda x: -x[1],  # latest first
    )
    survivors = [t for t in teams if last_killed_ts[t] is None]
    placements = {}
    rank = 1
    for t in survivors:
        placements[t] = rank
    if survivors:
        rank = len(survivors) + 1
    for t, _ts in eliminated:
        placements[t] = rank
        rank += 1
    summary = {
        t: {"final_kills": final_kills[t], "final_placement_rank": placements[t]}
        for t in teams
    }
    return rows, summary


def main():
    parser = ArgumentParser()
    parser.add_argument("--kills", default=KILL_EVENTS)
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--game-list", default=GAME_LIST)
    parser.add_argument("--year", type=int, default=5,
                        help="ALGS year to filter (Y5 default for Phase 0).")
    parser.add_argument("--out", default=OUT_PARQUET)
    args = parser.parse_args()

    logger.info(f"Loading {args.kills}...")
    kills = pd.read_parquet(args.kills)

    logger.info(f"Loading {args.game_list} and filtering to Y{args.year}...")
    games = pd.read_csv(args.game_list)
    games_y = games[games["tournament_year"] == args.year]
    logger.info(f"  Y{args.year} games: {len(games_y):,}")
    game_ids = set(games_y["game_id"])
    kills = kills[kills["game_id"].isin(game_ids)].copy()
    logger.info(f"  Y{args.year} kill events: {len(kills):,}")

    in_scope = sorted(set(kills["game_id"]))
    team_lookup, name_to_hash = build_team_lookup(args.damage_dir, game_ids=set(in_scope))

    logger.info(f"Loading {DOWN_EVENTS} and {HEAL_EVENTS}...")
    downs = pd.read_parquet(DOWN_EVENTS)
    downs = downs[downs["game_id"].isin(in_scope)]
    heals = pd.read_parquet(HEAL_EVENTS)
    heals = heals[heals["game_id"].isin(in_scope)]
    logger.info(f"  downs: {len(downs):,}, heals: {len(heals):,}")

    damage = load_damage_for_games(args.damage_dir, set(in_scope))
    damage_by_game = {gid: g for gid, g in damage.groupby("game_id", sort=False)}
    downs_by_game = {gid: g for gid, g in downs.groupby("game_id", sort=False)}
    heals_by_game = {gid: g for gid, g in heals.groupby("game_id", sort=False)}

    logger.info("Walking games and snapshotting state...")
    all_rows = []
    summaries = {}
    n_skipped = 0
    for i, gid in enumerate(in_scope):
        kills_g = kills[kills["game_id"] == gid]
        rows, summary = state_for_game(
            gid, kills_g, team_lookup, name_to_hash,
            damage_g=damage_by_game.get(gid),
            heals_g=heals_by_game.get(gid),
            downs_g=downs_by_game.get(gid),
        )
        if not rows:
            n_skipped += 1
            continue
        all_rows.extend(rows)
        summaries[gid] = summary
        if (i + 1) % 100 == 0:
            logger.info(f"  {i + 1}/{len(in_scope)} games, {len(all_rows):,} state rows")

    logger.info(f"Total state rows: {len(all_rows):,} (skipped {n_skipped} games)")

    state = pd.DataFrame(all_rows)
    # Attach per-team targets (final_kills, final_placement_rank) from summaries.
    flat_targets = []
    for gid, per_team in summaries.items():
        for t, vals in per_team.items():
            flat_targets.append({"game_id": gid, "team": t, **vals})
    targets = pd.DataFrame(flat_targets)
    state = state.merge(targets, on=["game_id", "team"], how="left")

    # Attach tournament metadata for downstream train/val/test split by tournament.
    meta_cols = ["tournament_full_name", "tournament_name", "tournament_split",
                 "tournament_region", "game_timestamp"]
    state = state.merge(games_y[["game_id"] + meta_cols],
                        on="game_id", how="left")

    logger.info(f"Final placement distribution:")
    pl = targets["final_placement_rank"].value_counts().sort_index()
    logger.info(f"\n{pl.head(25).to_string()}")
    logger.info(f"\nFinal kills distribution: {targets['final_kills'].describe().round(2).to_dict()}")
    logger.info(f"Tournaments in scope: {state['tournament_full_name'].nunique()}")

    state.to_parquet(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
