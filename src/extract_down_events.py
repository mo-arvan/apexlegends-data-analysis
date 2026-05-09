"""Extract playerDowned events from per-game pkls into a single parquet.

Each down is logged from multiple perspectives in the raw scrape (attacker
sees "Downed Y with Z", victim sees "Downed by X with Z"). We dedup by
(game_id, event_id) and consolidate the perspectives into one row per down,
carrying both attacker and victim hashes plus their positions.

The downstream eTTK-validation analysis needs downs (200 HP delivered), not
kills (the elimination, which can come later via bleed-out or finisher).
playerKilled events stay in the pkls; this extractor doesn't touch them.

Output:
  data/down_events.parquet   one row per (game_id, event_id) down
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
OUT_PARQUET = "data/down_events.parquet"

# Match "... with <weapon> — <distance>m" (em-dash is the literal separator).
DOWN_TEXT_RE = re.compile(r"with\s+(.+?)\s+[—-]\s+([\d.]+)\s*m\s*$")


def parse_weapon_and_distance(event_text):
    """Pull (weapon, distance_m) out of an event_text. Returns (None, None)
    if the text doesn't carry a parseable weapon-and-distance suffix
    (e.g., 'Bleed Out', 'The Ring' kills, malformed)."""
    if not isinstance(event_text, str):
        return None, None
    m = DOWN_TEXT_RE.search(event_text.strip())
    if not m:
        return None, None
    weapon = m.group(1).strip()
    try:
        distance = float(m.group(2))
    except (TypeError, ValueError):
        return weapon, None
    return weapon, distance


def downs_from_game(game_id, events_list):
    """Return a list of (one row per down) dicts for a single game."""
    if not events_list:
        return []
    df = pd.concat(events_list, ignore_index=True)
    if "event_type" not in df.columns:
        return []
    downs = df[df["event_type"] == "playerDowned"]
    if downs.empty:
        return []

    # Dedup by event_id; consolidate attacker + victim perspectives into one row.
    out = []
    for event_id, group in downs.groupby("event_id"):
        attacker_row = group[group["target"] == "attacker"]
        victim_row = group[group["target"] == "victim"]
        # If we don't have both perspectives, record what we have (rare).
        attacker_hash = attacker_row["player_hash"].iloc[0] if not attacker_row.empty else None
        attacker_x = int(attacker_row["x_position"].iloc[0]) if not attacker_row.empty else None
        attacker_y = int(attacker_row["y_position"].iloc[0]) if not attacker_row.empty else None
        victim_hash = victim_row["player_hash"].iloc[0] if not victim_row.empty else None
        victim_x = int(victim_row["x_position"].iloc[0]) if not victim_row.empty else None
        victim_y = int(victim_row["y_position"].iloc[0]) if not victim_row.empty else None
        # event_text and gametimestamp are identical across perspectives.
        first = group.iloc[0]
        weapon, distance = parse_weapon_and_distance(first["event_text"])
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
        rows.extend(downs_from_game(game_id, game.get("events", [])))
        if (i + 1) % 200 == 0:
            logger.info(f"  processed {i + 1}/{len(files)} games, {len(rows):,} downs so far")

    df = pd.DataFrame(rows)
    logger.info(f"Total downs extracted: {len(df):,} from {df['game_id'].nunique()} games")
    if df.empty:
        logger.error("No downs extracted; aborting write")
        return
    n_with_weapon = df["weapon"].notna().sum()
    logger.info(f"  parseable weapon+distance: {n_with_weapon:,} ({n_with_weapon / len(df):.1%})")
    n_unweapon = (df["weapon"].isna()).sum()
    if n_unweapon:
        sample_unparseable = df[df["weapon"].isna()]["event_text"].value_counts().head(5)
        logger.info(f"  unparseable event_texts (top 5):\n{sample_unparseable.to_string()}")

    df.to_parquet(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
