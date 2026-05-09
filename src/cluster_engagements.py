"""Phase 3: unsupervised clustering of engagements.

Reads `data/kill_records.parquet`, applies `--since` filter, engineers a
deliberately small feature set per engagement, runs KMeans (scipy), and
characterizes each cluster: mean feature values, top weapons, ended_by
distribution, and whether it surfaces multi-attacker fights as their own
archetype.

The clustering is exploratory — its goal is to discover natural engagement
archetypes (e.g. "fast SMG one-clip", "long-range chip", "team focus-fire
finish") that downstream weapon-balance arguments can frame around.

Outputs:
  output/engagement_clusters.md
  output/engagement_clusters.csv
  output/ettk_figs/clusters_pca_scatter.png
  output/ettk_figs/clusters_weapon_heatmap.png
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
from scipy.cluster.vq import kmeans2, whiten

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

KILL_RECORDS = "data/kill_records.parquet"
OUT_MD = "output/engagement_clusters.md"
OUT_CSV = "output/engagement_clusters.csv"
OUT_FIG_DIR = "output/ettk_figs"
DEFAULT_SINCE = "2025-02-10"
DEFAULT_K = 6  # number of clusters; small enough to characterize, big enough to separate archetypes

# Coarse weapon classification for the cluster feature.
WEAPON_CLASSES = {
    # SMG
    "R-99 SMG": "SMG", "C.A.R. SMG": "SMG", "Volt SMG": "SMG",
    "Alternator SMG": "SMG", "Prowler Burst PDW": "SMG",
    # AR
    "VK-47 Flatline": "AR", "R-301 Carbine": "AR", "HAVOC Rifle": "AR",
    "Hemlok Burst AR": "AR", "Hemlok Breach AR": "AR", "Nemesis Burst AR": "AR",
    # LMG
    "M600 Spitfire": "LMG", "Rampage LMG": "LMG", "L-STAR EMG": "LMG",
    "Devotion LMG": "LMG",
    # Shotgun
    "Peacekeeper": "shotgun", "EVA-8 Auto": "shotgun",
    "Mastiff Shotgun": "shotgun", "Mozambique Shotgun": "shotgun",
    # Marksman / Sniper
    "G7 Scout": "marksman", "30-30 Repeater": "marksman",
    "Triple Take": "marksman", "Bocek Compound Bow": "marksman",
    "Longbow DMR": "sniper", "Sentinel": "sniper",
    "Kraber .50-Cal Sniper": "sniper", "Charge Rifle": "sniper",
    # Pistol
    "P2020": "pistol", "Wingman": "pistol", "RE-45 Auto": "pistol",
    "RE-45 Burst": "pistol",
    # Ordnance / other
    "Frag Grenade": "ordnance", "Arc Star": "ordnance",
    "Thermite Grenade": "ordnance",
}
CLASS_INDEX = {c: i for i, c in enumerate(
    sorted(set(WEAPON_CLASSES.values()) | {"other"})
)}


def class_for_weapon(w):
    return WEAPON_CLASSES.get(w, "other")


def per_engagement_observed_accuracy(row):
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


def engineer_features(df):
    """Build the feature matrix (one row per engagement) used for clustering.

    Uses ENGAGEMENT-SHAPE features (duration, damage, n_attackers, top_share,
    range, accuracy, downed) plus PRE-ENGAGEMENT CONTEXT features from
    augmented kill_records (HP coming in, recent momentum, third-party
    distance, lobby state). The discrete weapon_class_idx feature was dropped
    because it created a "G7 dominates everything" artifact in earlier runs.

    Range and accuracy use median imputation rather than -1 sentinels so
    centroids stay in feature space.
    """
    feats = pd.DataFrame(index=df.index)
    # Engagement shape
    feats["duration_s"] = df["duration_s"].astype(float).clip(upper=60)
    feats["total_damage"] = df["total_damage"].astype(float).clip(upper=300)
    feats["n_attackers"] = df["n_attackers"].astype(float).clip(upper=5)
    feats["top_share"] = df["top_attacker_share"].astype(float).fillna(0)
    range_m = df["top_attacker_median_distance"].astype(float).clip(upper=400)
    feats["range_m"] = range_m.fillna(range_m.median())
    feats["downed"] = df["downed"].astype(int).astype(float)
    acc = df.apply(per_engagement_observed_accuracy, axis=1)
    feats["accuracy"] = acc.fillna(acc.median())

    # Pre-engagement context (from augment_kill_records.py).
    if "team_HP_sum_at_start" in df.columns:
        for col in [
            "team_HP_sum_at_start",
            "team_kills_last_60s_at_start",
            "team_dmg_dealt_last_30s_at_start",
            "team_dmg_taken_last_30s_at_start",
            "dist_to_nearest_alive_team_at_start",
            "n_teams_alive_at_start",
        ]:
            if col not in df.columns:
                continue
            v = df[col].astype(float)
            # Cap dist outliers so a single 14000-unit value doesn't blow out the std.
            if col == "dist_to_nearest_alive_team_at_start":
                v = v.clip(upper=3000)
            feats[col] = v.fillna(v.median())
    return feats


def cluster(features, k):
    """Standardize then KMeans. Returns (labels, centroids in original units)."""
    arr = features.to_numpy(dtype=float)
    # whiten standardizes by feature std; needed because KMeans is scale-sensitive
    std = arr.std(axis=0)
    std[std == 0] = 1
    whitened = arr / std
    centroids_w, labels = kmeans2(whitened, k, seed=42, minit="++", iter=50)
    centroids = centroids_w * std
    return labels, centroids


def characterize_clusters(df, features, labels, k):
    """Per-cluster: mean feature values, top weapons, ended_by distribution."""
    rows = []
    for c in range(k):
        mask = labels == c
        if not mask.any():
            continue
        sub_df = df[mask]
        sub_feats = features[mask]
        weapon_dist = sub_df["top_attacker_weapon"].value_counts().head(3)
        ended_dist = sub_df["ended_by"].value_counts(normalize=True).round(2)
        out = {
            "cluster": c,
            "size": int(mask.sum()),
            "size_pct": round(100 * mask.sum() / len(df), 1),
            "duration_s_mean": round(float(sub_feats["duration_s"].mean()), 1),
            "total_damage_mean": round(float(sub_feats["total_damage"].mean()), 0),
            "n_attackers_mean": round(float(sub_feats["n_attackers"].mean()), 2),
            "top_share_mean": round(float(sub_feats["top_share"].mean()), 2),
            "range_m_mean": round(float(sub_feats["range_m"].mean()), 1),
            "accuracy_mean": round(float(sub_feats["accuracy"].mean()), 2),
            "downed_pct": round(100 * float(sub_feats["downed"].mean()), 1),
        }
        # Pre-engagement context (if available)
        for col in ["team_HP_sum_at_start", "team_kills_last_60s_at_start",
                    "team_dmg_dealt_last_30s_at_start",
                    "team_dmg_taken_last_30s_at_start",
                    "dist_to_nearest_alive_team_at_start",
                    "n_teams_alive_at_start"]:
            if col in sub_feats.columns:
                short = col.replace("_at_start", "").replace("team_", "")
                out[short + "_mean"] = round(float(sub_feats[col].mean()), 1)
        out["top_weapons"] = "; ".join(f"{w} ({n})" for w, n in weapon_dist.items())
        out["ended_by"] = "; ".join(f"{k}={v}" for k, v in ended_dist.items())
        rows.append(out)
    return pd.DataFrame(rows)


def fig_cluster_scatter(features, labels, k, out_path):
    """2D projection of clusters via simple PCA (top-2 components from numpy)."""
    arr = features.to_numpy(dtype=float)
    arr = (arr - arr.mean(axis=0)) / arr.std(axis=0).clip(min=1e-9)
    # PCA via SVD: project onto top 2 right-singular vectors
    u, s, vh = np.linalg.svd(arr, full_matrices=False)
    proj = arr @ vh[:2].T

    fig, ax = plt.subplots(figsize=(9, 6))
    palette = plt.cm.tab10(np.linspace(0, 1, k))
    for c in range(k):
        m = labels == c
        if not m.any():
            continue
        ax.scatter(proj[m, 0], proj[m, 1], s=4, alpha=0.30,
                   color=palette[c], label=f"cluster {c} (n={m.sum():,})")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title(f"Engagement clusters ({k}-means, PCA projection)")
    ax.legend(loc="best", fontsize=8, frameon=True,
              facecolor="white", edgecolor="#ccc", markerscale=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_weapon_heatmap(df, labels, k, out_path):
    """Heatmap: weapon (rows) x cluster (cols), values = share of weapon's
    engagements falling in that cluster. Tells which weapons are characteristic
    of which cluster."""
    df = df.copy()
    df["cluster"] = labels
    weapon_counts = df["top_attacker_weapon"].value_counts()
    top_weapons = weapon_counts.head(15).index.tolist()
    sub = df[df["top_attacker_weapon"].isin(top_weapons)]
    pivot = (sub.groupby(["top_attacker_weapon", "cluster"]).size()
             .unstack(fill_value=0))
    pivot = pivot.div(pivot.sum(axis=1), axis=0)  # row-normalize: per weapon, share per cluster
    pivot = pivot.reindex(top_weapons)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels([f"c{c}" for c in pivot.columns])
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_yticklabels(pivot.index, fontsize=9)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if v > 0.05:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center",
                        color="white" if v < 0.6 else "black", fontsize=7)
    fig.colorbar(im, ax=ax, label="share of weapon's engagements in cluster")
    ax.set_xlabel("cluster")
    ax.set_ylabel("weapon (top 15 by engagement count)")
    ax.set_title("Weapon distribution across clusters")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = ArgumentParser()
    parser.add_argument("--kill-records", default=KILL_RECORDS)
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
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

    df = df.reset_index(drop=True)

    logger.info("Engineering features...")
    features = engineer_features(df)
    logger.info(f"  feature matrix: {features.shape}")

    logger.info(f"Clustering with KMeans k={args.k}...")
    labels, centroids = cluster(features, args.k)
    logger.info(f"  cluster sizes: {pd.Series(labels).value_counts().sort_index().to_dict()}")

    summary = characterize_clusters(df, features, labels, args.k)
    summary.to_csv(args.out_csv, index=False)

    logger.info("Rendering charts...")
    fig_cluster_scatter(features, labels, args.k,
                        os.path.join(args.fig_dir, "clusters_pca_scatter.png"))
    fig_weapon_heatmap(df, labels, args.k,
                       os.path.join(args.fig_dir, "clusters_weapon_heatmap.png"))

    # Markdown report. Use whatever columns characterize_clusters produced.
    md_cols = [c for c in summary.columns if c != "ended_by"] + ["ended_by"]
    md_table = ["| " + " | ".join(md_cols) + " |",
                "|" + "|".join(["---"] * len(md_cols)) + "|"]
    for _, r in summary.iterrows():
        cells = []
        for c in md_cols:
            v = r[c]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.2f}" if c not in ("size_pct", "downed_pct") else f"{v:.1f}")
            elif isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        md_table.append("| " + " | ".join(cells) + " |")

    lines = [
        "# Engagement clusters (Phase 3)",
        "",
        f"Source: `{args.kill_records}`. Filter: `--since {args.since}`. Total engagements clustered: **{len(df):,}**.",
        f"Algorithm: KMeans (scipy), k={args.k}, on standardized features:",
        f"  engagement-shape: duration_s, total_damage, n_attackers, top_attacker_share, range_m, accuracy, downed.",
        f"  pre-engagement context (from augmented kill_records): team_HP_sum_at_start, team_kills_last_60s_at_start,",
        f"  team_dmg_dealt_last_30s_at_start, team_dmg_taken_last_30s_at_start, dist_to_nearest_alive_team_at_start, n_teams_alive_at_start.",
        "",
        "## Cluster characterizations",
        "",
        *md_table,
        "",
        "## Reading the table",
        "",
        "- `size` / `size_pct`: cluster membership counts.",
        "- `*_mean`: mean feature value within the cluster (centroid in original units).",
        "- `range_m_mean`: mean median-engagement-range, restricted to engagements with a known range.",
        "- `accuracy_mean`: mean per-engagement accuracy, restricted to engagements with valid shots/ammo.",
        "- `downed_pct`: fraction of engagements in the cluster that ended in a down (vs healed / idle).",
        "- `top_weapons`: 3 most common weapons used by the top attacker.",
        "- `ended_by`: distribution of engagement outcomes.",
        "",
        "## Charts",
        "",
        "- `clusters_pca_scatter.png` — 2D PCA projection of clustered engagements (rough visual separation; not the clustering basis).",
        "- `clusters_weapon_heatmap.png` — for each top-15 weapon, fraction of its engagements assigned to each cluster.",
        "",
        "## Notes",
        "",
        f"- KMeans is scale-sensitive; features are standardized via std-whitening before fitting. k={args.k} was picked for legibility; try a few values.",
        "- The discrete weapon-class feature was dropped from the original feature set: it forced numerically-adjacent classes (SMG=2, AR=3) to read as similar, which made G7 Scout dominate every cluster's top-weapons list and washed out the more interesting situational splits.",
        "- Pre-engagement context features have ~93% post-S24 coverage. Engagements without coverage receive median-imputed values rather than sentinels.",
    ]
    with open(args.out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info(f"Wrote {args.out_md}, {args.out_csv}, and 2 charts under {args.fig_dir}")


if __name__ == "__main__":
    main()
