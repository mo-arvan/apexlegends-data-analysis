"""Phase 4: which weapons are underrated by usage relative to kill conversion?

For each weapon (used as top attacker in any engagement), compute:
  usage             = total engagements where this weapon was top attacker
  kill_conversion   = down-ending engagements / total
  one_clip_rate     = downs in one mag / total downs
  solo_down_share   = downs with single-attacker share >= 0.99 / total downs
  damage_efficiency = median (total_damage / 200) for downs (1.0 = no overkill)
  range_bandwidth   = p90 - p10 of median engagement range across downs

Composite **underrated_index** = mean(z_low_usage, z_high_conversion). High
values = "low usage but high kill conversion when used."

Outputs:
  output/underrated_weapons.md
  output/underrated_weapons.csv
  output/ettk_figs/underrated_scatter.png
  output/ettk_figs/underrated_ranked_bars.png
"""

import json
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
ETTK_RESULTS = "data/ettk_results.csv"
OUT_MD = "output/underrated_weapons.md"
OUT_CSV = "output/underrated_weapons.csv"
OUT_FIG_DIR = "output/ettk_figs"
DEFAULT_SINCE = "2025-02-10"
MIN_USAGE = 150  # weapons with fewer than this many engagements are too noisy

_HERE = Path(__file__).parent
_STYLE = _HERE / "research_vibrant.mplstyle"
if _STYLE.exists():
    plt.style.use(str(_STYLE))


def top_attacker_ammo(row):
    try:
        ctr = json.loads(row["contributors_json"])
    except Exception:
        return None
    top = next((c for c in ctr if c["attacker_hash"] == row["top_attacker_hash"]), None)
    if not top:
        return None
    return top.get("ammo_used")


def per_weapon_metrics(df, mag_by_weapon):
    rows = []
    for weapon, grp in df.groupby("top_attacker_weapon"):
        usage = len(grp)
        if usage < MIN_USAGE:
            continue
        downs = grp[grp["downed"]]
        n_downs = len(downs)
        if n_downs == 0:
            continue
        # one-clip rate: how many downs used <= weapon's mag
        mag = mag_by_weapon.get(weapon)
        n_one_clip = None
        if mag and pd.notna(mag):
            ammos = downs.apply(top_attacker_ammo, axis=1)
            valid = ammos.dropna()
            if len(valid):
                n_one_clip = int((valid <= mag).sum())
                one_clip_rate = n_one_clip / len(valid)
            else:
                one_clip_rate = None
        else:
            one_clip_rate = None
        # solo down share
        solo = downs[downs["top_attacker_share"] >= 0.99]
        solo_share = len(solo) / n_downs
        # damage efficiency on downs (closer to 1.0 = clean, >1.0 = overkill).
        # Use top_attacker_damage so multi-attacker totals don't inflate the
        # denominator for spray weapons.
        damage_eff = downs["top_attacker_damage"].median() / 200.0
        # range bandwidth
        ranges = downs["top_attacker_median_distance"].dropna()
        if len(ranges) >= 5:
            r10, r90 = float(ranges.quantile(0.10)), float(ranges.quantile(0.90))
            range_bw = r90 - r10
            range_median = float(ranges.median())
        else:
            r10, r90, range_bw, range_median = None, None, None, None

        rows.append({
            "weapon": weapon,
            "usage": usage,
            "n_downs": n_downs,
            "kill_conversion": n_downs / usage,
            "one_clip_rate": one_clip_rate,
            "solo_down_share": solo_share,
            "damage_efficiency": damage_eff,
            "range_p10": r10,
            "range_p90": r90,
            "range_bandwidth": range_bw,
            "range_median": range_median,
        })
    return pd.DataFrame(rows)


def add_underrated_index(metrics):
    if metrics.empty:
        metrics["z_low_usage"] = []
        metrics["z_high_conversion"] = []
        metrics["underrated_index"] = []
        return metrics
    log_usage = np.log(metrics["usage"].astype(float))
    z_low_usage = -((log_usage - log_usage.mean()) / log_usage.std(ddof=0))
    conv = metrics["kill_conversion"]
    z_high_conv = (conv - conv.mean()) / conv.std(ddof=0)
    metrics = metrics.copy()
    metrics["z_low_usage"] = z_low_usage.round(3)
    metrics["z_high_conversion"] = z_high_conv.round(3)
    metrics["underrated_index"] = ((z_low_usage + z_high_conv) / 2).round(3)
    return metrics


def fig_usage_conversion_scatter(metrics, out_path):
    if metrics.empty:
        return
    try:
        from adjustText import adjust_text
        have_adjust = True
    except Exception:
        have_adjust = False

    fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    x = metrics["usage"].astype(float)
    y = metrics["kill_conversion"]
    sizes = 30 + 6 * (metrics["underrated_index"] - metrics["underrated_index"].min()) ** 2
    sc = ax.scatter(x, y, s=sizes, c=metrics["underrated_index"],
                    cmap="RdYlGn", edgecolor="white", linewidth=0.6, alpha=0.92)
    fig.colorbar(sc, ax=ax, label="underrated_index (high = underrated)")
    ax.set_xscale("log")
    ax.set_xlabel("usage (engagements where weapon is top attacker, log scale)")
    ax.set_ylabel("kill_conversion (downs / total engagements)")
    median_usage = float(np.median(x))
    median_conv = float(y.median())
    ax.axvline(median_usage, color="#888", linestyle=":", alpha=0.6)
    ax.axhline(median_conv, color="#888", linestyle=":", alpha=0.6)
    # Quadrant labels
    ax.text(0.02, 0.97, "underrated\n(low use, high conv)",
            transform=ax.transAxes, fontsize=9, va="top", color="#117733",
            bbox=dict(facecolor="white", edgecolor="#117733", pad=2, alpha=0.85))
    ax.text(0.98, 0.97, "meta\n(high use, high conv)",
            transform=ax.transAxes, fontsize=9, va="top", ha="right", color="#0077BB",
            bbox=dict(facecolor="white", edgecolor="#0077BB", pad=2, alpha=0.85))
    ax.text(0.02, 0.03, "neglected\n(low use, low conv)",
            transform=ax.transAxes, fontsize=9, va="bottom", color="#888888",
            bbox=dict(facecolor="white", edgecolor="#888888", pad=2, alpha=0.85))
    ax.text(0.98, 0.03, "overrated\n(high use, low conv)",
            transform=ax.transAxes, fontsize=9, va="bottom", ha="right", color="#CC3311",
            bbox=dict(facecolor="white", edgecolor="#CC3311", pad=2, alpha=0.85))

    texts = [ax.text(xi, yi, w, fontsize=8)
             for xi, yi, w in zip(x, y, metrics["weapon"])]
    if have_adjust:
        adjust_text(texts, ax=ax,
                    arrowprops=dict(arrowstyle="-", color="#bbb", lw=0.6))

    ax.set_title("Weapon usage vs kill conversion")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_underrated_bars(metrics, out_path, n=12):
    if metrics.empty:
        return
    top = metrics.sort_values("underrated_index", ascending=False).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.4 * len(top) + 1.5))
    colors = plt.cm.RdYlGn((top["underrated_index"] - top["underrated_index"].min()) /
                            (top["underrated_index"].max() - top["underrated_index"].min() + 1e-9))
    ax.barh(top["weapon"], top["underrated_index"], color=colors,
            edgecolor="white", linewidth=0.5)
    for i, (w, idx, conv, use) in enumerate(zip(
            top["weapon"], top["underrated_index"],
            top["kill_conversion"], top["usage"])):
        ax.text(idx, i, f"  conv={conv:.0%}, n={int(use):,}",
                va="center", fontsize=8, color="#333")
    ax.set_xlabel("underrated_index (z-low-usage + z-high-conversion, /2)")
    ax.set_title(f"Top {n} most-underrated weapons")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = ArgumentParser()
    parser.add_argument("--kill-records", default=KILL_RECORDS)
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--out-md", default=OUT_MD)
    parser.add_argument("--out-csv", default=OUT_CSV)
    parser.add_argument("--fig-dir", default=OUT_FIG_DIR)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out_md) or ".", exist_ok=True)
    os.makedirs(args.fig_dir, exist_ok=True)

    logger.info(f"Loading {args.kill_records}...")
    df = pd.read_parquet(args.kill_records)
    n_raw = len(df)
    logger.info(f"  raw engagements: {n_raw:,}")

    if args.since:
        cutoff = int(datetime.strptime(args.since, "%Y-%m-%d")
                     .replace(tzinfo=timezone.utc).timestamp())
        df = df[df["game_timestamp"].astype("int64") >= cutoff]
        logger.info(f"  --since {args.since} -> kept {len(df):,} of {n_raw:,}")

    logger.info(f"Loading {ETTK_RESULTS}...")
    results = pd.read_csv(ETTK_RESULTS)
    mag_by_weapon = dict(zip(results["weapon"], results["mag_4"]))

    logger.info("Computing per-weapon metrics...")
    metrics = per_weapon_metrics(df, mag_by_weapon)
    metrics = add_underrated_index(metrics)
    metrics = metrics.sort_values("underrated_index", ascending=False).reset_index(drop=True)
    logger.info(f"  weapons in scope (usage >= {MIN_USAGE}): {len(metrics)}")

    metrics.to_csv(args.out_csv, index=False)

    logger.info("Rendering charts...")
    fig_usage_conversion_scatter(metrics, os.path.join(args.fig_dir, "underrated_scatter.png"))
    fig_underrated_bars(metrics, os.path.join(args.fig_dir, "underrated_ranked_bars.png"))

    # Markdown report
    cols = ["weapon", "usage", "n_downs", "kill_conversion", "one_clip_rate",
            "solo_down_share", "damage_efficiency", "range_median", "range_bandwidth",
            "underrated_index"]
    md_table = ["| " + " | ".join(cols) + " |",
                "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in metrics.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cells.append("")
            elif c in ("usage", "n_downs"):
                cells.append(f"{int(v):,}")
            elif c in ("kill_conversion", "one_clip_rate", "solo_down_share"):
                cells.append(f"{v:.0%}")
            elif c in ("damage_efficiency",):
                cells.append(f"{v:.2f}")
            elif c in ("range_median", "range_bandwidth"):
                cells.append(f"{v:.0f}")
            elif c == "underrated_index":
                cells.append(f"{v:+.2f}")
            else:
                cells.append(str(v))
        md_table.append("| " + " | ".join(cells) + " |")

    lines = [
        "# Underrated weapons (Phase 4)",
        "",
        f"Source: `{args.kill_records}`. Filter: `--since {args.since}`. Engagements: {len(df):,}.",
        f"Per-weapon minimum usage threshold: {MIN_USAGE} engagements.",
        "",
        "## Composite ranking",
        "",
        "**`underrated_index = mean(z_low_usage, z_high_conversion)`** — high values mark weapons that pros pick rarely but kill efficiently when used. Negative values mark either over-used or low-converting weapons.",
        "",
        *md_table,
        "",
        "## Reading the columns",
        "",
        "- `usage`: total engagements where this weapon was the top attacker (downs + healed + idle).",
        "- `n_downs`: of those, how many ended in a down.",
        "- `kill_conversion`: n_downs / usage. The fraction of engagements with this weapon that ended in a kill.",
        "- `one_clip_rate`: of downs, fraction where the top attacker used <= one magazine. High = weapon finishes cleanly.",
        "- `solo_down_share`: of downs, fraction where the top attacker dealt >= 99% of damage. High = weapon carries kills without teammate help.",
        "- `damage_efficiency`: median top-attacker damage on downs / 200. 1.0 = clean, <1.0 = teammates contributed, >1.0 = overshot the down threshold.",
        "- `range_median` / `range_bandwidth`: median range and p90-p10 spread of ranges in downing engagements. Wide bandwidth = weapon works at varied distances.",
        "- `underrated_index`: composite of low-usage + high-conversion z-scores.",
        "",
        "## Charts",
        "",
        "- `underrated_scatter.png` — usage (log x) vs kill_conversion (y) scatter, weapons labeled, color = underrated_index, with quadrant guides at the medians.",
        "- `underrated_ranked_bars.png` — top 12 weapons by underrated_index with their conversion rates and engagement counts.",
        "",
        "## Notes and caveats",
        "",
        "- Usage is engagements with the top attacker as this weapon, not pickup share or ammo-found share. A weapon a pro picked up but never fired is invisible to this metric; this only measures weapons that actually entered combat.",
        "- Kill conversion confounds weapon strength with the situations the weapon is used in. A weapon used only for confirmed-kill scenarios will look better than one used in chip-trades. Cross-reference with the cluster analysis in `output/engagement_clusters.md` to see where each weapon's engagements actually land.",
        "- `solo_down_share` rewards weapons with high per-shot damage (Wingman, Kraber, Peacekeeper) because they finish solo trades; it penalizes spray weapons that contribute to focus-fire.",
        "- `damage_efficiency` near 1.0 is best (no chip-damage waste). Values much above 1.0 indicate the weapon is being used to finish already-cracked targets, which is fine but masks true kill efficiency.",
    ]
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md}, {args.out_csv}, and 2 charts under {args.fig_dir}")


if __name__ == "__main__":
    main()
