"""Extract heal-item usage events from per-game pkls into a single parquet.

The raw scrape logs every consumable use as a `playerStatChanged`-adjacent
`inventoryUse` event with text like "Used x1  Shield Cell" or "Used x1
Med Kit". For HP-state engagement-window analysis we need to know when each
player healed and by how much.

This extractor maps the consumable name to a standard restore amount. Real
in-game heals can be partial (e.g. syringe applied with HP already at 99 only
restores 1 HP), but the events feed doesn't expose the actual delta. We use
the nominal amount and clamp to the assumed 200 HP cap downstream.

Output:
  data/heal_events.parquet   one row per inventoryUse heal event
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
OUT_PARQUET = "data/heal_events.parquet"

# Apex consumable restore amounts. Phoenix Kit restores both pools fully.
HEAL_AMOUNTS = {
    "Shield Cell":    {"shield": 25,  "health": 0},
    "Shield Battery": {"shield": 100, "health": 0},
    "Syringe":        {"shield": 0,   "health": 25},
    "Med Kit":        {"shield": 0,   "health": 100},
    "Phoenix Kit":    {"shield": 100, "health": 100},
}

# Match "Used x1  <item>" with one or more spaces before the item name.
USED_TEXT_RE = re.compile(r"^Used\s+x\d+\s+(.+?)\s*$")


def parse_item(event_text):
    if not isinstance(event_text, str):
        return None
    m = USED_TEXT_RE.match(event_text.strip())
    if not m:
        return None
    return m.group(1).strip()


def heals_from_game(game_id, events_list):
    if not events_list:
        return []
    df = pd.concat(events_list, ignore_index=True)
    if "event_type" not in df.columns:
        return []
    uses = df[df["event_type"] == "inventoryUse"]
    if uses.empty:
        return []
    out = []
    for _, row in uses.iterrows():
        item = parse_item(row["event_text"])
        if item not in HEAL_AMOUNTS:
            continue
        amounts = HEAL_AMOUNTS[item]
        out.append({
            "game_id": game_id,
            "event_id": int(row["event_id"]),
            "gametimestamp": int(row["event_timestamp"]),
            "player_hash": row["player_hash"],
            "x_position": int(row["x_position"]),
            "y_position": int(row["y_position"]),
            "item": item,
            "shield_restore": amounts["shield"],
            "health_restore": amounts["health"],
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
        rows.extend(heals_from_game(game_id, game.get("events", [])))
        if (i + 1) % 200 == 0:
            logger.info(f"  processed {i + 1}/{len(files)} games, {len(rows):,} heals so far")

    df = pd.DataFrame(rows)
    logger.info(f"Total heal events extracted: {len(df):,} from {df['game_id'].nunique()} games")
    if df.empty:
        logger.error("No heal events extracted; aborting write")
        return
    logger.info(f"  item distribution:\n{df['item'].value_counts().to_string()}")
    df.to_parquet(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
