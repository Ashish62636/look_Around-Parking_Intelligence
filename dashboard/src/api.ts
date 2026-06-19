import type {
  HeatmapGeoJSON,
  PriorityQueueItem,
  CongestionScoreResponse,
} from "./types";

const API_KEY = "parking_intel_key_2026";

const headers: HeadersInit = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const baseUrl = import.meta.env.VITE_API_URL || "";
  const response = await fetch(`${baseUrl}${url}`, {
    ...init,
    headers: { ...headers, ...init?.headers },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(
      `API Error ${response.status}: ${errorBody || response.statusText}`
    );
  }

  return response.json() as Promise<T>;
}

export async function fetchHeatmap(
  resolution: 7 | 9 = 9,
  start?: string,
  end?: string
): Promise<HeatmapGeoJSON> {
  const params = new URLSearchParams({ resolution: String(resolution) });
  if (start) params.set("start", start);
  if (end) params.set("end", end);

  return apiFetch<HeatmapGeoJSON>(`/api/v1/heatmap?${params}`);
}

export async function fetchEnforcementQueue(
  limit = 50,
  tier?: string,
  policeStation?: string
): Promise<PriorityQueueItem[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (tier) params.set("tier", tier);
  if (policeStation) params.set("police_station", policeStation);

  return apiFetch<PriorityQueueItem[]>(`/api/v1/enforcement-queue?${params}`);
}

export async function fetchCongestionScore(
  query: { junction_name: string } | { police_station: string }
): Promise<CongestionScoreResponse> {
  const params = new URLSearchParams(query);
  return apiFetch<CongestionScoreResponse>(
    `/api/v1/congestion-score?${params}`
  );
}
