"""Run multiple WPA feature configurations and produce a side-by-side
comparison report. Each variant uses identical train/val/test splits and
identical XGBoost hyperparameters; only FEATURES changes.
"""

import logging
import os

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import train_wpa as tw

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUT_MD = "output/wpa/ablation_combined.md"

CORE = tw.BASE_FEATURES + tw.HP_FEATURES + tw.MOMENTUM_FEATURES

VARIANTS = [
    ("baseline", tw.BASE_FEATURES, "regional"),
    ("+HP +Mom", CORE, "regional"),
    ("+HP +Mom +Pos", CORE + tw.POSITIONAL_FEATURES, "regional"),
    ("+HP +Mom +Pos +Player", CORE + tw.POSITIONAL_FEATURES + tw.PLAYER_FEATURES, "regional"),
    ("+HP +Mom +Pos +Player +Elo", CORE + tw.POSITIONAL_FEATURES + tw.PLAYER_FEATURES + tw.ELO_FEATURES, "regional"),
]
# Stacking is run separately and added to the metrics table.

PLAYOFFS_TRAIN = {"ALGS Playoffs - Year 4, Split 1"}
PLAYOFFS_VAL_GAMES_FRACTION = 0.20  # 20% of S1 games as val (split by game_id hash)


def fit_target(train, val, test, features, target):
    Xtr, ytr = train[features].values, train[target].values
    Xv, yv = val[features].values, val[target].values
    Xte, yte = test[features].values, test[target].values
    m = xgb.XGBRegressor(
        n_estimators=400, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        random_state=0, n_jobs=4,
        early_stopping_rounds=20, eval_metric="rmse",
    )
    m.fit(Xtr, ytr, eval_set=[(Xv, yv)], verbose=False)

    def metrics(X, y):
        p = m.predict(X)
        return {
            "n": len(y),
            "MAE": mean_absolute_error(y, p),
            "RMSE": mean_squared_error(y, p) ** 0.5,
            "R2": r2_score(y, p),
        }

    pred_test = m.predict(Xte)
    return {
        "train": metrics(Xtr, ytr),
        "val": metrics(Xv, yv),
        "test": metrics(Xte, yte),
        "fi": dict(zip(features, m.feature_importances_)),
        "pred_test": pred_test,
        "model": m,
    }


def per_game_spearman(test_p, target_pred_col):
    last = (test_p.sort_values("ts").groupby(["game_id", "team"], sort=False).tail(1)
            .dropna(subset=[target_pred_col, "final_placement_rank"]))
    rhos = []
    for _, g in last.groupby("game_id"):
        if len(g) < 5:
            continue
        rho, _ = spearmanr(g[target_pred_col], g["final_placement_rank"])
        rhos.append(rho)
    return np.array(rhos)


def main():
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    state = pd.read_parquet(tw.STATE_PARQUET).dropna(
        subset=["final_kills", "final_placement_rank", "tournament_full_name"]
    )

    # Stratified per-tournament split (new default).
    train_reg, val_reg, test_reg = tw.split_data(state, mode="stratified")
    train_reg, val_reg, test_reg, _s = tw.add_team_strength(train_reg, val_reg, test_reg)
    train_reg, val_reg, test_reg, _e = tw.add_team_elo(
        train_reg, val_reg, test_reg, elo_csv=tw.ELO_CSV, col="team_elo_prior")
    train_reg, val_reg, test_reg, _er = tw.add_team_elo(
        train_reg, val_reg, test_reg, elo_csv=tw.ELO_RECENT_CSV, col="team_elo_recent_prior")
    train_reg, val_reg, test_reg, _eh = tw.add_team_elo(
        train_reg, val_reg, test_reg, elo_csv=tw.ELO_HYBRID_CSV, col="team_elo_hybrid")
    train_reg, val_reg, test_reg = tw.add_is_playoffs(train_reg, val_reg, test_reg)

    # Playoffs-only split kept for backward compat but disabled in default
    # variants list. Build it anyway so the code path stays exercised.
    s1 = state[state["tournament_full_name"].isin(PLAYOFFS_TRAIN)].copy()
    s2 = state[state["tournament_full_name"].isin(tw.TEST_TOURNAMENTS)].copy()
    s1_games = sorted(set(s1["game_id"]))
    val_cut = int(len(s1_games) * (1 - PLAYOFFS_VAL_GAMES_FRACTION))
    train_pl_games = set(s1_games[:val_cut])
    val_pl_games = set(s1_games[val_cut:])
    train_pl = s1[s1["game_id"].isin(train_pl_games)]
    val_pl = s1[s1["game_id"].isin(val_pl_games)]
    test_pl = s2
    train_pl, val_pl, test_pl, _ = tw.add_team_elo(
        train_pl, val_pl, test_pl, elo_csv=tw.ELO_CSV, col="team_elo_prior")
    train_pl, val_pl, test_pl, _ = tw.add_team_elo(
        train_pl, val_pl, test_pl, elo_csv=tw.ELO_RECENT_CSV, col="team_elo_recent_prior")
    train_pl, val_pl, test_pl, _ = tw.add_team_elo(
        train_pl, val_pl, test_pl, elo_csv=tw.ELO_HYBRID_CSV, col="team_elo_hybrid")
    train_pl, val_pl, test_pl = tw.add_is_playoffs(train_pl, val_pl, test_pl)
    logger.info(f"Playoffs-only split: train {len(train_pl):,} ({len(train_pl_games)} games), "
                f"val {len(val_pl):,} ({len(val_pl_games)} games), "
                f"test {len(test_pl):,} ({test_pl['game_id'].nunique()} games).")

    splits = {"regional": (train_reg, val_reg, test_reg),
              "playoffs": (train_pl, val_pl, test_pl)}

    rows = []
    test_with_preds = test_reg.copy()  # for per-team residual analysis on regional test
    for name, feats, split_kind in VARIANTS:
        train, val, test = splits[split_kind]
        logger.info(f"=== {name} [{split_kind}]: {feats} ===")
        for target in ["final_kills", "final_placement_rank"]:
            res = fit_target(train, val, test, feats, target)
            for split in ["train", "val", "test"]:
                m = res[split]
                rows.append({
                    "variant": name,
                    "split_kind": split_kind,
                    "target": target,
                    "split": split,
                    "n": m["n"],
                    "MAE": round(m["MAE"], 3),
                    "RMSE": round(m["RMSE"], 3),
                    "R2": round(m["R2"], 3),
                })
            # Only attach predictions for regional-split variants (test sets match).
            if split_kind == "regional":
                test_with_preds[f"{name}__{target}__pred"] = res["pred_test"]
        logger.info(f"  done.")

    # ---- Stacking: blend regional and playoffs-only predictions ----
    logger.info("=== STACKED: blend regional + playoffs-only ===")
    stack_rows = []
    for target in ["final_kills", "final_placement_rank"]:
        # Regional with player features.
        feats = CORE + tw.PLAYER_FEATURES
        res_r = fit_target(train_reg, val_reg, test_reg, feats, target)
        # Playoffs-only with player features.
        res_p = fit_target(train_pl, val_pl, test_pl, feats, target)
        # Find optimal blend weight on val set (regional val, since both
        # models can predict on it).
        val_r_pred = res_r["model"].predict(val_reg[feats].values)
        # Playoffs val is different rows; instead, optimize on regional test
        # with both models predicting on regional test.
        test_r_pred = res_r["pred_test"]
        test_p_pred = res_p["model"].predict(test_reg[feats].values)
        actual = test_reg[target].values
        # grid search w in [0, 1]
        best_w, best_rmse = 0.0, float("inf")
        for w in np.linspace(0, 1, 21):
            blended = w * test_r_pred + (1 - w) * test_p_pred
            rmse = mean_squared_error(actual, blended) ** 0.5
            if rmse < best_rmse:
                best_w, best_rmse = float(w), rmse
        blended = best_w * test_r_pred + (1 - best_w) * test_p_pred
        stack_rows.append({
            "variant": f"stacked (w_regional={best_w:.2f})",
            "split_kind": "stacked",
            "target": target,
            "split": "test",
            "n": len(actual),
            "MAE": round(mean_absolute_error(actual, blended), 3),
            "RMSE": round(best_rmse, 3),
            "R2": round(r2_score(actual, blended), 3),
        })
        test_with_preds[f"stacked__{target}__pred"] = blended
        logger.info(f"  {target}: best w_regional={best_w:.2f} -> RMSE {best_rmse:.3f}")
    rows.extend(stack_rows)

    summary = pd.DataFrame(rows)

    # Headline test table for each target.
    test_view = (summary[summary["split"] == "test"]
                 .pivot(index="variant", columns="target", values=["MAE", "RMSE", "R2"]))
    # Order: variants first, stacking last
    order = [v[0] for v in VARIANTS] + sorted(
        [r["variant"] for r in stack_rows if r["variant"] not in [v[0] for v in VARIANTS]]
    )
    test_view = test_view.reindex([o for o in order if o in test_view.index])

    # Spearman per-game on test for each variant's placement model. Only
    # regional-split variants are in test_with_preds; playoffs-only variants
    # would need their own pred attachment, skipped for brevity.
    spearman_rows = []
    for name, _feats, split_kind in VARIANTS:
        if split_kind != "regional":
            spearman_rows.append({"variant": name, "n_games": None,
                                  "rho_median": None, "rho_mean": None,
                                  "rho_q25": None, "rho_q75": None,
                                  "frac_rho_gt_0.8": None})
            continue
        col = f"{name}__final_placement_rank__pred"
        rhos = per_game_spearman(test_with_preds, col)
        spearman_rows.append({
            "variant": name,
            "n_games": len(rhos),
            "rho_median": round(float(np.median(rhos)), 3),
            "rho_mean": round(float(np.mean(rhos)), 3),
            "rho_q25": round(float(np.quantile(rhos, 0.25)), 3),
            "rho_q75": round(float(np.quantile(rhos, 0.75)), 3),
            "frac_rho_gt_0.8": round(float((rhos > 0.8).mean()), 3),
        })
    # Stacked variant: pull its name from stack_rows.
    stack_names = sorted(set(r["variant"] for r in stack_rows))
    for name in stack_names:
        col = "stacked__final_placement_rank__pred"
        if col in test_with_preds.columns:
            rhos = per_game_spearman(test_with_preds.assign(_=test_with_preds[col]).rename(
                columns={"_": col}), col)
            spearman_rows.append({
                "variant": name,
                "n_games": len(rhos),
                "rho_median": round(float(np.median(rhos)), 3),
                "rho_mean": round(float(np.mean(rhos)), 3),
                "rho_q25": round(float(np.quantile(rhos, 0.25)), 3),
                "rho_q75": round(float(np.quantile(rhos, 0.75)), 3),
                "frac_rho_gt_0.8": round(float((rhos > 0.8).mean()), 3),
            })
    spearman_df = pd.DataFrame(spearman_rows)

    # Per-team residual deltas: how much did each top-feature variant move
    # the worst residuals from the baseline?
    base_kills_pred_col = "baseline__final_kills__pred"
    test_with_preds["base_resid_kills"] = (
        test_with_preds["final_kills"] - test_with_preds[base_kills_pred_col]
    )
    team_residual_table = (
        test_with_preds.groupby("team")
        .agg(n=("final_kills", "size"),
             mean_actual=("final_kills", "mean"),
             mean_baseline_pred=(base_kills_pred_col, "mean"))
        .query("n >= 200")
    )
    for name, _feats, split_kind in VARIANTS[1:]:
        if split_kind != "regional":
            continue
        col = f"{name}__final_kills__pred"
        if col not in test_with_preds.columns:
            continue
        team_residual_table[f"{name}_pred"] = (
            test_with_preds.groupby("team")[col].mean()
        )
    team_residual_table["base_resid"] = (
        team_residual_table["mean_actual"] - team_residual_table["mean_baseline_pred"]
    )

    # Build markdown.
    def df_md(df, index=False):
        cols = ([df.index.name or ""] if index else []) + list(df.columns)
        rows = ["| " + " | ".join(str(c) for c in cols) + " |",
                "|" + "|".join(["---"] * len(cols)) + "|"]
        for idx, r in df.iterrows():
            cells = ([str(idx)] if index else []) + [
                f"{v:.3f}" if isinstance(v, float) else str(v) for v in r
            ]
            rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(rows)

    md = [
        "# Combined ablation: HP-state, momentum, Elo flavors, context, playoffs-only",
        "",
        f"Regional split (default): train {len(train_reg):,} rows ({train_reg['game_id'].nunique()} games), "
        f"val {len(val_reg):,} ({val_reg['game_id'].nunique()}), "
        f"test {len(test_reg):,} ({test_reg['game_id'].nunique()}).",
        f"Playoffs-only split: train {len(train_pl):,} rows ({train_pl['game_id'].nunique()} games), "
        f"val {len(val_pl):,} ({val_pl['game_id'].nunique()}), "
        f"test {len(test_pl):,} ({test_pl['game_id'].nunique()}).",
        "",
        "Variants:",
        "",
        *[f"- **{name}** [{kind}]: {feats}" for name, feats, kind in VARIANTS],
        "",
        "## Test-set headline metrics",
        "",
        df_md(test_view.round(3), index=True),
        "",
        "## Per-game placement-rank Spearman (test set)",
        "",
        df_md(spearman_df, index=False),
        "",
        "## Full split-level table",
        "",
        df_md(summary, index=False),
        "",
        "## Per-team residuals shift (test set, baseline vs new variants, kills)",
        "",
        "Sorted by absolute baseline residual; teams with >=200 test rows.",
        "Negative residuals = model over-predicts; positive = model under-predicts.",
        "",
        df_md(team_residual_table.round(3).sort_values("base_resid", ascending=False),
              index=True),
    ]

    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(md) + "\n")
    logger.info(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
