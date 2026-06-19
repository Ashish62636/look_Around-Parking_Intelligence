import type { PriorityQueueItem } from "../types";
import { MapPin, Car, AlertCircle, ChevronRight } from "lucide-react";

interface Props {
  items: PriorityQueueItem[];
  selectedH3: string | null;
  onSelectItem: (item: PriorityQueueItem) => void;
  isLoading: boolean;
}

function getTierClass(tier: string): string {
  const map: Record<string, string> = {
    IMMEDIATE: "tier-immediate",
    HIGH: "tier-high",
    MODERATE: "tier-moderate",
    LOW: "tier-low",
    MINIMAL: "tier-minimal",
  };
  return map[tier] ?? "tier-minimal";
}

function ScoreBars({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-muted w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-surface-elevated overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, var(--color-accent-cyan), var(--color-accent-blue))`,
          }}
        />
      </div>
      <span className="text-xs font-mono text-text-secondary w-9 text-right">
        {pct}%
      </span>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="p-4 border-b border-border-default">
      <div className="animate-shimmer h-4 w-3/4 rounded mb-2" />
      <div className="animate-shimmer h-3 w-1/2 rounded" />
    </div>
  );
}

export function EnforcementQueue({
  items,
  selectedH3,
  onSelectItem,
  isLoading,
}: Props) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-0">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-text-muted">
        <AlertCircle size={32} className="mb-2 opacity-40" />
        <p className="text-sm">No enforcement items found</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col divide-y divide-border-default">
      {items.map((item, idx) => {
        const isSelected = selectedH3 === item.h3_index;

        return (
          <button
            key={item.h3_index}
            id={`enforcement-item-${idx}`}
            onClick={() => onSelectItem(item)}
            className={`
              w-full text-left p-4 transition-all duration-200 cursor-pointer
              hover:bg-surface-elevated
              ${isSelected ? "bg-surface-elevated border-l-2 border-l-accent-cyan" : "border-l-2 border-l-transparent"}
            `}
            style={{ animationDelay: `${idx * 40}ms` }}
          >
            {/* Header row */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-text-muted">
                  #{idx + 1}
                </span>
                <span className={`tier-badge ${getTierClass(item.priority_tier)}`}>
                  {item.priority_tier}
                </span>
              </div>
              <ChevronRight
                size={14}
                className={`text-text-muted transition-transform ${isSelected ? "rotate-90" : ""}`}
              />
            </div>

            {/* Station & violation */}
            <div className="flex items-center gap-1.5 mb-1">
              <MapPin size={12} className="text-accent-cyan shrink-0" />
              <span className="text-sm font-medium text-text-primary truncate">
                {item.police_station}
              </span>
            </div>

            <div className="flex items-center gap-1.5 mb-3">
              <Car size={12} className="text-accent-amber shrink-0" />
              <span className="text-xs text-text-secondary truncate">
                {item.top_violation} · {item.violation_count.toLocaleString()} violations
              </span>
            </div>

            {/* Score bars */}
            <div className="flex flex-col gap-1.5">
              <ScoreBars score={item.priority_score} label="Priority" />
              <ScoreBars score={item.congestion_score} label="Congestion" />
              <ScoreBars score={item.recurrence_score} label="Recurrence" />
            </div>

            {/* Expanded detail for selected */}
            {isSelected && (
              <div className="mt-3 pt-3 border-t border-border-default animate-fade-in">
                <p className="text-xs text-text-secondary mb-2">
                  <span className="font-medium text-text-primary">Action: </span>
                  {item.recommended_action}
                </p>
                <div className="flex flex-wrap gap-2 text-xs text-text-muted">
                  <span>Severity: {item.severity_mean.toFixed(2)}</span>
                  <span>·</span>
                  <span>
                    Hotspot: {item.is_hotspot ? `Rank #${item.hotspot_rank}` : "No"}
                  </span>
                  <span>·</span>
                  <span>Vehicle: {item.top_vehicle}</span>
                </div>
                <p className="mt-2 text-xs font-mono text-text-muted">
                  H3: {item.h3_index}
                </p>
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
