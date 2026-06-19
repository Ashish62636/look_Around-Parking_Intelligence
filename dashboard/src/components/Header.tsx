import { Radar, ExternalLink } from "lucide-react";

interface Props {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const TABS = [
  { id: "heatmap", label: "Heatmap" },
  { id: "enforcement", label: "Enforcement" },
  { id: "congestion", label: "Congestion" },
];

export function Header({ activeTab, onTabChange }: Props) {
  return (
    <header className="flex items-center justify-between h-14 px-5 border-b border-border-default bg-surface-secondary/80 backdrop-blur-md z-50">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent-cyan/10">
          <Radar size={18} className="text-accent-cyan" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-text-primary tracking-tight">
            look_Around
          </h1>
          <p className="text-[10px] text-text-muted -mt-0.5">
            Bengaluru Parking Intelligence
          </p>
        </div>
      </div>

      {/* Tabs */}
      <nav className="flex items-center gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            className={`
              px-4 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer
              ${
                activeTab === tab.id
                  ? "bg-accent-cyan/15 text-accent-cyan"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated"
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Right side */}
      <a
        href="https://github.com/Ashish62636/look_Around-Parking_Intelligence"
        target="_blank"
        rel="noopener noreferrer"
        className="p-2 rounded-lg hover:bg-surface-elevated transition-colors"
        aria-label="GitHub repository"
      >
        <ExternalLink size={16} className="text-text-muted" />
      </a>
    </header>
  );
}
