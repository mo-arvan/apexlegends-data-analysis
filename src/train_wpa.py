"""Phase 0 baseline WPA model: predict E[final_kills] and E[final_placement_rank]
for each team given a per-event match-state snapshot.

Two separate regressors so the score function (which varies by tournament)
can be applied post-hoc. WPA in any currency = score(state_after) - score(state_before),
where score is the tournament's own kills/placement table.

Train/val/test split is by tournament inside Y4 (single-year per Mo's
constraint that the game changes meaningfully across years):
  train: Pro League S1 + S2 (any region)
  val:   Playoffs Y4 Split 1 (Global)
  test:  Playoffs Y4 Split 2 (Global)

Outputs:
  output/wpa/baseline_metrics.md
  data/wpa_predictions.parquet  (test-set predictions for downstream WPA computation)
"""

import logging
import os
from argparse import ArgumentParser

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

STATE_PARQUET = "data/match_state.parquet"
OUT_DIR = "output/wpa"
PRED_PARQUET = "data/wpa_predictions.parquet"

BASE_FEATURES = [
    "n_alive_team",
    "kills_so_far_team",
    "n_teams_alive",
    "time_in_game_s",
    "kills_minus_leader",
]

HP_FEATURES = [
    "team_HP_sum",
]

MOMENTUM_FEATURES = [
    "team_dmg_dealt_last_30s",
    "team_dmg_taken_last_30s",
    "team_kills_last_60s",
    "time_since_last_dmg_dealt_s",
]

ELO_FEATURES = [
    "team_elo_prior",
]

ELO_RECENT_FEATURES = [
    "team_elo_recent_prior",
]

CONTEXT_FEATURES = [
    "is_playoffs",
]

PLAYER_FEATURES = [
    "team_avg_kpg",
    "team_max_kpg",
    "team_avg_dpg",
]

POSITIONAL_FEATURES = [
    "team_centroid_x",
    "team_centroid_y",
    "team_spread",
    "dist_to_nearest_alive_team",
]

ELO_HYBRID_FEATURES = [
    "team_elo_hybrid",
]

# Naive team-strength tried and dropped (overfit; see output/wpa/feature_ablation.md).
TEAM_STRENGTH_FEATURES = [
    "team_mean_kills_train",
    "team_mean_rank_train",
]

# Default model: base + HP + momentum + positional + player aggregates.
# With the stratified per-tournament split (each tournament in train/val/test),
# all four feature groups add value cleanly. Elo is neutral on top of these.
# For year-portable runs (Y6 etc) skip player aggregates which need their own
# per-year training computation.
import os as _os
if _os.environ.get("WPA_FEATURES") == "ingame_only":
    FEATURES = BASE_FEATURES + HP_FEATURES + MOMENTUM_FEATURES + POSITIONAL_FEATURES
else:
    FEATURES = (
        BASE_FEATURES + HP_FEATURES + MOMENTUM_FEATURES
        + POSITIONAL_FEATURES + PLAYER_FEATURES
    )

ELO_CSV = "data/team_elo_train_end.csv"
ELO_RECENT_CSV = "data/team_elo_recent_end.csv"
ELO_HYBRID_CSV = "data/team_elo_hybrid.csv"
ELO_DEFAULT = 1500.0

TRAIN_TOURNAMENTS = {"Pro League - Year 4, Split 1", "Pro League - Year 4, Split 2"}
VAL_TOURNAMENTS = {"ALGS Playoffs - Year 4, Split 1"}
TEST_TOURNAMENTS = {"ALGS Playoffs - Year 4, Split 2"}

# All Y4 tournaments; used by stratified split so every tournament contributes
# to train/val/test in proportional amounts.
ALL_Y4_TOURNAMENTS = {
    "Pro League - Year 4, Split 1",
    "Pro League - Year 4, Split 2",
    "ALGS Playoffs - Year 4, Split 1",
    "ALGS Playoffs - Year 4, Split 2",
    "PLQ - Year 4, Split 2",
}

# Hash-based deterministic game-id split fractions.
SPLIT_FRACTIONS = (0.70, 0.15, 0.15)  # train / val / test


def split_data(state, mode="stratified"):
    """
    mode='tournament' — original split: train=Pro League, val=Playoffs S1, test=Playoffs S2.
                        Tests cross-context generalization.
    mode='stratified'  — per-tournament hash-based game-id split (default).
                        Each tournament contributes to all three sets in proportion
                        SPLIT_FRACTIONS. Tests within-context predictive power.
    """
    if mode == "tournament":
        train = state[state["tournament_full_name"].isin(TRAIN_TOURNAMENTS)]
        val = state[state["tournament_full_name"].isin(VAL_TOURNAMENTS)]
        test = state[state["tournament_full_name"].isin(TEST_TOURNAMENTS)]
        return train, val, test

    # Stratified per-tournament hash split. Hash on game_id so the unit of
    # randomness is the game (no leakage of one game's events across splits).
    import hashlib

    def bucket(game_id):
        h = int(hashlib.md5(game_id.encode()).hexdigest(), 16) % 1000 / 1000.0
        if h < SPLIT_FRACTIONS[0]:
            return "train"
        if h < SPLIT_FRACTIONS[0] + SPLIT_FRACTIONS[1]:
            return "val"
        return "test"

    state = state.copy()
    state["_bucket"] = state["game_id"].map(bucket)
    train = state[state["_bucket"] == "train"].drop(columns="_bucket")
    val = state[state["_bucket"] == "val"].drop(columns="_bucket")
    test = state[state["_bucket"] == "test"].drop(columns="_bucket")
    return train, val, test


def add_team_strength(train, val, test):
    """Compute per-team mean final_kills and final_placement_rank using
    training-set games only (one row per (game, team), not per state row),
    then merge as static features into all three splits.

    Teams that don't appear in training receive the train-set overall mean as
    a fallback so unseen teams still get a sensible prior.
    """
    train_per_team_game = train.drop_duplicates(["game_id", "team"])[
        ["team", "final_kills", "final_placement_rank"]
    ]
    strength = train_per_team_game.groupby("team").agg(
        team_mean_kills_train=("final_kills", "mean"),
        team_mean_rank_train=("final_placement_rank", "mean"),
    ).reset_index()
    fallback_kills = train_per_team_game["final_kills"].mean()
    fallback_rank = train_per_team_game["final_placement_rank"].mean()

    def merge(df):
        out = df.merge(strength, on="team", how="left")
        out["team_mean_kills_train"] = out["team_mean_kills_train"].fillna(fallback_kills)
        out["team_mean_rank_train"] = out["team_mean_rank_train"].fillna(fallback_rank)
        return out

    return merge(train), merge(val), merge(test), strength


def add_team_elo(train, val, test, elo_csv=ELO_CSV, col="team_elo_prior"):
    """Merge a static team Elo column into all splits, falling back to the
    default rating when a team is unseen."""
    elo = pd.read_csv(elo_csv)[["team", col]]

    def merge(df):
        out = df.merge(elo, on="team", how="left")
        out[col] = out[col].fillna(ELO_DEFAULT)
        return out

    return merge(train), merge(val), merge(test), elo


def add_is_playoffs(train, val, test):
    """Add a binary feature marking playoffs games."""
    def tag(df):
        out = df.copy()
        out["is_playoffs"] = out["tournament_full_name"].str.contains(
            "Playoff", case=False, na=False
        ).astype(int)
        return out
    return tag(train), tag(val), tag(test)


def train_target(train, val, test, target):
    Xtr, ytr = train[FEATURES].values, train[target].values
    Xv, yv = val[FEATURES].values, val[target].values
    Xte, yte = test[FEATURES].values, test[target].values
    model = xgb.XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=0,
        n_jobs=4,
        early_stopping_rounds=20,
        eval_metric="rmse",
    )
    model.fit(Xtr, ytr, eval_set=[(Xv, yv)], verbose=False)

    def metrics(X, y, label):
        pred = model.predict(X)
        return {
            "split": label,
            "n": len(y),
            "MAE": mean_absolute_error(y, pred),
            "RMSE": mean_squared_error(y, pred) ** 0.5,
            "R2": r2_score(y, pred) if len(y) > 1 else float("nan"),
            "baseline_RMSE_mean": mean_squared_error(y, np.full_like(y, ytr.mean(), dtype=float)) ** 0.5,
        }

    rows = [metrics(Xtr, ytr, "train"),
            metrics(Xv, yv, "val"),
            metrics(Xte, yte, "test")]
    return model, pd.DataFrame(rows), model.predict(Xte)


def main():
    parser = ArgumentParser()
    parser.add_argument("--state", default=STATE_PARQUET)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--pred-out", default=PRED_PARQUET)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    logger.info(f"Loading {args.state}...")
    state = pd.read_parquet(args.state)
    state = state.dropna(subset=["final_kills", "final_placement_rank", "tournament_full_name"])
    logger.info(f"  state rows: {len(state):,}")

    train, val, test = split_data(state)
    logger.info(f"Train: {len(train):,} rows ({train['game_id'].nunique()} games, "
                f"{sorted(train['tournament_full_name'].unique())})")
    logger.info(f"Val:   {len(val):,} rows ({val['game_id'].nunique()} games)")
    logger.info(f"Test:  {len(test):,} rows ({test['game_id'].nunique()} games)")
    if len(train) == 0 or len(val) == 0 or len(test) == 0:
        logger.error("Empty split. Check tournament names.")
        return

    if any(f in FEATURES for f in TEAM_STRENGTH_FEATURES):
        logger.info("Computing team-strength features from train data only...")
        train, val, test, strength = add_team_strength(train, val, test)
        logger.info(f"  team-strength priors: {len(strength)} train teams")
    if any(f in FEATURES for f in ELO_FEATURES):
        logger.info(f"Loading Elo priors from {ELO_CSV}...")
        train, val, test, elo = add_team_elo(train, val, test)
        n_test_unseen = test[~test["team"].isin(elo["team"])]["team"].nunique()
        logger.info(f"  {len(elo)} teams with Elo; {n_test_unseen} test teams unseen (default {ELO_DEFAULT})")

    logger.info("Training E[final_kills] regressor...")
    model_k, metrics_k, pred_k_test = train_target(train, val, test, "final_kills")
    logger.info(f"\n{metrics_k.round(3).to_string(index=False)}")

    logger.info("Training E[final_placement_rank] regressor...")
    model_p, metrics_p, pred_p_test = train_target(train, val, test, "final_placement_rank")
    logger.info(f"\n{metrics_p.round(3).to_string(index=False)}")

    # Feature importance summary
    fi_k = pd.Series(model_k.feature_importances_, index=FEATURES).sort_values(ascending=False)
    fi_p = pd.Series(model_p.feature_importances_, index=FEATURES).sort_values(ascending=False)

    def df_to_md(df, index=False):
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
        "# WPA baseline metrics (Phase 0, Y4)",
        "",
        f"Source: `{args.state}`. Year 4 only.",
        "",
        f"- Train: {sorted(TRAIN_TOURNAMENTS)} ({train['game_id'].nunique()} games, {len(train):,} rows)",
        f"- Val:   {sorted(VAL_TOURNAMENTS)} ({val['game_id'].nunique()} games, {len(val):,} rows)",
        f"- Test:  {sorted(TEST_TOURNAMENTS)} ({test['game_id'].nunique()} games, {len(test):,} rows)",
        "",
        f"Features: {FEATURES}",
        "",
        "## Target 1: final_kills",
        "",
        df_to_md(metrics_k.round(3)),
        "",
        "Feature importance:",
        "",
        df_to_md(fi_k.round(3).to_frame("importance"), index=True),
        "",
        "## Target 2: final_placement_rank (1 = won, 20 = first eliminated)",
        "",
        df_to_md(metrics_p.round(3)),
        "",
        "Feature importance:",
        "",
        df_to_md(fi_p.round(3).to_frame("importance"), index=True),
        "",
        "## Reading the metrics",
        "",
        "- `MAE` / `RMSE`: smaller is better.",
        "- `R2`: 0 = no better than predicting the mean; 1 = perfect.",
        "- `baseline_RMSE_mean`: the RMSE you would get by always predicting the train-set mean. RMSE materially below this means the model has learned signal.",
        "",
        "## Next steps",
        "",
        "1. Add HP-state features (team_HP_sum from damage + heal events).",
        "2. Add ring-stage feature derived from 'Took damage from World with The Ring' events.",
        "3. Add positional features (per-map ring distance, team spread).",
        "4. Compose the two predictions through each tournament's score function and compute per-event WPA.",
        "5. Calibration plots and clutch-moment sanity check on a known finals.",
    ]
    out_md = os.path.join(args.out_dir, "baseline_metrics.md")
    with open(out_md, "w") as fh:
        fh.write("\n".join(md) + "\n")
    logger.info(f"Wrote {out_md}")

    # Save test-set predictions for downstream WPA computation.
    pred_df = test[["game_id", "event_id", "ts", "team", "final_kills", "final_placement_rank"] + FEATURES].copy()
    pred_df["pred_final_kills"] = pred_k_test
    pred_df["pred_final_placement_rank"] = pred_p_test
    pred_df.to_parquet(args.pred_out, index=False)
    logger.info(f"Wrote {args.pred_out}")


if __name__ == "__main__":
    main()
