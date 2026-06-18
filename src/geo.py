"""
src/geo.py
==========
H3 hexagonal geo-enrichment for the violations dataset.
Adds H3 indices at two resolutions and generates GeoJSON output.
"""

import logging
from typing import Any

import h3
import pandas as pd

logger = logging.getLogger(__name__)

# Resolutions per spec §4 / ADR-002
RES_CITY = 7   # ~5.16 km² — city-level overview
RES_STREET = 9  # ~0.11 km² — street-level detail


def add_h3_indices(df: pd.DataFrame) -> pd.DataFrame:
    """Add H3 hex indices at city-level and street-level resolutions."""
    df = df.copy()

    logger.info("Computing H3 indices (res %d, %d) ...", RES_CITY, RES_STREET)

    df["h3_city"] = df.apply(
        lambda row: h3.latlng_to_cell(row["latitude"], row["longitude"], RES_CITY),
        axis=1,
    )
    df["h3_street"] = df.apply(
        lambda row: h3.latlng_to_cell(row["latitude"], row["longitude"], RES_STREET),
        axis=1,
    )

    logger.info(
        "H3 done — unique city cells: %d, street cells: %d",
        df["h3_city"].nunique(),
        df["h3_street"].nunique(),
    )
    return df


def aggregate_h3_cells(
    df: pd.DataFrame,
    resolution: str = "h3_street",
) -> pd.DataFrame:
    """Aggregate violations per H3 cell.

    Returns a DataFrame with one row per cell:
      h3_index, violation_count, lat, lng, top_violation, police_station
    """
    agg = (
        df.groupby(resolution)
        .agg(
            violation_count=("id", "count"),
            top_violation=("primary_violation", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN"),
            police_station=("police_station", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN"),
            avg_hour=("hour_ist", "mean"),
        )
        .reset_index()
        .rename(columns={resolution: "h3_index"})
    )

    # Add cell centroid coordinates
    agg[["lat", "lng"]] = agg["h3_index"].apply(
        lambda h: pd.Series(h3.cell_to_latlng(h))
    )

    agg = agg.sort_values("violation_count", ascending=False).reset_index(drop=True)
    logger.info(
        "Aggregated %d cells — max violations in a cell: %d",
        len(agg),
        agg["violation_count"].max(),
    )
    return agg


def h3_cells_to_geojson(agg_df: pd.DataFrame) -> dict[str, Any]:
    """Convert aggregated H3 cell data to a GeoJSON FeatureCollection.

    Each feature is a hexagon polygon with properties:
      violation_count, top_violation, police_station
    """
    features = []
    for _, row in agg_df.iterrows():
        boundary = h3.cell_to_boundary(row["h3_index"])
        # h3 returns (lat, lng) tuples; GeoJSON needs [lng, lat]
        coords = [[lng, lat] for lat, lng in boundary]
        coords.append(coords[0])  # close the ring

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
            "properties": {
                "h3_index": row["h3_index"],
                "violation_count": int(row["violation_count"]),
                "top_violation": row["top_violation"],
                "police_station": row["police_station"],
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
            },
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    logger.info("GeoJSON built — %d features", len(features))
    return geojson
