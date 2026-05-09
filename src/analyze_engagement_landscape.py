"""Phase 2-pre: weapon-agnostic engagement landscape.

Sits in front of per-weapon analysis. Five descriptive views over all
engagements in `data/kill_records.parquet`:

  1. Engagement duration histogram (split by ended_by)
  2. Total damage delivered histogram (with shield/health reference lines)
  3. Number of distinct attackers per engagement
  4. Observed accuracy distribution (per engagement, weighted by top attacker)
  5. Engagement-type breakdown (ended_by) for context

Plus a 2D scatter: range vs. duration for down-ending engagements only.

The `--since YYYY-MM-DD` filter scopes by `game_timestamp` so analyses can
focus on a single weapon-balance regime (defaults to 2025-02-10, the S24
takeover patch where R-99 dropped 14->13).

Outputs:
  output/engagement_landscape.md
  output/ettk_figs/landscape_duration.png
  output/ettk_figs/landscape_total_damage.png
  output/ettk_figs/landscape_n_attackers.png
  output/ettk_figs/landscape_accuracy.png
  output/ettk_figs/landscape_ended_by.png
  output/ettk_figs/landscape_range_vs_duration.png
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
OUT_MD = "output/engagement_landscape.md"
OUT_FIG_DIR = "output/ettk_figs"
DEFAULT_SINCE = "2025-02-10"  # S24 Takeover patch: post-R-99 14->13 nerf

# Apex shield/health reference values (post-Y6 Evo Shield system)
HP_REFERENCES = [
    (50, "white shield only"),
    (75, "blue shield only"),
    (100, "100 HP (purple shield-only OR full body)"),
    (175, "blue + body"),
    (200, "purple + body (canonical)"),
    (225, "red + body"),
]

_HERE = Path(__file__).parent
_STYLE = _HERE / "research_vibrant.mplstyle"
if _STYLE.exists():
    plt.style.use(str(_STYLE))


def per_engagement_observed_accuracy(row):
    """Return top-attacker accuracy (shots_hit / ammo_used) for a row, or None
    if the contributors_json doesn't carry usable shots/ammo."""
    try:
        ctr = json.loads(row["contributors_json"])
    except Exception:
        return None
    top = next((c for c in ctr if c["attacker_hash"] == row["top_attacker_hash"]), None)
    if not top:
        return None
    ammo = top.get("ammo_used") or 0
    if ammo <= 0:
        return None
    return top.get("shots_hit", 0) / ammo


def fig_duration_hist(df, out_path):
    fig, ax = plt.subplots(figsize=(9, 5.0))
    cap = min(60, int(df["duration_s"].quantile(0.99)))
    bins = np.arange(0, cap + 1.5, 1.0)
    by_end = {k: df[df["ended_by"] == k]["duration_s"].clip(upper=cap) for k in ["down", "healed", "idle"]}
    palette = {"down": "#CC3311", "healed": "#009988", "idle": "#888888"}
    ax.hist([by_end[k] for k in ["down", "healed", "idle"]],
            bins=bins, stacked=True,
            color=[palette[k] for k in ["down", "healed", "idle"]],
            label=["down", "healed (target reset)", "idle (timeout)"],
            edgecolor="white", linewidth=0.4)
    ax.set_xlim(0, cap)
    ax.set_xlabel("engagement duration (s)")
    ax.set_ylabel("engagement count")
    ax.set_title("Engagement duration distribution")
    ax.legend(loc="upper right", fontsize=9, frameon=True,
              facecolor="white", edgecolor="#ccc")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_total_damage_hist(df, out_path):
    fig, ax = plt.subplots(figsize=(9, 5.0))
    cap = 260
    bins = np.arange(0, cap + 6, 5)
    by_end = {k: df[df["ended_by"] == k]["total_damage"].clip(upper=cap) for k in ["down", "healed", "idle"]}
    palette = {"down": "#CC3311", "healed": "#009988", "idle": "#888888"}
    ax.hist([by_end[k] for k in ["down", "healed", "idle"]],
            bins=bins, stacked=True,
            color=[palette[k] for k in ["down", "healed", "idle"]],
            label=["down", "healed (target reset)", "idle (timeout)"],
            edgecolor="white", linewidth=0.4)
    ymax = ax.get_ylim()[1]
    for hp, _ in HP_REFERENCES:
        ax.axvline(hp, color="#333", linestyle=":", linewidth=0.8, alpha=0.45)
        ax.text(hp, ymax * 0.98, f"{hp}", fontsize=7, ha="center", va="top",
                bbox=dict(facecolor="white", edgecolor="none", pad=1, alpha=0.8))
    ax.set_xlim(0, cap)
    ax.set_xlabel("total damage delivered (HP)")
    ax.set_ylabel("engagement count")
    ax.set_title("Damage delivered per engagement")
    ax.legend(loc="upper right", fontsize=9, frameon=True,
              facecolor="white", edgecolor="#ccc")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_n_attackers(df, out_path):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    n = df["n_attackers"].clip(upper=5)
    bins = np.arange(0.5, 6.5, 1.0)
    palette = {"down": "#CC3311", "healed": "#009988", "idle": "#888888"}
    by_end = {k: n[df["ended_by"] == k] for k in ["down", "healed", "idle"]}
    ax.hist([by_end[k] for k in ["down", "healed", "idle"]],
            bins=bins, stacked=True,
            color=[palette[k] for k in ["down", "healed", "idle"]],
            label=["down", "healed", "idle"],
            edgecolor="white", linewidth=0.4)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["1", "2", "3", "4", "5+"])
    ax.set_xlabel("distinct attackers in engagement")
    ax.set_ylabel("engagement count")
    ax.set_title("Number of attackers per engagement")
    ax.legend(loc="upper right", fontsize=9, frameon=True,
              facecolor="white", edgecolor="#ccc")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_accuracy_hist(df, accuracies, out_path):
    if not accuracies:
        return
    fig, ax = plt.subplots(figsize=(9, 5.0))
    bins = np.arange(0, 1.05, 0.05)
    ax.hist(accuracies, bins=bins, color="#0077BB", alpha=0.85,
            edgecolor="white", linewidth=0.5)
    s = pd.Series(accuracies)
    for q, label in [(0.25, "q25"), (0.50, "median"), (0.75, "q75")]:
        v = s.quantile(q)
        ax.axvline(v, color="#CC3311", linestyle="--", linewidth=1.0, alpha=0.8)
        ax.text(v, ax.get_ylim()[1] * 0.95, f"{label}={v:.2f}",
                fontsize=8, ha="center", va="top", color="#CC3311",
                bbox=dict(facecolor="white", edgecolor="none", pad=1, alpha=0.8))
    ax.set_xlim(0, 1)
    ax.set_xlabel("observed accuracy (top attacker, shots_hit / ammo_used)")
    ax.set_ylabel("engagement count")
    ax.set_title(f"Observed accuracy across engagements (n={len(accuracies):,})")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_ended_by(df, out_path):
    fig, ax = plt.subplots(figsize=(7, 4.0))
    counts = df["ended_by"].value_counts()
    order = ["down", "healed", "idle"]
    counts = counts.reindex(order, fill_value=0)
    palette = {"down": "#CC3311", "healed": "#009988", "idle": "#888888"}
    bars = ax.bar(counts.index, counts.values,
                  color=[palette[k] for k in counts.index],
                  edgecolor="white", linewidth=0.5)
    for b, v in zip(bars, counts.values):
        pct = v / counts.sum() * 100
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}\n({pct:.1f}%)",
                ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("engagement outcome")
    ax.set_ylabel("count")
    ax.set_title(f"Engagement outcomes (n={counts.sum():,})")
    ax.set_ylim(0, counts.max() * 1.18)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_range_vs_duration(df, out_path):
    """Scatter restricted to down-ending engagements where median distance
    is known. Shows whether long-range fights take longer."""
    sub = df[df["downed"] & df["top_attacker_median_distance"].notna()].copy()
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    cap_dur = min(20, int(sub["duration_s"].quantile(0.99)))
    cap_rng = min(150, int(sub["top_attacker_median_distance"].quantile(0.99)))
    sub = sub[sub["duration_s"] <= cap_dur]
    sub = sub[sub["top_attacker_median_distance"] <= cap_rng]
    ax.scatter(sub["top_attacker_median_distance"], sub["duration_s"],
               s=5, alpha=0.20, color="#0077BB", edgecolor="none")
    ax.set_xlim(0, cap_rng)
    ax.set_ylim(-0.3, cap_dur + 0.5)
    ax.set_xlabel("median range (m)")
    ax.set_ylabel("engagement duration (s)")
    ax.set_title(f"Range vs duration, down-ending engagements (n={len(sub):,})")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = ArgumentParser()
    parser.add_argument("--kill-records", default=KILL_RECORDS)
    parser.add_argument("--since", default=DEFAULT_SINCE,
                        help=f"Filter engagements to game_timestamp >= this date (YYYY-MM-DD). Default: {DEFAULT_SINCE}.")
    parser.add_argument("--out-md", default=OUT_MD)
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
        logger.info(f"  --since {args.since} -> kept {len(df):,} of {n_raw:,} ({len(df)/n_raw:.1%})")

    if df.empty:
        logger.error("No engagements after filter; aborting")
        return

    logger.info("Computing per-engagement observed accuracy from contributors_json...")
    accuracies = []
    for _, r in df.iterrows():
        a = per_engagement_observed_accuracy(r)
        if a is not None and 0 <= a <= 1:
            accuracies.append(a)
    logger.info(f"  accuracies extracted: {len(accuracies):,}")

    logger.info("Rendering charts...")
    fig_duration_hist(df, os.path.join(args.fig_dir, "landscape_duration.png"))
    fig_total_damage_hist(df, os.path.join(args.fig_dir, "landscape_total_damage.png"))
    fig_n_attackers(df, os.path.join(args.fig_dir, "landscape_n_attackers.png"))
    fig_accuracy_hist(df, accuracies, os.path.join(args.fig_dir, "landscape_accuracy.png"))
    fig_ended_by(df, os.path.join(args.fig_dir, "landscape_ended_by.png"))
    fig_range_vs_duration(df, os.path.join(args.fig_dir, "landscape_range_vs_duration.png"))

    # Markdown summary
    n = len(df)
    n_down = int(df["downed"].sum())
    end_counts = df["ended_by"].value_counts()
    multi = int((df["n_attackers"] > 1).sum())
    duration_q = df["duration_s"].quantile([0.25, 0.5, 0.75, 0.95]).round(2)
    dmg_q = df["total_damage"].quantile([0.25, 0.5, 0.75, 0.95]).round(0)
    acc_s = pd.Series(accuracies)
    acc_q = acc_s.quantile([0.25, 0.5, 0.75]).round(3) if not acc_s.empty else None

    lines = [
        "# Engagement landscape (weapon-agnostic)",
        "",
        f"Source: `{args.kill_records}`. Filter: `--since {args.since}`. Total engagements: **{n:,}**.",
        "",
        "## Headline numbers",
        "",
        f"- Engagements ending in down: **{n_down:,} ({n_down/n:.1%})**.",
        f"- Engagements ending in heal-back: **{end_counts.get('healed', 0):,} ({end_counts.get('healed', 0)/n:.1%})** — target absorbed damage but reset to full HP without going down.",
        f"- Engagements ending idle: **{end_counts.get('idle', 0):,} ({end_counts.get('idle', 0)/n:.1%})** — no follow-up damage within the idle timeout, victim survived without fully healing.",
        f"- Multi-attacker engagements: **{multi:,} ({multi/n:.1%})** — at least two players hit the victim within the engagement window.",
        "",
        "## Distributions",
        "",
        f"- **Duration** (s): q25={duration_q[0.25]}, median={duration_q[0.50]}, q75={duration_q[0.75]}, q95={duration_q[0.95]}.",
        f"- **Total damage delivered** (HP): q25={int(dmg_q[0.25])}, median={int(dmg_q[0.50])}, q75={int(dmg_q[0.75])}, q95={int(dmg_q[0.95])}.",
    ]
    if acc_q is not None:
        lines.append(f"- **Observed accuracy** (top attacker, shots_hit / ammo_used): q25={acc_q[0.25]}, median={acc_q[0.50]}, q75={acc_q[0.75]}, n={len(accuracies):,}.")

    lines += [
        "",
        "## Charts",
        "",
        "- `landscape_duration.png` — duration histogram, stacked by ended_by.",
        "- `landscape_total_damage.png` — damage-delivered histogram with shield-tier reference lines (50, 75, 100, 175, 200, 225 HP).",
        "- `landscape_n_attackers.png` — distinct-attacker count distribution.",
        "- `landscape_accuracy.png` — observed-accuracy distribution with q25/median/q75.",
        "- `landscape_ended_by.png` — engagement-outcome bar chart with counts and percentages.",
        "- `landscape_range_vs_duration.png` — scatter for down-ending engagements only; does range affect duration?",
        "",
        "## Notes",
        "",
        f"- The `--since` cutoff defaults to {DEFAULT_SINCE} (S24 Takeover patch, the post-R-99-14-to-13 regime). Earlier balance regimes are excluded by default to avoid mixing patch states.",
        "- Observed accuracy is the top attacker's `shots_hit / ammo_used` from the engagement's contributors. For multi-burst engagements this is a per-burst-aggregate, biased upward vs sustained-fire accuracy.",
        "- Range is the top attacker's median distance across the engagement; engagements without distance data (rare) are excluded from the range scatter.",
    ]
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md} and 6 charts under {args.fig_dir}")


if __name__ == "__main__":
    main()
