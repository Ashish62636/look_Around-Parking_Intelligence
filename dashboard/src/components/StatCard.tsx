import {
  Shield,
  AlertTriangle,
  TrendingUp,
  MapPin,
  type LucideIcon,
} from "lucide-react";

interface Props {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: "shield" | "alert" | "trending" | "pin";
  accentColor?: string;
  delay?: number;
}

const ICON_MAP: Record<Props["icon"], LucideIcon> = {
  shield: Shield,
  alert: AlertTriangle,
  trending: TrendingUp,
  pin: MapPin,
};

export function StatCard({
  label,
  value,
  subtitle,
  icon,
  accentColor = "var(--color-accent-blue)",
  delay = 0,
}: Props) {
  const Icon = ICON_MAP[icon];

  return (
    <div
      className="stat-card animate-fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium tracking-wider uppercase text-text-secondary">
          {label}
        </span>
        <div
          className="flex items-center justify-center w-8 h-8 rounded-lg"
          style={{ backgroundColor: `color-mix(in srgb, ${accentColor} 15%, transparent)` }}
        >
          <Icon size={16} style={{ color: accentColor }} />
        </div>
      </div>

      <p
        className="text-2xl font-bold tracking-tight"
        style={{ color: accentColor }}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>

      {subtitle && (
        <p className="mt-1 text-xs text-text-muted">{subtitle}</p>
      )}
    </div>
  );
}
