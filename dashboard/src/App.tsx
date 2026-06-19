"use client";

import { useState, useEffect, useCallback } from "react";
import type {
  HeatmapGeoJSON,
  HeatmapFeatureProperties,
  PriorityQueueItem,
  CongestionScoreResponse,
  MapViewState,
  HeatmapResolution,
  DashboardStats,
} from "./types";
import {
  fetchHeatmap,
  fetchEnforcementQueue,
  fetchCongestionScore,
} from "./api";
import { Header } from "./components/Header";
import { ControlsBar } from "./components/ControlsBar";
import { StatCard } from "./components/StatCard";
import { HeatmapMap, flyToCell } from "./components/HeatmapMap";
import { EnforcementQueue } from "./components/EnforcementQueue";
import { CellDetail } from "./components/CellDetail";
import { CongestionPanel } from "./components/CongestionPanel";
import { CongestionSearch } from "./components/CongestionSearch";

/* Bengaluru center */
const INITIAL_VIEW: MapViewState = {
  longitude: 77.594,
  latitude: 12.971,
  zoom: 12,
  pitch: 0,
  bearing: 0,
};

function computeStats(
  geojson: HeatmapGeoJSON | null,
  queue: PriorityQueueItem[]
): DashboardStats {
  const totalCells = geojson?.features?.length ?? 0;
  const totalViolations =
    geojson?.features?.reduce(
      (sum, f) => sum + f.properties.violation_count,
      0
    ) ?? 0;

  const immediateCells = queue.filter(
    (i) => i.priority_tier === "IMMEDIATE"
  ).length;
  const highCells = queue.filter((i) => i.priority_tier === "HIGH").length;
  const avgCongestion =
    queue.length > 0
      ? queue.reduce((s, i) => s + i.congestion_score, 0) / queue.length
      : 0;

  return { totalCells, totalViolations, immediateCells, highCells, avgCongestion };
}

export default function App() {
  /* ─── State ─── */
  const [activeTab, setActiveTab] = useState("heatmap");
  const [resolution, setResolution] = useState<HeatmapResolution>(9);
  const [tierFilter, setTierFilter] = useState("ALL");
  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW);

  // Data
  const [geojson, setGeojson] = useState<HeatmapGeoJSON | null>(null);
  const [queue, setQueue] = useState<PriorityQueueItem[]>([]);
  const [congestion, setCongestion] = useState<CongestionScoreResponse | null>(null);
  const [stats, setStats] = useState<DashboardStats>({
    totalCells: 0,
    totalViolations: 0,
    immediateCells: 0,
    highCells: 0,
    avgCongestion: 0,
  });

  // Selection & interaction
  const [selectedH3, setSelectedH3] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<HeatmapFeatureProperties | null>(null);

  // Loading
  const [loadingMap, setLoadingMap] = useState(true);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [loadingCongestion, setLoadingCongestion] = useState(false);

  // Error
  const [error, setError] = useState<string | null>(null);

  /* ─── Fetch heatmap on resolution change ─── */
  useEffect(() => {
    let cancelled = false;
    setLoadingMap(true);
    setError(null);

    fetchHeatmap(resolution)
      .then((data) => {
        if (!cancelled) {
          setGeojson(data);
          setLoadingMap(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(String(err));
          setLoadingMap(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [resolution]);

  /* ─── Fetch enforcement queue ─── */
  useEffect(() => {
    if (activeTab !== "enforcement") return;

    let cancelled = false;
    setLoadingQueue(true);

    const tier = tierFilter === "ALL" ? undefined : tierFilter;
    fetchEnforcementQueue(100, tier)
      .then((data) => {
        if (!cancelled) {
          setQueue(data);
          setLoadingQueue(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(String(err));
          setLoadingQueue(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, tierFilter]);

  /* ─── Also fetch full queue for stats if on heatmap tab ─── */
  useEffect(() => {
    if (activeTab === "heatmap" && queue.length === 0) {
      fetchEnforcementQueue(500).then(setQueue).catch(() => {});
    }
  }, [activeTab, queue.length]);

  /* ─── Compute stats when data changes ─── */
  useEffect(() => {
    setStats(computeStats(geojson, queue));
  }, [geojson, queue]);

  /* ─── Handlers ─── */
  const handleCellClick = useCallback(
    (props: HeatmapFeatureProperties) => {
      setSelectedH3(props.h3_index);
      setSelectedCell(props);
      setViewState(flyToCell(props.lat, props.lng, viewState));
    },
    [viewState]
  );

  const handleQueueSelect = useCallback(
    (item: PriorityQueueItem) => {
      setSelectedH3((prev) =>
        prev === item.h3_index ? null : item.h3_index
      );
      setViewState(flyToCell(item.lat, item.lng, viewState));
    },
    [viewState]
  );

  const handleCongestionLookup = useCallback(
    async (query: { junction_name: string } | { police_station: string }) => {
      setLoadingCongestion(true);
      setError(null);
      try {
        const data = await fetchCongestionScore(query);
        setCongestion(data);
        setActiveTab("congestion");
      } catch (err) {
        setError(String(err));
      } finally {
        setLoadingCongestion(false);
      }
    },
    []
  );

  const handleCellCongestionLookup = useCallback(
    (stationName: string) => {
      handleCongestionLookup({ police_station: stationName });
    },
    [handleCongestionLookup]
  );

  /* ─── Sidebar content based on active tab ─── */
  function renderSidebar() {
    switch (activeTab) {
      case "heatmap":
        return (
          <div className="flex flex-col gap-4 p-4">
            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                label="Total Cells"
                value={stats.totalCells}
                icon="pin"
                accentColor="var(--color-accent-cyan)"
                delay={0}
              />
              <StatCard
                label="Violations"
                value={stats.totalViolations}
                icon="alert"
                accentColor="var(--color-accent-amber)"
                delay={80}
              />
              <StatCard
                label="Immediate"
                value={stats.immediateCells}
                subtitle="Cells needing patrol"
                icon="shield"
                accentColor="var(--color-accent-red)"
                delay={160}
              />
              <StatCard
                label="High Priority"
                value={stats.highCells}
                subtitle="Elevated concern"
                icon="trending"
                accentColor="var(--color-accent-violet)"
                delay={240}
              />
            </div>

            {/* Cell detail */}
            {selectedCell && (
              <CellDetail
                cell={selectedCell}
                onClose={() => {
                  setSelectedCell(null);
                  setSelectedH3(null);
                }}
                onLookupCongestion={handleCellCongestionLookup}
              />
            )}
          </div>
        );

      case "enforcement":
        return (
          <EnforcementQueue
            items={queue}
            selectedH3={selectedH3}
            onSelectItem={handleQueueSelect}
            isLoading={loadingQueue}
          />
        );

      case "congestion":
        return (
          <div className="flex flex-col gap-4 p-4">
            {!congestion ? (
              <CongestionSearch
                onSearch={handleCongestionLookup}
                isLoading={loadingCongestion}
              />
            ) : (
              <CongestionPanel
                data={congestion}
                isLoading={loadingCongestion}
                onClose={() => setCongestion(null)}
              />
            )}
          </div>
        );

      default:
        return null;
    }
  }

  return (
    <div className="flex flex-col h-dvh overflow-hidden">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      <ControlsBar
        resolution={resolution}
        onResolutionChange={setResolution}
        tierFilter={tierFilter}
        onTierFilterChange={setTierFilter}
        activeTab={activeTab}
      />

      {/* Error banner */}
      {error && (
        <div className="px-5 py-2 bg-accent-red/10 border-b border-accent-red/20 text-xs text-accent-red">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-96 shrink-0 border-r border-border-default bg-surface-secondary/40 overflow-y-auto">
          {renderSidebar()}
        </aside>

        {/* Map */}
        <main className="flex-1 relative">
          <HeatmapMap
            geojson={geojson}
            viewState={viewState}
            onViewStateChange={setViewState}
            selectedH3={selectedH3}
            onCellClick={handleCellClick}
            isLoading={loadingMap}
            resolution={resolution}
          />
        </main>
      </div>
    </div>
  );
}
