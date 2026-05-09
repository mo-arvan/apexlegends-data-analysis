"""Phase 2: empirical eTTK analysis.

Loads the canonical kill records (Phase 1 output), filters to clean
single-attacker, full-HP-target downs, and compares observed empirical eTTK
to the modeled curve from `data/ettk_curves.csv` per weapon.

The "clean comparison slice" is the apples-to-apples to the published eTTK
series: down-ending engagement, one attacker carries (>= TOP_SHARE_MIN
share of damage), victim absorbed approximately 200 HP (FULL_HP_RANGE band).

Outputs:
  output/empirical_ttk_summary.md       per-weapon table: empirical vs modeled
  output/empirical_ttk_per_weapon.csv   the same table, machine-readable
  output/ettk_figs/empirical_<wpn>.png  per-weapon chart: modeled curve + empirical points
"""

import logging
import os
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

KILL_RECORDS = "data/kill_records.parquet"
ETTK_CURVES = "data/ettk_curves.csv"
ETTK_RESULTS = "data/ettk_results.csv"
OUT_MD = "output/empirical_ttk_summary.md"
OUT_CSV = "output/empirical_ttk_per_weapon.csv"
OUT_FIG_DIR = "output/ettk_figs"
DEFAULT_SINCE = "2025-02-10"  # matches landscape analyzer

# Slice thresholds for the "clean comparison" filter.
TOP_SHARE_MIN = 0.80     # single-attacker dominance
PURPLE_HP_LO = 190       # purple shield + body (canonical 200 HP)
PURPLE_HP_HI = 220
BLUE_HP_LO = 165         # blue shield + body (canonical 175 HP)
BLUE_HP_HI = 185
MIN_SAMPLES_PER_WEAPON = 20  # below this, weapon-level numbers are noise

# Apply the project's plot style if available.
_HERE = Path(__file__).parent
_STYLE = _HERE / "research_vibrant.mplstyle"
if _STYLE.exists():
    plt.style.use(str(_STYLE))


def hits_to_down(damage):
    """Total hits to deliver 200 HP using the overspill model.
    Mirrors src/analyze_ettk.py's hits_to_milestone with shield/health
    multipliers = 1.0 (no Disruptor / Hammerpoint)."""
    import math
    if damage <= 0:
        return None
    n_s_full = math.floor(100 / damage)
    shield_left = 100 - n_s_full * damage
    raw_used = shield_left  # mult = 1
    overspill = damage - raw_used
    n_s = n_s_full + 1
    health_remaining = max(0.0, 100 - overspill)
    n_h = math.ceil(health_remaining / damage)
    return n_s + n_h


def modeled_eTTK_at_full_acc(weapon, results_df):
    """Compute modeled eTTK at 100% accuracy from per-weapon stats."""
    row = results_df[results_df["weapon"] == weapon]
    if row.empty:
        return None
    r = row.iloc[0]
    hits = hits_to_down(int(r["damage"]) * int(r["pellets"] or 1))
    if hits is None or pd.isna(r["rpm_4"]):
        return None
    return (hits - 1) * 60 / float(r["rpm_4"])


def per_weapon_summary(kill_df, model_df, results_df, slice_label):
    """For each weapon with sufficient samples, compute empirical eTTK and
    observed accuracy quantiles and join with the modeled values.

    Splits the slice into TWO views per weapon:
      one_mag: top attacker used <= magazine size (true one-clip; matches model)
      reload : top attacker used > magazine size (multi-mag, reload included)
    """
    import json as _json
    mag_by_weapon = dict(zip(results_df["weapon"], results_df["mag_4"]))
    rows = []
    for weapon, grp in kill_df.groupby("top_attacker_weapon"):
        n = len(grp)
        if n < MIN_SAMPLES_PER_WEAPON:
            continue
        # Pull per-engagement top-attacker stats once.
        per_eng = []
        for _, r in grp.iterrows():
            try:
                ctr = _json.loads(r["contributors_json"])
                top = next((c for c in ctr if c["attacker_hash"] == r["top_attacker_hash"]), None)
            except Exception:
                continue
            if top is None:
                continue
            ammo = top.get("ammo_used") or 0
            per_eng.append({
                "eTTK": r["top_attacker_observed_eTTK"],
                "shots_hit": top.get("shots_hit") or 0,
                "ammo_used": ammo,
                "n_bursts": top.get("n_bursts") or 0,
                "accuracy": (top["shots_hit"] / ammo) if ammo > 0 else None,
            })
        if not per_eng:
            continue
        per_df = pd.DataFrame(per_eng)
        mag = mag_by_weapon.get(weapon)
        if mag and pd.notna(mag):
            one_mag_mask = per_df["ammo_used"] <= mag
        else:
            one_mag_mask = pd.Series(True, index=per_df.index)
        one_mag = per_df[one_mag_mask]
        reload_inc = per_df[~one_mag_mask]
        # Use the one-mag slice as the canonical comparison; degrade to all
        # records if magazine size is unknown.
        comp = one_mag if mag else per_df
        ettk = comp["eTTK"].astype(float)
        acc_series = comp["accuracy"].dropna()

        modeled_at_full = modeled_eTTK_at_full_acc(weapon, results_df)
        modeled_at_observed_median_acc = None
        if not model_df.empty and not acc_series.empty:
            mw = model_df[model_df["weapon"] == weapon]
            if not mw.empty:
                target_acc = round(acc_series.median(), 2)
                nearest = mw.iloc[(mw["accuracy"] - target_acc).abs().argsort()[:1]]
                if not nearest.empty and pd.notna(nearest["t_down"].iloc[0]):
                    modeled_at_observed_median_acc = float(nearest["t_down"].iloc[0])

        rows.append({
            "slice": slice_label,
            "weapon": weapon,
            "n_total": n,
            "n_one_mag": int(len(one_mag)) if mag else None,
            "n_reload_inc": int(len(reload_inc)) if mag else None,
            "empirical_eTTK_p25": round(float(ettk.quantile(0.25)), 2) if not ettk.empty else None,
            "empirical_eTTK_median": round(float(ettk.median()), 2) if not ettk.empty else None,
            "empirical_eTTK_p75": round(float(ettk.quantile(0.75)), 2) if not ettk.empty else None,
            "observed_acc_median": round(float(acc_series.median()), 3) if not acc_series.empty else None,
            "modeled_eTTK_at_full_acc": round(modeled_at_full, 2) if modeled_at_full is not None else None,
            "modeled_eTTK_at_observed_acc": round(modeled_at_observed_median_acc, 2) if modeled_at_observed_median_acc is not None else None,
        })

    out = pd.DataFrame(rows).sort_values("n_total", ascending=False).reset_index(drop=True)
    return out


def _one_mag_ettk_series(kill_df_w, mag):
    """Return list of empirical eTTK seconds for the one-mag subset."""
    import json as _json
    out = []
    for _, r in kill_df_w.iterrows():
        try:
            ctr = _json.loads(r["contributors_json"])
            top = next((c for c in ctr if c["attacker_hash"] == r["top_attacker_hash"]), None)
        except Exception:
            continue
        if not top:
            continue
        ammo = top.get("ammo_used") or 0
        if mag and ammo > mag:
            continue
        out.append(r["top_attacker_observed_eTTK"])
    return out


def render_per_weapon_ecdf(weapon, purple_df, blue_df, mag,
                           modeled_full, out_path):
    """Per-weapon ECDF: cumulative fraction of empirical eTTK <= x, with
    purple-shield and blue-shield slices on the same chart and a vertical
    line at the modeled full-accuracy eTTK."""
    purple_y = _one_mag_ettk_series(purple_df, mag)
    blue_y = _one_mag_ettk_series(blue_df, mag)
    if not purple_y and not blue_y:
        return False

    fig, ax = plt.subplots(figsize=(9, 5.0))
    cap = 8.0
    if modeled_full is not None:
        ax.axvline(modeled_full, color="#888", linestyle="--", linewidth=1.4,
                   alpha=0.7,
                   label=f"modeled @ 100% acc = {modeled_full:.2f}s")
    for vals, color, label in [
        (purple_y, "#CC3311",
         f"purple shield + body (n={len(purple_y)})" if purple_y else None),
        (blue_y, "#EE7733",
         f"blue shield + body (n={len(blue_y)})" if blue_y else None),
    ]:
        if not vals or label is None:
            continue
        sorted_vals = np.sort(np.array(vals, dtype=float))
        sorted_vals = np.minimum(sorted_vals, cap)
        ecdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
        ax.step(sorted_vals, ecdf, where="post",
                color=color, linewidth=2.0, label=label)

    ax.set_xlim(0, cap + 0.2)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("empirical eTTK (s)")
    ax.set_ylabel("cumulative fraction of one-mag downs")
    ax.set_title(f"{weapon}: empirical eTTK distribution")
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(loc="lower right", fontsize=9, frameon=True,
              facecolor="white", edgecolor="#ccc")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def main():
    parser = ArgumentParser()
    parser.add_argument("--kill-records", default=KILL_RECORDS)
    parser.add_argument("--ettk-curves", default=ETTK_CURVES)
    parser.add_argument("--since", default=DEFAULT_SINCE,
                        help=f"Filter engagements to game_timestamp >= this date (YYYY-MM-DD). Default: {DEFAULT_SINCE}.")
    parser.add_argument("--out-md", default=OUT_MD)
    parser.add_argument("--out-csv", default=OUT_CSV)
    parser.add_argument("--fig-dir", default=OUT_FIG_DIR)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out_md) or ".", exist_ok=True)
    os.makedirs(args.fig_dir, exist_ok=True)

    logger.info(f"Loading {args.kill_records}...")
    df = pd.read_parquet(args.kill_records)
    n_raw = len(df)
    logger.info(f"  total engagements: {n_raw:,}")

    if args.since:
        cutoff = int(datetime.strptime(args.since, "%Y-%m-%d")
                     .replace(tzinfo=timezone.utc).timestamp())
        df = df[df["game_timestamp"].astype("int64") >= cutoff]
        logger.info(f"  --since {args.since} -> kept {len(df):,} of {n_raw:,} ({len(df)/n_raw:.1%})")

    logger.info(f"Loading {args.ettk_curves}...")
    model = pd.read_csv(args.ettk_curves)
    logger.info(f"  modeled curves: {len(model):,} rows across {model['weapon'].nunique()} weapons")

    logger.info(f"Loading {ETTK_RESULTS}...")
    results = pd.read_csv(ETTK_RESULTS)
    mag_by_weapon = dict(zip(results["weapon"], results["mag_4"]))

    # Two HP slices: purple shield (canonical 200 HP) and blue shield (175 HP).
    # Filter on top_attacker_damage so multi-attacker engagements where the
    # top weapon only chipped don't get credited with the full HP-band TTK.
    purple = df[
        (df["downed"]) & (df["top_attacker_share"] >= TOP_SHARE_MIN) &
        (df["top_attacker_damage"] >= PURPLE_HP_LO) & (df["top_attacker_damage"] <= PURPLE_HP_HI)
    ].copy()
    blue = df[
        (df["downed"]) & (df["top_attacker_share"] >= TOP_SHARE_MIN) &
        (df["top_attacker_damage"] >= BLUE_HP_LO) & (df["top_attacker_damage"] <= BLUE_HP_HI)
    ].copy()
    logger.info(f"Purple-shield slice ({PURPLE_HP_LO}-{PURPLE_HP_HI} HP): {len(purple):,}")
    logger.info(f"Blue-shield slice ({BLUE_HP_LO}-{BLUE_HP_HI} HP): {len(blue):,}")

    summary_purple = per_weapon_summary(purple, model, results, "purple (200 HP)")
    summary_blue = per_weapon_summary(blue, model, results, "blue (175 HP)")
    summary = pd.concat([summary_purple, summary_blue], ignore_index=True)
    summary.to_csv(args.out_csv, index=False)

    # Per-weapon ECDF charts (one per weapon, both slices on same chart)
    weapons = sorted(set(summary["weapon"]))
    n_charts = 0
    for weapon in weapons:
        purple_w = purple[purple["top_attacker_weapon"] == weapon]
        blue_w = blue[blue["top_attacker_weapon"] == weapon]
        mag_raw = mag_by_weapon.get(weapon)
        mag = int(mag_raw) if mag_raw and pd.notna(mag_raw) else None
        modeled_full = modeled_eTTK_at_full_acc(weapon, results)
        safe_name = weapon.replace(" ", "_").replace(".", "").replace("/", "_")
        out_path = os.path.join(args.fig_dir, f"empirical_{safe_name}_ecdf.png")
        if render_per_weapon_ecdf(weapon, purple_w, blue_w, mag, modeled_full, out_path):
            n_charts += 1
    logger.info(f"Wrote {n_charts} per-weapon ECDF charts to {args.fig_dir}")

    # Markdown report
    cols = list(summary.columns)
    md = ["| " + " | ".join(cols) + " |",
          "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in summary.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.2f}")
            elif isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        md.append("| " + " | ".join(cells) + " |")

    lines = [
        "# Empirical eTTK vs modeled (Phase 2)",
        "",
        f"Source: `{args.kill_records}`. Filter: `--since {args.since}`. Two HP slices: **purple shield + body** ({PURPLE_HP_LO}-{PURPLE_HP_HI} HP, the modeled 200 HP target) and **blue shield + body** ({BLUE_HP_LO}-{BLUE_HP_HI} HP, validates against blue-shield victims).",
        f"Within each slice, filtered to down-ending engagements with single-attacker share >= {TOP_SHARE_MIN}.",
        f"The headline numbers below use only the **one-mag subset** (top attacker used <= weapon's purple-mag size).",
        f"Per-weapon minimum sample threshold: {MIN_SAMPLES_PER_WEAPON}.",
        "",
        "## Per-weapon comparison",
        "",
        *md,
        "",
        "## Reading the table",
        "",
        "- `slice`: which HP band the row's empirical numbers come from.",
        "- `n_total`: clean-slice down-ending engagements for this (weapon, slice).",
        "- `n_one_mag` / `n_reload_inc`: split by whether the top attacker used <= or > the weapon's purple-mag capacity.",
        "- `empirical_eTTK_*`: observed time-to-down quantiles in seconds, computed on the **one-mag subset** (or all clean-slice records when mag is unknown).",
        "- `observed_acc_median`: median of (top attacker's shots_hit / ammo_used) on the one-mag subset.",
        "- `modeled_eTTK_at_full_acc`: model prediction at 100% accuracy, computed from the per-weapon damage / mag / RPM via the overspill formula. The modeled value targets 200 HP regardless of slice; the blue-shield slice produces a faster empirical because the target absorbs less HP.",
        "- `modeled_eTTK_at_observed_acc`: model prediction at the observed-median accuracy, the more direct comparison to the empirical median in the purple-shield slice.",
        "",
        "## Per-weapon charts",
        "",
        "Each weapon with sufficient samples gets an `empirical_<weapon>_ecdf.png` under `output/ettk_figs/`: cumulative distribution of empirical eTTK in the one-mag subset, with separate curves for purple-shield and blue-shield victims, plus a vertical reference line at the modeled full-accuracy eTTK.",
        "",
        "## Caveats",
        "",
        "- Source timestamps are integer-second precision, so empirical eTTK has 1s granularity. Sub-second differences (e.g. R-99's 0.83s modeled) cannot be observed directly; the empirical median rounds.",
        "- Burst-level accuracy is biased upward because engagements often include hits across multiple bursts and only the burst-level shots_hit / ammo_used is observed; sustained-fire accuracy in the engagement may be lower.",
        "- HP-delivered banding is approximate. Purple ~ 200, blue ~ 175. Red shield (225) victims are not extracted as a separate slice; they would need a 215-235 band but are rare in pro play.",
        "- The one-mag filter relies on `ammo_used` being correctly attributed to the top attacker. Multi-burst engagements where a small share comes from a teammate may slightly under-count the top attacker's ammo.",
    ]
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md} and {args.out_csv}")


if __name__ == "__main__":
    main()
