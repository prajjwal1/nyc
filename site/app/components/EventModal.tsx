"use client";

import { useEffect, useState } from "react";
import { Event, CATEGORY_CONFIG, SOURCE_LABELS, HIGHLIGHT_CONFIG } from "../lib/types";
import { trackAccountClick, trackEventOpen, hideEvent, toggleSavedLocal, isSavedLocal } from "../lib/interests";
import { downloadIcs } from "../lib/ics";

interface Props {
  event: Event | null;
  onClose: () => void;
  onAccountClick: (account: string) => void;
}

// Full-screen modal that lets the user evaluate an event without leaving
// the site. Mirrors the IG-post-tap experience: big image, full caption,
// action buttons, and a single explicit "Open original" link for when
// they want to actually buy tickets / see the source.
export default function EventModal({ event, onClose, onAccountClick }: Props) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (event) setSaved(isSavedLocal(event.id));
  }, [event]);

  // Close on ESC
  useEffect(() => {
    if (!event) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    // Lock body scroll
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [event, onClose]);

  if (!event) return null;

  const dateLabel = formatDate(event.date);
  const timeStr = event.startTime
    ? formatTime(event.startTime) +
      (event.endTime ? ` – ${formatTime(event.endTime)}` : "")
    : null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-6 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-2xl max-h-[95vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-white/95 hover:bg-white flex items-center justify-center text-gray-700 shadow-md transition-colors"
          aria-label="Close"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Hero image */}
        {event.imageUrl && (
          <div className="w-full bg-gray-100 max-h-[70vh] overflow-hidden">
            <img
              src={event.imageUrl}
              alt=""
              className="w-full h-auto object-contain max-h-[70vh]"
            />
          </div>
        )}

        <div className="p-5 space-y-4">
          {/* Date pill + highlights */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2.5 py-1 rounded-lg bg-gray-900 text-white text-xs font-semibold">
              {dateLabel}
              {timeStr ? ` · ${timeStr}` : ""}
            </span>
            {(event.highlights || []).slice(0, 4).map((h) => {
              const config = HIGHLIGHT_CONFIG[h];
              if (!config) return null;
              return (
                <span
                  key={h}
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${config.color}`}
                >
                  {config.label}
                </span>
              );
            })}
            {event.price === "free" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                FREE
              </span>
            )}
            {event.price && event.price !== "free" && event.price !== "unknown" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700">
                {event.price}
              </span>
            )}
          </div>

          {/* Title */}
          <h2 className="text-xl font-semibold text-gray-900 leading-tight">
            {event.title}
          </h2>

          {/* Location */}
          {event.location.name && (
            <div className="flex items-start gap-2 text-sm text-gray-700">
              <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <div>
                <div className="font-medium">{event.location.name}</div>
                {event.location.address && (
                  <div className="text-xs text-gray-500">{event.location.address}</div>
                )}
                {event.location.neighborhood && (
                  <div className="text-xs text-gray-500">{event.location.neighborhood}</div>
                )}
              </div>
            </div>
          )}

          {/* Categories */}
          {event.categories.filter((c) => c !== "free" && c !== "other").length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {event.categories
                .filter((c) => c !== "free" && c !== "other")
                .map((cat) => {
                  const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
                  return (
                    <span
                      key={cat}
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${config.color}`}
                    >
                      {config.label}
                    </span>
                  );
                })}
            </div>
          )}

          {/* Description */}
          {event.description && (
            <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
              {event.description}
            </p>
          )}

          {/* Source attribution */}
          <div className="flex items-center gap-2 text-xs text-gray-500 pt-2 border-t border-gray-100">
            {event.instagramAccount ? (
              <button
                onClick={() => {
                  trackAccountClick(event.instagramAccount);
                  onAccountClick(event.instagramAccount!);
                  onClose();
                }}
                className="font-medium text-gray-700 hover:text-gray-900 hover:underline"
              >
                @{event.instagramAccount}
              </button>
            ) : (
              <span className="font-medium text-gray-700">
                {SOURCE_LABELS[event.source] || event.source}
              </span>
            )}
            {event.accountVerified && (
              <span className="text-blue-500" title="Verified">✓</span>
            )}
            {event.likes && event.likes > 30 ? (
              <span>· ❤ {formatCount(event.likes)}</span>
            ) : null}
            {event.contributingSources && event.contributingSources.length >= 2 && (
              <span title="Cross-source verified">
                · seen on {event.contributingSources.length} sources
              </span>
            )}
          </div>

          {/* Action row */}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <a
              href={event.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 transition-colors"
            >
              Open original
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
            <button
              onClick={() => {
                setSaved(toggleSavedLocal(event.id));
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                saved
                  ? "border-amber-300 bg-amber-50 text-amber-800"
                  : "border-gray-200 text-gray-700 hover:bg-gray-50"
              }`}
            >
              <svg className="w-4 h-4" fill={saved ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
              {saved ? "Saved" : "Save"}
            </button>
            <button
              onClick={() => downloadIcs(event)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Add to calendar
            </button>
            <button
              onClick={() => {
                hideEvent(event.id);
                onClose();
              }}
              className="ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-gray-500 hover:bg-gray-50 text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Hide
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return m === 0 ? `${hour} ${ampm}` : `${hour}:${m.toString().padStart(2, "0")} ${ampm}`;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + "k";
  return String(n);
}
