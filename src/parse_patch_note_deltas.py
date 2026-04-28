"""Extract per-weapon stat deltas from EA patch note markdown files.

Patch note format across seasons is consistent enough to mine:
  **Weapon Name**

  - Damage increased to 17 (was 15)
  - Magazine size changes

      - Base: 19 (was 20)
      - White: 23 (was 25)
      - ...

  - Hipfire accuracy significantly reduced     # qualitative, no numbers

This script walks each patch-note .md, finds `**Weapon**` headings that match
a known weapon (from wiki.gg), collects every bullet below it until the next
weapon, and tries to extract numeric deltas. Every bullet gets a row in the
output so qualitative changes aren't lost.

Output:
  data/patch_note_deltas.csv
      one row per bullet, with best-effort delta extraction
  output/patch_note_deltas_summary.md
      quick sanity summary: counts per weapon, counts of numeric vs qualitative

Downstream code can apply these chronologically to guns_stats.csv.
"""
import csv
import json
import logging
import os
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PATCH_NOTES_DIR = "data/patch_notes"
WIKIGG_INDEX = "data/weapons_wiki/wikigg/index.json"
OUT_CSV = "data/patch_note_deltas.csv"
OUT_MD = "output/patch_note_deltas_summary.md"

# Aliases: patch notes sometimes shorten or retag weapon names. Map known
# variants to the canonical wiki.gg name so they merge cleanly.
WEAPON_ALIASES = {
    "mastiff": "Mastiff Shotgun",
    "mastiff shotgun": "Mastiff Shotgun",
    "eva-8": "EVA-8 Auto",
    "eva 8": "EVA-8 Auto",
    "eva-8 auto": "EVA-8 Auto",
    "mozambique": "Mozambique Shotgun",
    "mozambique shotgun": "Mozambique Shotgun",
    "peacekeeper": "Peacekeeper",
    "havoc": "HAVOC Rifle",
    "havoc rifle": "HAVOC Rifle",
    "hemlok": "Hemlok Burst AR",
    "hemlok burst ar": "Hemlok Burst AR",
    "hemlok breach ar": "Hemlok Breach AR",
    "flatline": "VK-47 Flatline",
    "vk-47 flatline": "VK-47 Flatline",
    "car": "C.A.R. SMG",
    "c.a.r.": "C.A.R. SMG",
    "c.a.r. smg": "C.A.R. SMG",
    "alternator": "Alternator SMG",
    "alternator smg": "Alternator SMG",
    "r-99": "R-99 SMG",
    "r-99 smg": "R-99 SMG",
    "r-301": "R-301 Carbine",
    "r-301 carbine": "R-301 Carbine",
    "volt": "Volt SMG",
    "volt smg": "Volt SMG",
    "prowler": "Prowler Burst PDW",
    "prowler burst pdw": "Prowler Burst PDW",
    "prowler pdw": "Prowler Burst PDW",
    "p2020": "P2020",
    "re-45": "RE-45 Auto",
    "re-45 auto": "RE-45 Auto",
    "re-45 burst": "RE-45 Burst",
    "wingman": "Wingman",
    "30-30": "30-30 Repeater",
    "30-30 repeater": "30-30 Repeater",
    "g7 scout": "G7 Scout",
    "triple take": "Triple Take",
    "triple-take": "Triple Take",
    "bocek": "Bocek Compound Bow",
    "bocek compound bow": "Bocek Compound Bow",
    "longbow": "Longbow DMR",
    "longbow dmr": "Longbow DMR",
    "sentinel": "Sentinel",
    "kraber": "Kraber .50-Cal Sniper",
    "charge rifle": "Charge Rifle",
    "nemesis": "Nemesis Burst AR",
    "nemesis burst ar": "Nemesis Burst AR",
    "rampage": "Rampage LMG",
    "rampage lmg": "Rampage LMG",
    "devotion": "Devotion LMG",
    "devotion lmg": "Devotion LMG",
    "spitfire": "M600 Spitfire",
    "m600 spitfire": "M600 Spitfire",
    "l-star": "L-STAR EMG",
    "l-star emg": "L-STAR EMG",
}

# Each entry: (pattern, group index of NEW value, group index of OLD value or None).
DELTA_PATTERNS = [
    # "... to 17 (was 15)"  — most specific, try first
    (re.compile(r"\bto\s+(\d+(?:\.\d+)?)\s*\(\s*[Ww]as\s+(\d+(?:\.\d+)?)\s*\)"), 1, 2),
    # "17 (was 15)"          — nested level bullets ("Base: 17 (was 15)"), also tolerates "17(was 15)"
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*\(\s*[Ww]as\s+(\d+(?:\.\d+)?)\s*\)"), 1, 2),
    # "increased to 17"      — partial, no explicit old value
    (re.compile(r"\b(?:increased|decreased|reduced|raised|lowered|dropped|set)\s+to\s+(\d+(?:\.\d+)?)"), 1, None),
    # "from 15 to 17"        — M then N; group 2 is new
    (re.compile(r"\bfrom\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\b"), 2, 1),
    # "15 → 17"              — M then N; group 2 is new
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:→|-&gt;|->)\s*(\d+(?:\.\d+)?)"), 2, 1),
]

# Stat keyword → canonical stat name. First match wins, so list longer /
# more-qualified phrases before shorter ones.
#
# Design rule: anything like "<qualifier> damage" (Beam Shot damage, Limb
# damage, Shattercaps damage, etc.) is mapped to a DIFFERENT stat hint than
# base damage so it doesn't overwrite body damage downstream. Unmapped hints
# get recorded in the history as change_notes but never mutate a CSV column.
STAT_KEYWORDS = [
    # Shotgun per-pellet and pellet count
    ("damage per pellet", "damage_per_pellet"),
    ("pellets per blast", "pellets_per_shot"),
    ("pellet count", "pellets_per_shot"),
    # Attachment / hop-up / firing-mode qualifiers that look like damage but aren't base.
    ("shattercaps damage per pellet", "shattercaps_damage"),
    ("shattercaps damage", "shattercaps_damage"),
    ("beam shot damage", "beam_shot_damage"),
    ("full burst damage", "full_burst_damage"),
    ("headshot damage", "headshot_damage"),
    ("limb damage", "limb_multiplier"),
    ("arm damage", "arm_multiplier"),
    ("charged damage", "charged_damage"),
    ("energized damage", "energized_damage"),
    ("max energized damage", "max_energized_damage"),
    ("max body damage", "max_body_damage"),
    ("max damage", "max_damage"),
    ("hammer point damage", "hammerpoint_damage"),
    ("hammerpoint damage", "hammerpoint_damage"),
    ("disruptor damage", "disruptor_damage"),
    ("hammer point", "hammerpoint"),
    ("hammerpoint", "hammerpoint"),
    # Base damage (matches only when no qualifier claimed the line first).
    ("base damage", "damage"),
    ("body damage", "damage"),
    ("damage", "damage"),
    # Magazine
    ("magazine size", "magazine_size"),
    ("mag size", "magazine_size"),
    ("clip size", "magazine_size"),
    ("clip", "magazine_size"),
    ("magazine", "magazine_size"),
    # Fire rate / reload / timings
    ("rate of fire", "rate_of_fire"),
    ("fire rate", "rate_of_fire"),
    ("rpm", "rate_of_fire"),
    ("reload speed", "reload_speed"),
    ("reload time", "reload_speed"),
    ("empty reload", "reload_speed"),
    ("tac reload", "reload_speed"),
    ("full reload", "reload_speed"),
    ("burst fire delay", "burst_delay"),
    ("burst delay", "burst_delay"),
    ("charge time", "charge_time"),
    ("draw time", "charge_time"),
    # Multipliers (multiplier variants only; *_damage already captured above)
    ("headshot multiplier", "head_multiplier"),
    ("leg multiplier", "leg_multiplier"),
    # Timings / handling (unmapped to CSV; recorded as notes only)
    ("ads in", "ads_time"),
    ("ads out", "ads_time"),
    ("deploy time", "deploy_time"),
    ("holster time", "holster_time"),
    ("hipfire", "hipfire"),
    ("recoil", "recoil"),
    ("projectile speed", "projectile_speed"),
]

# Level prefixes inside nested magazine/reload lists.
LEVEL_PREFIX_RE = re.compile(
    r"^\s*[-*]?\s*(?P<level>(?:base|white|blue|purple|purple/gold|gold|level\s*\d+))\s*:",
    re.IGNORECASE,
)


def load_known_weapons():
    if not os.path.exists(WIKIGG_INDEX):
        raise FileNotFoundError(f"{WIKIGG_INDEX} not present; run scrape_weapons_wiki.py first")
    with open(WIKIGG_INDEX) as fh:
        idx = json.load(fh)
    # Base weapon pages (no slash, no parenthetical mobile variant)
    names = {e["title"] for e in idx if "/" not in e["title"] and "(Mobile)" not in e["title"]}
    # Add alias canonical targets to be safe.
    names.update(WEAPON_ALIASES.values())
    return names


# Match a weapon header line. Handles:
#   **Weapon**                        (2024 patches)
#   ###### **Weapon**                 (2025+ patches)
#   ###### **Weapon** *(Previous Hotfix)*
#   **Weapon [Care Package]**
WEAPON_HEADER_RE = re.compile(
    r"^\s*(?:#+\s+)?\*\*\s*(?P<body>[^*]+?)\s*\*\*(?:\s*\*[^*]*\*)?\s*$"
)
# Splits multi-weapon headers like "Spitfire & Rampage LMG" into pieces.
CONJUNCTION_RE = re.compile(r"\s*(?:&amp;|&|,| and )\s*", re.IGNORECASE)


# Common class-suffix tokens that often appear on patch-note weapon headers
# (e.g. "Spitfire LMG", "Wingman Pistol"). Stripping them lets us match an
# alias entry that's keyed only on the short name ("spitfire").
CLASS_SUFFIXES = ("lmg", "smg", "ar", "pdw", "dmr", "emg", "carbine",
                  "rifle", "pistol", "shotgun", "sniper")


def _canonicalize_one(name, known_weapons):
    core = re.sub(r"\s*[\[(][^\])]*[\])]\s*$", "", name).strip()
    if not core:
        return None
    if core in known_weapons:
        return core
    key = core.lower()
    if key in WEAPON_ALIASES:
        return WEAPON_ALIASES[key]
    # Fallback: strip a trailing class suffix and retry. "Spitfire LMG" -> "Spitfire".
    parts = key.split()
    if len(parts) >= 2 and parts[-1] in CLASS_SUFFIXES:
        short = " ".join(parts[:-1])
        if short in WEAPON_ALIASES:
            return WEAPON_ALIASES[short]
        short_title = core.rsplit(" ", 1)[0]
        if short_title in known_weapons:
            return short_title
    return None


def match_weapon_header(line, known_weapons):
    """Return a list of canonical weapon names if this line is a weapon heading, else []."""
    m = WEAPON_HEADER_RE.match(line)
    if not m:
        return []
    body = m.group("body").strip()
    # Shortcut: single weapon, no conjunctions
    single = _canonicalize_one(body, known_weapons)
    if single:
        return [single]
    # Try splitting on conjunctions (handles "Spitfire & Rampage LMG").
    parts = [p for p in CONJUNCTION_RE.split(body) if p.strip()]
    if len(parts) <= 1:
        return []
    found = []
    for p in parts:
        c = _canonicalize_one(p, known_weapons)
        if c:
            found.append(c)
    return found


def parse_frontmatter(text):
    """Return (frontmatter_dict, body_text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end < 0:
        return {}, text
    fm_raw = text[3:end].strip()
    body = text[end + 5:]
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


def parse_bullet(raw_line):
    """Return dict with: text (cleaned), stat_hint, new_value, old_value, delta_type, level."""
    text = raw_line.lstrip()
    # drop leading "- " bullet marker
    text = re.sub(r"^[-*]\s+", "", text)
    text = text.strip()
    # Recognise level-row format ("Base: 19 (was 20)") for nested magazine/reload bullets.
    level_match = LEVEL_PREFIX_RE.match(text)
    level = level_match.group("level").strip().lower() if level_match else None

    lower = text.lower()
    stat_hint = None
    for kw, canon in STAT_KEYWORDS:
        if kw in lower:
            stat_hint = canon
            break

    new_value = old_value = None
    for pat, new_g, old_g in DELTA_PATTERNS:
        m = pat.search(text)
        if m:
            new_value = m.group(new_g)
            if old_g is not None and m.lastindex and m.lastindex >= old_g:
                old_value = m.group(old_g)
            break

    if new_value is not None:
        delta_type = "numeric" if old_value is not None else "numeric_partial"
    elif re.search(r"\bremoved\b", lower):
        delta_type = "removed"
    elif re.search(r"\badded\b", lower) or re.search(r"\bnew\b", lower):
        delta_type = "added"
    elif re.search(r"\b(increased|decreased|reduced|raised|lowered|improved|adjusted|tightened|slightly)\b", lower):
        delta_type = "qualitative"
    else:
        delta_type = "unknown"

    return {
        "text": text,
        "stat_hint": stat_hint,
        "new_value": new_value,
        "old_value": old_value,
        "delta_type": delta_type,
        "level": level,
    }


def walk_patch_file(path, known_weapons):
    """Yield dicts: {weapon, text, stat_hint, new_value, old_value, delta_type, level}."""
    with open(path) as fh:
        content = fh.read()
    _, body = parse_frontmatter(content)

    current_weapons = []
    for line in body.splitlines():
        # Section-reset: non-weapon header of depth <= 4 clears the weapon context.
        # (Depth-6 headers are used for the weapon subheads themselves.)
        if re.match(r"^#{1,5}\s", line) and current_weapons:
            if not re.match(r"^#{1,5}\s+(Old|New)\s*$", line, re.IGNORECASE):
                # But don't clear if this header is itself a weapon header
                if not match_weapon_header(line, known_weapons):
                    current_weapons = []
        heads = match_weapon_header(line, known_weapons)
        if heads:
            current_weapons = heads
            continue
        if current_weapons and re.match(r"^\s*[-*]\s", line):
            parsed = parse_bullet(line)
            for w in current_weapons:
                out = dict(parsed)
                out["weapon"] = w
                yield out


def main():
    os.makedirs("output", exist_ok=True)
    known_weapons = load_known_weapons()
    logger.info(f"Known canonical weapons: {len(known_weapons)}")

    rows = []
    per_patch_counts = defaultdict(lambda: defaultdict(int))
    for fname in sorted(os.listdir(PATCH_NOTES_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(PATCH_NOTES_DIR, fname)
        # date prefix + slug
        m = re.match(r"^(\d{4}-\d{2}-\d{2})_(.+)\.md$", fname)
        date, slug = (m.group(1), m.group(2)) if m else ("", fname[:-3])

        count_in_file = 0
        for item in walk_patch_file(path, known_weapons):
            rows.append({
                "date": date,
                "patch_slug": slug,
                "weapon": item["weapon"],
                "stat_hint": item["stat_hint"] or "",
                "level": item["level"] or "",
                "delta_type": item["delta_type"],
                "old_value": item["old_value"] or "",
                "new_value": item["new_value"] or "",
                "bullet_text": item["text"],
            })
            count_in_file += 1
            per_patch_counts[slug][item["delta_type"]] += 1
        if count_in_file:
            logger.info(f"  {fname}: {count_in_file} bullet(s) under recognised weapons")

    with open(OUT_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date", "patch_slug", "weapon", "stat_hint",
                                                "level", "delta_type", "old_value", "new_value",
                                                "bullet_text"])
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {OUT_CSV} ({len(rows)} rows)")

    # Per-weapon / per-delta-type summary
    per_weapon = defaultdict(lambda: defaultdict(int))
    per_type = defaultdict(int)
    for r in rows:
        per_weapon[r["weapon"]][r["delta_type"]] += 1
        per_type[r["delta_type"]] += 1

    lines = ["# Patch-note delta extraction summary\n",
             f"- Total extracted bullets: **{len(rows)}**",
             f"- Distinct weapons touched: **{len(per_weapon)}**",
             "",
             "## By delta type"]
    for k in ("numeric", "numeric_partial", "qualitative", "added", "removed", "unknown"):
        lines.append(f"- `{k}`: {per_type[k]}")
    lines.extend(["", "## Bullets per weapon (sorted desc)"])
    for weapon, types in sorted(per_weapon.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(types.values())
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(types.items()) if v)
        lines.append(f"- **{weapon}** ({total}): {breakdown}")
    lines.extend(["", "## Bullets per patch"])
    for slug, types in sorted(per_patch_counts.items()):
        total = sum(types.values())
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(types.items()) if v)
        lines.append(f"- `{slug}` ({total}): {breakdown}")

    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
