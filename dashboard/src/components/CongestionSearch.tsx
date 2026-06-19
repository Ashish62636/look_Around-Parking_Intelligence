import { useState } from "react";
import { Search, Building2, Crosshair } from "lucide-react";

interface Props {
  onSearch: (query: { junction_name: string } | { police_station: string }) => void;
  isLoading: boolean;
}

type SearchMode = "station" | "junction";

export function CongestionSearch({ onSearch, isLoading }: Props) {
  const [mode, setMode] = useState<SearchMode>("station");
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    if (mode === "station") {
      onSearch({ police_station: query.trim() });
    } else {
      onSearch({ junction_name: query.trim() });
    }
  }

  return (
    <div className="glass-card p-4 animate-fade-in">
      <h3 className="text-sm font-semibold text-text-primary mb-3">
        Congestion Lookup
      </h3>

      {/* Mode toggle */}
      <div className="flex rounded-lg overflow-hidden border border-border-default mb-3">
        <button
          type="button"
          onClick={() => setMode("station")}
          className={`
            flex-1 flex items-center justify-center gap-1.5
            px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer
            ${mode === "station" ? "bg-accent-blue/15 text-accent-blue" : "text-text-muted hover:text-text-secondary"}
          `}
        >
          <Building2 size={12} />
          Station
        </button>
        <button
          type="button"
          onClick={() => setMode("junction")}
          className={`
            flex-1 flex items-center justify-center gap-1.5
            px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer
            ${mode === "junction" ? "bg-accent-blue/15 text-accent-blue" : "text-text-muted hover:text-text-secondary"}
          `}
        >
          <Crosshair size={12} />
          Junction
        </button>
      </div>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          id="congestion-search-input"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            mode === "station"
              ? "e.g. Upparpet, Shivajinagar"
              : "e.g. Safina Plaza, KR Market"
          }
          className="
            flex-1 bg-surface-elevated border border-border-default rounded-lg
            px-3 py-2 text-xs text-text-primary placeholder:text-text-muted
            focus:outline-none focus:border-accent-cyan
          "
        />
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="
            flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
            bg-accent-blue/15 text-accent-blue
            hover:bg-accent-blue/25 disabled:opacity-40
            transition-colors cursor-pointer
          "
        >
          <Search size={12} />
          {isLoading ? "…" : "Lookup"}
        </button>
      </form>
    </div>
  );
}
