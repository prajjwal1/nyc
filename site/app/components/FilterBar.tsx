"use client";

import { useEffect, useRef, useState } from "react";
import { CATEGORY_CONFIG, SOURCE_LABELS } from "../lib/types";
import type { SortMode } from "../hooks/useEvents";
import { loadSearchHistory, pushSearchHistory, clearSearchHistory } from "../lib/interests";

interface FilterBarProps {
  categories: string[];
  setCategories: (c: string[]) => void;
  sources: string[];
  setSources: (s: string[]) => void;
  search: string;
  setSearch: (s: string) => void;
  priceFilter: "all" | "free" | "paid";
  setPriceFilter: (p: "all" | "free" | "paid") => void;
  sortMode: SortMode;
  setSortMode: (s: SortMode) => void;
  allSources: string[];
  allCategories: string[];
  onQuickFilter: (preset: string) => void;
}

export default function FilterBar({
  categories,
  setCategories,
  sources,
  setSources,
  search,
  setSearch,
  priceFilter,
  setPriceFilter,
  sortMode,
  setSortMode,
  allSources,
  allCategories,
  onQuickFilter,
}: FilterBarProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const searchWrapRef = useRef<HTMLDivElement | null>(null);

  // Refresh history whenever input gains focus or after a commit
  const refreshHistory = () => setHistory(loadSearchHistory());

  // Commit on Enter or blur after typing
  const commitSearch = () => {
    if (search && search.trim().length >= 2) {
      pushSearchHistory(search);
    }
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!historyOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (searchWrapRef.current && !searchWrapRef.current.contains(e.target as Node)) {
        setHistoryOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [historyOpen]);

  const toggleCategory = (cat: string) => {
    setCategories(
      categories.includes(cat)
        ? categories.filter((c) => c !== cat)
        : [...categories, cat]
    );
  };

  const toggleSource = (src: string) => {
    setSources(
      sources.includes(src)
        ? sources.filter((s) => s !== src)
        : [...sources, src]
    );
  };

  const hasFilters = categories.length > 0 || sources.length > 0 || search || priceFilter !== "all";

  return (
    <div className="space-y-4">
      <div className="relative" ref={searchWrapRef}>
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          placeholder="Search events, venues, @accounts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => { refreshHistory(); setHistoryOpen(true); }}
          onBlur={() => commitSearch()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              commitSearch();
              setHistoryOpen(false);
              (e.target as HTMLInputElement).blur();
            } else if (e.key === "Escape") {
              setHistoryOpen(false);
            }
          }}
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-gray-200 bg-white"
        />
        {historyOpen && history.length > 0 && (
          <div className="absolute z-30 mt-1 left-0 right-0 bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden">
            <div className="px-3 py-2 flex items-center justify-between text-[10px] uppercase tracking-wide text-gray-400 border-b border-gray-100">
              <span>Recent searches</span>
              <button
                onMouseDown={(e) => {
                  e.preventDefault();
                  clearSearchHistory();
                  setHistory([]);
                }}
                className="hover:text-gray-700 normal-case tracking-normal"
              >
                clear
              </button>
            </div>
            {history.map((q) => (
              <button
                key={q}
                onMouseDown={(e) => {
                  e.preventDefault();
                  setSearch(q);
                  pushSearchHistory(q);
                  setHistoryOpen(false);
                }}
                className="block w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 truncate"
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
      <p className="-mt-3 text-[11px] text-gray-400">
        Try <button onClick={() => setSearch("@theskint")} className="underline hover:text-gray-700">@theskint</button>,{" "}
        <button onClick={() => setSearch("brooklyn bowl")} className="underline hover:text-gray-700">brooklyn bowl</button>,{" "}
        <button onClick={() => setSearch("jazz")} className="underline hover:text-gray-700">jazz</button>
      </p>

      <div className="flex flex-wrap gap-2 text-sm">
        <button
          onClick={() => onQuickFilter("today")}
          className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium transition-colors"
        >
          Today
        </button>
        <button
          onClick={() => onQuickFilter("weekend")}
          className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium transition-colors"
        >
          This Weekend
        </button>
        <button
          onClick={() => onQuickFilter("week")}
          className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium transition-colors"
        >
          This Week
        </button>
        <button
          onClick={() => onQuickFilter("meet-people")}
          className="px-3 py-1.5 rounded-lg bg-fuchsia-100 hover:bg-fuchsia-200 text-fuchsia-800 font-medium transition-colors"
        >
          Meet People
        </button>
        <button
          onClick={() => onQuickFilter("saved")}
          className="px-3 py-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-800 font-medium transition-colors"
        >
          ★ Saved
        </button>
        <button
          onClick={() => onQuickFilter("free")}
          className="px-3 py-1.5 rounded-lg bg-emerald-100 hover:bg-emerald-200 text-emerald-800 font-medium transition-colors"
        >
          Free
        </button>
      </div>

      <div>
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
          Categories
        </p>
        <div className="flex flex-wrap gap-1.5">
          {allCategories.map((cat) => {
            const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
            const active = categories.includes(cat);
            return (
              <button
                key={cat}
                onClick={() => toggleCategory(cat)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  active
                    ? "bg-gray-900 text-white"
                    : `${config.color} hover:opacity-80`
                }`}
              >
                {config.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
          Price
        </p>
        <div className="flex gap-1.5">
          {(["all", "free", "paid"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPriceFilter(p)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                priceFilter === p
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
          Sort by
        </p>
        <div className="flex gap-1.5">
          {(["relevance", "time"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSortMode(s)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                sortMode === s
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s === "relevance" ? "For You" : "Time"}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
          Sources
        </p>
        <div className="flex flex-wrap gap-1.5">
          {allSources.map((src) => {
            const active = sources.includes(src);
            return (
              <button
                key={src}
                onClick={() => toggleSource(src)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  active
                    ? "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {SOURCE_LABELS[src] || src}
              </button>
            );
          })}
        </div>
      </div>

      {hasFilters && (
        <button
          onClick={() => {
            setCategories([]);
            setSources([]);
            setSearch("");
            setPriceFilter("all");
          }}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          Clear all filters
        </button>
      )}
    </div>
  );
}
