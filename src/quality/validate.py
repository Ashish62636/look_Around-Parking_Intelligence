"""
src/quality/validate.py
========================
Assertion-based schema validation for the violations dataset.
Replaces Great Expectations at hackathon scale.
"""

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

# Bengaluru bounding box (generous)
BLR_LAT_MIN, BLR_LAT_MAX = 12.7, 13.2
BLR_LON_MIN, BLR_LON_MAX = 77.3, 77.9

REQUIRED_COLUMNS = [
    "id", "latitude", "longitude", "violation_type",
    "created_datetime", "police_station",
]


@dataclass
class ValidationReport:
    """Container for validation results."""

    total_rows: int = 0
    passed: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate_dataframe(df: pd.DataFrame) -> ValidationReport:
    """Run all assertion-based checks against the loaded DataFrame."""
    report = ValidationReport(total_rows=len(df))

    # ------------------------------------------------------------------
    # 1. Required columns exist
    # ------------------------------------------------------------------
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        report.errors.append(f"Missing required columns: {missing}")
        return report  # can't proceed without columns

    # ------------------------------------------------------------------
    # 2. No duplicate IDs
    # ------------------------------------------------------------------
    dup_count = df["id"].duplicated().sum()
    if dup_count > 0:
        report.warnings.append(f"Duplicate IDs: {dup_count}")
    else:
        report.passed += 1

    # ------------------------------------------------------------------
    # 3. Lat/lon within Bengaluru bounds
    # ------------------------------------------------------------------
    lat_ok = df["latitude"].between(BLR_LAT_MIN, BLR_LAT_MAX)
    lon_ok = df["longitude"].between(BLR_LON_MIN, BLR_LON_MAX)
    geo_ok = lat_ok & lon_ok
    geo_bad = (~geo_ok).sum()
    report.stats["geo_outliers"] = int(geo_bad)
    if geo_bad > 0:
        pct = geo_bad / len(df) * 100
        if pct > 5:
            report.errors.append(
                f"Too many geo outliers: {geo_bad:,} ({pct:.1f}%)"
            )
        else:
            report.warnings.append(
                f"Geo outliers (outside Bengaluru bbox): {geo_bad:,} ({pct:.1f}%)"
            )
    report.passed += 1

    # ------------------------------------------------------------------
    # 4. created_datetime not null
    # ------------------------------------------------------------------
    created_null = df["created_datetime"].isna().sum()
    report.stats["created_datetime_null"] = int(created_null)
    if created_null > 0:
        report.warnings.append(f"created_datetime NULL: {created_null:,}")
    report.passed += 1

    # ------------------------------------------------------------------
    # 5. closed_datetime >= created_datetime (where both exist)
    # ------------------------------------------------------------------
    if "closed_datetime" in df.columns:
        both = df.dropna(subset=["created_datetime", "closed_datetime"])
        bad_order = (both["closed_datetime"] < both["created_datetime"]).sum()
        report.stats["closed_before_created"] = int(bad_order)
        if bad_order > 0:
            report.warnings.append(
                f"closed_datetime < created_datetime: {bad_order:,} rows"
            )
        report.stats["closed_datetime_null"] = int(df["closed_datetime"].isna().sum())
        report.stats["closed_datetime_null_pct"] = round(
            df["closed_datetime"].isna().sum() / len(df) * 100, 1
        )
        report.passed += 1

    # ------------------------------------------------------------------
    # 6. junction_name sparsity
    # ------------------------------------------------------------------
    if "junction_name" in df.columns:
        no_junction = (
            df["junction_name"].isna()
            | (df["junction_name"].str.strip().str.lower() == "no junction")
        ).sum()
        report.stats["junction_no_junction_pct"] = round(
            no_junction / len(df) * 100, 1
        )
        if no_junction / len(df) > 0.5:
            report.warnings.append(
                f"junction_name is 'No Junction' or NULL for {no_junction:,} rows "
                f"({report.stats['junction_no_junction_pct']}%) — "
                f"use police_station or H3 as spatial grouping instead"
            )
        report.passed += 1

    report.failed = len(report.errors)

    # Log summary
    logger.info(
        "Validation: %d passed, %d errors, %d warnings",
        report.passed, report.failed, len(report.warnings),
    )
    return report
