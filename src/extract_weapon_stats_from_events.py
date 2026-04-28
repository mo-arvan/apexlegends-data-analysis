"""Derive weapon stats from ALGS damage-event parquets.

Reads every file in data/events_processed/*.parquet and produces a per-weapon
summary of the stats that games actually reveal:

- `damage` per bullet (mode of damage_arr). Body shots dominate the distribution,
  so the mode is the base body damage. Smaller values are leg shots (× leg_mult),
  larger are headshots (× head_mult) or Disruptor/Hammerpoint-modified.
- `damage_histogram` top 8 most-common damage values with counts, for
  manually spotting head/leg multipliers.
- `mag_size_observed` = 99th percentile of ammo_used (approximates max mag
  under realistic conditions, robust to outlier multi-reload events).
- `mag_size_max` = max ammo_used across all events (hard ceiling observed).
- Accuracy quantiles per weapon from (shots_hit / ammo_used), ignoring null
  ammo and impossible rows where hits > fired.
- Event and shot sample sizes so weapons with thin data are obvious.

Does NOT attempt to derive: head/leg multipliers (unreliable because hit location
is not recorded), reload times, deploy/holster, attachment multipliers.

Output:
  data/weapon_stats_from_events.csv         # one row per weapon
  output/weapon_stats_from_events.md        # human-readable report with histograms

  # When --latest-tournament-only is set, names switch to *_latest_tournament:
  data/weapon_stats_latest_tournament.csv
  output/weapon_stats_latest_tournament.md
"""

import logging
import os
from argparse import ArgumentParser
from collections import Counter

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EVENTS_DIR = "data/events_processed"
GAME_LIST_CSV = "data/algs_game_list.csv"
OUT_CSV = "data/weapon_stats_from_events.csv"
OUT_MD = "output/weapon_stats_from_events.md"
# When --latest-tournament-only is set, write here instead so downstream
# (build_ettk_inputs.py) finds the filtered stats under their canonical name.
OUT_CSV_LATEST = "data/weapon_stats_latest_tournament.csv"
OUT_MD_LATEST = "output/weapon_stats_latest_tournament.md"

# The event feed uses inconsistent weapon names across scraping eras. This maps
# every raw variant we've seen to a single canonical name. Unknown raw names
# pass through unchanged so new weapons aren't silently dropped.
WEAPON_NAME_CANON = {
    "ChargeRifle": "Charge Rifle",
    "G7Scout": "G7 Scout",
    "TripleTake": "Triple Take",
    "ThermiteGrenade": "Thermite Grenade",
    "ArcStar": "Arc Star",
    "FragGrenade": "Frag Grenade",
    "Sniper'sMark": "Sniper's Mark",
}


def load_all_events():
    files = sorted(f for f in os.listdir(EVENTS_DIR) if f.endswith(".parquet"))
    logger.info(f"Loading {len(files)} game parquets...")
    dfs = []
    for i, f in enumerate(files):
        try:
            df = pd.read_parquet(os.path.join(EVENTS_DIR, f))
            dfs.append(df)
        except Exception as exc:
            logger.warning(f"  {f}: {exc}")
        if (i + 1) % 200 == 0:
            logger.info(f"  loaded {i + 1}/{len(files)}")
    out = pd.concat(dfs, ignore_index=True)
    out["weapon"] = out["weapon"].replace(WEAPON_NAME_CANON)
    logger.info(f"Loaded {len(out):,} damage-event rows from {len(files)} games")
    return out


def explode_damages(df):
    """Return a Series of individual damage values per shot hit."""
    all_vals = []
    for arr in df["damage_arr"]:
        if arr is None:
            continue
        for v in arr:
            if v is None:
                continue
            try:
                all_vals.append(int(v))
            except (TypeError, ValueError):
                pass
    return pd.Series(all_vals, dtype="int64")


def summarize_weapon(weapon, sub):
    damages = explode_damages(sub)
    if len(damages) == 0:
        return None

    counter = Counter(damages.tolist())
    top = counter.most_common(8)
    mode_val, mode_n = top[0]

    # Accuracy: len(damage_arr) / ammo_used, where both are present and hits <= fired.
    # ammo_used is an int per row (sum across shots in the event).
    accs = []
    ammo_vals = []
    for _, row in sub[["damage_arr", "ammo_used"]].iterrows():
        arr = row["damage_arr"]
        ammo = row["ammo_used"]
        if arr is None:
            continue
        hits = len(arr)
        try:
            fired = int(ammo)
        except (TypeError, ValueError):
            continue
        if fired <= 0:
            continue
        if hits > fired:
            # Shotgun pellets-counted-as-hits or data corruption. Skip.
            continue
        accs.append(hits / fired)
        ammo_vals.append(fired)

    acc_series = (
        pd.Series(accs, dtype="float64") if accs else pd.Series([], dtype="float64")
    )
    ammo_series = (
        pd.Series(ammo_vals, dtype="int64")
        if ammo_vals
        else pd.Series([], dtype="int64")
    )

    return {
        "weapon": weapon,
        "events": len(sub),
        "shots_hit": len(damages),
        "damage_mode": mode_val,
        "damage_mode_share": round(mode_n / len(damages), 3),
        "damage_top8": ";".join(f"{v}x{n}" for v, n in top),
        "accuracy_n": len(acc_series),
        "accuracy_median": round(acc_series.median(), 3) if len(acc_series) else None,
        "accuracy_p25": round(acc_series.quantile(0.25), 3)
        if len(acc_series)
        else None,
        "accuracy_p75": round(acc_series.quantile(0.75), 3)
        if len(acc_series)
        else None,
        "ammo_used_sum": int(ammo_series.sum()) if len(ammo_series) else None,
        "ammo_used_median": round(float(ammo_series.median()), 1)
        if len(ammo_series)
        else None,
        "mag_size_observed_p99": int(ammo_series.quantile(0.99))
        if len(ammo_series)
        else None,
        "mag_size_max": int(ammo_series.max()) if len(ammo_series) else None,
    }


def filter_latest_tournament(df):
    games = pd.read_csv(GAME_LIST_CSV, na_filter=False)
    games["game_timestamp"] = pd.to_numeric(games["game_timestamp"], errors="coerce")
    latest_ts = games["game_timestamp"].max()
    latest_games = games[games["game_timestamp"] == latest_ts]
    if latest_games.empty:
        logger.warning(
            "Latest-tournament filter found no games; leaving events unfiltered"
        )
        return df

    latest_tournament = latest_games.iloc[0]["tournament_full_name"]
    keep = set(
        games[games["tournament_full_name"] == latest_tournament]["game_id"].astype(str)
    )
    before = len(df)
    out = df[df["game_hash"].astype(str).isin(keep)]
    logger.info(
        "Latest-tournament filter: %s (%d games), kept %d/%d event rows",
        latest_tournament,
        len(keep),
        len(out),
        before,
    )
    return out


def filter_games_by_year(df, min_year, max_year):
    if min_year is None and max_year is None:
        return df
    games = pd.read_csv(GAME_LIST_CSV, na_filter=False)
    games["tournament_year"] = pd.to_numeric(games["tournament_year"], errors="coerce")
    if min_year is not None:
        games = games[games["tournament_year"] >= min_year]
    if max_year is not None:
        games = games[games["tournament_year"] <= max_year]
    keep = set(games["game_id"].astype(str))
    before = len(df)
    out = df[df["game_hash"].astype(str).isin(keep)]
    logger.info(
        f"Year filter [{min_year}, {max_year}]: {len(out):,}/{before:,} event rows kept "
        f"({len(keep)} tournament games in range)"
    )
    return out


def main():
    os.makedirs("output", exist_ok=True)
    parser = ArgumentParser()
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Keep only events from tournaments with tournament_year >= this.",
    )
    parser.add_argument("--max-year", type=int, default=None)
    parser.add_argument("--out-csv", default=None,
                        help=f"Default: {OUT_CSV}, or {OUT_CSV_LATEST} when --latest-tournament-only is set.")
    parser.add_argument("--out-md", default=None,
                        help=f"Default: {OUT_MD}, or {OUT_MD_LATEST} when --latest-tournament-only is set.")
    parser.add_argument(
        "--latest-tournament-only",
        action="store_true",
        help="Keep only events from the most recent tournament in algs_game_list.csv.",
    )
    args = parser.parse_args()
    # Default outputs depend on whether we're filtering. Downstream
    # (build_ettk_inputs.py) reads the *_latest_tournament names.
    if args.out_csv is None:
        args.out_csv = OUT_CSV_LATEST if args.latest_tournament_only else OUT_CSV
    if args.out_md is None:
        args.out_md = OUT_MD_LATEST if args.latest_tournament_only else OUT_MD

    df = load_all_events()
    if args.latest_tournament_only:
        df = filter_latest_tournament(df)
    df = filter_games_by_year(df, args.min_year, args.max_year)
    if len(df) == 0:
        logger.error(
            "No events left after year filter. Check algs_game_list.csv coverage."
        )
        return
    logger.info(f"Unique weapons after filter: {df['weapon'].nunique()}")

    rows = []
    for weapon, sub in df.groupby("weapon", dropna=True):
        summary = summarize_weapon(weapon, sub)
        if summary:
            rows.append(summary)

    out = pd.DataFrame(rows).sort_values("shots_hit", ascending=False)
    out.to_csv(args.out_csv, index=False)
    logger.info(f"Wrote {args.out_csv} ({len(out)} weapons)")

    # Markdown report
    lines = [
        "# Weapon stats derived from ALGS event data\n",
        f"- Games processed: {df['game_hash'].nunique():,}",
        f"- Total damage-event rows: {len(df):,}",
        f"- Unique weapons: {len(out)}",
        "",
        "Mode = most common damage value per shot; dominates the distribution for body-shot",
        "weapons and approximates base per-bullet damage. Shotguns show per-blast totals so the",
        "mode is pellet-count-dependent. Headshots and leg shots appear as secondary peaks.",
        "",
        "| weapon | events | shots_hit | damage_mode | mode_share | top_8 |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in out.iterrows():
        lines.append(
            f"| {r['weapon']} | {r['events']} | {r['shots_hit']} | **{r['damage_mode']}** "
            f"| {r['damage_mode_share']:.2f} | {r['damage_top8']} |"
        )
    lines += [
        "",
        "## Observed magazine size and accuracy",
        "",
        "`mag_size_observed_p99` is the 99th percentile of ammo_used per event; approximates",
        "max mag size under realistic fire conditions. `mag_size_max` is the hard observed ceiling",
        "(may include multi-reload events). Accuracy = hits / ammo_used, filtered for null ammo",
        "and rows where hits > fired (shotgun pellet quirks).",
        "",
        "| weapon | n | acc_p25 | acc_med | acc_p75 | mag_p99 | mag_max |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in out.iterrows():
        lines.append(
            f"| {r['weapon']} | {r['accuracy_n']} | {r['accuracy_p25'] or ''} "
            f"| {r['accuracy_median'] or ''} | {r['accuracy_p75'] or ''} "
            f"| {r['mag_size_observed_p99'] or ''} | {r['mag_size_max'] or ''} |"
        )
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
