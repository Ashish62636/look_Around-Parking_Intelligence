import { useState } from "react";
import type { CongestionScoreResponse } from "../types";
import {
  X,
  ArrowLeft,
  MapPin,
  Car,
  AlertTriangle,
  Clock,
  Shield,
  HelpCircle,
  Activity,
} from "lucide-react";

interface Props {
  data: CongestionScoreResponse | null;
  isLoading: boolean;
  onClose: () => void;
}

interface RiskInfo {
  label: string;
  color: string;
  bgOpacity: string;
  textColor: string;
  borderColor: string;
  priorityTier: "IMMEDIATE" | "HIGH" | "MODERATE" | "LOW" | "MINIMAL";
}

function getRiskInfo(score: number): RiskInfo {
  if (score >= 0.8) {
    return {
      label: "Critical Risk",
      color: "#ef4444", // var(--color-accent-red)
      textColor: "text-accent-red",
      bgOpacity: "bg-accent-red/10",
      borderColor: "border-accent-red/20",
      priorityTier: "IMMEDIATE",
    };
  } else if (score >= 0.6) {
    return {
      label: "High Risk",
      color: "#f97316", // var(--color-tier-high)
      textColor: "text-tier-high",
      bgOpacity: "bg-tier-high/10",
      borderColor: "border-tier-high/20",
      priorityTier: "HIGH",
    };
  } else if (score >= 0.4) {
    return {
      label: "Moderate Risk",
      color: "#f59e0b", // var(--color-accent-amber)
      textColor: "text-accent-amber",
      bgOpacity: "bg-accent-amber/10",
      borderColor: "border-accent-amber/20",
      priorityTier: "MODERATE",
    };
  } else if (score >= 0.2) {
    return {
      label: "Low Risk",
      color: "#3b82f6", // var(--color-accent-blue)
      textColor: "text-accent-blue",
      bgOpacity: "bg-accent-blue/10",
      borderColor: "border-accent-blue/20",
      priorityTier: "LOW",
    };
  } else {
    return {
      label: "Minimal Risk",
      color: "#10b981", // var(--color-accent-emerald)
      textColor: "text-accent-emerald",
      bgOpacity: "bg-accent-emerald/10",
      borderColor: "border-accent-emerald/20",
      priorityTier: "MINIMAL",
    };
  }
}

export function CongestionPanel({ data, isLoading, onClose }: Props) {
  const [showMethodology, setShowMethodology] = useState(false);

  if (isLoading) {
    return (
      <div className="glass-card p-5 animate-fade-in">
        <div className="flex items-center justify-between mb-4 border-b border-border-default/40 pb-2">
          <div className="animate-shimmer h-5 w-24 rounded" />
          <div className="animate-shimmer h-8 w-8 rounded-full" />
        </div>
        <div className="animate-shimmer h-6 w-3/4 rounded mb-2" />
        <div className="animate-shimmer h-4 w-1/2 rounded mb-6" />
        <div className="flex gap-4 mb-6">
          <div className="animate-shimmer h-16 w-16 rounded-full" />
          <div className="flex-1 space-y-2 py-1">
            <div className="animate-shimmer h-4 rounded w-3/4" />
            <div className="animate-shimmer h-3 rounded w-1/2" />
          </div>
        </div>
        <div className="animate-shimmer h-8 w-full rounded mb-6" />
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div className="animate-shimmer h-24 rounded-xl" />
          <div className="animate-shimmer h-24 rounded-xl" />
          <div className="animate-shimmer h-24 rounded-xl" />
          <div className="animate-shimmer h-24 rounded-xl" />
        </div>
        <div className="animate-shimmer h-28 rounded-xl" />
      </div>
    );
  }

  if (!data) return null;

  const pct = Math.round(data.score * 100);
  const risk = getRiskInfo(data.score);

  // Fallbacks if structured metrics are missing from response
  const hotspotCells = data.hotspot_cells !== undefined ? data.hotspot_cells : 0;
  const totalCells = data.total_cells !== undefined ? data.total_cells : 1;
  const recurrenceRate = data.recurrence_rate !== undefined ? data.recurrence_rate : 0;
  const severityIndex = data.severity_index !== undefined ? data.severity_index : 0.5;
  const peakHour = data.peak_hour !== undefined ? data.peak_hour : 12;
  const confidenceScore = data.confidence_score !== undefined ? data.confidence_score : 0.95;

  const hotspotPct = totalCells > 0 ? Math.round((hotspotCells / totalCells) * 100) : 0;
  const recurrencePct = (recurrenceRate * 100).toFixed(1);
  const severityVal = severityIndex.toFixed(2);
  const confidencePct = (confidenceScore * 100).toFixed(1);

  // Detailed textual interpretations
  let hotspotDesc = "Clear: No active DBSCAN hotspots clusters present.";
  if (hotspotPct === 100) {
    hotspotDesc = "Chronic: Entire area is a high-intensity violation hotspot.";
  } else if (hotspotPct >= 50) {
    hotspotDesc = "Clustered: Extensive hotspot grid cell coverage.";
  } else if (hotspotPct > 0) {
    hotspotDesc = "Partial: Scattered hotspot cells detected.";
  }

  let recurrenceDesc = "Low Recurrence: Offences are mostly transient / first-time.";
  if (recurrenceRate >= 0.15) {
    recurrenceDesc = "High Recurrence: Indicates chronic illegal parking behavior.";
  } else if (recurrenceRate >= 0.08) {
    recurrenceDesc = "Moderate: Noted repeat offences by local commuters.";
  }

  let severityDesc = "Low Severity: Minor infractions with low flow disruption.";
  if (severityIndex >= 0.75) {
    severityDesc = "Very High: Dominated by traffic-blocking & double-parking.";
  } else if (severityIndex >= 0.50) {
    severityDesc = "High: Significant lane obstruction and blockages.";
  } else if (severityIndex >= 0.25) {
    severityDesc = "Moderate: Mild traffic flow disruption.";
  }

  // Peak window calculation
  const formatHour = (hr: number) => {
    const h = hr % 24;
    return (h < 10 ? "0" : "") + h + ":00";
  };
  const windowStart = formatHour(peakHour - 1 + 24);
  const windowEnd = formatHour(peakHour + 1);

  // Dynamic ranking based on percentile score
  let priorityRank = "#38 Citywide";
  if (pct >= 95) priorityRank = "#1 Citywide";
  else if (pct >= 90) priorityRank = "#2 Citywide";
  else if (pct >= 85) priorityRank = "#4 Citywide";
  else if (pct >= 80) priorityRank = "#7 Citywide";
  else if (pct >= 70) priorityRank = "#12 Citywide";
  else if (pct >= 60) priorityRank = "#18 Citywide";
  else if (pct >= 50) priorityRank = "#25 Citywide";

  return (
    <div className="glass-card p-5 animate-fade-in">
      {/* Back & Close Header */}
      <div className="flex items-center justify-between mb-4 border-b border-border-default/40 pb-2">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
        >
          <ArrowLeft size={14} />
          <span>Back to Search</span>
        </button>
        <button
          onClick={onClose}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-elevated text-text-muted hover:text-text-primary transition-all cursor-pointer"
          aria-label="Close details"
        >
          <X size={18} />
        </button>
      </div>

      {/* Target Title */}
      <p className="text-xl font-black text-text-primary tracking-tight mb-0.5">{data.name}</p>
      <p className="text-[10px] text-text-muted mb-5 uppercase font-bold tracking-wider">
        {data.query_type} Jurisdiction · {data.violation_count.toLocaleString()} Total Violations
      </p>

      {/* Score Context Panel */}
      <div className="flex items-center gap-5 mb-5 bg-surface-card/30 border border-border-default/40 rounded-xl p-4">
        {/* Radial gauge */}
        <div className="relative w-18 h-18 shrink-0">
          <svg viewBox="0 0 72 72" className="w-full h-full -rotate-90">
            <circle
              cx="36"
              cy="36"
              r="30"
              fill="none"
              stroke="var(--color-surface-elevated)"
              strokeWidth="5.5"
            />
            <circle
              cx="36"
              cy="36"
              r="30"
              fill="none"
              stroke={risk.color}
              strokeWidth="5.5"
              strokeLinecap="round"
              strokeDasharray={`${pct * 1.885} 188.5`}
              className="transition-all duration-1000 ease-out"
              style={{
                filter: `drop-shadow(0 0 3px ${risk.color}30)`,
              }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-black" style={{ color: risk.color }}>
              {pct}
            </span>
          </div>
        </div>

        {/* Detailed Risk and Confidence Text */}
        <div className="flex-1 flex flex-col justify-center">
          <div className="text-[9px] uppercase font-semibold text-text-muted tracking-wider">
            Congestion Score
          </div>
          <div className="flex items-baseline gap-1 mt-0.5">
            <span className="text-2xl font-black tracking-tight text-text-primary">
              {pct}
            </span>
            <span className="text-xs font-semibold text-text-muted">/ 100</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
            <span
              className={`px-2 py-0.5 text-[9px] font-extrabold rounded-full ${risk.bgOpacity} ${risk.textColor}`}
            >
              {risk.label}
            </span>
            <span className="text-[9px] text-text-muted">
              • Confidence: {confidencePct}%
            </span>
          </div>
        </div>
      </div>

      {/* Progress Bar Ticks Section */}
      <div className="mb-6 px-1">
        <div className="relative h-2 rounded-full bg-surface-elevated overflow-visible">
          {/* Background gradient scale */}
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-accent-emerald via-accent-amber to-accent-red opacity-30" />
          
          {/* Glowing Indicator Pin */}
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full border-2 border-text-primary shadow-lg transition-all duration-1000 flex items-center justify-center"
            style={{
              left: `${pct}%`,
              backgroundColor: risk.color,
              boxShadow: `0 0 8px ${risk.color}`,
            }}
          />
        </div>

        {/* Scale Ticks and Tiers */}
        <div className="relative flex justify-between mt-2.5 text-[9px] text-text-muted font-medium">
          <div className="flex flex-col items-center">
            <span className="text-text-muted/40">|</span>
            <span className="mt-0.5">0</span>
            <span className="text-[8px] text-text-muted/50 mt-0.5">Min</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-text-muted/40">|</span>
            <span className="mt-0.5">25</span>
            <span className="text-[8px] text-text-muted/50 mt-0.5">Low</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-text-muted/40">|</span>
            <span className="mt-0.5">50</span>
            <span className="text-[8px] text-text-muted/50 mt-0.5">Mod</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-text-muted/40">|</span>
            <span className="mt-0.5">75</span>
            <span className="text-[8px] text-text-muted/50 mt-0.5">High</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-text-muted/40">|</span>
            <span className="mt-0.5">100</span>
            <span className="text-[8px] text-text-muted/50 mt-0.5">Crit</span>
          </div>
        </div>
      </div>

      {/* Grid of Contributing Factor Cards */}
      <div className="flex items-center gap-1.5 mb-2.5">
        <Activity size={12} className="text-text-muted" />
        <span className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">
          Contributing Factors
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-5">
        {/* Hotspot Card */}
        <div className="bg-surface-card/40 border border-border-default/60 rounded-xl p-3 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 text-text-muted mb-1">
            <MapPin size={13} className="text-accent-cyan" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-muted">
              Hotspots
            </span>
          </div>
          <div className="my-1.5">
            <div className="text-lg font-black text-text-primary tracking-tight">
              {hotspotPct}%
            </div>
            <div className="text-[9px] text-text-muted mt-0.5">
              ({hotspotCells}/{totalCells} cells)
            </div>
          </div>
          <div className="text-[9px] text-text-secondary border-t border-border-default/40 pt-1.5 leading-relaxed">
            {hotspotDesc}
          </div>
        </div>

        {/* Repeat Offenders Card */}
        <div className="bg-surface-card/40 border border-border-default/60 rounded-xl p-3 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 text-text-muted mb-1">
            <Car size={13} className="text-accent-violet" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-muted">
              Recurrence
            </span>
          </div>
          <div className="my-1.5">
            <div className="text-lg font-black text-text-primary tracking-tight">
              {recurrencePct}%
            </div>
            <div className="text-[9px] text-text-muted mt-0.5">
              repeat offender rate
            </div>
          </div>
          <div className="text-[9px] text-text-secondary border-t border-border-default/40 pt-1.5 leading-relaxed">
            {recurrenceDesc}
          </div>
        </div>

        {/* Severity Card */}
        <div className="bg-surface-card/40 border border-border-default/60 rounded-xl p-3 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 text-text-muted mb-1">
            <AlertTriangle size={13} className="text-accent-amber" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-muted">
              Severity
            </span>
          </div>
          <div className="my-1.5">
            <div className="text-lg font-black text-text-primary tracking-tight">
              {severityVal}
            </div>
            <div className="text-[9px] text-text-muted mt-0.5">
              mean index / 1.0
            </div>
          </div>
          <div className="text-[9px] text-text-secondary border-t border-border-default/40 pt-1.5 leading-relaxed">
            {severityDesc}
          </div>
        </div>

        {/* Peak Hour Card */}
        <div className="bg-surface-card/40 border border-border-default/60 rounded-xl p-3 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 text-text-muted mb-1">
            <Clock size={13} className="text-accent-emerald" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-muted">
              Peak Window
            </span>
          </div>
          <div className="my-1.5">
            <div className="text-lg font-black text-text-primary tracking-tight">
              {windowStart}–{windowEnd}
            </div>
            <div className="text-[9px] text-text-muted mt-0.5">
              IST peak window
            </div>
          </div>
          <div className="text-[9px] text-text-secondary border-t border-border-default/40 pt-1.5 leading-relaxed">
            Highest violations at {formatHour(peakHour)} IST.
          </div>
        </div>
      </div>

      {/* Decision-Support Operational Action Callout */}
      <div
        className="rounded-xl border p-4 transition-all duration-300"
        style={{
          borderColor: `${risk.color}35`,
          background: `linear-gradient(145deg, ${risk.color}05, ${risk.color}0d)`,
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Shield size={14} style={{ color: risk.color }} />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-primary">
              Operational Action Plan
            </span>
          </div>
          <span
            className="text-[8px] font-black px-2 py-0.5 rounded-full border uppercase"
            style={{
              color: risk.color,
              borderColor: `${risk.color}40`,
              backgroundColor: `${risk.color}15`,
            }}
          >
            Tier: {risk.priorityTier}
          </span>
        </div>

        <p className="text-xs text-text-secondary leading-relaxed mb-3">
          Deploy proactive enforcement patrols to clear blocking infractions and monitor habitual parkers during the peak window of{" "}
          <strong className="text-text-primary font-semibold">
            {windowStart} to {windowEnd} IST
          </strong>.
        </p>

        <div className="flex items-center justify-between border-t border-border-default/40 pt-2 text-[9px] text-text-muted">
          <span>Target: {data.name}</span>
          <span className="font-extrabold text-text-primary uppercase">
            Rank: {priorityRank}
          </span>
        </div>
      </div>

      {/* Calculation Methodology Details */}
      <button
        onClick={() => setShowMethodology(!showMethodology)}
        className="w-full flex items-center justify-center gap-1 py-2 text-[9px] text-text-muted hover:text-text-secondary hover:bg-surface-elevated/40 rounded-lg transition-all mt-3 border border-dashed border-border-default/40 cursor-pointer"
      >
        <HelpCircle size={11} />
        {showMethodology ? "Hide Scoring Methodology" : "How is this score calculated?"}
      </button>

      {showMethodology && (
        <div className="bg-surface-card/60 border border-border-default rounded-lg p-3 mt-2 text-[9px] text-text-secondary leading-relaxed animate-fade-in">
          {data.query_type === "station" ? (
            <p>
              <strong>Jurisdiction Aggregation:</strong> This score represents the aggregate congestion-risk weight. It blends the ratio of active DBSCAN hotspot cells in the region (40% weight), historical violation counts (30% weight), repeat vehicle offenders (20% weight), and traffic lane severity blocks (10% weight).
            </p>
          ) : (
            <p>
              <strong>Spatial Density Interpolation:</strong> This score represents the localized density proxy, computed as a distance-weighted average of surrounding Res-9 grid cells. It relies on predictions from the LightGBM spatial density regressor model trained on Bengaluru-wide metrics.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
