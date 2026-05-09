"""Hybrid Elo: only use the team Elo prior for teams whose training-set
residual is small with the in-game-only model (BASE + HP + Mom + Player).

The intuition from the +Elo experiments: top teams' Elo correctly identifies
their tier and helps. Mid-tier teams' Elo wrongly amplifies regional Pro
League performance that doesn't transfer to global Playoffs. So include the
Elo only when the model's train-time prediction error is small enough that
the prior is trustworthy.

Output:
  data/team_elo_hybrid.csv  with columns: team, team_elo_prior,
    team_elo_hybrid, train_resid_kills, reliable
"""

import logging
from argparse import ArgumentParser

import pandas as pd
import xgboost as xgb

import train_wpa as tw

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OUT_CSV = "data/team_elo_hybrid.csv"
RESID_THRESHOLD = 0.30  # |mean kill residual| under this = "reliable"


def main():
    parser = ArgumentParser()
    parser.add_argument("--threshold", type=float, default=RESID_THRESHOLD)
    parser.add_argument("--out", default=OUT_CSV)
    args = parser.parse_args()

    state = pd.read_parquet(tw.STATE_PARQUET).dropna(
        subset=["final_kills", "final_placement_rank", "tournament_full_name"]
    )
    train, val, test = tw.split_data(state)

    # In-game-only features (no Elo, no team-strength).
    features = (tw.BASE_FEATURES + tw.HP_FEATURES + tw.MOMENTUM_FEATURES
                + ["team_avg_kpg", "team_max_kpg", "team_avg_dpg"])
    logger.info(f"Training on TRAIN with features: {features}")
    m = xgb.XGBRegressor(
        n_estimators=400, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        random_state=0, n_jobs=4,
        early_stopping_rounds=20, eval_metric="rmse",
    )
    m.fit(
        train[features].values, train["final_kills"].values,
        eval_set=[(val[features].values, val["final_kills"].values)],
        verbose=False,
    )
    logger.info("Predicting on train and computing per-team residual...")
    train = train.copy()
    train["pred_kills"] = m.predict(train[features].values)
    train["resid_kills"] = train["final_kills"] - train["pred_kills"]
    team_resid = train.groupby("team")["resid_kills"].mean()

    elo = pd.read_csv(tw.ELO_CSV)[["team", "team_elo_prior"]]
    out = elo.merge(team_resid.rename("train_resid_kills"), on="team", how="left")
    out["train_resid_kills"] = out["train_resid_kills"].fillna(0.0)
    out["reliable"] = out["train_resid_kills"].abs() < args.threshold
    out["team_elo_hybrid"] = out["team_elo_prior"].where(
        out["reliable"], tw.ELO_DEFAULT
    )

    n_reliable = out["reliable"].sum()
    logger.info(f"Reliable teams (|train_resid_kills| < {args.threshold}): "
                f"{n_reliable}/{len(out)} ({n_reliable / len(out):.0%})")
    logger.info(f"Hybrid Elo range: {out['team_elo_hybrid'].min():.0f} -> "
                f"{out['team_elo_hybrid'].max():.0f}")
    out.to_csv(args.out, index=False)
    logger.info(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
