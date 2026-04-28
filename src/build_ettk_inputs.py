"""Phase 1 of the eTTK analysis: build the per-weapon input table.

Joins event-derived damage / pick rate / accuracy with patches-derived
magazine / reload / RPM / multipliers. Emits a single CSV that the eTTK
computation script consumes, with a `_source` marker per stat for provenance.

Scope: close-range meta weapons with >= MIN_SHOTS_HIT shots landed. Thin-sample
weapons are excluded from the main table but listed in an appendix file.
"""

import csv
import json
import logging
import os
from argparse import ArgumentParser

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_EVENT_STATS_CSV = "data/weapon_stats_latest_tournament.csv"
PATCHES_CSV = "data/weapon_current_from_patches.csv"
WIKIGG_INFOBOX_DIR = "data/weapons_wiki/wikigg/infobox"
OUT_CSV = "data/weapon_stats_for_ettk.csv"
OUT_APPENDIX = "data/weapon_stats_for_ettk_excluded.csv"

MIN_SHOTS_HIT = 100
# Ordnance / interaction / non-weapon entries we never want in the analysis.
EXCLUDE_ALWAYS = {
    "Arc Star", "Frag Grenade", "Thermite Grenade", "Breach Charge",
    "Stinger Bolt", "Explosive Arrow", "Honorable Fisticuffs",
    "Electrified Door", "Whistler", "Crushed", "Sniper's Mark",
    "Tracker Dart", "Minigun", "Weapon Overheat", "mp_weapon_bubble_bunker",
    "Charge Rifle",  # low sample + unique mechanic, excluded by default
}

# Map event-feed weapon names to the canonical names in patches-derived CSV.
# "Hemlok" in Y6 events is the S28.1 Breach AR (old Burst moved to Elite).
# "RE-45" in Y6 events is the S28.1 Burst form (now permanent per Aftershock).
EVENT_TO_PATCHES_NAME = {
    "R-99": "R-99 SMG",
    "Hemlok": "Hemlok Breach AR",
    "Alternator": "Alternator SMG",
    "RE-45": "RE-45 Burst",
    "Volt": "Volt SMG",
    "Prowler": "Prowler Burst PDW",
    "C.A.R.": "C.A.R. SMG",
    "R-301": "R-301 Carbine",
    "Flatline": "VK-47 Flatline",
    "Nemesis": "Nemesis Burst AR",
    "HAVOC": "HAVOC Rifle",
    "Peacekeeper": "Peacekeeper",
    "Mozambique": "Mozambique Shotgun",
    "Mastiff": "Mastiff Shotgun",
    "EVA-8": "EVA-8 Auto",
    "Wingman": "Wingman",
    "G7 Scout": "G7 Scout",
    "Triple Take": "Triple Take",
    "30-30": "30-30 Repeater",
    "Bocek": "Bocek Compound Bow",
    "Longbow": "Longbow DMR",
    "Sentinel": "Sentinel",
    "Kraber": "Kraber .50-Cal Sniper",
    "Charge Rifle": "Charge Rifle",
    "L-STAR": "L-STAR EMG",
    "Devotion": "Devotion LMG",
    "Spitfire": "M600 Spitfire",
    "Rampage": "Rampage LMG",
    "P2020": "P2020",
}

# Hop-up overrides for the current season (state not encoded in patches CSV).
# Galvanic Gavel (added 2025-11-03 patch): CAR ships with Disruptor Rounds
# active by default on first pickup. Disruptor adds +20% damage vs evo
# shields. Add a row here when other weapons get analogous default hop-ups.
HOPUP_OVERRIDES = {
    "C.A.R. SMG": {"evo": 1.20, "non_evo": 1.00},
}


def load_event_stats(event_stats_csv):
    df = pd.read_csv(event_stats_csv)
    df["weapon_canonical"] = (
        df["weapon"].map(EVENT_TO_PATCHES_NAME).fillna(df["weapon"])
    )
    logger.info(
        "Event stats: %d rows, %s total shots from %s",
        len(df),
        f"{df['shots_hit'].sum():,}",
        event_stats_csv,
    )
    return df


def load_patches_stats():
    df = pd.read_csv(PATCHES_CSV, na_filter=False)
    logger.info(f"Patches-derived stats: {len(df)} weapons")
    return df


def load_wikigg_infoboxes():
    """Return dict[weapon_title] -> infobox dict."""
    out = {}
    if not os.path.exists(WIKIGG_INFOBOX_DIR):
        return out
    for fname in os.listdir(WIKIGG_INFOBOX_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(WIKIGG_INFOBOX_DIR, fname)) as fh:
            doc = json.load(fh)
        out[doc["title"]] = doc.get("infobox", {})
    logger.info(f"wiki.gg infoboxes: {len(out)}")
    return out


def _wiki_to_rpm(v):
    """wiki.gg sometimes stores fire rate as rounds/sec. Convert to rpm."""
    f = _to_float(v)
    if f is None:
        return None
    return int(f * 60) if f < 100 else int(f)


def _wiki_purple_level(v):
    """Extract purple-tier value from a {{Level0123}} list.

    Apex tiers go: 0 = no attachment / base, 1 = white, 2 = blue,
    3 = purple. Gold has the SAME magazine size as purple (gold's bonus is
    quick-reload, not extra capacity). So the largest list value = the purple
    tier we model against. Wiki templates render 4 values [base, white, blue,
    purple/gold]; we take the last.
    """
    if isinstance(v, list) and v:
        return _to_float(v[-1])
    return _to_float(v)


def _to_float(v, default=None):
    try:
        if v == "" or v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def build_row(y6, patches, wiki_ib):
    """Assemble one weapon's eTTK input record. Fills from wiki.gg when patches empty."""
    wname = y6["weapon_canonical"]

    # Damage: prefer Y6 event mode. Ground truth.
    damage = int(y6["damage_mode"])
    damage_source = "y6_events"

    # Helper: patches value, fallback to wiki.gg, with source tracking.
    def from_patches_or_wiki(patch_field, wiki_extract):
        pv = _to_float(patches.get(patch_field))
        if pv is not None:
            return pv, "patches"
        if wiki_ib:
            wv = wiki_extract(wiki_ib)
            if wv is not None:
                return wv, "wikigg"
        return None, "missing"

    # Reference tier is purple (level 3) — matches the purple-shielded target.
    # Gold mag has the same capacity as purple (gold's bonus is quick-reload),
    # so the patches CSV's `magazine_4` column already holds the purple value.
    mag_4, mag_source = from_patches_or_wiki(
        "magazine_4", lambda ib: _wiki_purple_level(ib.get("magazineSize"))
    )
    # Sanity check: magazine_4 (purple/gold) should be the highest tier. If
    # patches has a lower value than magazine_3 it's parser-inverted (e.g.
    # Wingman's Feb 2025 patch note "base reduced to 5" landed in the wrong
    # slot). Fall back to wiki when the wiki value is larger and looks valid.
    patches_m3 = _to_float(patches.get("magazine_3"))
    if (mag_4 is not None and patches_m3 is not None and mag_4 < patches_m3
            and wiki_ib):
        wiki_mag = _wiki_purple_level(wiki_ib.get("magazineSize"))
        if wiki_mag is not None and wiki_mag > mag_4:
            mag_4 = wiki_mag
            mag_source = "wikigg (patches inverted)"
    rpm_4, rpm_source = from_patches_or_wiki(
        "rpm_4", lambda ib: _wiki_to_rpm(ib.get("rateOfFire"))
    )
    # Patch-note text sometimes uses rounds-per-second instead of rpm
    # (e.g. "Fire rate increased to 3" for the EVA-8). Anything below 10
    # is implausible as actual rpm — Kraber, the slowest, is 25 — so treat
    # values <10 as rounds/sec and convert.
    if rpm_4 is not None and rpm_4 < 10:
        rpm_4 = rpm_4 * 60
        rpm_source = f"{rpm_source}_x60"
    reload_4, reload_source = from_patches_or_wiki(
        "reload_time_4", lambda ib: _wiki_purple_level(ib.get("fullReload"))
    )
    pellets = _to_float(patches.get("pellets_per_shot"))
    # head/leg multipliers: prefer patches; fall back to wikigg's
    # damageHead / damageBody when patches has no value (catches new
    # weapon variants like Hemlok Breach AR that have no baseline row).
    head_mult = _to_float(patches.get("head_multiplier"))
    if head_mult is None and wiki_ib:
        wb = _to_float(wiki_ib.get("damageBody"))
        wh = _to_float(wiki_ib.get("damageHead"))
        if wb and wh:
            head_mult = round(wh / wb, 3)
    if head_mult is None:
        head_mult = 1.0
    leg_mult = _to_float(patches.get("leg_multiplier"))
    if leg_mult is None and wiki_ib:
        wb = _to_float(wiki_ib.get("damageBody"))
        wl = _to_float(wiki_ib.get("damageLegs"))
        if wb and wl:
            leg_mult = round(wl / wb, 3)
    if leg_mult is None:
        leg_mult = 1.0
    evo_mult = _to_float(patches.get("evo_damage_multiplier"), 1.0)
    non_evo_mult = _to_float(patches.get("non_evo_damage_multiplier"), 1.0)
    if wname in HOPUP_OVERRIDES:
        evo_mult = HOPUP_OVERRIDES[wname]["evo"]
        non_evo_mult = HOPUP_OVERRIDES[wname]["non_evo"]
    deploy = _to_float(patches.get("deploy_time"), 0.0)
    holster = _to_float(patches.get("holster_time"), 0.0)
    bullets_per_burst = _to_float(patches.get("bullets_per_burst"))
    burst_fire_delay = _to_float(patches.get("burst_fire_delay"))
    firing_mode = patches.get("firing_mode") or ""
    # S28.1 Aftershock removed Hemlok Breach AR's burst mode; it's auto now.
    # Patches-derived may still have empty firing_mode because the new weapon
    # didn't have a baseline row. Default auto for weapons without burst data.
    if not firing_mode:
        firing_mode = "burst" if (bullets_per_burst and burst_fire_delay) else "auto"
    weapon_class = patches.get("class") or (wiki_ib.get("type", "") if wiki_ib else "")

    # Mag cross-check with Y6 observed mag ceiling. Prefer Y6 only if it
    # clearly disagrees with patches/wiki (captures a patch not yet in our
    # delta chain).
    # Observed p99 shots-per-engagement is NOT weapon mag size. Pros swap
    # before emptying mags (especially shotguns / LMGs), so the event p99 is
    # always ≤ real mag. Trust patches / wiki for mag, don't override.

    return {
        "weapon": wname,
        "class": weapon_class,
        "firing_mode": firing_mode,
        "damage": damage,
        "damage_source": damage_source,
        "pellets_per_shot": int(pellets) if pellets else "",
        "magazine_4": int(mag_4) if mag_4 else "",
        "magazine_4_source": mag_source,
        "rpm_4": int(rpm_4) if rpm_4 else "",
        "rpm_4_source": rpm_source,
        "reload_time_4": reload_4 if reload_4 else "",
        "reload_time_4_source": reload_source,
        "head_multiplier": head_mult,
        "leg_multiplier": leg_mult,
        "evo_damage_multiplier": evo_mult,
        "non_evo_damage_multiplier": non_evo_mult,
        "deploy_time": deploy,
        "holster_time": holster,
        "bullets_per_burst": int(bullets_per_burst) if bullets_per_burst else "",
        "burst_fire_delay": burst_fire_delay if burst_fire_delay else "",
        "y6_events": int(y6["events"]),
        "y6_shots_hit": int(y6["shots_hit"]),
        "y6_ammo_used_sum": y6.get("ammo_used_sum", ""),
        "y6_ammo_used_median": y6.get("ammo_used_median", ""),
        "y6_damage_mode_share": float(y6["damage_mode_share"]),
        "y6_accuracy_median": y6.get("accuracy_median", ""),
        "y6_accuracy_p25": y6.get("accuracy_p25", ""),
        "y6_accuracy_p75": y6.get("accuracy_p75", ""),
        "y6_mag_max": y6.get("mag_size_max", ""),
    }


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--event-stats-csv",
        default=DEFAULT_EVENT_STATS_CSV,
        help="Per-weapon event summary CSV to use for ETTK inputs.",
    )
    parser.add_argument("--out-csv", default=OUT_CSV)
    parser.add_argument("--out-appendix", default=OUT_APPENDIX)
    args = parser.parse_args()

    y6_df = load_event_stats(args.event_stats_csv)
    patches_df = load_patches_stats()
    patches_by_name = {row["weapon_name"]: row for _, row in patches_df.iterrows()}
    wikigg_ib = load_wikigg_infoboxes()

    in_scope = []
    excluded = []

    for _, y6 in y6_df.iterrows():
        wname = y6["weapon_canonical"]
        shots = int(y6["shots_hit"])
        patches_row = patches_by_name.get(wname)

        reasons = []
        # Scope is now every firearm with sufficient sample + stat coverage.
        # Ordnance / utility / low-sample never-weapons stay out.
        if y6["weapon"] in EXCLUDE_ALWAYS or wname in EXCLUDE_ALWAYS:
            reasons.append("ordnance_or_utility")
        if shots < MIN_SHOTS_HIT:
            reasons.append(f"thin_sample({shots}<{MIN_SHOTS_HIT})")
        if patches_row is None:
            reasons.append("no_patches_data")
            patches_row = {}

        if reasons:
            excluded.append(
                {
                    "weapon": wname,
                    "event_name": y6["weapon"],
                    "shots_hit": shots,
                    "damage_mode": y6["damage_mode"],
                    "reasons": ";".join(reasons),
                }
            )
            continue

        row = build_row(y6, patches_row, wikigg_ib.get(wname, {}))
        # Secondary gate: if core eTTK stats are still missing, push to excluded.
        if row["magazine_4"] == "" or row["rpm_4"] == "" or row["reload_time_4"] == "":
            excluded.append(
                {
                    "weapon": wname,
                    "event_name": y6["weapon"],
                    "shots_hit": shots,
                    "damage_mode": y6["damage_mode"],
                    "reasons": f"missing_stats(mag={row['magazine_4_source']},rpm={row['rpm_4_source']},reload={row['reload_time_4_source']})",
                }
            )
            continue
        in_scope.append(row)

    if in_scope:
        out_cols = list(in_scope[0].keys())
        with open(args.out_csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=out_cols)
            w.writeheader()
            w.writerows(in_scope)
        logger.info(f"Wrote {args.out_csv}: {len(in_scope)} weapons in scope")
    else:
        logger.warning("No weapons made the scope filter!")

    if excluded:
        with open(args.out_appendix, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(excluded[0].keys()))
            w.writeheader()
            w.writerows(excluded)
        logger.info(f"Wrote {args.out_appendix}: {len(excluded)} weapons excluded")

    # Quick on-screen preview of the in-scope table
    if in_scope:
        preview = pd.DataFrame(in_scope)[
            [
                "weapon",
                "damage",
                "magazine_4",
                "rpm_4",
                "reload_time_4",
                "y6_shots_hit",
                "y6_accuracy_median",
            ]
        ]
        logger.info("\n" + preview.to_string(index=False))


if __name__ == "__main__":
    main()
