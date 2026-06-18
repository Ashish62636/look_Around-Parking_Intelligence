"""
src/models/hotspot.py
=====================
DBSCAN-based spatial hotspot detection on H3 cell centroids.

Clusters spatially-close, high-violation cells into enforcement hotspots.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# H3 res-9 edge length ~174m → a cluster should span ~2-3 cells
# At Bengaluru's latitude (~13°N), 1° latitude ≈ 111 km
# eps = 0.004° ≈ 444m — catches adjacent H3 res-9 cells
DEFAULT_EPS_DEG = 0.004
DEFAULT_MIN_SAMPLES = 3


def detect_hotspots(
    cell_features: pd.DataFrame,
    *,
    eps: float = DEFAULT_EPS_DEG,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    violation_threshold_pct: float = 25.0,
) -> pd.DataFrame:
    """Run DBSCAN on high-violation H3 cells to identify enforcement hotspots.

    Args:
        cell_features: DataFrame with columns: h3_index, lat, lng, violation_count, ...
        eps: DBSCAN neighbourhood radius in degrees (~0.004° ≈ 444m at 13°N)
        min_samples: Minimum cells to form a cluster
        violation_threshold_pct: Only cluster cells above this percentile of
            violation_count. Prevents diluting hotspots with low-activity cells.

    Returns:
        cell_features with added columns:
          - cluster_id: DBSCAN label (-1 = noise, 0+ = cluster)
          - is_hotspot: bool — True if part of a cluster
          - hotspot_rank: rank of the cluster by total violations (1 = worst)
          - hotspot_density: normalized violation density within the cluster
    """
    df = cell_features.copy()

    # ---- Filter to high-violation cells for clustering ----------------------
    threshold = np.percentile(df["violation_count"], violation_threshold_pct)
    high_mask = df["violation_count"] >= threshold
    high_cells = df[high_mask].copy()

    logger.info(
        "DBSCAN input: %d cells above P%.0f threshold (%d violations) out of %d total",
        len(high_cells),
        violation_threshold_pct,
        threshold,
        len(df),
    )

    if len(high_cells) < min_samples:
        logger.warning("Too few cells above threshold — no clustering possible")
        df["cluster_id"] = -1
        df["is_hotspot"] = False
        df["hotspot_rank"] = 0
        df["hotspot_density"] = 0.0
        return df

    # ---- DBSCAN on (lat, lng) coordinates -----------------------------------
    coords = high_cells[["lat", "lng"]].values
    db = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean")
    labels = db.fit_predict(coords)
    high_cells["cluster_id"] = labels

    # ---- Merge back to full DataFrame ---------------------------------------
    df["cluster_id"] = -1
    df.loc[high_mask, "cluster_id"] = high_cells["cluster_id"].values
    df["is_hotspot"] = df["cluster_id"] >= 0

    n_clusters = df["cluster_id"].max() + 1 if df["is_hotspot"].any() else 0
    n_noise = (df["cluster_id"] == -1).sum()

    logger.info(
        "DBSCAN result: %d clusters, %d hotspot cells, %d noise cells",
        n_clusters,
        df["is_hotspot"].sum(),
        n_noise,
    )

    # ---- Rank clusters by total violation count -----------------------------
    if n_clusters > 0:
        cluster_totals = (
            df[df["is_hotspot"]]
            .groupby("cluster_id")["violation_count"]
            .sum()
            .sort_values(ascending=False)
        )
        rank_map = {cid: rank + 1 for rank, cid in enumerate(cluster_totals.index)}
        df["hotspot_rank"] = df["cluster_id"].map(rank_map).fillna(0).astype(int)

        # Density: normalize violation_count within each cluster to [0, 1]
        cluster_max = (
            df[df["is_hotspot"]]
            .groupby("cluster_id")["violation_count"]
            .transform("max")
        )
        df.loc[df["is_hotspot"], "hotspot_density"] = (
            df.loc[df["is_hotspot"], "violation_count"] / cluster_max
        )
        df["hotspot_density"] = df["hotspot_density"].fillna(0.0)
    else:
        df["hotspot_rank"] = 0
        df["hotspot_density"] = 0.0

    # ---- Log top clusters ---------------------------------------------------
    if n_clusters > 0:
        for cid in list(rank_map.keys())[:5]:
            cluster_df = df[df["cluster_id"] == cid]
            logger.info(
                "  Cluster %d (rank %d): %d cells, %d total violations, "
                "station: %s",
                cid,
                rank_map[cid],
                len(cluster_df),
                cluster_df["violation_count"].sum(),
                cluster_df["police_station"].mode().iloc[0]
                if len(cluster_df["police_station"].mode()) > 0
                else "UNKNOWN",
            )

    return df


def summarize_hotspots(cell_features: pd.DataFrame) -> pd.DataFrame:
    """Build a summary table of hotspot clusters for the API response.

    Returns one row per cluster with:
      cluster_id, rank, total_violations, cell_count, center_lat, center_lng,
      top_violation, top_station, avg_severity
    """
    hotspots = cell_features[cell_features["is_hotspot"]].copy()

    if hotspots.empty:
        return pd.DataFrame()

    summary = (
        hotspots.groupby("cluster_id")
        .agg(
            rank=("hotspot_rank", "first"),
            total_violations=("violation_count", "sum"),
            cell_count=("h3_index", "count"),
            center_lat=("lat", "mean"),
            center_lng=("lng", "mean"),
            avg_severity=("severity_mean", "mean"),
            top_violation=(
                "top_violation",
                lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
            ),
            top_station=(
                "police_station",
                lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "UNKNOWN",
            ),
        )
        .reset_index()
        .sort_values("rank")
        .reset_index(drop=True)
    )

    logger.info("Hotspot summary: %d clusters", len(summary))
    return summary
