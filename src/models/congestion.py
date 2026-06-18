"""
src/models/congestion.py
========================
LightGBM-based congestion-impact scoring.

Uses violation density as the proxy target (ADR-003).
The model learns which cell features best predict high-violation zones,
and its normalized predictions become the congestion-impact score (0–1).
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

logger = logging.getLogger(__name__)

# Features used by the congestion model
# NOTE: violation_count is excluded — it IS the target (log1p form).
# severity_sum is excluded — it's count * severity_mean (leaks count).
# This forces the model to learn from behavioral patterns, not count itself.
FEATURE_COLS = [
    "severity_mean",
    "hour_std",
    "weekday_pct",
    "vehicle_diversity",
    "unique_vehicles",
    "recurrence_score",
    "hotspot_density",
]


def train_congestion_model(
    cell_features: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train a LightGBM model to score congestion impact per H3 cell.

    Target: log1p(violation_count) — violation density as congestion proxy.
    Features: severity, temporal spread, vehicle diversity, recurrence, hotspot density.

    Returns:
        dict with keys:
          - model: trained LightGBM Booster
          - feature_importance: dict of feature → importance score
          - metrics: dict with MAE, R2 on test set
          - predictions: Series of raw predictions for all cells
    """
    import lightgbm as lgb

    df = cell_features.copy()

    # ---- Prepare features and target ----------------------------------------
    available_cols = [c for c in FEATURE_COLS if c in df.columns]
    missing = set(FEATURE_COLS) - set(available_cols)
    if missing:
        logger.warning("Missing feature columns: %s — skipping them", missing)

    X = df[available_cols].fillna(0)
    y = np.log1p(df["violation_count"])  # log-transform for better distribution

    logger.info(
        "Training congestion model — %d samples, %d features, target range: %.2f–%.2f",
        len(X),
        len(available_cols),
        y.min(),
        y.max(),
    )

    # ---- Train/test split ---------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    # ---- LightGBM training --------------------------------------------------
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    params = {
        "objective": "regression",
        "metric": "mae",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "seed": random_state,
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=200,
        valid_sets=[valid_data],
        callbacks=[lgb.log_evaluation(period=0)],  # suppress per-round logs
    )

    # ---- Evaluate -----------------------------------------------------------
    y_pred_test = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred_test)
    r2 = r2_score(y_test, y_pred_test)

    logger.info("Congestion model — MAE: %.4f, R2: %.4f", mae, r2)

    # ---- Feature importance -------------------------------------------------
    importance = dict(
        zip(available_cols, model.feature_importance(importance_type="gain"))
    )
    # Normalize to percentages
    total_imp = sum(importance.values())
    if total_imp > 0:
        importance = {k: round(v / total_imp * 100, 1) for k, v in importance.items()}

    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for feat, imp in sorted_imp[:5]:
        logger.info("  Feature: %-20s — %.1f%%", feat, imp)

    # ---- Predictions for all cells ------------------------------------------
    y_pred_all = model.predict(X)

    return {
        "model": model,
        "feature_importance": importance,
        "metrics": {"mae": float(mae), "r2": float(r2)},
        "predictions": pd.Series(y_pred_all, index=df.index),
        "feature_cols": available_cols,
    }


def compute_congestion_scores(
    cell_features: pd.DataFrame,
    predictions: pd.Series,
) -> pd.DataFrame:
    """Normalize model predictions to a 0–1 congestion score.

    Applies min-max normalization on the raw predictions.
    Also computes a severity-adjusted score that blends model output
    with direct severity information.

    Returns:
        cell_features with added columns:
          - congestion_raw: raw model prediction (log-scale)
          - congestion_score: normalized 0–1 score
    """
    df = cell_features.copy()

    df["congestion_raw"] = predictions.values

    # Min-max normalize to [0, 1]
    raw_min = df["congestion_raw"].min()
    raw_max = df["congestion_raw"].max()
    raw_range = raw_max - raw_min

    if raw_range > 0:
        df["congestion_score"] = (df["congestion_raw"] - raw_min) / raw_range
    else:
        df["congestion_score"] = 0.5

    # Clamp to [0, 1]
    df["congestion_score"] = df["congestion_score"].clip(0, 1)

    logger.info(
        "Congestion scores — min: %.3f, mean: %.3f, max: %.3f, "
        "cells above 0.8: %d",
        df["congestion_score"].min(),
        df["congestion_score"].mean(),
        df["congestion_score"].max(),
        (df["congestion_score"] > 0.8).sum(),
    )

    return df


def compute_station_congestion(
    cell_features: pd.DataFrame,
    station_features: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate cell-level congestion scores to station-level.

    For the congestion-score API endpoint (ADR-009).
    """
    # Map each cell's congestion score to its station
    station_scores = (
        cell_features.groupby("police_station")
        .agg(
            congestion_score_mean=("congestion_score", "mean"),
            congestion_score_max=("congestion_score", "max"),
            congestion_score_p90=("congestion_score", lambda x: np.percentile(x, 90)),
            hotspot_cells=("is_hotspot", "sum"),
            total_cells=("h3_index", "count"),
        )
        .reset_index()
    )

    # Merge into station_features
    sf = station_features.merge(station_scores, on="police_station", how="left")

    # Use P90 as the station's congestion score (captures worst areas)
    sf["congestion_score"] = sf["congestion_score_p90"].fillna(0).clip(0, 1)

    sf = sf.sort_values("congestion_score", ascending=False).reset_index(drop=True)

    logger.info(
        "Station congestion — top: %s (score: %.3f), bottom: %s (score: %.3f)",
        sf.iloc[0]["police_station"],
        sf.iloc[0]["congestion_score"],
        sf.iloc[-1]["police_station"],
        sf.iloc[-1]["congestion_score"],
    )

    return sf
