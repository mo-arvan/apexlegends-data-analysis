"""Phase 1: build the canonical engagement / kill-records table.

Reads damage events, downs, and heals; uses the state-based engagement
definition (HP window with idle timeout) chosen in Phase 0; emits one row
per engagement with both single-attacker derived columns and a
multi-attacker contributors array.

Each row covers ONE victim's continuous HP-out-of-max window, regardless of
how many attackers contributed. The contributors array lets downstream
analyses pick the slice they need (single-attacker for empirical eTTK,
multi-attacker preserved for clustering).

Output:
  data/kill_records.parquet
"""

import json
import logging
import os
from argparse import ArgumentParser
from collections import Counter

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DAMAGE_DIR = "data/tournament_damage_events"
DOWNS_PARQUET = "data/down_events.parquet"
HEALS_PARQUET = "data/heal_events.parquet"
HASH_TO_NAME_JSON = "data/player_to_hash.json"
OUT_PARQUET = "data/kill_records.parquet"

HP_HARD_CAP = 225
HP_INITIAL = 100
IDLE_TIMEOUT = 30

# Canonical Apex max-HP tiers (no shield, white/blue/purple body, +/- helmet
# rounding). The engagement walker can latch onto a transient mid-fight HP
# value as "max HP seen"; we snap to the nearest tier at finalization to drop
# that noise (~14% of rows pre-snap).
HP_TIERS = (100, 125, 150, 175, 200, 225)

# Things that show up as `top_attacker_weapon` but are not gun balance
# signal. Engagements where one of these tops the contributor list are
# dropped entirely from the kill_records output.
NON_WEAPONS = {
    "Frag Grenade", "Breach Charge", "Arc Star", "Thermite Grenade",
    "Explosive Arrow", "Stinger Bolt",
    "mp_weapon_bubble_bunker", "mp_weapon_charge_gauntlet",
    "Electrified Door", "Minigun",
    "Sniper's Mark", "Honorable Fisticuffs", "Whistler", "Tracker Dart", "Crushed",
}

# Drop ranges past this; observed >500m hits are almost all map-edge or
# hazard-attribution artifacts (Charge Rifle's real engagements stay well
# under this).
RANGE_CAP_M = 500.0


def snap_to_hp_tier(hp):
    return min(HP_TIERS, key=lambda t: abs(t - hp))


def primary_victim_for_burst(target_arr, damage_arr):
    if target_arr is None or len(target_arr) == 0:
        return None, 0
    if damage_arr is None or len(damage_arr) != len(target_arr):
        damage_arr = [1] * len(target_arr)
    by_victim = {}
    for v, d in zip(target_arr, damage_arr):
        by_victim[v] = by_victim.get(v, 0) + (d or 0)
    if not by_victim:
        return None, 0
    top = max(by_victim.items(), key=lambda kv: kv[1])
    return top[0], top[1]


def explode_bursts(damage_df):
    """Reduce each burst to (attacker, primary_victim, weapon, start_ts,
    end_ts, damage, shots_hit, ammo_used, distance). The end_ts is
    start_ts + event_duration so multi-second bursts contribute their full
    span to engagement timing.
    """
    if damage_df.empty:
        return pd.DataFrame(columns=["game_id", "attacker_hash", "victim_name",
                                     "weapon", "burst_start_ts", "burst_end_ts",
                                     "damage", "shots_hit", "ammo_used", "distance"])
    rows = []
    for r in damage_df.itertuples(index=False):
        primary_victim, primary_damage = primary_victim_for_burst(
            r.target_arr, r.damage_arr
        )
        if primary_victim is None:
            continue
        ammo = r.ammo_used
        start_ts = int(r.event_start_timestamp)
        # event_duration is in seconds; default to 0 if missing.
        duration = int(r.event_duration) if pd.notna(r.event_duration) else 0
        rows.append((
            r.game_id, r.player_hash, primary_victim, r.weapon_name,
            start_ts, start_ts + duration,
            int(primary_damage), int(r.shots_hit),
            int(ammo) if pd.notna(ammo) else None,
            float(r.distance) if pd.notna(r.distance) else None,
        ))
    return pd.DataFrame(rows, columns=["game_id", "attacker_hash", "victim_name",
                                       "weapon", "burst_start_ts", "burst_end_ts",
                                       "damage", "shots_hit", "ammo_used", "distance"])


def engagements_for_victim(victim, dmg_grp, heals_v, downs_v,
                           idle_timeout=IDLE_TIMEOUT):
    """State-based engagement walker for one victim. Returns a list of
    engagement dicts, each with full contributor breakdown."""
    events = []
    for b in dmg_grp.itertuples(index=False):
        events.append((b.burst_start_ts, "damage", {
            "damage": b.damage, "attacker": b.attacker_hash,
            "weapon": b.weapon, "shots_hit": b.shots_hit,
            "ammo_used": b.ammo_used, "distance": b.distance,
            "burst_end_ts": b.burst_end_ts,
        }))
    if heals_v is not None and not heals_v.empty:
        for h in heals_v.itertuples(index=False):
            events.append((h.gametimestamp, "heal",
                           h.shield_restore + h.health_restore))
    if downs_v is not None and not downs_v.empty:
        for d in downs_v.itertuples(index=False):
            events.append((d.gametimestamp, "down", d.attacker_hash))
    events.sort(key=lambda x: x[0])

    out = []
    hp = HP_INITIAL
    max_hp_seen = HP_INITIAL

    cur = None  # current open engagement state
    last_damage_ts = None

    def open_engagement(ts):
        return {
            "start_ts": ts,
            "end_ts": ts,
            "victim_hp_at_start": hp,
            "max_hp_seen_at_start": max_hp_seen,
            "contributors": {},  # attacker_hash -> agg dict
            "n_bursts": 0,
            "ended_by": None,
        }

    def attribute_burst(state, payload, ts):
        atk = payload["attacker"]
        burst_end = payload["burst_end_ts"]
        agg = state["contributors"].setdefault(atk, {
            "attacker_hash": atk,
            "weapons_damage": Counter(),
            "damage": 0,
            "shots_hit": 0,
            "ammo_used": 0,
            "first_hit_ts": ts,
            "last_hit_ts": burst_end,
            "n_bursts": 0,
            "ranges": [],
        })
        agg["damage"] += payload["damage"]
        agg["weapons_damage"][payload["weapon"]] += payload["damage"]
        agg["shots_hit"] += payload["shots_hit"]
        if payload["ammo_used"] is not None:
            agg["ammo_used"] += payload["ammo_used"]
        agg["last_hit_ts"] = max(agg["last_hit_ts"], burst_end)
        agg["n_bursts"] += 1
        if payload["distance"] is not None:
            agg["ranges"].append(payload["distance"])
        state["n_bursts"] += 1
        state["end_ts"] = max(state["end_ts"], burst_end)

    def close(state, end_ts, reason):
        state["end_ts"] = end_ts
        state["ended_by"] = reason
        out.append(state)

    for ts, ev_type, payload in events:
        # Idle close before processing the next event.
        if cur is not None and last_damage_ts is not None and ts - last_damage_ts > idle_timeout:
            close(cur, last_damage_ts, "idle")
            cur = None
            last_damage_ts = None

        if ev_type == "damage":
            if cur is None:
                cur = open_engagement(ts)
            attribute_burst(cur, payload, ts)
            hp = max(0, hp - payload["damage"])
            last_damage_ts = ts
        elif ev_type == "heal":
            hp = min(HP_HARD_CAP, hp + payload)
            max_hp_seen = max(max_hp_seen, hp)
            if cur is not None and hp >= max_hp_seen:
                close(cur, ts, "healed")
                cur = None
                last_damage_ts = None
        elif ev_type == "down":
            if cur is not None:
                close(cur, ts, "down")
                cur = None
                last_damage_ts = None
            hp = max_hp_seen  # post-down: assume restored

    if cur is not None:
        close(cur, last_damage_ts if last_damage_ts is not None else cur["start_ts"], "idle")

    return out


def finalize_engagement(eng, game_id, victim, victim_hash, hash_to_name,
                        tournament_meta):
    """Convert raw engagement state into the canonical row schema."""
    contributors = []
    for atk_hash, agg in eng["contributors"].items():
        weapons_damage = agg["weapons_damage"]
        top_weapon = weapons_damage.most_common(1)[0][0] if weapons_damage else None
        contributors.append({
            "attacker_hash": atk_hash,
            "attacker_name": hash_to_name.get(atk_hash),
            "top_weapon": top_weapon,
            "weapons_damage": dict(weapons_damage),
            "damage": agg["damage"],
            "shots_hit": agg["shots_hit"],
            "ammo_used": agg["ammo_used"],
            "n_bursts": agg["n_bursts"],
            "first_hit_ts": agg["first_hit_ts"],
            "last_hit_ts": agg["last_hit_ts"],
            "median_distance": (
                float(pd.Series(agg["ranges"]).median())
                if agg["ranges"] else None
            ),
        })

    total_damage = sum(c["damage"] for c in contributors)
    contributors.sort(key=lambda c: c["damage"], reverse=True)
    top = contributors[0] if contributors else None

    top_range = top["median_distance"] if top else None
    if top_range is not None and top_range > RANGE_CAP_M:
        top_range = None  # outlier; drop rather than cap so it doesn't bias percentiles

    return {
        "game_id": game_id,
        "victim_name": victim,
        "victim_hash": victim_hash,
        "start_ts": eng["start_ts"],
        "end_ts": eng["end_ts"],
        "duration_s": eng["end_ts"] - eng["start_ts"],
        "ended_by": eng["ended_by"],
        "downed": eng["ended_by"] == "down",
        "victim_hp_at_start": eng["victim_hp_at_start"],
        "max_hp_seen_at_start": snap_to_hp_tier(eng["max_hp_seen_at_start"]),
        "total_damage": total_damage,
        "n_attackers": len(contributors),
        "n_bursts": eng["n_bursts"],
        # Derived single-attacker view
        "top_attacker_hash": top["attacker_hash"] if top else None,
        "top_attacker_name": top["attacker_name"] if top else None,
        "top_attacker_weapon": top["top_weapon"] if top else None,
        "top_attacker_damage": top["damage"] if top else 0,
        "top_attacker_share": (top["damage"] / total_damage) if (top and total_damage > 0) else 0,
        "top_attacker_observed_eTTK": (
            (top["last_hit_ts"] - top["first_hit_ts"]) if top else None
        ),
        "top_attacker_median_distance": top_range,
        # Multi-attacker contributors as JSON string (parquet-friendly)
        "contributors_json": json.dumps(contributors, default=str),
        # Tournament metadata
        **tournament_meta,
    }


def build_records_for_game(game_id, dmg_df_game, downs_game, heals_game,
                           hash_to_name, victim_hash_lookup, tournament_meta):
    """Return list of finalized engagement record dicts for one game."""
    bursts = explode_bursts(dmg_df_game)
    if bursts.empty:
        return []
    heals_by_victim = ({v: g for v, g in heals_game.groupby("victim_name", sort=False)}
                       if not heals_game.empty else {})
    downs_by_victim = ({v: g for v, g in downs_game.groupby("victim_name", sort=False)}
                       if not downs_game.empty else {})

    records = []
    for victim, vd in bursts.groupby("victim_name", sort=False):
        engs = engagements_for_victim(
            victim, vd, heals_by_victim.get(victim), downs_by_victim.get(victim),
        )
        victim_hash = victim_hash_lookup.get(victim)
        for eng in engs:
            records.append(
                finalize_engagement(eng, game_id, victim, victim_hash,
                                    hash_to_name, tournament_meta)
            )
    return records


def main():
    parser = ArgumentParser()
    parser.add_argument("--damage-dir", default=DAMAGE_DIR)
    parser.add_argument("--downs", default=DOWNS_PARQUET)
    parser.add_argument("--heals", default=HEALS_PARQUET)
    parser.add_argument("--out", default=OUT_PARQUET)
    parser.add_argument("--max-games", type=int, default=None)
    args = parser.parse_args()

    logger.info("Loading hash->name map...")
    with open(HASH_TO_NAME_JSON) as fh:
        hash_to_name = json.load(fh)

    logger.info("Loading downs and heals...")
    downs = pd.read_parquet(args.downs)
    heals = pd.read_parquet(args.heals)
    logger.info(f"  downs: {len(downs):,}, heals: {len(heals):,}")

    logger.info("Loading damage events...")
    damage_files = sorted(f for f in os.listdir(args.damage_dir) if f.endswith(".parquet"))
    all_damage = []
    for f in damage_files:
        df = pd.read_parquet(os.path.join(args.damage_dir, f))
        for h, n in zip(df["player_hash"], df["player_name"]):
            if h not in hash_to_name:
                hash_to_name[h] = n
        all_damage.append(df)
    damage = pd.concat(all_damage, ignore_index=True)
    logger.info(f"  damage events: {len(damage):,}")

    # Reverse map: name -> hash (for victim_hash lookup; victims appear by name in damage events)
    name_to_hash = {n: h for h, n in hash_to_name.items()}

    # Annotate downs with name (for filtering by victim_name in engagement walker)
    downs["victim_name"] = downs["victim_hash"].map(hash_to_name)
    heals["player_name"] = heals["player_hash"].map(hash_to_name)
    heals = heals.rename(columns={"player_name": "victim_name"}).dropna(subset=["victim_name"])

    games = damage["game_id"].unique().tolist()
    if args.max_games is not None:
        games = games[:args.max_games]
    logger.info(f"Processing {len(games)} games...")

    # Pre-group per-game
    damage_by_game = {gid: g for gid, g in damage.groupby("game_id", sort=False)}
    downs_by_game = {gid: g for gid, g in downs.groupby("game_id", sort=False)}
    heals_by_game = {gid: g for gid, g in heals.groupby("game_id", sort=False)}
    empty_downs = downs.iloc[0:0]
    empty_heals = heals.iloc[0:0]

    # Build per-game tournament metadata from the damage table (any row works)
    META_COLS = ["tournament_full_name", "tournament_name", "tournament_year",
                 "tournament_split", "tournament_region", "tournament_day",
                 "game_map", "game_timestamp", "game_num"]
    meta_by_game = (damage.drop_duplicates("game_id")
                    .set_index("game_id")[META_COLS]
                    .to_dict(orient="index"))

    all_records = []
    for i, game_id in enumerate(games):
        gd = damage_by_game.get(game_id)
        if gd is None or gd.empty:
            continue
        all_records.extend(build_records_for_game(
            game_id, gd,
            downs_by_game.get(game_id, empty_downs),
            heals_by_game.get(game_id, empty_heals),
            hash_to_name, name_to_hash,
            meta_by_game.get(game_id, {}),
        ))
        if (i + 1) % 200 == 0:
            logger.info(f"  processed {i + 1}/{len(games)} games, {len(all_records):,} engagements")

    df = pd.DataFrame(all_records)
    n_pre = len(df)
    logger.info(f"Total engagements (pre-filter): {n_pre:,}")

    if not df.empty:
        # Drop walker-noise rows: started at 0 HP (target was already dead).
        before = len(df)
        df = df[df["victim_hp_at_start"] > 0]
        logger.info(f"  drop victim_hp_at_start==0: -{before - len(df):,}")

        # Drop unmapped victims; observed to be ~all non-down engagements
        # (likely shoutcaster spectator-overlay duplicates) and only inflate
        # the usage denominator for kill_conversion.
        before = len(df)
        df = df[df["victim_hash"].notna()]
        logger.info(f"  drop null victim_hash: -{before - len(df):,}")

        # Drop engagements led by non-weapons (grenades, abilities, hazards).
        before = len(df)
        df = df[~df["top_attacker_weapon"].isin(NON_WEAPONS)]
        logger.info(f"  drop NON_WEAPONS top weapon: -{before - len(df):,}")

        n_down = df["downed"].sum()
        logger.info(f"Final engagements: {len(df):,} (kept {len(df)/n_pre:.1%})")
        logger.info(f"  ended in down: {n_down:,} ({n_down / len(df):.1%})")
        logger.info(f"  ended_by distribution: {df['ended_by'].value_counts().to_dict()}")
        logger.info(f"  multi-attacker: {(df['n_attackers'] > 1).sum():,}")

    df.to_parquet(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
