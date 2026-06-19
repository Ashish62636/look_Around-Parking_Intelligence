"use client";

import { useCallback, useMemo, useState } from "react";
import { Map as MapGL } from "react-map-gl/maplibre";
import { DeckGL } from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { FlyToInterpolator } from "@deck.gl/core";
import type { HeatmapGeoJSON, HeatmapFeatureProperties, MapViewState } from "../types";
import "maplibre-gl/dist/maplibre-gl.css";

interface Props {
  geojson: HeatmapGeoJSON | null;
  viewState: MapViewState;
  onViewStateChange: (vs: MapViewState) => void;
  selectedH3: string | null;
  onCellClick: (props: HeatmapFeatureProperties) => void;
  isLoading: boolean;
  resolution?: number;
}

/* Color scale: violation_count → RGBA */
function getHexColor(count: number, maxCount: number): [number, number, number, number] {
  const t = Math.min(count / maxCount, 1);

  if (t < 0.2) return [6, 182, 212, 140];       // cyan — low
  if (t < 0.4) return [16, 185, 129, 160];       // emerald
  if (t < 0.6) return [245, 158, 11, 180];       // amber
  if (t < 0.8) return [249, 115, 22, 200];       // orange
  return [239, 68, 68, 220];                      // red — critical
}

const DARK_BASEMAP =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export function HeatmapMap({
  geojson,
  viewState,
  onViewStateChange,
  selectedH3,
  onCellClick,
  isLoading,
  resolution,
}: Props) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const formatScaleNum = (val: number): string => {
    if (val >= 1000) {
      return (val / 1000).toFixed(val % 1000 === 0 ? 0 : 1) + "k";
    }
    return val.toString();
  };

  const maxCount = useMemo(() => {
    if (!geojson?.features?.length) return 1;
    return Math.max(
      ...geojson.features.map((f) => f.properties.violation_count)
    );
  }, [geojson]);

  const layers = useMemo(() => {
    if (!geojson?.features?.length) return [];

    return [
      new GeoJsonLayer({
        id: "heatmap-hex",
        data: geojson,
        pickable: true,
        stroked: true,
        filled: true,
        extruded: false,
        getFillColor: (d) => {
          const props = (d as { properties: HeatmapFeatureProperties }).properties;
          if (selectedH3 && props.h3_index === selectedH3) {
            return [139, 92, 246, 240]; // Violet for selected
          }
          return getHexColor(props.violation_count, maxCount);
        },
        getLineColor: (d) => {
          const props = (d as { properties: HeatmapFeatureProperties }).properties;
          if (selectedH3 && props.h3_index === selectedH3) {
            return [139, 92, 246, 255];
          }
          return [255, 255, 255, 30];
        },
        getLineWidth: (d) => {
          const props = (d as { properties: HeatmapFeatureProperties }).properties;
          return selectedH3 && props.h3_index === selectedH3 ? 3 : 1;
        },
        lineWidthUnits: "pixels" as const,
        updateTriggers: {
          getFillColor: [selectedH3, maxCount],
          getLineColor: [selectedH3],
          getLineWidth: [selectedH3],
        },
        onClick: ({ object }) => {
          if (object) {
            const props = (object as { properties: HeatmapFeatureProperties }).properties;
            onCellClick(props);
          }
        },
        transitions: {
          getFillColor: 300,
        },
      }),
    ];
  }, [geojson, selectedH3, maxCount, onCellClick]);

  const handleViewStateChange = useCallback(
    ({ viewState: vs }: { viewState: MapViewState }) => {
      onViewStateChange(vs);
    },
    [onViewStateChange]
  );

  return (
    <div className="relative w-full h-full">
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={true}
        layers={layers}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
        getTooltip={({ object }) => {
          if (!object) return null;
          const p = (object as { properties: HeatmapFeatureProperties }).properties;
          return {
            html: `
              <div style="
                background: rgba(11,15,25,0.95);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(30,41,59,0.8);
                border-radius: 8px;
                padding: 10px 14px;
                font-family: Inter, sans-serif;
                min-width: 180px;
              ">
                <div style="font-size:12px;font-weight:600;color:#f1f5f9;margin-bottom:6px;">
                  ${p.police_station}
                </div>
                <div style="font-size:11px;color:#94a3b8;margin-bottom:3px;">
                  Violations: <span style="color:#06b6d4;font-weight:600;">${p.violation_count.toLocaleString()}</span>
                </div>
                <div style="font-size:11px;color:#94a3b8;">
                  Type: <span style="color:#f59e0b;">${p.top_violation}</span>
                </div>
              </div>
            `,
            style: {
              backgroundColor: "transparent",
              border: "none",
              padding: "0",
              boxShadow: "none",
            },
          };
        }}
      >
        <MapGL
          mapStyle={DARK_BASEMAP}
          attributionControl={false}
        />
      </DeckGL>

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-primary/60 backdrop-blur-sm z-10">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-text-secondary">Loading heatmap data…</p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-6 left-6 glass-card px-5 py-4 z-10 w-64 shadow-2xl transition-all duration-300">
        <div className="flex flex-col mb-2.5">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-text-primary">
            Violation Density
          </span>
          <span className="text-[9px] text-text-muted mt-0.5 font-semibold h-3.5 flex items-center">
            {hoveredIndex === null ? (
              resolution === 7
                ? "Normalized Per City Cell (H3 Res 7)"
                : "Normalized Per Street Cell (H3 Res 9)"
            ) : (
              (() => {
                const minVal = Math.round(maxCount * (hoveredIndex * 0.2));
                const maxVal = Math.round(maxCount * ((hoveredIndex + 1) * 0.2));
                const labels = ["Low Density", "Medium Density", "High Density", "Severe Density", "Critical Density"];
                const colors = ["text-accent-cyan", "text-accent-emerald", "text-accent-amber", "text-tier-high", "text-accent-red"];

                if (hoveredIndex === 4) {
                  return (
                    <span className="animate-fade-in font-bold">
                      {formatScaleNum(minVal)}+ (
                      <span className={colors[hoveredIndex]}>{labels[hoveredIndex]}</span>)
                    </span>
                  );
                }
                return (
                  <span className="animate-fade-in font-bold">
                    {formatScaleNum(minVal)} – {formatScaleNum(maxVal)} (
                    <span className={colors[hoveredIndex]}>{labels[hoveredIndex]}</span>)
                  </span>
                );
              })()
            )}
          </span>
        </div>

        {/* Continuous Color Bar with Hover Hitboxes */}
        <div className="relative h-3 rounded-full mb-1.5 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-accent-cyan via-accent-emerald via-accent-amber via-accent-red/80 to-accent-red" />

          {/* Transparent Hover Hitboxes */}
          <div className="absolute inset-0 flex">
            {[0, 1, 2, 3, 4].map((idx) => (
              <div
                key={idx}
                className="flex-1 h-full cursor-help hover:bg-white/10 transition-colors"
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
              />
            ))}
          </div>
        </div>

        {/* Scale Ticks and Dynamic Values */}
        <div className="relative flex justify-between text-[9px] text-text-muted font-bold px-3 font-sans">
          <span>0</span>
          <span>{formatScaleNum(Math.round(maxCount * 0.25))}</span>
          <span>{formatScaleNum(Math.round(maxCount * 0.5))}</span>
          <span>{formatScaleNum(Math.round(maxCount * 0.75))}</span>
          <span>{formatScaleNum(maxCount)}</span>
        </div>

        {/* Tick Mark Pipes */}
        <div className="relative flex justify-between px-3.5 text-[7px] text-text-muted/30 leading-none -mt-0.5">
          <span>|</span>
          <span>|</span>
          <span>|</span>
          <span>|</span>
          <span>|</span>
        </div>

        {/* Risk Tiers Labels for accessibility */}
        <div className="flex justify-between mt-3 pt-2.5 border-t border-border-default/40 text-[9px] font-black uppercase font-sans px-3">
          <span className="text-accent-cyan">Low</span>
          <span className="text-accent-emerald">Med</span>
          <span className="text-accent-amber">High</span>
          <span className="text-tier-high" style={{ color: "var(--color-tier-high)" }}>Severe</span>
          <span className="text-accent-red">Critical</span>
        </div>
      </div>
    </div>
  );
}

/* Helper to fly-to a cell */
export function flyToCell(
  lat: number,
  lng: number,
  currentVS: MapViewState
): MapViewState {
  return {
    ...currentVS,
    latitude: lat,
    longitude: lng,
    zoom: 14,
    transitionDuration: 800,
    transitionInterpolator: new FlyToInterpolator(),
  } as MapViewState;
}
