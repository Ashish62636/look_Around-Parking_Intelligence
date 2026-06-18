"""
src/pipeline.py
===============
End-to-end pipeline orchestrator for Phase 1 (Geo + Features) and Phase 2 (ML Core).

Usage:
    python -m src.pipeline                         # default CSV
    python -m src.pipeline --csv path/to/file.csv  # custom path
"""

import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

# ---- Project imports --------------------------------------------------------
from src.ingest import load_csv, clean_dataframe
from src.quality.validate import validate_dataframe
from src.geo import add_h3_indices, aggregate_h3_cells, h3_cells_to_geojson
from src.features import (
    add_severity,
    build_cell_features,
    build_station_features,
    build_temporal_profile,
)
from src.models.hotspot import detect_hotspots, summarize_hotspots
from src.models.congestion import (
    train_congestion_model,
    compute_congestion_scores,
    compute_station_congestion,
)
from src.models.priority import build_priority_queue, build_station_priority_queue

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

TOTAL_STEPS = 16


def run_pipeline(csv_path: str | Path | None = None) -> dict:
    """Execute the full Phase 1 + Phase 2 pipeline.

    Phase 1 — Geo + Features (steps 1–10):
        1. Load CSV via DuckDB
        2. Clean (parse JSON, fix timestamps, extract IST features)
        3. Validate (assertion-based schema checks)
        4. H3 enrichment (res-7 city, res-9 street)
        5. Add severity weights
        6. Build per-cell features (street-level)
        7. Build per-station features
        8. Build temporal profiles
        9. Generate GeoJSON
       10. Persist Phase 1 outputs

    Phase 2 — ML Core (steps 11–16):
       11. DBSCAN hotspot detection
       12. LightGBM congestion model
       13. Congestion scores (cell + station)
       14. Enforcement priority queue
       15. Persist Phase 2 outputs
       16. Summary

    Returns:
        dict with all computed outputs
    """
    t0 = time.perf_counter()

    # ======================================================================
    # PHASE 1 — Geo + Features
    # ======================================================================
    logger.info("=" * 60)
    logger.info("PIPELINE — START (Phase 1 + Phase 2)")
    logger.info("=" * 60)

    # ---- 1. Load ----
    df = load_csv(csv_path) if csv_path else load_csv()
    t_load = time.perf_counter()
    logger.info("[1/%d] CSV loaded in %.2fs", TOTAL_STEPS, t_load - t0)

    # ---- 2. Clean ----
    df = clean_dataframe(df)
    t_clean = time.perf_counter()
    logger.info("[2/%d] Cleaned in %.2fs", TOTAL_STEPS, t_clean - t_load)

    # ---- 3. Validate ----
    report = validate_dataframe(df)
    t_validate = time.perf_counter()
    logger.info("[3/%d] Validated in %.2fs", TOTAL_STEPS, t_validate - t_clean)

    if not report.ok:
        logger.error("Validation FAILED: %s", report.errors)
        raise RuntimeError(f"Validation failed: {report.errors}")

    if report.warnings:
        for w in report.warnings:
            logger.warning("  WARN: %s", w)

    # ---- 4. H3 enrichment ----
    df = add_h3_indices(df)
    t_h3 = time.perf_counter()
    logger.info("[4/%d] H3 enrichment in %.2fs", TOTAL_STEPS, t_h3 - t_validate)

    # ---- 5. Severity weights ----
    df = add_severity(df)
    t_sev = time.perf_counter()
    logger.info("[5/%d] Severity added in %.2fs", TOTAL_STEPS, t_sev - t_h3)

    # ---- 6. Per-cell features (street-level) ----
    cell_features = build_cell_features(df, h3_col="h3_street")
    t_cell = time.perf_counter()
    logger.info("[6/%d] Cell features in %.2fs", TOTAL_STEPS, t_cell - t_sev)

    # ---- 7. Per-station features ----
    station_features = build_station_features(df)
    t_station = time.perf_counter()
    logger.info("[7/%d] Station features in %.2fs", TOTAL_STEPS, t_station - t_cell)

    # ---- 8. Temporal profiles ----
    temporal_profiles = build_temporal_profile(df, h3_col="h3_street")
    t_temporal = time.perf_counter()
    logger.info("[8/%d] Temporal profiles in %.2fs", TOTAL_STEPS, t_temporal - t_station)

    # ---- 9. GeoJSON (street + city) ----
    agg_street = aggregate_h3_cells(df, resolution="h3_street")
    geojson_street = h3_cells_to_geojson(agg_street)

    agg_city = aggregate_h3_cells(df, resolution="h3_city")
    geojson_city = h3_cells_to_geojson(agg_city)
    t_geojson = time.perf_counter()
    logger.info("[9/%d] GeoJSON built in %.2fs", TOTAL_STEPS, t_geojson - t_temporal)

    # ---- 10. Persist Phase 1 outputs ----
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temporal_profiles.to_parquet(OUTPUT_DIR / "temporal_profiles.parquet", index=False)
    with open(OUTPUT_DIR / "heatmap_street.geojson", "w") as f:
        json.dump(geojson_street, f)
    with open(OUTPUT_DIR / "heatmap_city.geojson", "w") as f:
        json.dump(geojson_city, f)
    t_p1_persist = time.perf_counter()
    logger.info("[10/%d] Phase 1 outputs saved in %.2fs", TOTAL_STEPS, t_p1_persist - t_geojson)

    t_phase1 = t_p1_persist - t0
    logger.info("-" * 40)
    logger.info("Phase 1 complete in %.2fs", t_phase1)
    logger.info("-" * 40)

    # ======================================================================
    # PHASE 2 — ML Core
    # ======================================================================

    # ---- 11. DBSCAN hotspot detection ----
    cell_features = detect_hotspots(cell_features)
    t_dbscan = time.perf_counter()
    logger.info("[11/%d] DBSCAN hotspots in %.2fs", TOTAL_STEPS, t_dbscan - t_p1_persist)

    # ---- 12. LightGBM congestion model ----
    model_result = train_congestion_model(cell_features)
    t_lgbm = time.perf_counter()
    logger.info(
        "[12/%d] LightGBM trained in %.2fs — MAE: %.4f, R2: %.4f",
        TOTAL_STEPS,
        t_lgbm - t_dbscan,
        model_result["metrics"]["mae"],
        model_result["metrics"]["r2"],
    )

    # ---- 13. Congestion scores (cell + station) ----
    cell_features = compute_congestion_scores(cell_features, model_result["predictions"])
    station_features = compute_station_congestion(cell_features, station_features)
    t_scores = time.perf_counter()
    logger.info("[13/%d] Congestion scores in %.2fs", TOTAL_STEPS, t_scores - t_lgbm)

    # ---- 14. Enforcement priority queues ----
    priority_queue = build_priority_queue(cell_features)
    station_priority = build_station_priority_queue(station_features)
    hotspot_summary = summarize_hotspots(cell_features)
    t_queue = time.perf_counter()
    logger.info("[14/%d] Priority queues in %.2fs", TOTAL_STEPS, t_queue - t_scores)

    # ---- 15. Persist Phase 2 outputs ----
    cell_features.to_parquet(OUTPUT_DIR / "cell_features.parquet", index=False)
    station_features.to_parquet(OUTPUT_DIR / "station_features.parquet", index=False)

    # Priority queue — save without the dict column for CSV readability
    pq_csv = priority_queue.drop(columns=["contributing_factors"], errors="ignore")
    pq_csv.to_csv(OUTPUT_DIR / "priority_queue.csv", index=False)
    pq_csv.head(50).to_csv(OUTPUT_DIR / "top50_priority.csv", index=False)

    # Station priority
    station_priority.to_csv(OUTPUT_DIR / "station_priority.csv", index=False)

    # Hotspot summary
    hotspot_summary.to_csv(OUTPUT_DIR / "hotspot_summary.csv", index=False)

    # Station features (updated with congestion)
    station_features.to_csv(OUTPUT_DIR / "station_features.csv", index=False)

    # Model metadata
    model_meta = {
        "feature_importance": model_result["feature_importance"],
        "metrics": model_result["metrics"],
        "feature_cols": model_result["feature_cols"],
    }
    with open(OUTPUT_DIR / "model_metadata.json", "w") as f:
        json.dump(model_meta, f, indent=2)

    t_persist = time.perf_counter()
    logger.info("[15/%d] Phase 2 outputs saved in %.2fs", TOTAL_STEPS, t_persist - t_queue)

    # ---- 16. Summary ----
    total = t_persist - t0
    logger.info("=" * 60)
    logger.info(
        "PIPELINE COMPLETE in %.2fs (%.1f min) — Phase 1: %.1fs, Phase 2: %.1fs",
        total, total / 60, t_phase1, total - t_phase1,
    )
    logger.info("=" * 60)
    logger.info("  Rows: %d", len(df))
    logger.info("  H3 street cells: %d", df["h3_street"].nunique())
    logger.info("  H3 city cells: %d", df["h3_city"].nunique())
    logger.info("  Stations: %d", station_features["police_station"].nunique())
    logger.info(
        "  Hotspot clusters: %d (%d cells)",
        cell_features["cluster_id"].max() + 1 if cell_features["is_hotspot"].any() else 0,
        cell_features["is_hotspot"].sum(),
    )
    logger.info(
        "  LightGBM — MAE: %.4f, R2: %.4f",
        model_result["metrics"]["mae"],
        model_result["metrics"]["r2"],
    )
    logger.info(
        "  Priority queue — IMMEDIATE: %d, HIGH: %d, MODERATE: %d",
        (priority_queue["priority_tier"] == "IMMEDIATE").sum(),
        (priority_queue["priority_tier"] == "HIGH").sum(),
        (priority_queue["priority_tier"] == "MODERATE").sum(),
    )
    logger.info("  Outputs in: %s", OUTPUT_DIR)

    return {
        "df": df,
        "cell_features": cell_features,
        "station_features": station_features,
        "temporal_profiles": temporal_profiles,
        "geojson_street": geojson_street,
        "geojson_city": geojson_city,
        "validation_report": report,
        "hotspot_summary": hotspot_summary,
        "model_result": model_result,
        "priority_queue": priority_queue,
        "station_priority": station_priority,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    csv_arg = None
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        csv_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    result = run_pipeline(csv_arg)

    pq = result["priority_queue"]
    sf = result["station_priority"]

    print("\n" + "=" * 50)
    print("  PIPELINE SUMMARY")
    print("=" * 50)
    print(f"  Total rows:          {len(result['df']):,}")
    print(f"  H3 street cells:     {result['cell_features'].shape[0]:,}")
    print(f"  H3 city cells:       {len(result['geojson_city']['features']):,}")
    print(f"  Police stations:     {result['station_features'].shape[0]:,}")
    print(f"  Hotspot clusters:    {result['hotspot_summary'].shape[0]:,}")
    print(f"  LightGBM MAE:       {result['model_result']['metrics']['mae']:.4f}")
    print(f"  LightGBM R2:        {result['model_result']['metrics']['r2']:.4f}")
    print(f"  Priority IMMEDIATE:  {(pq['priority_tier'] == 'IMMEDIATE').sum():,}")
    print(f"  Priority HIGH:       {(pq['priority_tier'] == 'HIGH').sum():,}")
    print(f"  Top station:         {sf.iloc[0]['police_station']} "
          f"(score: {sf.iloc[0]['priority_score']:.3f})")
    print(f"  Outputs saved to:    {OUTPUT_DIR}")
