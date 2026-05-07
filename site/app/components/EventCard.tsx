"use client";

import { useState } from "react";
import { Event, CATEGORY_CONFIG, SOURCE_LABELS, HIGHLIGHT_CONFIG } from "../lib/types";
import { trackAccountClick, trackEventOpen, hideEvent, toggleSavedLocal, isSavedLocal } from "../lib/interests";
import { downloadIcs } from "../lib/ics";

interface EventCardProps {
  event: Event;
  variant?: "compact" | "feed" | "grid";
  onAccountClick?: (account: string) => void;
  onHide?: (eventId: string) => void;
  onSelect?: (event: Event) => void;
}

export default function EventCard({ event, variant = "feed", onAccountClick, onHide, onSelect }: EventCardProps) {
  const timeStr = event.startTime
    ? formatTime(event.startTime) +
      (event.endTime ? ` – ${formatTime(event.endTime)}` : "")
    : null;

  if (variant === "compact") {
    return <CompactCard event={event} timeStr={timeStr} />;
  }

  if (variant === "grid") {
    return <GridCard event={event} onSelect={onSelect} />;
  }

  // IG events are inherently visual — when we have a usable image, lead with
  // a large flyer like an IG grid post so the user can scan visually rather
  // than reading metadata.
  if (event.source === "instagram" && event.imageUrl) {
    return <MediaFirstCard event={event} timeStr={timeStr} onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelect} />;
  }

  return <FeedCard event={event} timeStr={timeStr} onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelect} />;
}

function GridCard({ event, onSelect }: { event: Event; onSelect?: (event: Event) => void }) {
  const handleClick = (e: React.MouseEvent) => {
    if (onSelect) {
      e.preventDefault();
      onSelect(event);
    } else {
      trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl);
    }
  };
  const dateLabel = formatDateLabel(event.date);
  const startsSoon = isStartingSoon(event);
  return (
    <a
      href={event.sourceUrl}
      onClick={handleClick}
      target="_blank"
      rel="noopener noreferrer"
      className="block group relative aspect-square rounded-lg overflow-hidden bg-gray-100 hover:opacity-90 transition-opacity"
      title={event.title}
    >
      {event.imageUrl ? (
        <img
          src={event.imageUrl}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center p-2 text-center">
          <span className="text-xs font-medium text-gray-700 line-clamp-4">
            {event.title}
          </span>
        </div>
      )}
      {/* Date pill */}
      <div className="absolute top-1.5 left-1.5 bg-white/95 backdrop-blur rounded px-1.5 py-0.5 text-[10px] font-semibold text-gray-900 shadow-sm">
        {dateLabel}
      </div>
      {/* Starting soon pulse */}
      {startsSoon && (
        <div className="absolute top-1.5 right-1.5 bg-rose-600 text-white rounded px-1.5 py-0.5 text-[10px] font-bold animate-pulse">
          NOW
        </div>
      )}
      {/* Bottom title overlay on hover */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="text-[11px] font-semibold text-white line-clamp-2">
          {event.title}
        </div>
      </div>
    </a>
  );
}

function isStartingSoon(event: Event): boolean {
  if (!event.startTime) return false;
  try {
    const todayStr = new Date().toISOString().split("T")[0];
    if (event.date !== todayStr) return false;
    const [h, m] = event.startTime.split(":").map(Number);
    const start = new Date();
    start.setHours(h, m, 0, 0);
    const diffMs = start.getTime() - new Date().getTime();
    return diffMs > 0 && diffMs < 2.5 * 3600 * 1000; // starts in next 2.5h
  } catch {
    return false;
  }
}

function MediaFirstCard({
  event,
  timeStr,
  onAccountClick,
  onHide,
  onSelect,
}: {
  event: Event;
  timeStr: string | null;
  onAccountClick?: (account: string) => void;
  onHide?: (eventId: string) => void;
  onSelect?: (event: Event) => void;
}) {
  const dateLabel = formatDateLabel(event.date);
  const [saved, setSaved] = useState(() => isSavedLocal(event.id));
  const handleOpen = (e: React.MouseEvent) => {
    if (onSelect) {
      e.preventDefault();
      onSelect(event);
    } else {
      trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl);
    }
  };
  const handleHide = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    hideEvent(event.id);
    onHide?.(event.id);
  };
  const handleSave = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSaved(toggleSavedLocal(event.id));
  };
  return (
    <a
      href={event.sourceUrl}
      onClick={handleOpen}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white rounded-xl border border-gray-200 hover:border-gray-300 hover:shadow-md transition-all overflow-hidden"
    >
      <div className="relative aspect-square bg-gray-100">
        <img
          src={event.imageUrl!}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
        {/* Date badge top-left */}
        <div className="absolute top-2 left-2 bg-white/95 backdrop-blur rounded-lg px-2 py-1 text-xs font-semibold text-gray-900 shadow-sm">
          {dateLabel}
        </div>
        {/* Likes badge top-right when meaningful */}
        {event.likes && event.likes > 50 ? (
          <div className="absolute top-2 right-2 bg-black/60 text-white rounded-lg px-2 py-1 text-xs font-medium backdrop-blur">
            ❤ {formatCount(event.likes)}
          </div>
        ) : null}
        {/* Highlight badges bottom-left */}
        {(event.highlights || []).length > 0 && (
          <div className="absolute bottom-2 left-2 right-2 flex flex-wrap gap-1">
            {(event.highlights || [])
              .filter((h) => h !== "free")
              .slice(0, 3)
              .map((h) => {
                const config = HIGHLIGHT_CONFIG[h];
                if (!config) return null;
                return (
                  <span
                    key={h}
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${config.color}`}
                  >
                    {config.label}
                  </span>
                );
              })}
          </div>
        )}
      </div>
      <div className="p-3">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">
          {event.title}
        </h3>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
          {timeStr && (
            <span className="flex items-center gap-1">
              <ClockIcon />
              {timeStr}
            </span>
          )}
          {event.location.name && (
            <span className="flex items-center gap-1 truncate">
              <PinIcon />
              <span className="truncate">{event.location.name}</span>
            </span>
          )}
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] text-gray-500">
          {event.instagramAccount ? (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                trackAccountClick(event.instagramAccount);
                onAccountClick?.(event.instagramAccount!);
              }}
              className="hover:text-gray-900 hover:underline font-medium"
              title={`See more from @${event.instagramAccount}`}
            >
              @{event.instagramAccount}
              {event.accountVerified && (
                <span className="text-blue-500 ml-1" title="Verified">✓</span>
              )}
            </button>
          ) : (
            <span>{SOURCE_LABELS[event.source] || event.source}</span>
          )}
          <div className="flex items-center gap-2">
            {event.price === "free" && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                FREE
              </span>
            )}
            <button
              onClick={handleSave}
              className={`transition-colors ${saved ? "text-amber-500" : "text-gray-400 hover:text-amber-500"}`}
              title={saved ? "Unsave" : "Save"}
              aria-label={saved ? "Unsave" : "Save"}
            >
              <StarIcon filled={saved} />
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                downloadIcs(event);
              }}
              className="text-gray-400 hover:text-gray-700 transition-colors"
              title="Add to calendar"
              aria-label="Add to calendar"
            >
              <CalendarIcon />
            </button>
            <button
              onClick={handleHide}
              className="text-gray-300 hover:text-rose-500 transition-colors"
              title="Hide this event"
              aria-label="Hide"
            >
              <HideIcon />
            </button>
          </div>
        </div>
      </div>
    </a>
  );
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg className="w-4 h-4" fill={filled ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  );
}

function HideIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

function formatDateLabel(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function FeedCard({
  event,
  timeStr,
  onAccountClick,
  onHide,
  onSelect,
}: {
  event: Event;
  timeStr: string | null;
  onAccountClick?: (account: string) => void;
  onHide?: (eventId: string) => void;
  onSelect?: (event: Event) => void;
}) {
  const [savedF, setSavedF] = useState(() => isSavedLocal(event.id));
  const handleCardClick = (e: React.MouseEvent) => {
    if (onSelect) {
      e.preventDefault();
      onSelect(event);
    } else {
      trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl);
    }
  };
  const handleHide = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    hideEvent(event.id);
    onHide?.(event.id);
  };
  const handleSaveF = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSavedF(toggleSavedLocal(event.id));
  };
  // Show description only if it's high-signal (not just a fragment of a larger caption)
  const desc = event.description?.trim();
  const showDesc =
    desc && desc.length > 30 && desc.length < 300 &&
    !desc.toLowerCase().startsWith("link in bio") &&
    !desc.toLowerCase().startsWith("photo by");

  return (
    <a
      href={event.sourceUrl}
      onClick={handleCardClick}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white rounded-xl border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all overflow-hidden"
    >
      <div className="flex gap-3 p-3">
        {event.imageUrl && (
          <div className="shrink-0 w-24 h-24 rounded-lg overflow-hidden bg-gray-100">
            <img
              src={event.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">
            {event.title}
          </h3>

          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
            {timeStr && (
              <span className="flex items-center gap-1">
                <ClockIcon />
                {timeStr}
              </span>
            )}
            {event.location.name && (
              <span className="flex items-center gap-1 truncate">
                <PinIcon />
                <span className="truncate">{event.location.name}</span>
                {event.location.neighborhood && (
                  <span className="text-gray-400 shrink-0">· {event.location.neighborhood}</span>
                )}
              </span>
            )}
          </div>

          {showDesc && (
            <p className="mt-1.5 text-xs text-gray-600 line-clamp-2 leading-relaxed">
              {desc}
            </p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            {/* Highlight badges first — most important signals */}
            {(event.highlights || [])
              .filter((h) => h !== "free")  // free shown as category below
              .slice(0, 3)
              .map((h) => {
                const config = HIGHLIGHT_CONFIG[h];
                if (!config) return null;
                return (
                  <span
                    key={h}
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${config.color}`}
                  >
                    {config.label}
                  </span>
                );
              })}
            {event.price === "free" && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                FREE
              </span>
            )}
            {event.categories
              .filter((c) => c !== "free" && c !== "other")
              .slice(0, 2)
              .map((cat) => {
                const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
                return (
                  <span
                    key={cat}
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${config.color}`}
                  >
                    {config.label}
                  </span>
                );
              })}
            <span className="text-[10px] text-gray-400 ml-auto uppercase tracking-wide flex items-center gap-1">
              {event.likes && event.likes > 30 ? (
                <span title="Likes" className="normal-case tracking-normal">
                  ❤ {formatCount(event.likes)}
                </span>
              ) : null}
              {event.instagramAccount ? (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    trackAccountClick(event.instagramAccount);
                onAccountClick?.(event.instagramAccount!);
                  }}
                  className="hover:text-gray-700 hover:underline focus:outline-none"
                  title={`See more from @${event.instagramAccount}`}
                >
                  @{event.instagramAccount}
                </button>
              ) : (
                <span>{SOURCE_LABELS[event.source] || event.source}</span>
              )}
              {event.accountVerified && (
                <span className="text-blue-500" title="Verified">✓</span>
              )}
              <button
                onClick={handleSaveF}
                className={`transition-colors ${savedF ? "text-amber-500" : "text-gray-400 hover:text-amber-500"}`}
                title={savedF ? "Unsave" : "Save"}
                aria-label={savedF ? "Unsave" : "Save"}
              >
                <StarIcon filled={savedF} />
              </button>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  downloadIcs(event);
                }}
                className="text-gray-400 hover:text-gray-700 transition-colors"
                title="Add to calendar"
                aria-label="Add to calendar"
              >
                <CalendarIcon />
              </button>
              <button
                onClick={handleHide}
                className="text-gray-300 hover:text-rose-500 transition-colors"
                title="Hide this event"
                aria-label="Hide"
              >
                <HideIcon />
              </button>
            </span>
          </div>
        </div>
      </div>
    </a>
  );
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + "k";
  return String(n);
}

function CompactCard({ event, timeStr }: { event: Event; timeStr: string | null }) {
  return (
    <a
      href={event.sourceUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-all"
    >
      <div className="flex gap-4">
        {event.imageUrl && (
          <div className="shrink-0 w-16 h-16 rounded-lg overflow-hidden bg-gray-100">
            <img
              src={event.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 line-clamp-2">{event.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
            {timeStr && (
              <span className="flex items-center gap-1">
                <ClockIcon />
                {timeStr}
              </span>
            )}
            {event.location.name && (
              <span className="flex items-center gap-1 truncate">
                <PinIcon />
                {event.location.name}
              </span>
            )}
            <span className="text-xs text-gray-400 ml-auto">
              {SOURCE_LABELS[event.source] || event.source}
            </span>
          </div>
        </div>
      </div>
    </a>
  );
}

function formatTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return m === 0
    ? `${hour} ${ampm}`
    : `${hour}:${m.toString().padStart(2, "0")} ${ampm}`;
}

function ClockIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  );
}
