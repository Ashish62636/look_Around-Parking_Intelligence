/* ─── API Response Types ─── */

export interface HeatmapFeatureProperties {
  h3_index: string;
  violation_count: number;
  top_violation: string;
  police_station: string;
  lat: number;
  lng: number;
}

export interface HeatmapFeature {
  type: "Feature";
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  properties: HeatmapFeatureProperties;
}

export interface HeatmapGeoJSON {
  type: "FeatureCollection";
  features: HeatmapFeature[];
  metadata?: {
    resolution: number;
    start: string | null;
    end: string | null;
    feature_count: number;
  };
}

export interface CongestionScoreResponse {
  query_type: "junction" | "station";
  name: string;
  score: number;
  violation_count: number;
  contributing_factors: string[];
  hotspot_cells?: number;
  total_cells?: number;
  recurrence_rate?: number;
  severity_index?: number;
  peak_hour?: number;
  confidence_score?: number;
}


export interface PriorityQueueItem {
  h3_index: string;
  priority_score: number;
  priority_tier: "IMMEDIATE" | "HIGH" | "MODERATE" | "LOW" | "MINIMAL";
  recommended_action: string;
  violation_count: number;
  severity_mean: number;
  recurrence_score: number;
  is_hotspot: boolean;
  hotspot_rank: number | null;
  congestion_score: number;
  police_station: string;
  top_violation: string;
  top_vehicle: string;
  lat: number;
  lng: number;
  contributing_factors: Record<string, number>;
}

export interface AlertDispatchPayload {
  h3_index: string;
  threshold: number;
  webhook_url: string;
}

export interface AlertDispatchResponse {
  status: string;
  message: string;
  alert_triggered: boolean;
  current_count: number;
}

/* ─── UI State Types ─── */

export type ViewMode = "heatmap" | "enforcement" | "congestion";

export type HeatmapResolution = 7 | 9;

export interface MapViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export interface DashboardStats {
  totalCells: number;
  totalViolations: number;
  immediateCells: number;
  highCells: number;
  avgCongestion: number;
}
