"use client";

import { useEffect, useRef, useState } from "react";
import {
  loadSearchHistory,
  pushSearchHistory,
  trackSearchSignal,
  clearSearchHistory,
} from "../lib/interests";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export default function SearchBar({ value, onChange, placeholder }: Props) {
  const [focused, setFocused] = useState(false);
  const [history, setHistory] = useState<string[]>(() => loadSearchHistory());
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setFocused(false);
      }
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (q.length >= 2) {
      pushSearchHistory(q);
      trackSearchSignal(q);
      setHistory(loadSearchHistory());
    }
    (document.activeElement as HTMLElement)?.blur();
    setFocused(false);
  };

  const showDropdown = focused && (history.length > 0 || value.length === 0);

  return (
    <div ref={wrapRef} className="relative mb-6">
      <form onSubmit={handleSubmit} className="relative">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8b918e]"
        >
          <circle cx="11" cy="11" r="6" strokeWidth="1.5" />
          <path d="m20 20-4-4" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          value={value}
          onChange={(ev) => onChange(ev.target.value)}
          onFocus={() => {
            setHistory(loadSearchHistory());
            setFocused(true);
          }}
          placeholder={placeholder || "Search events, venues, @accounts..."}
          enterKeyHint="search"
          className="h-11 w-full rounded-xl border border-[#d8d0c1] bg-[#fffdf8] pl-10 pr-10 text-[15px] outline-none transition placeholder:text-sm placeholder:text-[#8b918e] focus:border-[#8a9c94] focus:ring-2 focus:ring-[#173c35]/10"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear search"
            className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full text-lg text-[#66716c] hover:bg-[#f0ede6]"
          >
            ×
          </button>
        )}
      </form>

      {showDropdown && history.length > 0 && (
        <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-xl border border-[#d7d5cd] bg-white p-2 shadow-[0_12px_28px_rgba(23,58,49,0.08)]">
          <div className="mb-1 flex items-center justify-between px-2 py-1">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-[#8b918e]">Recent</span>
            <button
              type="button"
              onClick={() => {
                clearSearchHistory();
                setHistory([]);
              }}
              className="text-[11px] text-[#9a684e] hover:underline"
            >
              Clear
            </button>
          </div>
          {history.slice(0, 8).map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => {
                onChange(q);
                trackSearchSignal(q);
                setFocused(false);
              }}
              className="flex w-full items-center gap-2 rounded-full px-3 py-2 text-left text-sm text-[#354a43] hover:bg-[#f8f3e8]"
            >
              <span className="text-[#8b918e]">↻</span>
              <span className="truncate">{q}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
