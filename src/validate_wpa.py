"""Phase 0 validation suite for the WPA baseline.

Six diagnostics:
  1. Calibration       -- mean predicted vs mean actual, binned by prediction
  2. Error stratify    -- RMSE/MAE by time_in_game, n_teams_alive, n_alive_team
  3. Per-team residual -- which teams are systematically over/under-predicted?
  4. Per-game ranking  -- within each game, does the model order teams correctly?
  5. Worst predictions -- top residuals to inspect manually
  6. Residual hist     -- are errors symmetric / bell-shaped?

Runs on both val and test splits; writes
  output/wpa/validation.md
  output/wpa/figs/*.png

Splits inferred from the same tournament-name lists used by train_wpa.py.
"""

import logging
import os
from argparse import ArgumentParser

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error

from train_wpa import (ELO_FEATURES, FEATURES, TEAM_STRENGTH_FEATURES,
                       TEST_TOURNAMENTS, TRAIN_TOURNAMENTS, VAL_TOURNAMENTS,
                       add_team_elo, add_team_strength, split_data)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

STATE_PARQUET = "data/match_state.parquet"
OUT_DIR = "output/wpa"
FIG_DIR = "output/wpa/figs"


def fit_models(state):
    train, val, test = split_data(state)
    if any(f in FEATURES for f in TEAM_STRENGTH_FEATURES):
        train, val, test, _strength = add_team_strength(train, val, test)
    if any(f in FEATURES for f in ELO_FEATURES):
        train, val, test, _elo = add_team_elo(train, val, test)
    out = {}
    for target in ["final_kills", "final_placement_rank"]:
        m = xgb.XGBRegressor(
            n_estimators=400, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=0, n_jobs=4,
            early_stopping_rounds=20, eval_metric="rmse",
        )
        m.fit(
            train[FEATURES].values, train[target].values,
            eval_set=[(val[FEATURES].values, val[target].values)],
            verbose=False,
        )
        out[target] = m
    return out, train, val, test


def predict_into(df, models):
    df = df.copy()
    df["pred_final_kills"] = models["final_kills"].predict(df[FEATURES].values)
    df["pred_final_placement_rank"] = models["final_placement_rank"].predict(df[FEATURES].values)
    df["resid_kills"] = df["final_kills"] - df["pred_final_kills"]
    df["resid_rank"] = df["final_placement_rank"] - df["pred_final_placement_rank"]
    return df


# 1. Calibration
def calibration_table(df, target, n_bins=10):
    pred_col = f"pred_{target}"
    df = df[[target, pred_col]].dropna().copy()
    df["bin"] = pd.qcut(df[pred_col], q=n_bins, duplicates="drop")
    g = df.groupby("bin", observed=True).agg(
        n=(target, "size"),
        mean_pred=(pred_col, "mean"),
        mean_actual=(target, "mean"),
        std_actual=(target, "std"),
    ).round(3).reset_index(drop=True)
    g["residual"] = (g["mean_actual"] - g["mean_pred"]).round(3)
    return g


def fig_calibration(df, target, out_path):
    pred_col = f"pred_{target}"
    df = df[[target, pred_col]].dropna()
    fig, ax = plt.subplots(figsize=(6, 6), layout="constrained")
    # 50 quantile bins for the scatter; line of identity for the diagonal
    df = df.copy()
    df["bin"] = pd.qcut(df[pred_col], q=50, duplicates="drop")
    g = df.groupby("bin", observed=True).agg(
        mean_pred=(pred_col, "mean"),
        mean_actual=(target, "mean"),
        n=(target, "size"),
    )
    ax.scatter(g["mean_pred"], g["mean_actual"], s=g["n"] / g["n"].max() * 80 + 10,
               alpha=0.6, edgecolor="white", linewidth=0.5)
    lo = min(g["mean_pred"].min(), g["mean_actual"].min())
    hi = max(g["mean_pred"].max(), g["mean_actual"].max())
    ax.plot([lo, hi], [lo, hi], "--", color="#888", linewidth=1, label="perfect calibration")
    ax.set_xlabel(f"mean predicted {target}")
    ax.set_ylabel(f"mean actual {target}")
    ax.set_title(f"Calibration: {target}")
    ax.legend(loc="upper left")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# 2. Error stratification
def error_by_bucket(df, by_col, target, bins=None, labels=None):
    pred_col = f"pred_{target}"
    df = df[[by_col, target, pred_col]].dropna().copy()
    if bins is not None:
        df["bucket"] = pd.cut(df[by_col], bins=bins, labels=labels, include_lowest=True)
    else:
        df["bucket"] = df[by_col].astype("Int64").astype(str)
    g = df.groupby("bucket", observed=True).apply(
        lambda x: pd.Series({
            "n": len(x),
            "MAE": mean_absolute_error(x[target], x[pred_col]),
            "RMSE": mean_squared_error(x[target], x[pred_col]) ** 0.5,
            "mean_actual": x[target].mean(),
            "std_actual": x[target].std(),
        }), include_groups=False,
    ).round(3)
    return g


def fig_error_by_bucket(df, by_col, target, bins, labels, out_path, by_label):
    g = error_by_bucket(df, by_col, target, bins=bins, labels=labels)
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    x = np.arange(len(g))
    ax.bar(x, g["RMSE"], color="#0077BB", alpha=0.85, label="RMSE")
    ax.bar(x, g["MAE"], color="#EE7733", alpha=0.85, label="MAE", width=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(g.index.astype(str), rotation=15, ha="right")
    ax.set_xlabel(by_label)
    ax.set_ylabel("error")
    for xi, n in zip(x, g["n"]):
        ax.text(xi, 0, f"n={int(n):,}", ha="center", va="bottom",
                fontsize=7, color="#444", rotation=90)
    ax.set_title(f"{target} error by {by_label}")
    ax.legend(loc="upper right", fontsize=8)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# 3. Per-team residuals
def per_team_residuals(df, target, min_rows=200):
    pred_col = f"pred_{target}"
    df = df.dropna(subset=[target, pred_col, "team"]).copy()
    g = df.groupby("team").agg(
        n=(target, "size"),
        mean_actual=(target, "mean"),
        mean_pred=(pred_col, "mean"),
    )
    g["mean_residual"] = (g["mean_actual"] - g["mean_pred"]).round(3)
    return g[g["n"] >= min_rows].sort_values("mean_residual")


def fig_team_residuals(df, target, out_path, min_rows=200, top_k=12):
    g = per_team_residuals(df, target, min_rows=min_rows)
    if len(g) == 0:
        return
    pos = g.sort_values("mean_residual", ascending=False).head(top_k)
    neg = g.sort_values("mean_residual").head(top_k)
    sel = pd.concat([neg, pos]).sort_values("mean_residual")
    fig, ax = plt.subplots(figsize=(8, max(4, 0.32 * len(sel))), layout="constrained")
    colors = ["#CC3311" if r < 0 else "#117733" for r in sel["mean_residual"]]
    ax.barh(sel.index, sel["mean_residual"], color=colors, edgecolor="white", linewidth=0.5)
    for y, (team, row) in enumerate(sel.iterrows()):
        ax.text(row["mean_residual"], y,
                f"  n={int(row['n']):,}",
                va="center", fontsize=7, color="#444")
    ax.axvline(0, color="#888", linewidth=0.6)
    ax.set_xlabel(f"mean residual ({target}) — positive: outperformed model")
    ax.set_title(f"Per-team residuals: {target} (min n={min_rows})")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# 4. Per-game rank correlation
def per_game_rank_corr(df):
    """For each game, take the LAST snapshot per team, compute spearman
    between predicted_placement_rank and actual_placement_rank."""
    last = (df.sort_values("ts").groupby(["game_id", "team"], sort=False).tail(1)
            .dropna(subset=["pred_final_placement_rank", "final_placement_rank"]))
    rows = []
    for gid, g in last.groupby("game_id"):
        if len(g) < 5:
            continue
        rho, _ = spearmanr(g["pred_final_placement_rank"], g["final_placement_rank"])
        rows.append({"game_id": gid, "n_teams": len(g), "spearman_rho": rho})
    return pd.DataFrame(rows)


# 5. Worst predictions
def worst_predictions(df, target, n=20):
    pred_col = f"pred_{target}"
    df = df.dropna(subset=[target, pred_col]).copy()
    df["abs_resid"] = (df[target] - df[pred_col]).abs()
    return df.nlargest(n, "abs_resid")[
        ["game_id", "team", "ts", "n_alive_team", "kills_so_far_team",
         "n_teams_alive", "time_in_game_s", target, pred_col, "abs_resid"]
    ].round(2)


# 6. Residual histogram
def fig_residual_hist(df, target, out_path):
    pred_col = f"pred_{target}"
    resid = (df[target] - df[pred_col]).dropna()
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.hist(resid, bins=60, color="#0077BB", alpha=0.85, edgecolor="white", linewidth=0.4)
    ax.axvline(0, color="#888", linewidth=0.8)
    ax.axvline(resid.mean(), color="#CC3311", linewidth=1.0, label=f"mean={resid.mean():+.2f}")
    ax.axvline(resid.median(), color="#117733", linewidth=1.0, label=f"median={resid.median():+.2f}")
    ax.set_xlabel(f"residual: actual - predicted ({target})")
    ax.set_ylabel("count")
    ax.set_title(f"Residual distribution: {target}")
    ax.legend()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def df_to_md(df, index=False):
    cols = ([df.index.name or "bucket"] if index else []) + list(df.columns)
    rows = ["| " + " | ".join(str(c) for c in cols) + " |",
            "|" + "|".join(["---"] * len(cols)) + "|"]
    for idx, r in df.iterrows():
        cells = ([str(idx)] if index else []) + [
            f"{v:.3f}" if isinstance(v, float) else str(v) for v in r
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def main():
    parser = ArgumentParser()
    parser.add_argument("--state", default=STATE_PARQUET)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--fig-dir", default=FIG_DIR)
    args = parser.parse_args()
    os.makedirs(args.fig_dir, exist_ok=True)

    logger.info(f"Loading {args.state}...")
    state = pd.read_parquet(args.state).dropna(
        subset=["final_kills", "final_placement_rank", "tournament_full_name"]
    )

    logger.info("Fitting models on train, predicting on train/val/test...")
    models, train, val, test = fit_models(state)
    train_p = predict_into(train, models)
    val_p = predict_into(val, models)
    test_p = predict_into(test, models)

    sections = [
        "# WPA validation (Phase 0, Y4)",
        "",
        f"Train: {len(train):,} rows, {train['game_id'].nunique()} games. "
        f"Val: {len(val):,} rows, {val['game_id'].nunique()} games. "
        f"Test: {len(test):,} rows, {test['game_id'].nunique()} games.",
        "",
    ]

    # 1. Calibration
    sections += ["## 1. Calibration (test set)", ""]
    for target in ["final_kills", "final_placement_rank"]:
        cal = calibration_table(test_p, target, n_bins=10)
        sections += [f"### {target}", "", df_to_md(cal), ""]
        fig_calibration(test_p, target,
                        os.path.join(args.fig_dir, f"calibration_{target}.png"))

    # 2. Error stratification (test set)
    sections += ["## 2. Error stratification (test set)", ""]

    time_bins = [-1, 60, 300, 600, 900, 1200, 1800, 1e9]
    time_labels = ["<1m", "1-5m", "5-10m", "10-15m", "15-20m", "20-30m", "30m+"]
    teams_bins = [-1, 5, 10, 14, 18, 21]
    teams_labels = ["1-5", "6-10", "11-14", "15-18", "19-20"]
    alive_bins = [-1, 0, 1, 2, 3]
    alive_labels = ["0 (eliminated)", "1", "2", "3"]

    for target in ["final_kills", "final_placement_rank"]:
        sections += [f"### {target} by time_in_game_s",
                     "",
                     df_to_md(error_by_bucket(test_p, "time_in_game_s", target,
                                              bins=time_bins, labels=time_labels),
                              index=True),
                     ""]
        fig_error_by_bucket(test_p, "time_in_game_s", target,
                            time_bins, time_labels,
                            os.path.join(args.fig_dir, f"error_by_time_{target}.png"),
                            by_label="time_in_game")

        sections += [f"### {target} by n_teams_alive",
                     "",
                     df_to_md(error_by_bucket(test_p, "n_teams_alive", target,
                                              bins=teams_bins, labels=teams_labels),
                              index=True),
                     ""]
        fig_error_by_bucket(test_p, "n_teams_alive", target,
                            teams_bins, teams_labels,
                            os.path.join(args.fig_dir, f"error_by_n_teams_{target}.png"),
                            by_label="n_teams_alive")

        sections += [f"### {target} by n_alive_team",
                     "",
                     df_to_md(error_by_bucket(test_p, "n_alive_team", target,
                                              bins=alive_bins, labels=alive_labels),
                              index=True),
                     ""]

    # 3. Per-team residuals (test set)
    sections += ["## 3. Per-team residuals (test set, min n=200)", ""]
    for target in ["final_kills", "final_placement_rank"]:
        g = per_team_residuals(test_p, target, min_rows=200)
        if len(g) == 0:
            sections += [f"### {target}", "", "_no teams with n>=200_", ""]
            continue
        worst = g.sort_values("mean_residual").head(8)
        best = g.sort_values("mean_residual", ascending=False).head(8)
        sections += [f"### {target} — most under-predicted (model said worse than actual)", "",
                     df_to_md(best.round(3), index=True), ""]
        sections += [f"### {target} — most over-predicted (model said better than actual)", "",
                     df_to_md(worst.round(3), index=True), ""]
        fig_team_residuals(test_p, target,
                           os.path.join(args.fig_dir, f"team_residuals_{target}.png"),
                           min_rows=200, top_k=12)

    # 4. Per-game rank correlation
    sections += ["## 4. Per-game placement-rank Spearman (test set)", ""]
    rk = per_game_rank_corr(test_p)
    sections += [
        f"Median Spearman rho across {len(rk)} test games: **{rk['spearman_rho'].median():.3f}**.",
        f"Mean: {rk['spearman_rho'].mean():.3f}. q25: {rk['spearman_rho'].quantile(.25):.3f}. "
        f"q75: {rk['spearman_rho'].quantile(.75):.3f}.",
        "",
        f"Games with rho < 0.5: {(rk['spearman_rho'] < 0.5).sum()} / {len(rk)}.",
        f"Games with rho > 0.8: {(rk['spearman_rho'] > 0.8).sum()} / {len(rk)}.",
        "",
        "_Spearman rho measures whether the model's ordering of teams within a game matches "
        "the actual placement order, ignoring absolute prediction errors._",
        "",
    ]

    # 5. Worst predictions
    sections += ["## 5. Worst predictions (test set, top 15 absolute residuals)", ""]
    for target in ["final_kills", "final_placement_rank"]:
        sections += [f"### {target}", "",
                     df_to_md(worst_predictions(test_p, target, n=15)),
                     ""]

    # 6. Residual histograms
    sections += ["## 6. Residual distributions", ""]
    for target in ["final_kills", "final_placement_rank"]:
        fig_residual_hist(test_p, target,
                          os.path.join(args.fig_dir, f"resid_hist_{target}.png"))
        sections += [f"![Residual hist {target}](figs/resid_hist_{target}.png)", ""]

    out_md = os.path.join(args.out_dir, "validation.md")
    with open(out_md, "w") as fh:
        fh.write("\n".join(sections) + "\n")
    logger.info(f"Wrote {out_md} and figures to {args.fig_dir}")


if __name__ == "__main__":
    main()
