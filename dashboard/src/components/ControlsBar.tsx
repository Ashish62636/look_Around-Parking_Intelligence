import { Layers, Filter } from "lucide-react";
import type { HeatmapResolution } from "../types";

interface Props {
  resolution: HeatmapResolution;
  onResolutionChange: (res: HeatmapResolution) => void;
  tierFilter: string;
  onTierFilterChange: (tier: string) => void;
  activeTab: string;
}

const TIERS = ["ALL", "IMMEDIATE", "HIGH", "MODERATE", "LOW", "MINIMAL"];

export function ControlsBar({
  resolution,
  onResolutionChange,
  tierFilter,
  onTierFilterChange,
  activeTab,
}: Props) {
  return (
    <div className="flex items-center gap-4 px-5 py-2.5 border-b border-border-default bg-surface-secondary/60 backdrop-blur-sm">
      {/* Resolution toggle */}
      <div className="flex items-center gap-2">
        <Layers size={14} className="text-text-muted" />
        <span className="text-xs text-text-secondary">Resolution:</span>
        <div className="flex rounded-lg overflow-hidden border border-border-default">
          {([7, 9] as HeatmapResolution[]).map((res) => (
            <button
              key={res}
              id={`res-toggle-${res}`}
              onClick={() => onResolutionChange(res)}
              className={`
                px-3 py-1 text-xs font-medium transition-colors cursor-pointer
                ${
                  resolution === res
                    ? "bg-accent-cyan/15 text-accent-cyan"
                    : "text-text-muted hover:text-text-secondary hover:bg-surface-elevated"
                }
              `}
            >
              {res === 7 ? "City (R7)" : "Street (R9)"}
            </button>
          ))}
        </div>
      </div>

      {/* Tier filter — only on enforcement tab */}
      {activeTab === "enforcement" && (
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-text-muted" />
          <span className="text-xs text-text-secondary">Tier:</span>
          <select
            id="tier-filter"
            value={tierFilter}
            onChange={(e) => onTierFilterChange(e.target.value)}
            className="
              bg-surface-card border border-border-default rounded-lg
              px-3 py-1 text-xs text-text-primary
              focus:outline-none focus:border-accent-cyan
              cursor-pointer
            "
          >
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t === "ALL" ? "All Tiers" : t}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
