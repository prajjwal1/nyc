"use client";

import { useState } from "react";

interface HeaderProps {
  totalEvents: number;
  thisWeekCount?: number;
  lastUpdated?: string;
  newSinceLastVisit?: number;
}

export default function Header({
  totalEvents,
  thisWeekCount,
  lastUpdated,
  newSinceLastVisit,
}: HeaderProps) {
  const [copied, setCopied] = useState(false);
  const handleShare = async () => {
    if (typeof window === "undefined") return;
    const url = window.location.href;
    try {
      const nav = navigator as Navigator & { share?: (data: ShareData) => Promise<void> };
      if (nav.share) {
        await nav.share({ title: "NYC Events", url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };
  const updatedStr = lastUpdated
    ? new Date(lastUpdated).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;
  // Iter 105: surface staleness as a color cue so the user knows when
  // they're looking at old data (the IG-session-refresh bottleneck has
  // left feeds stale before). gray = fresh (<8h), amber = stale (8-48h),
  // red = very stale (>48h).
  const ageHours = lastUpdated
    ? (Date.now() - new Date(lastUpdated).getTime()) / 3_600_000
    : null;
  const updatedColorClass =
    ageHours == null
      ? "text-gray-400"
      : ageHours < 8
      ? "text-gray-400"
      : ageHours < 48
      ? "text-amber-600"
      : "text-rose-600 font-semibold";
  const updatedTooltip =
    ageHours == null
      ? undefined
      : ageHours < 8
      ? `${ageHours.toFixed(1)}h ago`
      : ageHours < 48
      ? `${ageHours.toFixed(1)}h ago — feed is getting stale; the scraper may be blocked`
      : `${(ageHours / 24).toFixed(1)} days ago — the scraper hasn't run successfully. IG session likely expired.`;

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">NYC Events</h1>
            <p className="text-sm text-gray-500">
              {thisWeekCount !== undefined && thisWeekCount > 0 ? (
                <>
                  <span className="font-semibold text-gray-700">{thisWeekCount}</span>
                  {" "}this week
                  <span className="text-gray-400"> · {totalEvents} total</span>
                </>
              ) : (
                <>{totalEvents} events from across the city</>
              )}
              {newSinceLastVisit && newSinceLastVisit > 0 ? (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 text-[11px] font-semibold">
                  ✨ {newSinceLastVisit} new since you last visited
                </span>
              ) : null}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {updatedStr && (
              <p className={`text-xs ${updatedColorClass}`} title={updatedTooltip}>
                Updated {updatedStr}
                {ageHours != null && ageHours >= 48 && (
                  <span className="ml-1">⚠</span>
                )}
              </p>
            )}
            <button
              onClick={handleShare}
              className="text-xs text-gray-500 hover:text-gray-900 flex items-center gap-1"
              title="Copy link to current view"
            >
              {copied ? (
                <span className="text-emerald-600">Copied!</span>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                  </svg>
                  Share view
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
