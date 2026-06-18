"""
src/api/schemas.py
==================
Pydantic response and request models for the FastAPI service.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class CongestionScoreResponse(BaseModel):
    """Response model for the congestion score endpoint."""
    query_type: str = Field(..., description="The spatial entity type queried (junction or station)")
    name: str = Field(..., description="The name of the junction or police station")
    score: float = Field(..., description="Normalized congestion-impact score (0.0 to 1.0)")
    violation_count: int = Field(..., description="Total violations associated with this entity")
    contributing_factors: List[str] = Field(..., description="Human-readable breakdown of contributing congestion factors")


class PriorityQueueItem(BaseModel):
    """Response model for a single item in the enforcement priority queue."""
    h3_index: str = Field(..., description="The H3 spatial cell index (res-9)")
    priority_score: float = Field(..., description="Normalized priority ranking score (0.0 to 1.0)")
    priority_tier: str = Field(..., description="Priority tier (IMMEDIATE, HIGH, MODERATE, LOW, MINIMAL)")
    recommended_action: str = Field(..., description="Action recommendation for enforcement teams")
    violation_count: int = Field(..., description="Total violations in this cell")
    severity_mean: float = Field(..., description="Average severity score of violations in this cell")
    recurrence_score: float = Field(..., description="Ratio of repeat offender vehicles in this cell")
    is_hotspot: bool = Field(..., description="Whether the cell lies within a DBSCAN hotspot cluster")
    hotspot_rank: Optional[float] = Field(None, description="Global rank of the DBSCAN cluster (if hotspot)")
    congestion_score: float = Field(..., description="Normalized congestion-impact score from LightGBM")
    police_station: str = Field(..., description="Main police station jurisdiction for this cell")
    top_violation: str = Field(..., description="Most common violation type in this cell")
    top_vehicle: str = Field(..., description="Most common vehicle type in this cell")
    lat: float = Field(..., description="Latitude of cell centroid")
    lng: float = Field(..., description="Longitude of cell centroid")
    contributing_factors: Dict[str, float] = Field(..., description="Weights of factors that drove the priority score")


class AlertDispatchPayload(BaseModel):
    """Payload to stub the stretch alert dispatcher endpoint."""
    h3_index: str = Field(..., description="H3 cell index to watch")
    threshold: int = Field(..., description="Violation count threshold to trigger the alert")
    webhook_url: str = Field(..., description="Destination URL to fire the alert payload to")


class AlertDispatchResponse(BaseModel):
    """Response for the alert dispatcher stub."""
    status: str = Field("success", description="Dispatch status")
    message: str = Field(..., description="Detail message")
    alert_triggered: bool = Field(..., description="True if cell violation count exceeded threshold")
    current_count: int = Field(..., description="Current violation count in that cell")
