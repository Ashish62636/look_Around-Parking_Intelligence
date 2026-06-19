import type { HeatmapFeatureProperties } from "../types";
import { X, MapPin, AlertTriangle, Search } from "lucide-react";

interface Props {
  cell: HeatmapFeatureProperties | null;
  onClose: () => void;
  onLookupCongestion: (stationName: string) => void;
}

export function CellDetail({ cell, onClose, onLookupCongestion }: Props) {
  if (!cell) return null;

  return (
    <div className="glass-card p-4 animate-fade-in min-w-64">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <MapPin size={14} className="text-accent-cyan" />
          <span className="text-sm font-semibold text-text-primary">
            Cell Detail
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-elevated transition-colors cursor-pointer"
          aria-label="Close cell detail"
        >
          <X size={14} className="text-text-muted" />
        </button>
      </div>

      {/* Station */}
      <p className="text-base font-bold text-text-primary mb-1">
        {cell.police_station}
      </p>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="p-2 rounded-lg bg-surface-elevated">
          <p className="text-xs text-text-muted">Violations</p>
          <p className="text-lg font-bold text-accent-cyan">
            {cell.violation_count.toLocaleString()}
          </p>
        </div>
        <div className="p-2 rounded-lg bg-surface-elevated">
          <p className="text-xs text-text-muted">Top Type</p>
          <div className="flex items-center gap-1 mt-1">
            <AlertTriangle size={12} className="text-accent-amber shrink-0" />
            <p className="text-xs font-medium text-accent-amber truncate">
              {cell.top_violation}
            </p>
          </div>
        </div>
      </div>

      {/* Coords */}
      <p className="text-xs font-mono text-text-muted mb-3">
        {cell.lat.toFixed(4)}°N, {cell.lng.toFixed(4)}°E
      </p>

      {/* H3 */}
      <p className="text-xs font-mono text-text-muted mb-3">
        H3: {cell.h3_index}
      </p>

      {/* Congestion lookup CTA */}
      <button
        onClick={() => onLookupCongestion(cell.police_station)}
        className="
          w-full flex items-center justify-center gap-2
          py-2 rounded-lg text-xs font-medium
          bg-accent-cyan/10 text-accent-cyan
          hover:bg-accent-cyan/20 transition-colors cursor-pointer
        "
      >
        <Search size={12} />
        View Congestion Score
      </button>
    </div>
  );
}
