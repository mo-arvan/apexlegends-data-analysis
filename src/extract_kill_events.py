"""Extract playerKilled events from per-game pkls into a single parquet.

A "kill" is the elimination of a player (the post-down finish, or a direct
elim if they were already downed). It is distinct from a "down": a downed
player can be revived; a killed player is permanently out for that round
(modulo respawn beacons, which are rare and handled separately).

Each kill is logged from three perspectives in the raw scrape (victim,
attacker, awardedTo). We dedup by (game_id, event_id) and consolidate into
one row per elimination.

The WPA model needs eliminations to track team-alive state and final kill
counts. Bleed Out kills (player downed earlier and never revived) are the
ones that actually move the alive-state counter. Direct-weapon kills mean
the player was either already downed or got insta-eliminated.

Output:
  data/kill_events.parquet   one row per (game_id, event_id) elimination
"""

import logging
import os
import pickle
import re
from argparse import ArgumentParser

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EVENTS_DIR = "data/events"
OUT_PARQUET = "data/kill_events.parquet"

KILL_TEXT_RE = re.compile(r"with\s+(.+?)\s+[—-]\s+([\d.]+)\s*m\s*$")


def parse_weapon_and_distance(event_text):
    if not isinstance(event_text, str):
        return None, None
    m = KILL_TEXT_RE.search(event_text.strip())
    if not m:
        return None, None
    weapon = m.group(1).strip()
    try:
        distance = float(m.group(2))
    except (TypeError, ValueError):
        return weapon, None
    return weapon, distance


def kills_from_game(game_id, events_list):
    if not events_list:
        return []
    df = pd.concat(events_list, ignore_index=True)
    if "event_type" not in df.columns:
        return []
    kills = df[df["event_type"] == "playerKilled"]
    if kills.empty:
        return []

    out = []
    for event_id, group in kills.groupby("event_id"):
        attacker_row = group[group["target"] == "attacker"]
        victim_row = group[group["target"] == "victim"]
        attacker_hash = attacker_row["player_hash"].iloc[0] if not attacker_row.empty else None
        attacker_x = int(attacker_row["x_position"].iloc[0]) if not attacker_row.empty else None
        attacker_y = int(attacker_row["y_position"].iloc[0]) if not attacker_row.empty else None
        victim_hash = victim_row["player_hash"].iloc[0] if not victim_row.empty else None
        victim_x = int(victim_row["x_position"].iloc[0]) if not victim_row.empty else None
        victim_y = int(victim_row["y_position"].iloc[0]) if not victim_row.empty else None
        first = group.iloc[0]
        weapon, distance = parse_weapon_and_distance(first["event_text"])
        # Bleed Out flag: kill was a delayed finish from an earlier down.
        is_bleed_out = isinstance(first["event_text"], str) and "Bleed Out" in first["event_text"]
        out.append({
            "game_id": game_id,
            "event_id": int(event_id),
            "gametimestamp": int(first["event_timestamp"]),
            "event_time_label": first["event_time"],
            "attacker_hash": attacker_hash,
            "victim_hash": victim_hash,
            "attacker_x": attacker_x,
            "attacker_y": attacker_y,
            "victim_x": victim_x,
            "victim_y": victim_y,
            "weapon": weapon,
            "distance_m": distance,
            "is_bleed_out": is_bleed_out,
            "event_text": first["event_text"],
        })
    return out


def main():
    parser = ArgumentParser()
    parser.add_argument("--events-dir", default=EVENTS_DIR)
    parser.add_argument("--out", default=OUT_PARQUET)
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(args.events_dir) if f.endswith(".pkl"))
    logger.info(f"Reading {len(files)} per-game pkls from {args.events_dir}")

    rows = []
    for i, fname in enumerate(files):
        game_id = fname[:-4]
        try:
            with open(os.path.join(args.events_dir, fname), "rb") as fh:
                game = pickle.load(fh)
        except Exception as exc:
            logger.warning(f"  {fname}: {exc}")
            continue
        rows.extend(kills_from_game(game_id, game.get("events", [])))
        if (i + 1) % 200 == 0:
            logger.info(f"  processed {i + 1}/{len(files)} games, {len(rows):,} kills so far")

    df = pd.DataFrame(rows)
    logger.info(f"Total kills extracted: {len(df):,} from {df['game_id'].nunique()} games")
    if df.empty:
        logger.error("No kills extracted; aborting write")
        return
    n_bleed = df["is_bleed_out"].sum()
    logger.info(f"  Bleed Out kills: {n_bleed:,} ({n_bleed / len(df):.1%})")
    n_with_weapon = df["weapon"].notna().sum()
    logger.info(f"  parseable weapon+distance: {n_with_weapon:,} ({n_with_weapon / len(df):.1%})")

    df.to_parquet(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
