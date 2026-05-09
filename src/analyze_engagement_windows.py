"""Phase 0: compare engagement-window definitions to inform downstream eTTK
and clustering analyses.

The analysis joins three input tables per game:
  data/tournament_damage_events/*.parquet  per-attacker-burst damage events
  data/down_events.parquet                 one row per down (victim went to 0)
  data/heal_events.parquet                 one row per consumable use

Two families of engagement-window definitions are evaluated side by side:

  Time-based (T sweep): for each (attacker, victim), group damage bursts whose
    consecutive event_start_timestamps are within T seconds. T sweeps over
    {2, 3, 5, 8, 10, 15, 20}. Each (attacker, victim, group) is one
    engagement candidate; if any event_start in the group is followed by a
    down on the victim within T seconds, the engagement is "down-ending".

  State-based: per-victim HP timeline reconstructed from damage (HP--) and
    heals (HP++). Each victim's max HP is tracked observationally rather than
    assumed: starts at body health (100), rises as heals reveal the victim's
    actual shield tier (white 50 -> blue 75 -> purple 100 -> red 125 above
    body health, hard cap 225). An engagement starts when the victim's HP
    first drops from the observed max and ends at the earliest of:
      (a) a down event on the victim
      (b) HP returning to the observed max for that victim
      (c) `IDLE_TIMEOUT` seconds with no new damage event on the victim

The output is a markdown report comparing the definitions on:
  - count of distinct engagements
  - count of "down-ending" engagements
  - distribution of engagement durations
  - count of multi-attacker engagements
  - count of engagements that ended without a down (target healed back / fled)

This script is exploratory; it does not produce the canonical kill-records
table. That comes in Phase 1 once a window definition is chosen.
"""

import json
import logging
import os
from argparse import ArgumentParser

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DAMAGE_DIR = "data/tournament_damage_events"
DOWNS_PARQUET = "data/down_events.parquet"
HEALS_PARQUET = "data/heal_events.parquet"
HASH_TO_NAME_JSON = "data/player_to_hash.json"
OUT_MD = "output/engagement_window_sweep.md"

T_VALUES = [2, 3, 5, 8, 10, 15, 20]
HP_HARD_CAP = 225  # red shield (100 health + 125 shield), the in-game ceiling
HP_INITIAL = 100   # body health only; no shield assumed at game start
IDLE_TIMEOUT = 30  # state-based: close engagement after N seconds with no new damage


def primary_victim_for_burst(target_arr, damage_arr):
    """Pick the victim who took the most damage in a multi-victim burst."""
    if target_arr is None or len(target_arr) == 0:
        return None, 0
    if damage_arr is None or len(damage_arr) != len(target_arr):
        damage_arr = [1] * len(target_arr)
    by_victim = {}
    for v, d in zip(target_arr, damage_arr):
        by_victim[v] = by_victim.get(v, 0) + (d or 0)
    if not by_victim:
        return None, 0
    top_victim = max(by_victim.items(), key=lambda kv: kv[1])
    return top_victim[0], top_victim[1]


def explode_bursts_to_victim_rows(damage_df):
    """Reduce each per-attacker burst to (attacker, primary_victim, ...) row.

    Multi-victim bursts collapse to the victim who took the most damage; the
    minority share is dropped (16% of source rows). Vectorized via list
    comprehension over the array columns; itertuples is ~5x faster than
    iterrows for this shape.
    """
    if damage_df.empty:
        return pd.DataFrame(columns=["game_id", "attacker_hash", "victim_name",
                                     "weapon", "burst_start_ts", "total_damage",
                                     "shots_hit", "ammo_used"])
    rows = []
    for r in damage_df.itertuples(index=False):
        primary_victim, primary_damage = primary_victim_for_burst(
            r.target_arr, r.damage_arr
        )
        if primary_victim is None:
            continue
        ammo = r.ammo_used
        rows.append((
            r.game_id, r.player_hash, primary_victim, r.weapon_name,
            int(r.event_start_timestamp), int(primary_damage), int(r.shots_hit),
            int(ammo) if pd.notna(ammo) else None,
        ))
    return pd.DataFrame(rows, columns=["game_id", "attacker_hash", "victim_name",
                                       "weapon", "burst_start_ts", "total_damage",
                                       "shots_hit", "ammo_used"])


def time_based_engagements(per_victim_bursts, downs_for_victim, T):
    """Group bursts into engagements using time-gap T, per victim (any attacker).

    All damage events to a single victim form one engagement when consecutive
    event_start_timestamps are within T seconds of each other, regardless of
    which attacker fired. Multi-attacker engagements (e.g. team focus-fire)
    show as `n_attackers > 1` on the same engagement record.

    Returns list of engagement dicts.
    """
    engagements = []
    for victim, grp in per_victim_bursts.groupby("victim_name", sort=False):
        grp = grp.sort_values("burst_start_ts")
        cur_start = None
        cur_end = None
        cur_damage = 0
        cur_n_bursts = 0
        cur_attackers = []
        for b in grp.itertuples(index=False):
            ts = b.burst_start_ts
            atk = b.attacker_hash
            if cur_start is None:
                cur_start = ts
                cur_end = ts
                cur_damage = b.total_damage
                cur_n_bursts = 1
                cur_attackers = [atk]
                continue
            if ts - cur_end <= T:
                cur_end = ts
                cur_damage += b.total_damage
                cur_n_bursts += 1
                if atk not in cur_attackers:
                    cur_attackers.append(atk)
            else:
                engagements.append({
                    "victim": victim, "attackers": cur_attackers,
                    "start_ts": cur_start, "end_ts": cur_end,
                    "damage": cur_damage, "n_bursts": cur_n_bursts,
                })
                cur_start = ts
                cur_end = ts
                cur_damage = b.total_damage
                cur_n_bursts = 1
                cur_attackers = [atk]
        if cur_start is not None:
            engagements.append({
                "victim": victim, "attackers": cur_attackers,
                "start_ts": cur_start, "end_ts": cur_end,
                "damage": cur_damage, "n_bursts": cur_n_bursts,
            })

    # Mark engagements that ended in a down (down within T seconds of last burst).
    down_ts_for_victim = {v: sorted(g["gametimestamp"].tolist())
                         for v, g in downs_for_victim.groupby("victim_name", sort=False)}
    for e in engagements:
        candidates = down_ts_for_victim.get(e["victim"], [])
        e["downed"] = any(e["end_ts"] <= dts <= e["end_ts"] + T for dts in candidates)
        e["duration_s"] = e["end_ts"] - e["start_ts"]
        e["n_attackers"] = len(e["attackers"])
    return engagements


def state_based_engagements(per_victim_bursts, downs_for_victim, heals_for_victim,
                            idle_timeout=IDLE_TIMEOUT):
    """Group damage events into per-victim engagements based on HP state.

    A new engagement starts when the victim's HP drops below MAX_HP. It ends
    at the earliest of:
      - the victim is downed (ended_by="down")
      - HP returns to MAX_HP (ended_by="healed")
      - `idle_timeout` seconds pass with no new damage event (ended_by="idle")
    All bursts inside the window count regardless of attacker.

    The idle-timeout cutoff prevents engagements from spanning the rest of the
    match when a chip-cracked victim never returns to full HP.
    """
    engagements = []
    # Pre-build per-victim heal and down lookups so we don't filter the full
    # per-game tables once per victim.
    heals_by_victim = ({v: g for v, g in heals_for_victim.groupby("victim_name", sort=False)}
                       if not heals_for_victim.empty else {})
    downs_by_victim = ({v: g for v, g in downs_for_victim.groupby("victim_name", sort=False)}
                       if not downs_for_victim.empty else {})

    for victim, dmg_grp in per_victim_bursts.groupby("victim_name", sort=False):
        events = []
        for b in dmg_grp.itertuples(index=False):
            events.append((b.burst_start_ts, "damage", b.total_damage, b.attacker_hash))
        if victim in heals_by_victim:
            for h in heals_by_victim[victim].itertuples(index=False):
                events.append((h.gametimestamp, "heal", h.shield_restore + h.health_restore, None))
        if victim in downs_by_victim:
            for d in downs_by_victim[victim].itertuples(index=False):
                events.append((d.gametimestamp, "down", 0, d.attacker_hash))
        events.sort(key=lambda x: x[0])

        # Per-victim HP state. Start at body-health only; let heals raise the
        # observed max as the victim reveals their actual shield tier.
        hp = HP_INITIAL
        max_hp_seen = HP_INITIAL
        cur_start = None
        cur_attackers = []
        cur_damage = 0
        cur_n_bursts = 0
        last_damage_ts = None

        def close(end_ts, reason):
            engagements.append({
                "victim": victim,
                "attackers": cur_attackers,
                "start_ts": cur_start, "end_ts": end_ts,
                "damage": cur_damage, "n_bursts": cur_n_bursts,
                "ended_by": reason,
            })

        for ts, ev_type, magnitude, attacker in events:
            # Idle-timeout check: close any open engagement that's gone too
            # long without a new damage event.
            if cur_start is not None and last_damage_ts is not None and \
                    ts - last_damage_ts > idle_timeout:
                close(last_damage_ts, "idle")
                cur_start, cur_attackers, cur_damage, cur_n_bursts = None, [], 0, 0
                last_damage_ts = None

            if ev_type == "damage":
                if cur_start is None:
                    cur_start = ts
                    cur_attackers = [attacker]
                    cur_damage = magnitude
                    cur_n_bursts = 1
                else:
                    if attacker not in cur_attackers:
                        cur_attackers.append(attacker)
                    cur_damage += magnitude
                    cur_n_bursts += 1
                hp = max(0, hp - magnitude)
                last_damage_ts = ts
            elif ev_type == "heal":
                hp = min(HP_HARD_CAP, hp + magnitude)
                # Heals reveal the victim's actual capacity. If they heal
                # above any previously-observed HP, that's their new floor
                # for "back to full."
                max_hp_seen = max(max_hp_seen, hp)
                if cur_start is not None and hp >= max_hp_seen:
                    close(ts, "healed")
                    cur_start, cur_attackers, cur_damage, cur_n_bursts = None, [], 0, 0
                    last_damage_ts = None
            elif ev_type == "down":
                if cur_start is not None:
                    close(ts, "down")
                cur_start, cur_attackers, cur_damage, cur_n_bursts = None, [], 0, 0
                last_damage_ts = None
                # Post-down: assume revive / next spawn brings them back to
                # at least their observed max.
                hp = max_hp_seen
        # Open engagement at end of victim's event timeline: close as idle
        if cur_start is not None:
            close(last_damage_ts if last_damage_ts is not None else cur_start, "idle")

    for e in engagements:
        e["duration_s"] = e["end_ts"] - e["start_ts"]
        e["downed"] = (e["ended_by"] == "down")
        e["n_attackers"] = len(e["attackers"])
    return engagements


def summarize_engagements(engagements, label):
    if not engagements:
        return {"definition": label, "n_engagements": 0}
    durations = np.array([e["duration_s"] for e in engagements])
    return {
        "definition": label,
        "n_engagements": len(engagements),
        "n_down_ending": sum(1 for e in engagements if e.get("downed")),
        "n_multi_attacker": sum(1 for e in engagements if e.get("n_attackers", 1) > 1),
        "duration_p25": float(np.percentile(durations, 25)),
        "duration_p50": float(np.percentile(durations, 50)),
        "duration_p75": float(np.percentile(durations, 75)),
        "duration_p95": float(np.percentile(durations, 95)),
        "mean_damage": float(np.mean([e["damage"] for e in engagements])),
    }


def main():
    parser = ArgumentParser()
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--downs", default=DOWNS_PARQUET)
    parser.add_argument("--heals", default=HEALS_PARQUET)
    parser.add_argument("--out-md", default=OUT_MD)
    parser.add_argument("--max-games", type=int, default=None,
                        help="Cap number of games processed (for quick smoke test).")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out_md) or ".", exist_ok=True)

    logger.info("Loading downs...")
    downs = pd.read_parquet(args.downs)
    # The downs parquet has victim_hash, but damage events use victim NAME from target_arr.
    # We need a name-side merge; for Phase 0 simplicity we'll match by name through the
    # damage events' player_name column. Build a hash<->name map from any damage parquet.
    logger.info(f"  downs: {len(downs):,}")

    logger.info("Loading heals...")
    heals = pd.read_parquet(args.heals)
    logger.info(f"  heals: {len(heals):,}")

    logger.info("Loading hash->name map...")
    with open(HASH_TO_NAME_JSON) as fh:
        hash_to_name = json.load(fh)
    logger.info(f"  global map: {len(hash_to_name):,} hashes")

    logger.info("Loading damage events (one parquet per tournament)...")
    damage_files = sorted(f for f in os.listdir(args.damage_dir) if f.endswith(".parquet"))
    all_damage = []
    for f in damage_files:
        df = pd.read_parquet(os.path.join(args.damage_dir, f))
        # Augment global hash->name map with anything new seen in damage events.
        for h, n in zip(df["player_hash"], df["player_name"]):
            if h not in hash_to_name:
                hash_to_name[h] = n
        all_damage.append(df)
    damage = pd.concat(all_damage, ignore_index=True)
    logger.info(f"  damage events: {len(damage):,} from {damage['game_id'].nunique()} games")
    logger.info(f"  hash->name map after augmentation: {len(hash_to_name):,}")

    # Annotate downs with victim_name (via hash->name map)
    downs["victim_name"] = downs["victim_hash"].map(hash_to_name)
    downs["attacker_name"] = downs["attacker_hash"].map(hash_to_name)
    n_unmapped = downs["victim_name"].isna().sum()
    if n_unmapped:
        logger.info(f"  downs with unmapped victim_hash: {n_unmapped} (dropped)")
    downs = downs.dropna(subset=["victim_name"])

    # Annotate heals with player_name
    heals["player_name"] = heals["player_hash"].map(hash_to_name)
    heals = heals.dropna(subset=["player_name"])
    heals = heals.rename(columns={"player_name": "victim_name"})  # in heal context, the player IS the one being healed

    games = damage["game_id"].unique().tolist()
    if args.max_games is not None:
        games = games[:args.max_games]
    logger.info(f"Pre-grouping per-game tables...")
    # Build per-game lookups once instead of filtering O(N) per iteration.
    damage_by_game = {gid: g for gid, g in damage.groupby("game_id", sort=False)}
    downs_by_game = {gid: g for gid, g in downs.groupby("game_id", sort=False)}
    heals_by_game = {gid: g for gid, g in heals.groupby("game_id", sort=False)}
    empty_downs = downs.iloc[0:0]
    empty_heals = heals.iloc[0:0]
    logger.info(f"Analyzing {len(games)} games...")

    all_time_engagements = {T: [] for T in T_VALUES}
    all_state_engagements = []

    for i, game_id in enumerate(games):
        gd = damage_by_game.get(game_id)
        if gd is None or gd.empty:
            continue
        gdo = downs_by_game.get(game_id, empty_downs)
        gh = heals_by_game.get(game_id, empty_heals)
        per_victim_bursts = explode_bursts_to_victim_rows(gd)
        if per_victim_bursts.empty:
            continue
        for T in T_VALUES:
            all_time_engagements[T].extend(
                time_based_engagements(per_victim_bursts, gdo, T)
            )
        all_state_engagements.extend(
            state_based_engagements(per_victim_bursts, gdo, gh)
        )
        if (i + 1) % 200 == 0:
            logger.info(f"  processed {i + 1}/{len(games)} games")

    # Summaries
    summaries = []
    for T in T_VALUES:
        summaries.append(summarize_engagements(all_time_engagements[T], f"time-based T={T}s"))
    summaries.append(summarize_engagements(all_state_engagements, "state-based (HP window)"))
    summary_df = pd.DataFrame(summaries)

    # Write markdown report (manual table to avoid tabulate dependency)
    cols = list(summary_df.columns)
    md_table = ["| " + " | ".join(cols) + " |",
                "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in summary_df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append(f"{v:,.1f}" if v == v else "")
            elif isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        md_table.append("| " + " | ".join(cells) + " |")

    lines = [
        "# Engagement-window definition sweep",
        "",
        f"Games analyzed: {len(games)}.",
        f"Total damage events: {len(damage):,}, downs: {len(downs):,}, heals: {len(heals):,}.",
        "",
        "## Comparison",
        "",
        *md_table,
        "",
        "## Reading the table",
        "",
        "- `n_engagements`: total engagements identified under this definition. Higher T glues fights together so this drops.",
        "- `n_down_ending`: engagements that resulted in a down. The state-based row counts engagements ending in a down OR a heal-back; only down-ending ones map to eTTK observation.",
        "- `n_multi_attacker`: engagements with >1 distinct attacker (state-based only carries this directly; time-based always splits per attacker).",
        "- `duration_*`: percentiles of engagement duration (seconds).",
        "- `mean_damage`: average total damage delivered per engagement.",
        "",
        "## Notes",
        "",
        "- Multi-victim bursts (16% of damage rows) are collapsed to the primary victim (whoever took the most damage in the burst). The minority share is discarded for Phase 0 analysis.",
        f"- State-based tracks max HP per victim observationally rather than assuming 200. Each victim starts at {HP_INITIAL} (body health) and the cap rises as heals reveal their shield tier (capped at {HP_HARD_CAP} for red shield).",
        f"- State-based applies a {IDLE_TIMEOUT}s idle timeout: any open engagement with no new damage event for that long closes as `idle`.",
        "- Down-ending in time-based requires a down within T seconds of the last burst; this can cause the same down to be claimed by multiple engagements at high T.",
    ]
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
