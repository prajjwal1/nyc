"use client";

import { useState } from "react";

interface HeaderProps {
  totalEvents: number;
  lastUpdated?: string;
  newSinceLastVisit?: number;
  igCaptureCount?: number;
  igEphemeralCount?: number;
}

export default function Header({
  totalEvents,
  lastUpdated,
  newSinceLastVisit,
  igCaptureCount,
  igEphemeralCount,
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

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">NYC Events</h1>
            <p className="text-sm text-gray-500">
              {totalEvents} events from across the city
              {newSinceLastVisit && newSinceLastVisit > 0 ? (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 text-[11px] font-semibold">
                  ✨ {newSinceLastVisit} new since you last visited
                </span>
              ) : null}
            </p>
            {igCaptureCount !== undefined && igCaptureCount > 0 && (
              <p className="mt-1 text-xs text-gray-500">
                <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-fuchsia-50 text-fuchsia-800 font-medium">
                  📲 {igCaptureCount} from Instagram
                </span>
                {igEphemeralCount !== undefined && igEphemeralCount > 0 && (
                  <span className="ml-2 text-gray-400">
                    ({igEphemeralCount} from stories/highlights you'd otherwise have to scroll to see)
                  </span>
                )}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {updatedStr && (
              <p className="text-xs text-gray-400">Updated {updatedStr}</p>
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
