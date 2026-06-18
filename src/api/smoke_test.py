"""
src/api/smoke_test.py
=====================
Smoke test script for the FastAPI service.
Uses TestClient to verify API responses, headers, and schemas in-memory.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient
from src.api.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_smoke_tests():
    logger.info("Initializing API smoke tests...")
    
    # 1. Initialize TestClient within context manager to trigger lifespan startup
    with TestClient(app) as client:
        logger.info("TestClient initialized and context manager entered (lifespan ran).")
        
        # API key configured for tests (default)
        headers = {"X-API-Key": "parking_intel_key_2026"}
        invalid_headers = {"X-API-Key": "wrong_key_123"}
        
        # ---- Test 0: Root endpoint (No Auth required) ----
        logger.info("Testing GET / ...")
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        logger.info("  Root: OK")
    
        # ---- Test 1: Auth check (verify unauthorized & forbidden) ----
        logger.info("Testing Auth validation on /api/v1/enforcement-queue ...")
        # Missing API Key
        r = client.get("/api/v1/enforcement-queue")
        assert r.status_code == 401
        assert "Missing API Key" in r.json()["detail"]
        
        # Invalid API Key
        r = client.get("/api/v1/enforcement-queue", headers=invalid_headers)
        assert r.status_code == 403
        assert "Invalid API Key" in r.json()["detail"]
        logger.info("  Auth: OK")
    
        # ---- Test 2: Heatmap Endpoint (Static Cache) ----
        logger.info("Testing GET /api/v1/heatmap (static cache res-9) ...")
        r = client.get("/api/v1/heatmap?resolution=9", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0
        # Check properties
        prop = data["features"][0]["properties"]
        assert "h3_index" in prop
        assert "violation_count" in prop
        assert "top_violation" in prop
        assert "police_station" in prop
        logger.info("  Heatmap (Static): OK (found %d features)", len(data["features"]))
    
        # ---- Test 3: Heatmap Endpoint (Dynamic Filter) ----
        logger.info("Testing GET /api/v1/heatmap (dynamic filtering res-9) ...")
        # Filter for first month (Nov 2023)
        r = client.get("/api/v1/heatmap?resolution=9&start=2023-11-10&end=2023-11-30", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "FeatureCollection"
        logger.info("  Heatmap (Dynamic): OK (found %d features for Nov 2023)", len(data["features"]))
    
        # ---- Test 4: Congestion Score (Police Station) ----
        station_name = "Upparpet"
        logger.info("Testing GET /api/v1/congestion-score for Station: %s ...", station_name)
        r = client.get(f"/api/v1/congestion-score?police_station={station_name}", headers=headers)
        assert r.status_code == 200
        res = r.json()
        assert res["query_type"] == "station"
        assert res["name"] == station_name
        assert 0.0 <= res["score"] <= 1.0
        assert len(res["contributing_factors"]) > 0
        logger.info("  Congestion (Station): OK (score: %.3f)", res["score"])
    
        # ---- Test 5: Congestion Score (Junction) ----
        junction_name = "Safina Plaza"
        logger.info("Testing GET /api/v1/congestion-score for Junction: %s ...", junction_name)
        r = client.get(f"/api/v1/congestion-score?junction_name={junction_name}", headers=headers)
        assert r.status_code == 200
        res = r.json()
        assert res["query_type"] == "junction"
        assert junction_name.lower() in res["name"].lower()
        assert 0.0 <= res["score"] <= 1.0
        assert len(res["contributing_factors"]) > 0
        logger.info("  Congestion (Junction): OK (score: %.3f)", res["score"])
    
        # ---- Test 6: Enforcement Queue ----
        logger.info("Testing GET /api/v1/enforcement-queue (limit=5, tier=IMMEDIATE) ...")
        r = client.get("/api/v1/enforcement-queue?limit=5&tier=IMMEDIATE", headers=headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) <= 5
        if items:
            item = items[0]
            assert item["priority_tier"] == "IMMEDIATE"
            assert "h3_index" in item
            assert "priority_score" in item
            assert "recommended_action" in item
            assert "contributing_factors" in item
            assert isinstance(item["contributing_factors"], dict)
        logger.info("  Enforcement Queue: OK (returned %d IMMEDIATE items)", len(items))
    
        # ---- Test 7: Alert Dispatch ----
        logger.info("Testing POST /api/v1/alerts/dispatch ...")
        # Fetch first index from cell features to use as test
        test_h3 = "8960145b553ffff" # HAL Old Airport area / Upparpet area cell
        payload = {
            "h3_index": test_h3,
            "threshold": 100,
            "webhook_url": "https://httpbin.org/post"
        }
        r = client.post("/api/v1/alerts/dispatch", json=payload, headers=headers)
        assert r.status_code == 200
        res = r.json()
        assert res["status"] == "success"
        assert "alert_triggered" in res
        assert "current_count" in res
        logger.info("  Alert Dispatch: OK (triggered: %s, count: %d)", res["alert_triggered"], res["current_count"])
    
        logger.info("=" * 50)
        logger.info("  ALL API SMOKE TESTS PASSED SUCCESSFULLY!")
        logger.info("=" * 50)


if __name__ == "__main__":
    try:
        run_smoke_tests()
    except AssertionError as e:
        logger.error("Smoke test ASSERTION FAILED: %s", str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("Smoke test FAILED with exception: %s", str(e), exc_info=True)
        sys.exit(1)
