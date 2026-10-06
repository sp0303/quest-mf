import React, { useEffect, useRef, useState } from "react";
import { Loader2, Search, X } from "lucide-react";

export interface ScreenerSearchProps {
  /** Committed query (from the URL). */
  value: string;
  /** Called with the debounced query. */
  onSearch: (q: string) => void;
  isSearching?: boolean;
  resultCount?: number;
  debounceMs?: number;
}

export const ScreenerSearch: React.FC<ScreenerSearchProps> = ({
  value,
  onSearch,
  isSearching = false,
  resultCount,
  debounceMs = 300,
}) => {
  const [text, setText] = useState(value);
  const committed = useRef(value);

  // Follow external URL changes (back/forward, clear from elsewhere).
  useEffect(() => {
    if (value !== committed.current) {
      committed.current = value;
      setText(value);
    }
  }, [value]);

  useEffect(() => {
    if (text.trim() === committed.current) return;
    const id = window.setTimeout(() => {
      committed.current = text.trim();
      onSearch(text.trim());
    }, debounceMs);
    return () => window.clearTimeout(id);
  }, [text, debounceMs, onSearch]);

  const clear = () => {
    setText("");
    committed.current = "";
    onSearch("");
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2">
      <div className="relative flex-1 max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-mid-gray" aria-hidden="true" />
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && clear()}
          placeholder="Search funds or AMCs — e.g. “axis small”, “hdfc flexi”"
          aria-label="Search funds by name or AMC"
          className="w-full h-10 pl-9 pr-9 rounded-2xl border border-hairline bg-paper text-sm text-ink placeholder:text-mid-gray focus:outline-none focus:ring-2 focus:ring-ink/20"
        />
        {isSearching ? (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-mid-gray" aria-hidden="true" />
        ) : (
          text && (
            <button
              type="button"
              onClick={clear}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-2xl text-mid-gray hover:text-ink"
            >
              <X className="w-4 h-4" />
            </button>
          )
        )}
      </div>
      {value && resultCount !== undefined && (
        <span className="text-xs text-mid-gray" role="status" aria-live="polite">
          {resultCount} {resultCount === 1 ? "fund" : "funds"} match “{value}”
        </span>
      )}
    </div>
  );
};
