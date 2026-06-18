"""
src/models/priority.py
======================
Enforcement priority queue builder.

Composite scoring per ADR-007:
  - Hotspot cluster density rank — 40%
  - Violation count (recent window) — 30%
  - Recurrence trend              — 20%
  - Violation severity            — 10%
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Priority score weights (ADR-007)
W_HOTSPOT = 0.40
W_VIOLATION = 0.30
W_RECURRENCE = 0.20
W_SEVERITY = 0.10

# Recommended enforcement actions based on score thresholds
ACTION_TIERS = [
    (0.8, "IMMEDIATE", "Deploy patrol unit — critical hotspot with high recurrence"),
    (0.6, "HIGH", "Schedule enforcement sweep within 24 hours"),
    (0.4, "MODERATE", "Include in weekly enforcement rotation"),
    (0.2, "LOW", "Monitor — add to watch list for trend analysis"),
    (0.0, "MINIMAL", "No immediate action — periodic monitoring sufficient"),
]


def _normalize_series(s: pd.Series) -> pd.Series:
    """Min-max normalize a series to [0, 1]."""
    s_min, s_max = s.min(), s.max()
    if s_max - s_min > 0:
        return (s - s_min) / (s_max - s_min)
    return pd.Series(0.5, index=s.index)


def build_priority_queue(
    cell_features: pd.DataFrame,
    *,
    top_n: int | None = None,
) -> pd.DataFrame:
    """Build the enforcement priority queue from enriched cell features.

    Args:
        cell_features: DataFrame with columns from Phase 1 + hotspot + congestion
        top_n: If set, return only the top N entries. None = all cells.

    Returns:
        DataFrame sorted by priority_score (descending) with columns:
          h3_index, priority_score, priority_tier, recommended_action,
          violation_count, severity_mean, recurrence_score, is_hotspot,
          hotspot_rank, congestion_score, police_station, top_violation,
          lat, lng, contributing_factors
    """
    df = cell_features.copy()

    # ---- Normalize each component to [0, 1] --------------------------------
    # 1. Hotspot component: cells in clusters get density score; others get 0
    hotspot_component = df["hotspot_density"].fillna(0)

    # 2. Violation count (log-scale for better spread)
    violation_component = _normalize_series(np.log1p(df["violation_count"]))

    # 3. Recurrence score (already 0–1 from features.py)
    recurrence_component = df["recurrence_score"].fillna(0).clip(0, 1)

    # 4. Severity (already ~0.5–1.0 from features.py)
    severity_component = _normalize_series(df["severity_mean"].fillna(0))

    # ---- Composite priority score -------------------------------------------
    df["priority_score"] = (
        W_HOTSPOT * hotspot_component
        + W_VIOLATION * violation_component
        + W_RECURRENCE * recurrence_component
        + W_SEVERITY * severity_component
    )

    # Re-normalize final score to [0, 1]
    df["priority_score"] = _normalize_series(df["priority_score"])

    # ---- Assign tier and recommended action ---------------------------------
    def _get_tier(score: float) -> tuple[str, str]:
        for threshold, tier, action in ACTION_TIERS:
            if score >= threshold:
                return tier, action
        return "MINIMAL", "No immediate action"

    tiers = df["priority_score"].apply(_get_tier)
    df["priority_tier"] = tiers.apply(lambda t: t[0])
    df["recommended_action"] = tiers.apply(lambda t: t[1])

    # ---- Contributing factors breakdown -------------------------------------
    df["contributing_factors"] = df.apply(
        lambda row: {
            "hotspot_density": round(float(hotspot_component.loc[row.name]), 3),
            "violation_intensity": round(float(violation_component.loc[row.name]), 3),
            "recurrence": round(float(recurrence_component.loc[row.name]), 3),
            "severity": round(float(severity_component.loc[row.name]), 3),
        },
        axis=1,
    )

    # ---- Sort and select output columns -------------------------------------
    output_cols = [
        "h3_index", "priority_score", "priority_tier", "recommended_action",
        "violation_count", "severity_mean", "recurrence_score",
        "is_hotspot", "hotspot_rank", "congestion_score",
        "police_station", "top_violation", "top_vehicle",
        "lat", "lng", "contributing_factors",
    ]
    # Only keep columns that exist
    output_cols = [c for c in output_cols if c in df.columns]

    result = df[output_cols].sort_values("priority_score", ascending=False).reset_index(drop=True)

    if top_n is not None:
        result = result.head(top_n)

    # ---- Log summary --------------------------------------------------------
    tier_counts = result["priority_tier"].value_counts()
    logger.info("Priority queue built — %d entries", len(result))
    for tier, count in tier_counts.items():
        logger.info("  %s: %d cells", tier, count)

    logger.info(
        "  Top priority: %s (score: %.3f, %d violations, station: %s)",
        result.iloc[0]["h3_index"],
        result.iloc[0]["priority_score"],
        result.iloc[0]["violation_count"],
        result.iloc[0]["police_station"],
    )

    return result


def build_station_priority_queue(
    station_features: pd.DataFrame,
) -> pd.DataFrame:
    """Build a station-level enforcement priority queue.

    Simpler variant — ranks stations by their aggregate congestion and severity.
    """
    df = station_features.copy()

    # Use congestion_score if available, else fall back to violation density
    if "congestion_score" in df.columns:
        congestion = df["congestion_score"].fillna(0)
    else:
        congestion = _normalize_series(np.log1p(df["violation_count"]))

    violation_component = _normalize_series(np.log1p(df["violation_count"]))
    recurrence_component = df["recurrence_score"].fillna(0).clip(0, 1)
    severity_component = _normalize_series(df["severity_mean"].fillna(0))

    df["priority_score"] = (
        W_HOTSPOT * congestion
        + W_VIOLATION * violation_component
        + W_RECURRENCE * recurrence_component
        + W_SEVERITY * severity_component
    )
    df["priority_score"] = _normalize_series(df["priority_score"])

    def _get_tier(score: float) -> tuple[str, str]:
        for threshold, tier, action in ACTION_TIERS:
            if score >= threshold:
                return tier, action
        return "MINIMAL", "No immediate action"

    tiers = df["priority_score"].apply(_get_tier)
    df["priority_tier"] = tiers.apply(lambda t: t[0])
    df["recommended_action"] = tiers.apply(lambda t: t[1])

    df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)

    logger.info(
        "Station priority queue — %d stations, top: %s (%.3f)",
        len(df),
        df.iloc[0]["police_station"],
        df.iloc[0]["priority_score"],
    )

    return df
