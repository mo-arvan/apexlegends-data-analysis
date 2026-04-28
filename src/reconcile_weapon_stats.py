"""Reconcile weapon stats across sources.

Sources consulted:
  1. data/guns_stats.csv                               (existing project CSV, S21-era baseline)
  2. data/weapons_wiki/wikigg/infobox/*.json           (wiki.gg infoboxes)
  3. data/weapons_wiki/fandom/infobox/*.json           (fandom infoboxes)
  4. data/weapon_current_from_patches.csv              (S21 baseline + patch-note deltas applied)

Event-data cross-check is a separate script (needs fresh ALGS data).

Output:
  data/weapon_stats_reconciliation.csv     # one row per (weapon, stat) with a column per source
  output/weapon_stats_reconciliation.md    # human-readable summary, grouped by weapon
"""
import csv
import json
import logging
import os
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = "data/guns_stats.csv"
WIKIGG_INFOBOX_DIR = "data/weapons_wiki/wikigg/infobox"
FANDOM_INFOBOX_DIR = "data/weapons_wiki/fandom/infobox"
PATCHES_DERIVED_CSV = "data/weapon_current_from_patches.csv"
OUT_CSV = "data/weapon_stats_reconciliation.csv"
OUT_MD = "output/weapon_stats_reconciliation.md"

# Stats we compare. Tuple of (canonical_name, csv_column, wiki_key_with_extractor).
# extractor returns a normalized value or None.
DAMAGE_BODY_RE = re.compile(r"^\s*(\d+)(?:\s*×\s*(\d+))?", re.IGNORECASE)

# Collapse class-name variants. Keys are lowercased.
CLASS_CANONICAL = {
    "ar": "AR", "assault rifle": "AR", "assault rifle (ar)": "AR",
    "smg": "SMG", "submachine gun": "SMG",
    "lmg": "LMG", "light machine gun": "LMG",
    "shotgun": "Shotgun",
    "sniper": "Sniper", "sniper rifle": "Sniper",
    "marksman": "Marksman", "marksman rifle": "Marksman", "marksman weapon": "Marksman",
    "pistol": "Pistol",
    "care package": "CarePackage", "care package weapon": "CarePackage",
}


def canonicalize_class(v):
    if not v:
        return None
    key = str(v).strip().lower()
    return CLASS_CANONICAL.get(key, str(v).strip())


def parse_damage_body(v):
    """'15' -> (15, None); '16×6 (96)' -> (16, 6); '11×8' -> (11, 8)."""
    if v is None or isinstance(v, list):
        return (None, None)
    m = DAMAGE_BODY_RE.match(str(v))
    if not m:
        return (None, None)
    dmg = int(m.group(1))
    pellets = int(m.group(2)) if m.group(2) else None
    return (dmg, pellets)


def as_number(v):
    try:
        if isinstance(v, list):
            return [as_number(x) for x in v]
        s = str(v).strip()
        if not s:
            return None
        return float(s) if "." in s else int(s)
    except (ValueError, TypeError):
        return None


def level0123_to_four(v):
    """Return a list of 4 numbers. If scalar given, repeat. If None, return None."""
    if v is None:
        return None
    if isinstance(v, list):
        vals = [as_number(x) for x in v]
        # Pad or truncate to 4
        while len(vals) < 4:
            vals.append(vals[-1] if vals else None)
        return vals[:4]
    n = as_number(v)
    if n is None:
        return None
    return [n, n, n, n]


def normalize_wiki_infobox(ib):
    """Map a wiki infobox dict into our CSV schema. Returns dict of normalized fields.

    Missing fields are left as None so comparisons show gaps explicitly.
    """
    damage, pellets = parse_damage_body(ib.get("damageBody"))
    head_damage, _ = parse_damage_body(ib.get("damageHead"))
    leg_damage, _ = parse_damage_body(ib.get("damageLegs"))

    head_mult = round(head_damage / damage, 3) if damage and head_damage else None
    leg_mult = round(leg_damage / damage, 3) if damage and leg_damage else None

    return {
        "damage": damage,
        "pellets_per_shot": pellets,
        "head_multiplier": head_mult,
        "leg_multiplier": leg_mult,
        "rpm_levels": level0123_to_four(ib.get("rateOfFire")),
        "magazine_levels": level0123_to_four(ib.get("magazineSize")),
        "reload_levels": level0123_to_four(ib.get("fullReload")),
        "class": canonicalize_class(ib.get("type")),
        "ammo": ib.get("ammoType") or None,
    }


def normalize_csv_row(row):
    """Map a guns_stats.csv row into the same shape used for wikis."""
    def _num(k):
        v = row.get(k)
        return as_number(v) if v not in ("", None) else None

    damage = _num("damage")
    pellets = _num("pellets_per_shot")
    head_mult = _num("head_multiplier")
    leg_mult = _num("leg_multiplier")
    rpm_levels = [_num(f"rpm_{i}") for i in range(1, 5)]
    mag_levels = [_num(f"magazine_{i}") for i in range(1, 5)]
    reload_levels = [_num(f"reload_time_{i}") for i in range(1, 5)]
    # treat all-None as None overall
    rpm_levels = rpm_levels if any(x is not None for x in rpm_levels) else None
    mag_levels = mag_levels if any(x is not None for x in mag_levels) else None
    reload_levels = reload_levels if any(x is not None for x in reload_levels) else None
    return {
        "damage": damage,
        "pellets_per_shot": pellets,
        "head_multiplier": head_mult,
        "leg_multiplier": leg_mult,
        "rpm_levels": rpm_levels,
        "magazine_levels": mag_levels,
        "reload_levels": reload_levels,
        "class": canonicalize_class(row.get("class")),
        "ammo": None,  # CSV doesn't carry ammo type
    }


def load_csv_weapons(path=CSV_PATH):
    """Return dict[weapon_name] -> normalized stats. Only "baseline" rows
    (no bracketed variant suffix), since variant rows would dominate the join."""
    out = {}
    with open(path) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row["weapon_name"]
            if "[" in name:
                continue
            out[name] = normalize_csv_row(row)
    return out


def load_wiki_weapons(infobox_dir):
    """Return dict[weapon_name] -> normalized stats. Skip mobile/variant pages."""
    out = {}
    for fname in sorted(os.listdir(infobox_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(infobox_dir, fname)) as fh:
            doc = json.load(fh)
        title = doc.get("title", "")
        ib = doc.get("infobox") or {}
        # Filter out variant / non-primary pages. The base weapon page has no "/"
        # in its title; everything with a slash is a variant (Heart Stealer,
        # April Fools', Mobile, Sniper's Mark, etc.). Also skip grenades, the
        # Power Sword melee, and the summary "Weapon" page.
        if ("/" in title or "(Mobile)" in title
                or title.endswith("Weapon")
                or title in ("Grenade", "Arc Star", "Frag Grenade", "Thermite Grenade",
                             "Power Sword", "Throwing Knife")):
            continue
        if not ib or "damageBody" not in ib:
            continue
        out[title] = normalize_wiki_infobox(ib)
    return out


def values_match(a, b):
    if a is None or b is None:
        return None  # can't compare
    if isinstance(a, list) and isinstance(b, list):
        return a == b
    return a == b


def reconcile(csv_map, wikigg_map, fandom_map, patches_map):
    """Build one row per (weapon, stat) with columns per source + an agreement flag."""
    all_weapons = sorted(set(csv_map) | set(wikigg_map) | set(fandom_map) | set(patches_map))
    stats = ["damage", "pellets_per_shot", "head_multiplier", "leg_multiplier",
             "rpm_levels", "magazine_levels", "reload_levels", "class"]
    rows = []
    for weapon in all_weapons:
        csv_row = csv_map.get(weapon)
        gg_row = wikigg_map.get(weapon)
        fd_row = fandom_map.get(weapon)
        pd_row = patches_map.get(weapon)
        for stat in stats:
            csv_v = csv_row.get(stat) if csv_row else None
            gg_v = gg_row.get(stat) if gg_row else None
            fd_v = fd_row.get(stat) if fd_row else None
            pd_v = pd_row.get(stat) if pd_row else None
            sources_with_value = [("csv", csv_v), ("wikigg", gg_v),
                                  ("fandom", fd_v), ("patches", pd_v)]
            present = [(n, v) for n, v in sources_with_value if v is not None]
            if not present:
                agree = "no_data"
            elif len({json.dumps(v, default=str) for _, v in present}) == 1:
                agree = f"agree_{len(present)}"
            else:
                agree = "DISAGREE"
            # Highlight the most actionable case: patches_derived vs wikigg disagree
            # (both are "current" estimates; if they agree, trust; if not, human needed).
            gg_pd_status = None
            if gg_v is not None and pd_v is not None:
                gg_pd_status = "match" if json.dumps(gg_v, default=str) == json.dumps(pd_v, default=str) else "mismatch"
            rows.append({
                "weapon": weapon,
                "stat": stat,
                "csv": csv_v,
                "wikigg": gg_v,
                "fandom": fd_v,
                "patches": pd_v,
                "agreement": agree,
                "wikigg_vs_patches": gg_pd_status or "",
                "sources_with_data": len(present),
            })
    return rows


def write_csv_report(rows, path):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["weapon", "stat", "csv", "wikigg", "fandom", "patches",
                    "agreement", "wikigg_vs_patches", "sources_with_data"])
        for r in rows:
            def _j(v):
                return json.dumps(v, default=str) if v is not None else ""
            w.writerow([r["weapon"], r["stat"], _j(r["csv"]), _j(r["wikigg"]),
                        _j(r["fandom"]), _j(r["patches"]),
                        r["agreement"], r["wikigg_vs_patches"], r["sources_with_data"]])


def write_md_report(rows, path):
    # Group by weapon
    by_weapon = defaultdict(list)
    for r in rows:
        by_weapon[r["weapon"]].append(r)

    # Summary counts
    total = len(rows)
    by_agreement = defaultdict(int)
    for r in rows:
        by_agreement[r["agreement"]] += 1

    disagree_weapons = sorted({r["weapon"] for r in rows if r["agreement"] == "DISAGREE"})
    missing_in_csv = sorted({r["weapon"] for r in rows
                             if r["csv"] is None and (r["wikigg"] is not None or r["fandom"] is not None)})
    missing_in_wikigg = sorted({r["weapon"] for r in rows
                                if r["wikigg"] is None and (r["csv"] is not None or r["fandom"] is not None)})

    # How often wikigg and patches-derived agree where both are present.
    gg_pd_match = sum(1 for r in rows if r["wikigg_vs_patches"] == "match")
    gg_pd_mismatch = sum(1 for r in rows if r["wikigg_vs_patches"] == "mismatch")

    lines = []
    lines.append("# Weapon stats reconciliation\n")
    lines.append(f"- Total (weapon, stat) cells: **{total}**")
    for k in ("DISAGREE", "agree_4", "agree_3", "agree_2", "agree_1", "no_data"):
        lines.append(f"- `{k}`: {by_agreement[k]}")
    lines.append("")
    lines.append("## wiki.gg vs patch-notes-derived (both are 'current' estimates)\n")
    lines.append(f"- Both present + match: **{gg_pd_match}**")
    lines.append(f"- Both present + **mismatch**: **{gg_pd_mismatch}** (these are the cells most worth reviewing)")
    lines.append("")
    lines.append(f"## Weapons with at least one DISAGREE across all sources ({len(disagree_weapons)})\n")
    for w in disagree_weapons:
        lines.append(f"- {w}")
    lines.append("")
    lines.append(f"## Weapons in a wiki but NOT in current guns_stats.csv ({len(missing_in_csv)})\n")
    for w in missing_in_csv:
        lines.append(f"- {w}")
    lines.append("")
    lines.append(f"## Weapons in CSV or fandom but NOT in wiki.gg ({len(missing_in_wikigg)})\n")
    for w in missing_in_wikigg:
        lines.append(f"- {w}")
    lines.append("")

    # Mismatches specifically between wikigg and patch-notes-derived are the
    # "something is off" signal. List them first, grouped by weapon.
    mismatch_rows = [r for r in rows if r["wikigg_vs_patches"] == "mismatch"]
    lines.append(f"## wiki.gg ≠ patch-notes-derived ({len(mismatch_rows)} cells)\n")
    lines.append("| weapon | stat | wikigg | patches | csv | fandom |")
    lines.append("|---|---|---|---|---|---|")
    for r in mismatch_rows:
        def fmt(v):
            return "" if v is None else str(v)
        lines.append(f"| {r['weapon']} | {r['stat']} | {fmt(r['wikigg'])} | {fmt(r['patches'])} | "
                     f"{fmt(r['csv'])} | {fmt(r['fandom'])} |")
    lines.append("")
    lines.append("## Per-weapon detail\n")

    for weapon in sorted(by_weapon):
        lines.append(f"### {weapon}\n")
        lines.append("| stat | csv | wikigg | fandom | patches | agreement | gg↔patches |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in by_weapon[weapon]:
            def fmt(v):
                return "" if v is None else str(v)
            lines.append(f"| {r['stat']} | {fmt(r['csv'])} | {fmt(r['wikigg'])} | {fmt(r['fandom'])} | "
                         f"{fmt(r['patches'])} | {r['agreement']} | {r['wikigg_vs_patches']} |")
        lines.append("")

    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def main():
    os.makedirs("output", exist_ok=True)
    csv_map = load_csv_weapons()
    logger.info(f"CSV baseline rows (no variants): {len(csv_map)}")
    wikigg_map = load_wiki_weapons(WIKIGG_INFOBOX_DIR)
    logger.info(f"wiki.gg weapon pages: {len(wikigg_map)}")
    fandom_map = load_wiki_weapons(FANDOM_INFOBOX_DIR)
    logger.info(f"fandom weapon pages: {len(fandom_map)}")
    if os.path.exists(PATCHES_DERIVED_CSV):
        patches_map = load_csv_weapons(PATCHES_DERIVED_CSV)
        logger.info(f"patch-notes-derived weapons: {len(patches_map)}")
    else:
        patches_map = {}
        logger.warning(f"{PATCHES_DERIVED_CSV} missing; run apply_patch_deltas.py first")

    rows = reconcile(csv_map, wikigg_map, fandom_map, patches_map)
    write_csv_report(rows, OUT_CSV)
    write_md_report(rows, OUT_MD)
    logger.info(f"Wrote {OUT_CSV} and {OUT_MD}")

    by_agreement = defaultdict(int)
    for r in rows:
        by_agreement[r["agreement"]] += 1
    for k, n in sorted(by_agreement.items()):
        logger.info(f"  {k}: {n}")


if __name__ == "__main__":
    main()
