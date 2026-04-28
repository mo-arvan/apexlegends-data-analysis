"""Apply patch-note deltas chronologically to the guns_stats.csv baseline.

Produces a historical weapon-stats table with one row per (weapon, patch) where
the weapon changed in that patch. Each row is a full snapshot of that weapon's
stats after the patch. Carries forward unchanged stats from the previous row,
so reading the latest row per weapon gives the current-per-patch-notes state,
and picking the latest row ≤ a tournament date reconstructs the stats in force
at that time.

Inputs:
  data/guns_stats.csv                 # baseline (S21-era), one row per weapon
  data/patch_note_deltas.csv          # extracted bullets, 394+ rows
Outputs:
  data/weapon_history.csv             # long history table (per weapon × patch-where-changed)
  data/weapon_current_from_patches.csv # latest row per weapon = current derived stats
  data/weapon_history_unapplied.csv   # bullets that couldn't map cleanly to a CSV column
"""
import csv
import json
import logging
import os
from collections import defaultdict
from copy import deepcopy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASELINE_CSV = "data/guns_stats.csv"
DELTAS_CSV = "data/patch_note_deltas.csv"
OUT_HISTORY = "data/weapon_history.csv"
OUT_CURRENT = "data/weapon_current_from_patches.csv"
OUT_UNAPPLIED = "data/weapon_history_unapplied.csv"

# Level label → magazine_N / reload_time_N / rpm_N index (1..4).
LEVEL_TO_IDX = {
    "base": 1, "no": 1, "level 0": 1,
    "white": 2, "common": 2, "level 1": 2,
    "blue": 3, "rare": 3, "level 2": 3,
    "purple": 4, "purple/gold": 4, "gold": 4, "epic": 4, "legendary": 4, "level 3": 4,
}

# stat_hint → column writer. Returns a list of (column_name, new_value) pairs.
def mutations_for(stat_hint, level, new_value, csv_row):
    """Return list of (column, value) pairs the bullet should mutate, or [] to skip."""
    if new_value is None or new_value == "":
        return []
    try:
        nv = float(new_value) if "." in str(new_value) else int(new_value)
    except ValueError:
        return []

    lvl_idx = LEVEL_TO_IDX.get((level or "").strip().lower()) if level else None

    if stat_hint == "damage" or stat_hint == "damage_per_pellet":
        # For shotguns with pellets_per_shot, damage column is per-pellet already.
        return [("damage", nv)]
    if stat_hint == "pellets_per_shot":
        return [("pellets_per_shot", nv)]
    if stat_hint == "head_multiplier":
        return [("head_multiplier", nv)]
    if stat_hint == "leg_multiplier":
        return [("leg_multiplier", nv)]
    if stat_hint == "burst_delay":
        return [("burst_fire_delay", nv)]
    if stat_hint == "charge_time":
        return [("charge_time", nv)]
    if stat_hint == "magazine_size":
        if lvl_idx:
            return [(f"magazine_{lvl_idx}", nv)]
        # No level → ambiguous. Patch notes sometimes phrase as e.g. "Magazine
        # size increased to 36" meaning the gold/purple top tier. Treat as
        # top-tier (mag_4) and record nothing else; analysts can review via
        # applied_deltas column.
        return [("magazine_4", nv)]
    if stat_hint == "rate_of_fire":
        if lvl_idx:
            return [(f"rpm_{lvl_idx}", nv)]
        # Fire rate changes almost always apply across all mag tiers.
        return [(f"rpm_{i}", nv) for i in range(1, 5)]
    if stat_hint == "reload_speed":
        if lvl_idx:
            return [(f"reload_time_{lvl_idx}", nv)]
        return [(f"reload_time_{i}", nv) for i in range(1, 5)]
    # Unmapped: hipfire, recoil, projectile_speed, max_damage, hammerpoint, ads_time, deploy/holster, etc.
    return []


def load_baseline():
    """Return dict[weapon_name] -> row dict. Only canonical rows (no [variant])."""
    rows = {}
    columns = []
    with open(BASELINE_CSV) as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames or []
        for row in reader:
            name = row["weapon_name"]
            if "[" in name:
                continue
            rows[name] = row
    return rows, columns


def load_deltas():
    """Return list of delta dicts, sorted by (date, patch_slug)."""
    out = []
    with open(DELTAS_CSV) as fh:
        for row in csv.DictReader(fh):
            out.append(row)
    out.sort(key=lambda r: (r.get("date", ""), r.get("patch_slug", "")))
    return out


def format_delta_note(bullet_row, applied_cols):
    """Human-readable description of what a bullet did."""
    w = bullet_row["weapon"]
    stat = bullet_row.get("stat_hint") or "?"
    level = bullet_row.get("level") or ""
    old = bullet_row.get("old_value") or ""
    new = bullet_row.get("new_value") or ""
    delta_type = bullet_row.get("delta_type") or ""
    if applied_cols and old and new:
        return f"{','.join(applied_cols)}: {old}→{new}"
    if applied_cols and new:
        return f"{','.join(applied_cols)}: ?→{new}"
    if delta_type == "qualitative":
        return f"[{stat or 'qualitative'}] {bullet_row.get('bullet_text','')}"
    if delta_type == "unknown":
        return f"[unknown] {bullet_row.get('bullet_text','')}"
    return f"[{delta_type}/{stat}{'/'+level if level else ''}] {bullet_row.get('bullet_text','')}"


def main():
    baseline, columns = load_baseline()
    deltas = load_deltas()
    logger.info(f"Baseline weapons (canonical rows): {len(baseline)}")
    logger.info(f"Delta bullets: {len(deltas)}")

    # Group deltas by (date, patch_slug, weapon)
    grouped = defaultdict(list)
    for d in deltas:
        key = (d["date"], d["patch_slug"], d["weapon"])
        grouped[key].append(d)

    # Chronological patch keys sorted
    patch_keys = sorted({(d["date"], d["patch_slug"]) for d in deltas})

    # state[weapon] = current row (dict with same columns as CSV); tracked across patches
    state = {w: dict(row) for w, row in baseline.items()}

    # Weapons appearing in deltas but not in baseline: seed them with a sparse row
    # so we still capture their history.
    for (date, slug, weapon), _ in grouped.items():
        if weapon not in state:
            new_row = {c: "" for c in columns}
            new_row["weapon_name"] = weapon
            state[weapon] = new_row

    history_rows = []
    unapplied_rows = []

    # Record initial baseline as the earliest history entry.
    for weapon, row in sorted(state.items()):
        if weapon in baseline:
            out_row = dict(row)
            out_row["patch_date"] = "baseline"
            out_row["patch_slug"] = "guns_stats.csv (S21-era snapshot)"
            out_row["applied_deltas"] = ""
            out_row["change_notes"] = ""
            history_rows.append(out_row)

    # Iterate patches in chronological order, emit a snapshot row per (patch, weapon-that-changed)
    for date, slug in patch_keys:
        # Which weapons changed in this patch
        weapons_in_patch = sorted({d["weapon"] for d in deltas
                                   if d["date"] == date and d["patch_slug"] == slug})
        for weapon in weapons_in_patch:
            bullets = grouped[(date, slug, weapon)]
            current = state[weapon]
            applied_notes = []
            qualitative_notes = []
            for b in bullets:
                muts = mutations_for(b.get("stat_hint") or "", b.get("level") or "",
                                     b.get("new_value") or "", current)
                if muts:
                    cols_changed = []
                    for col, val in muts:
                        old = current.get(col, "")
                        current[col] = val
                        cols_changed.append(col)
                    applied_notes.append(format_delta_note(b, cols_changed))
                else:
                    # Record as either qualitative or unapplied.
                    note = format_delta_note(b, [])
                    qualitative_notes.append(note)
                    unapplied_rows.append({
                        "date": date, "patch_slug": slug, "weapon": weapon,
                        "stat_hint": b.get("stat_hint") or "",
                        "level": b.get("level") or "",
                        "delta_type": b.get("delta_type") or "",
                        "old_value": b.get("old_value") or "",
                        "new_value": b.get("new_value") or "",
                        "bullet_text": b.get("bullet_text") or "",
                        "reason": "no_csv_column_mapping" if b.get("new_value") else "no_numeric_value",
                    })

            # Only emit a row if something actually happened (avoid trivial empty rows)
            if applied_notes or qualitative_notes:
                out_row = dict(current)
                out_row["patch_date"] = date
                out_row["patch_slug"] = slug
                out_row["applied_deltas"] = " | ".join(applied_notes)
                out_row["change_notes"] = " | ".join(qualitative_notes)
                history_rows.append(out_row)

    # Output columns: original guns_stats.csv columns + metadata columns
    out_columns = list(columns) + ["patch_date", "patch_slug", "applied_deltas", "change_notes"]

    with open(OUT_HISTORY, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_columns)
        w.writeheader()
        for row in history_rows:
            w.writerow({c: row.get(c, "") for c in out_columns})
    logger.info(f"Wrote {OUT_HISTORY} ({len(history_rows)} rows)")

    # "Current" = latest row per weapon across all history (including baseline).
    latest = {}
    for row in history_rows:
        latest[row["weapon_name"]] = row
    with open(OUT_CURRENT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_columns)
        w.writeheader()
        for weapon, row in sorted(latest.items()):
            w.writerow({c: row.get(c, "") for c in out_columns})
    logger.info(f"Wrote {OUT_CURRENT} ({len(latest)} weapons, latest snapshot)")

    with open(OUT_UNAPPLIED, "w", newline="") as fh:
        fieldnames = ["date", "patch_slug", "weapon", "stat_hint", "level", "delta_type",
                      "old_value", "new_value", "bullet_text", "reason"]
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in unapplied_rows:
            w.writerow(row)
    logger.info(f"Wrote {OUT_UNAPPLIED} ({len(unapplied_rows)} bullets not applied to CSV columns)")

    # Summary
    applied_count = sum(1 for r in history_rows if r.get("applied_deltas"))
    logger.info(f"Patches × weapons with at least one applied delta: {applied_count}")


if __name__ == "__main__":
    main()
