"""
src/features.py
===============
Feature engineering for parking violations dataset.
Builds derived features for congestion scoring and enforcement priority.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Violation severity weights (hand-tuned for demo, per ADR-007)
# Higher weight = more disruptive to traffic flow
# ---------------------------------------------------------------------------
SEVERITY_WEIGHTS: dict[str, float] = {
    "NO PARKING":                        0.9,
    "DOUBLE PARKING":                    1.0,
    "WRONG PARKING":                     0.7,
    "PARKING NEAR BUS STOP":             0.85,
    "PARKING NEAR ROAD CROSSING":        0.8,
    "PARKING IN PEDESTRIAN CROSSING":    0.95,
    "PARKING NEAR TRAFFIC SIGNAL":       0.85,
    "PARKING ON FOOTPATH":               0.6,
    "PARKING NEAR FIRE HYDRANT":         0.75,
    "PARKING IN NO PARKING ZONE":        0.9,
    "PARKING ON YELLOW LINE":            0.7,
    "OBSTRUCTIVE PARKING":               0.95,
    "PARKING ON MAIN ROAD":              0.8,
    "PARKING NEAR HOSPITAL":             0.7,
    "PARKING NEAR SCHOOL":               0.75,
    "UNAUTHORIZED PARKING":              0.65,
}
DEFAULT_SEVERITY = 0.5


def add_severity(df: pd.DataFrame) -> pd.DataFrame:
    """Add a severity weight column based on the primary violation type."""
    df = df.copy()
    df["severity"] = df["primary_violation"].map(SEVERITY_WEIGHTS).fillna(DEFAULT_SEVERITY)
    logger.info(
        "Severity added — mean: %.3f, max: %.3f",
        df["severity"].mean(),
        df["severity"].max(),
    )
    return df


def build_cell_features(df: pd.DataFrame, h3_col: str = "h3_street") -> pd.DataFrame:
    """Build per-H3-cell feature vectors for the ML pipeline.

    Returns one row per H3 cell with:
      - violation_count: total violations in the cell
      - severity_mean / severity_sum: aggregate severity
      - hour_peak: most common violation hour
      - hour_std: spread of violation hours (24h-active vs rush-hour spike)
      - weekday_pct: % of violations on weekdays (Mon-Fri)
      - vehicle_diversity: number of unique vehicle types
      - top_violation: most common violation type
      - top_vehicle: most common vehicle type
      - police_station: majority station for this cell
      - lat, lng: cell centroid
      - recurrence_score: repeat-offence rate in the cell
    """
    import h3 as h3lib

    agg = df.groupby(h3_col).agg(
        violation_count=("id", "count"),
        severity_mean=("severity", "mean"),
        severity_sum=("severity", "sum"),
        hour_peak=("hour_ist", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 12),
        hour_std=("hour_ist", "std"),
        weekday_pct=(
            "day_of_week",
            lambda x: (x < 5).sum() / len(x) if len(x) > 0 else 0.0,
        ),
        vehicle_diversity=("vehicle_type", "nunique"),
        top_violation=(
            "primary_violation",
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
        ),
        top_vehicle=(
            "vehicle_type",
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
        ),
        police_station=(
            "police_station",
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
        ),
        unique_vehicles=("vehicle_number", "nunique"),
        total_violations_all=("id", "count"),  # alias for clarity
    ).reset_index().rename(columns={h3_col: "h3_index"})

    # ---- Recurrence score: ratio of repeat vehicles -------------------------
    vehicle_counts = (
        df.groupby([h3_col, "vehicle_number"])
        .size()
        .reset_index(name="visit_count")
    )
    repeat_stats = (
        vehicle_counts.groupby(h3_col)
        .agg(
            repeat_vehicles=("visit_count", lambda x: (x > 1).sum()),
            total_unique=("visit_count", "count"),
        )
        .reset_index()
        .rename(columns={h3_col: "h3_index"})
    )
    repeat_stats["recurrence_score"] = (
        repeat_stats["repeat_vehicles"] / repeat_stats["total_unique"]
    ).clip(0, 1)

    agg = agg.merge(
        repeat_stats[["h3_index", "recurrence_score"]],
        on="h3_index",
        how="left",
    )
    agg["recurrence_score"] = agg["recurrence_score"].fillna(0.0)

    # ---- Cell centroids -----------------------------------------------------
    agg[["lat", "lng"]] = agg["h3_index"].apply(
        lambda h: pd.Series(h3lib.cell_to_latlng(h))
    )

    # ---- Fill NaN in hour_std (cells with 1 violation) ----------------------
    agg["hour_std"] = agg["hour_std"].fillna(0.0)

    # ---- Drop helper column -------------------------------------------------
    agg = agg.drop(columns=["total_violations_all"], errors="ignore")

    agg = agg.sort_values("violation_count", ascending=False).reset_index(drop=True)

    logger.info(
        "Cell features built — %d cells, top cell: %d violations",
        len(agg),
        agg["violation_count"].max(),
    )
    return agg


def build_station_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-police-station feature summaries.

    Used by the congestion-score endpoint (ADR-009).
    """
    agg = df.groupby("police_station").agg(
        violation_count=("id", "count"),
        severity_mean=("severity", "mean"),
        severity_sum=("severity", "sum"),
        hour_peak=("hour_ist", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 12),
        unique_cells_street=("h3_street", "nunique"),
        unique_cells_city=("h3_city", "nunique"),
        top_violation=(
            "primary_violation",
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
        ),
        top_vehicle=(
            "vehicle_type",
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
        ),
        unique_vehicles=("vehicle_number", "nunique"),
    ).reset_index()

    # Recurrence at station level
    vehicle_counts = (
        df.groupby(["police_station", "vehicle_number"])
        .size()
        .reset_index(name="visit_count")
    )
    repeat_stats = (
        vehicle_counts.groupby("police_station")
        .agg(
            repeat_vehicles=("visit_count", lambda x: (x > 1).sum()),
            total_unique=("visit_count", "count"),
        )
        .reset_index()
    )
    repeat_stats["recurrence_score"] = (
        repeat_stats["repeat_vehicles"] / repeat_stats["total_unique"]
    ).clip(0, 1)

    agg = agg.merge(
        repeat_stats[["police_station", "recurrence_score"]],
        on="police_station",
        how="left",
    )
    agg["recurrence_score"] = agg["recurrence_score"].fillna(0.0)

    agg = agg.sort_values("violation_count", ascending=False).reset_index(drop=True)

    logger.info(
        "Station features built — %d stations, top: %s (%d violations)",
        len(agg),
        agg.iloc[0]["police_station"],
        agg.iloc[0]["violation_count"],
    )
    return agg


def build_temporal_profile(df: pd.DataFrame, h3_col: str = "h3_street") -> pd.DataFrame:
    """Build hourly violation profiles per H3 cell.

    Returns a pivoted DataFrame: rows = h3_index, columns = hour_0..hour_23.
    Each value is the percentage of that cell's violations occurring in that hour.
    """
    hourly = (
        df.groupby([h3_col, "hour_ist"])
        .size()
        .reset_index(name="count")
    )
    total_per_cell = hourly.groupby(h3_col)["count"].transform("sum")
    hourly["pct"] = hourly["count"] / total_per_cell

    pivoted = hourly.pivot(index=h3_col, columns="hour_ist", values="pct").fillna(0)
    pivoted.columns = [f"hour_{int(c)}" for c in pivoted.columns]
    pivoted = pivoted.reset_index().rename(columns={h3_col: "h3_index"})

    logger.info("Temporal profiles built — %d cells x %d hours", len(pivoted), len(pivoted.columns) - 1)
    return pivoted
