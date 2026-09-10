"use client";

import { useState, useEffect } from "react";

interface HeaderProps {
  totalEvents: number;
  title?: string;
  thisWeekCount?: number;
  lastUpdated?: string;
  newSinceLastVisit?: number;
}

export default function Header({
  totalEvents,
  title = "What's happening in NYC",
  thisWeekCount,
  lastUpdated,
  newSinceLastVisit,
}: HeaderProps) {
  const [copied, setCopied] = useState(false);
  const [currentTime, setCurrentTime] = useState<number | null>(null);
  useEffect(() => {
    queueMicrotask(() => setCurrentTime(Date.now()));
  }, []);
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
  // left event data stale before). With quarter-hour CI monitoring, data is
  // fresh under an hour, delayed from one to two hours, and stale after two.
  const ageHours = lastUpdated && currentTime != null
    ? (currentTime - new Date(lastUpdated).getTime()) / 3_600_000
    : null;
  const updatedColorClass =
    ageHours == null
      ? "text-gray-400"
      : ageHours < 1
      ? "text-gray-400"
      : ageHours < 2
      ? "text-amber-600"
      : "text-rose-600 font-semibold";
  const updatedTooltip =
    ageHours == null
      ? undefined
      : ageHours < 1
      ? `${ageHours.toFixed(1)}h ago`
      : ageHours < 2
      ? `${ageHours.toFixed(1)}h ago — event data is getting stale; the scraper may be blocked`
      : `${ageHours.toFixed(1)}h ago — automated refresh or deployment is delayed.`;

  return (
    <header>
      <div className="mx-auto max-w-6xl px-4 pb-7 pt-10 sm:px-6 sm:pb-9 sm:pt-14">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h1 className="max-w-3xl font-editorial text-[42px] leading-[0.98] tracking-[-0.035em] text-[#173c35] sm:text-[56px]">
              {title}
            </h1>
            <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px] font-medium text-[#6b7570]">
              {thisWeekCount !== undefined && thisWeekCount > 0 ? (
                <>
                  <span>
                    <span className="font-semibold text-[#173c35]">{thisWeekCount}</span> this week
                    <span className="text-[#a8a59d]"> · {totalEvents} total</span>
                  </span>
                </>
              ) : (
                <span>{totalEvents} events from across the city</span>
              )}
              {updatedStr && (
                <span className={`text-[10px] uppercase tracking-[0.08em] ${updatedColorClass}`} title={updatedTooltip}>
                  Updated {updatedStr}
                  {ageHours != null && ageHours >= 2 && <span className="ml-1">⚠ stale</span>}
                </span>
              )}
            </div>
            {newSinceLastVisit && newSinceLastVisit > 0 ? (
              <div className="mt-3 flex items-center gap-1.5 text-[11px] font-medium text-[#31554c]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#ad5b3d]" aria-hidden="true" />
                <span>
                  {newSinceLastVisit} new since you last visited
                </span>
              </div>
            ) : null}
          </div>
          <div className="flex items-center gap-2 sm:justify-end">
            <button
              onClick={handleShare}
              className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[#d9d7d0] bg-[#fbfaf7] px-4 text-xs font-semibold text-[#53625d] shadow-[0_1px_0_rgba(23,60,53,0.04)] transition hover:-translate-y-0.5 hover:border-[#aebbb5] hover:text-[#173c35] hover:shadow-sm"
              title="Copy link to current view"
            >
              {copied ? (
                <span className="text-emerald-700">Copied!</span>
              ) : (
                <>
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                  </svg>
                  Share
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
