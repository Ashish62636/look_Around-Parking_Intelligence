"""
src/api/main.py
===============
FastAPI application for the Parking Intelligence API service.
Implements the core endpoints for violation heatmap, congestion score,
and enforcement priority queue. Loads precomputed outputs at startup (ADR-005).
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, Depends, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware


from src.api.auth import verify_api_key
from src.api.schemas import (
    CongestionScoreResponse,
    PriorityQueueItem,
    AlertDispatchPayload,
    AlertDispatchResponse,
)
from src.models.priority import build_priority_queue

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CLEANED_PARQUET = PROCESSED_DIR / "cleaned_violations.parquet"
CSV_PATH = PROJECT_ROOT / "jan to may police violation_anonymized791b166.csv"

# In-memory database caches
CELL_FEATURES: Optional[pd.DataFrame] = None
STATION_FEATURES: Optional[pd.DataFrame] = None
PRIORITY_QUEUE: Optional[pd.DataFrame] = None
GEOJSON_STREET: Optional[dict] = None
GEOJSON_CITY: Optional[dict] = None
CLEANED_DF: Optional[pd.DataFrame] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager that loads precomputed data and ensures self-healing caches."""
    global CELL_FEATURES, STATION_FEATURES, PRIORITY_QUEUE, GEOJSON_STREET, GEOJSON_CITY, CLEANED_DF

    logger.info("Initializing API backend lifecycle...")

    # 1. Self-healing check: run pipeline if files don't exist
    required_files = ["cell_features.parquet", "station_features.parquet", "heatmap_street.geojson", "heatmap_city.geojson"]
    missing = [f for f in required_files if not (PROCESSED_DIR / f).exists()]
    
    if missing:
        logger.warning("Missing precomputed files: %s. Executing pipeline run...", missing)
        try:
            from src.pipeline import run_pipeline
            run_pipeline()
        except Exception as e:
            logger.error("Failed to execute self-healing pipeline run: %s", str(e))
            raise RuntimeError(f"Startup pipeline run failed: {str(e)}")

    # 2. Load precomputed features into memory
    try:
        CELL_FEATURES = pd.read_parquet(PROCESSED_DIR / "cell_features.parquet")
        STATION_FEATURES = pd.read_parquet(PROCESSED_DIR / "station_features.parquet")
        
        # Build priority queue in memory to guarantee dict type preservation in contributing_factors
        PRIORITY_QUEUE = build_priority_queue(CELL_FEATURES)
        
        with open(PROCESSED_DIR / "heatmap_street.geojson", "r") as f:
            GEOJSON_STREET = json.load(f)
        with open(PROCESSED_DIR / "heatmap_city.geojson", "r") as f:
            GEOJSON_CITY = json.load(f)
            
        logger.info(
            "Caches initialized: %d cells, %d stations, %d priority items",
            len(CELL_FEATURES),
            len(STATION_FEATURES),
            len(PRIORITY_QUEUE)
        )
    except Exception as e:
        logger.error("Error loading precomputed files into memory: %s", str(e))
        raise RuntimeError(f"Startup cache load failed: {str(e)}")

    # 3. Load or create cleaned_violations.parquet for fast dynamic queries
    try:
        if CLEANED_PARQUET.exists():
            logger.info("Loading cleaned violations from parquet cache...")
            CLEANED_DF = pd.read_parquet(CLEANED_PARQUET)
        else:
            logger.info("Cleaned violations parquet cache not found. Generating...")
            from src.ingest import load_csv, clean_dataframe
            from src.geo import add_h3_indices
            
            df = load_csv(CSV_PATH)
            df = clean_dataframe(df)
            df = add_h3_indices(df)
            
            CLEANED_PARQUET.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(CLEANED_PARQUET, index=False)
            CLEANED_DF = df
            
        logger.info("Cleaned dataset cached. Row count: %d", len(CLEANED_DF))
    except Exception as e:
        logger.error("Failed to load/create cleaned violations cache: %s", str(e))
        logger.warning("Dynamic date filtering on /heatmap will not be available.")

    yield
    
    # Clean up caches
    CELL_FEATURES = None
    STATION_FEATURES = None
    PRIORITY_QUEUE = None
    GEOJSON_STREET = None
    GEOJSON_CITY = None
    CLEANED_DF = None
    logger.info("API backend shutdown complete.")


# Initialize app with lifespan
app = FastAPI(
    title="look_Around — Bengaluru Parking Intelligence API",
    description="Backend API for AI-driven spatial parking violation patterns, congestion scoring, and patrol enforcement priority queues.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware to support dashboard connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon demo simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Service status checking endpoint."""
    return {
        "status": "active",
        "service": "look_Around-Parking_Intelligence API",
        "documentation": "/docs",
        "message": "Welcome to the Bengaluru Parking Intelligence dashboard API."
    }


@app.get("/api/v1/heatmap", dependencies=[Depends(verify_api_key)])
async def get_heatmap(
    resolution: int = Query(9, description="H3 resolution: 7 (city-level, ~5.16km\u00b2) or 9 (street-level, ~0.11km\u00b2)"),
    start: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
):
    """Retrieve geo-enriched H3 hexagons in GeoJSON format.
    
    Serves from precomputed static files by default (<10ms).
    Dynamically recomputes via DuckDB if start or end parameters are provided.
    """
    if resolution not in (7, 9):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"resolution must be 7 or 9, got {resolution}",
        )

    # 1. Static Cache Serve (Default)
    if not start and not end:
        if resolution == 7:
            return GEOJSON_CITY
        return GEOJSON_STREET

    # 2. Dynamic Filtration
    if CLEANED_DF is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cleaned dataset cache is not loaded. Dynamic query unavailable.",
        )

    try:
        filtered_df = CLEANED_DF
        if start:
            start_date = pd.to_datetime(start).date()
            filtered_df = filtered_df[filtered_df["date_ist"] >= start_date]
        if end:
            end_date = pd.to_datetime(end).date()
            filtered_df = filtered_df[filtered_df["date_ist"] <= end_date]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}",
        )

    if filtered_df.empty:
        return {"type": "FeatureCollection", "features": []}

    # Dynamic aggregation via DuckDB
    import duckdb
    con = duckdb.connect()
    con.register("df_temp", filtered_df)
    
    h3_col = "h3_street" if resolution == 9 else "h3_city"
    
    try:
        agg_df = con.execute(f"""
            SELECT 
                {h3_col} AS h3_index,
                COUNT(*) AS violation_count,
                MODE(primary_violation) AS top_violation,
                MODE(police_station) AS police_station
            FROM df_temp
            GROUP BY {h3_col}
        """).fetchdf()
    finally:
        con.close()

    # Reconstruct H3 boundary geometries
    import h3
    features = []
    
    for _, row in agg_df.iterrows():
        h3_idx = row["h3_index"]
        if not h3_idx or h3_idx == "none" or pd.isna(h3_idx):
            continue
        try:
            lat, lng = h3.cell_to_latlng(h3_idx)
            boundary = h3.cell_to_boundary(h3_idx)
            # GeoJSON polygons need coordinate rings of [lng, lat]
            coords = [[lng, lat] for lat, lng in boundary]
            coords.append(coords[0])  # Close polygon
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
                "properties": {
                    "h3_index": h3_idx,
                    "violation_count": int(row["violation_count"]),
                    "top_violation": str(row["top_violation"]),
                    "police_station": str(row["police_station"]),
                    "lat": float(lat),
                    "lng": float(lng),
                }
            })
        except Exception:
            # Skip invalid cells
            continue

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "resolution": resolution,
            "start": start,
            "end": end,
            "feature_count": len(features)
        }
    }


@app.get("/api/v1/congestion-score", response_model=CongestionScoreResponse, dependencies=[Depends(verify_api_key)])
async def get_congestion_score(
    junction_name: Optional[str] = Query(None, description="Junction name (exact or case-insensitive)"),
    police_station: Optional[str] = Query(None, description="Police station name"),
):
    """Retrieve congestion-impact score (0.0 to 1.0) and supporting factors.
    
    Accepts either police_station or junction_name query parameter (ADR-009).
    Junction scores represent the weighted average congestion of their containing cells.
    """
    if not junction_name and not police_station:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'junction_name' or 'police_station' query parameter",
        )

    # 1. Police Station Lookup
    if police_station:
        if STATION_FEATURES is None:
            raise HTTPException(status_code=500, detail="Station cache uninitialized")
            
        station_match = STATION_FEATURES[
            STATION_FEATURES["police_station"].str.lower() == police_station.lower()
        ]
        
        if station_match.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Police station '{police_station}' not found. Check casing or try Upparpet, Shivajinagar, or Malleshwaram.",
            )
            
        row = station_match.iloc[0]
        score = float(row["congestion_score"])
        violations = int(row["violation_count"])
        
        # Contributing factors narrative
        factors = []
        hotspots = int(row.get("hotspot_cells", 0))
        total_c = int(row.get("total_cells", 1))
        recurrence = float(row.get("recurrence_score", 0.0))
        sev = float(row.get("severity_mean", 0.5))
        h_peak = int(row.get("hour_peak", 12))
        
        if hotspots > 0:
            factors.append(f"DBSCAN Cluster: Contains {hotspots} chronic hotspot grid cell(s) out of {total_c} total spatial cells under jurisdiction.")
        else:
            factors.append(f"DBSCAN Cluster: No high-intensity hotspot clusters detected in the {total_c} spatial cells.")
            
        factors.append(f"Vehicle Recurrence: {recurrence:.1%} of vehicle plates recorded here show repeat offences, indicating chronic parkers.")
        factors.append(f"Violation Severity: Average violation severity index is {sev:.2f}/1.0, influenced by traffic-blocking offences.")
        factors.append(f"Temporal Peak: Violation intensity peaks around hour {h_peak:02d}:00 IST, correlating with traffic congestion hours.")

        return CongestionScoreResponse(
            query_type="station",
            name=str(row["police_station"]),
            score=score,
            violation_count=violations,
            contributing_factors=factors,
        )

    # 2. Junction Name Lookup (Dynamic aggregation over cells)
    if junction_name:
        if CLEANED_DF is None or CELL_FEATURES is None:
            raise HTTPException(status_code=500, detail="Data caches uninitialized for dynamic queries")
            
        j_mask = CLEANED_DF["junction_name"].str.contains(junction_name, case=False, na=False, regex=False)
        j_df = CLEANED_DF[j_mask]
        
        if j_df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Junction '{junction_name}' not found. Sample valid junctions: 'Safina Plaza', 'KR Market', 'Elite'.",
            )
            
        # Group by junction name to find the most frequent matching junction name in the subset
        real_j_name = str(j_df["junction_name"].mode().iloc[0])
        # Filter j_df to only contain records of this specific matched junction to avoid mixing multiple junctions
        j_df = j_df[j_df["junction_name"] == real_j_name]
        violations = len(j_df)
        
        # Map to spatial cells and pull LightGBM predictions
        associated_cells = j_df["h3_street"].unique()
        cell_scores = CELL_FEATURES[CELL_FEATURES["h3_index"].isin(associated_cells)]
        
        if not cell_scores.empty:
            # Calculate counts for weights
            weights = cell_scores["violation_count"].values
            score = float(np.average(cell_scores["congestion_score"], weights=weights))
            recurrence = float(np.average(cell_scores["recurrence_score"], weights=weights))
            sev = float(np.average(cell_scores["severity_mean"], weights=weights))
            
            top_row = cell_scores.sort_values("violation_count", ascending=False).iloc[0]
            police_st = str(top_row["police_station"])
            top_viol = str(top_row["top_violation"])
        else:
            score = 0.5
            recurrence = 0.0
            sev = 0.5
            police_st = "Unknown"
            top_viol = "Unknown"

        factors = [
            f"Spatial Context: Located in {len(associated_cells)} street-level hex cell(s) under {police_st} Police Station jurisdiction.",
            f"Primary Offence: '{top_viol}' is the single most dominant violation type recorded here.",
            f"Vehicle Recurrence: Plotted vehicle numbers reveal a {recurrence:.1%} repeat-offence rate in this zone.",
            f"Severity Index: Average severity weight of {sev:.2f}/1.0 indicates impact on traffic lanes.",
            f"Congestion Proxy: LightGBM model score is {score:.3f} based on local spatial density predictors."
        ]

        return CongestionScoreResponse(
            query_type="junction",
            name=real_j_name,
            score=score,
            violation_count=violations,
            contributing_factors=factors,
        )


@app.get("/api/v1/enforcement-queue", response_model=List[PriorityQueueItem], dependencies=[Depends(verify_api_key)])
async def get_enforcement_queue(
    limit: int = Query(20, description="Maximum cells to return", ge=1, le=500),
    tier: Optional[str] = Query(None, description="Filter by priority tier (IMMEDIATE, HIGH, MODERATE, LOW, MINIMAL)"),
    police_station: Optional[str] = Query(None, description="Filter by police station name"),
):
    """Retrieve ranked list of H3 cells for proactive patrol dispatch (ADR-007).
    
    Priority Score formula blends:
      - DBSCAN hotspot density (40%)
      - Violation volume (30%)
      - Recurrence trend (20%)
      - Severity index (10%)
    """
    if PRIORITY_QUEUE is None:
        raise HTTPException(status_code=500, detail="Priority queue cache is uninitialized")

    df = PRIORITY_QUEUE.copy()

    # Filter station
    if police_station:
        df = df[df["police_station"].str.lower() == police_station.lower()]
        
    # Filter tier
    if tier:
        df = df[df["priority_tier"].str.lower() == tier.lower()]
        
    df = df.head(limit)
    
    # Handle NaN values to prevent Pydantic/JSON errors
    df = df.replace({np.nan: None})
    df = df.where(pd.notnull(df), None)

    items = []
    for _, row in df.iterrows():
        hotspot_rank = int(row["hotspot_rank"]) if row["is_hotspot"] else None
        
        items.append(
            PriorityQueueItem(
                h3_index=str(row["h3_index"]),
                priority_score=float(row["priority_score"]),
                priority_tier=str(row["priority_tier"]),
                recommended_action=str(row["recommended_action"]),
                violation_count=int(row["violation_count"]),
                severity_mean=float(row["severity_mean"]),
                recurrence_score=float(row["recurrence_score"]),
                is_hotspot=bool(row["is_hotspot"]),
                hotspot_rank=hotspot_rank,
                congestion_score=float(row["congestion_score"]),
                police_station=str(row["police_station"]),
                top_violation=str(row["top_violation"]),
                top_vehicle=str(row["top_vehicle"]),
                lat=float(row["lat"]),
                lng=float(row["lng"]),
                contributing_factors=dict(row["contributing_factors"]),
            )
        )

    return items


@app.post("/api/v1/alerts/dispatch", response_model=AlertDispatchResponse, dependencies=[Depends(verify_api_key)])
async def dispatch_alert(payload: AlertDispatchPayload):
    """Stub endpoint simulating webhook dispatches on violation threshold triggers."""
    if CELL_FEATURES is None:
        raise HTTPException(status_code=500, detail="Cell database uninitialized")
        
    cell_match = CELL_FEATURES[CELL_FEATURES["h3_index"] == payload.h3_index]
    if cell_match.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"H3 cell index '{payload.h3_index}' not found in data.",
        )
        
    current_count = int(cell_match.iloc[0]["violation_count"])
    triggered = current_count > payload.threshold
    
    if triggered:
        logger.info(
            "Webhook Alert Triggered: Fired payload to %s for cell %s (Count: %d > %d)",
            payload.webhook_url,
            payload.h3_index,
            current_count,
            payload.threshold,
        )
        msg = f"Alert triggered! Cell violation count ({current_count}) exceeds threshold ({payload.threshold}). Webhook dispatched."
    else:
        msg = f"Alert threshold not crossed. Cell count ({current_count}) is <= threshold ({payload.threshold})."

    return AlertDispatchResponse(
        status="success",
        message=msg,
        alert_triggered=triggered,
        current_count=current_count,
    )
