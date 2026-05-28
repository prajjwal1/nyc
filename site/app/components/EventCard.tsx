"use client";

import { useState } from "react";
import { Event, CATEGORY_CONFIG, SOURCE_LABELS, HIGHLIGHT_CONFIG } from "../lib/types";
import { trackAccountClick, trackEventOpen, hideEvent, toggleSavedLocal, isSavedLocal, isEventOpened } from "../lib/interests";
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
      trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl, event.startTime, event.date);
    }
  };
  const dateLabel = formatDateLabel(event.date);
  const startsSoon = isStartingSoon(event);
  const opened = isEventOpened(event.id);
  return (
    <a
      href={event.sourceUrl}
      onClick={handleClick}
      target="_blank"
      rel="noopener noreferrer"
      className={`block group relative aspect-square rounded-lg overflow-hidden bg-gray-100 hover:opacity-90 transition-opacity ${
        opened ? "opacity-60" : ""
      }`}
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
        // No image — keep the cell text-only with the title prominently
        // displayed on a clean neutral surface (no decorative placeholder).
        <div className="w-full h-full bg-white flex items-center justify-center p-3 text-center">
          <span className="text-sm font-semibold text-gray-900 line-clamp-5 leading-snug">
            {event.title}
          </span>
        </div>
      )}
      {/* Date pill — or "Spot" for evergreen */}
      <div className={`absolute top-1.5 left-1.5 backdrop-blur rounded px-1.5 py-0.5 text-[10px] font-semibold shadow-sm ${
        event.evergreen
          ? "bg-teal-100/95 text-teal-900"
          : "bg-white/95 text-gray-900"
      }`}>
        {event.evergreen ? "🗺 Spot" : dateLabel}
      </div>
      {/* Multi-image badge (IG-style stack icon) */}
      {event.extraImages && event.extraImages.length > 0 && (
        <div className="absolute top-1.5 right-1.5 bg-black/60 text-white rounded px-1.5 py-0.5 text-[9px] font-bold backdrop-blur flex items-center gap-1">
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 11H5m14-7H5m14 14H5" />
          </svg>
          {1 + event.extraImages.length}
        </div>
      )}
      {/* Starting soon pulse */}
      {startsSoon && (
        <div className="absolute top-1.5 right-1.5 bg-rose-600 text-white rounded px-1.5 py-0.5 text-[10px] font-bold animate-pulse">
          NOW
        </div>
      )}
      {/* Conviction glyph — sky ★ for follow, amber ♥ for affinity */}
      {(event.userFollowing || event.userAffinity) && (
        <div
          className={`absolute bottom-1.5 left-1.5 rounded-full w-5 h-5 flex items-center justify-center text-[11px] font-bold backdrop-blur ${
            event.userFollowing ? "bg-sky-500/95 text-white" : "bg-amber-500/95 text-white"
          }`}
          title={
            event.userFollowing
              ? `Because you follow @${event.account || event.instagramAccount || ""}`
              : `From accounts you save from`
          }
        >
          {event.userFollowing ? "★" : "♥"}
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
      trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl, event.startTime, event.date);
    }
  };
  const handleHide = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    hideEvent(event.id, {
      account: event.instagramAccount,
      categories: event.categories,
      sourceUrl: event.sourceUrl,
    });
    onHide?.(event.id);
  };
  const handleSave = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSaved(toggleSavedLocal(event.id, { account: event.instagramAccount, categories: event.categories, sourceUrl: event.sourceUrl, stub: { id: event.id, title: event.title, date: event.date, sourceUrl: event.sourceUrl, imageUrl: event.imageUrl, instagramAccount: event.instagramAccount, accountVerified: event.accountVerified, startTime: event.startTime, locationName: event.location?.name } }));
  };
  const opened = isEventOpened(event.id);
  const convictionFollow = !!event.userFollowing;
  const convictionAffinity = !convictionFollow && !!event.userAffinity;
  const convictionAccount = event.account || event.instagramAccount || "";
  const cardChrome = convictionFollow
    ? "ring-1 ring-sky-300 shadow-[inset_3px_0_0_0_#0ea5e9]"
    : convictionAffinity
    ? "ring-1 ring-amber-300 shadow-[inset_3px_0_0_0_#f59e0b]"
    : "border border-gray-200 hover:border-gray-300";
  return (
    <a
      href={event.sourceUrl}
      onClick={handleOpen}
      target="_blank"
      rel="noopener noreferrer"
      className={`block bg-white rounded-xl ${cardChrome} hover:shadow-md transition-all overflow-hidden ${
        opened ? "opacity-60" : ""
      }`}
    >
      {(convictionFollow || convictionAffinity) && convictionAccount && (
        <div
          className={`px-3 py-1 text-[11px] font-semibold flex items-center gap-1 ${
            convictionFollow ? "bg-sky-50 text-sky-800" : "bg-amber-50 text-amber-800"
          }`}
        >
          <span>{convictionFollow ? "Because you follow" : "From accounts you save from"}</span>
          <span className="font-bold">@{convictionAccount}</span>
        </div>
      )}
      <div className="relative aspect-[4/3] sm:aspect-[16/10] max-h-72 bg-gray-100 overflow-hidden">
        <img
          src={event.imageUrl!}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
        {/* Date badge top-left — or "Spot" pill for evergreen recs */}
        <div className={`absolute top-2 left-2 backdrop-blur rounded-lg px-2 py-1 text-xs font-semibold shadow-sm ${
          event.evergreen
            ? "bg-teal-100/95 text-teal-900"
            : "bg-white/95 text-gray-900"
        }`}>
          {event.evergreen ? "🗺 Spot" : dateLabel}
        </div>
        {/* Likes badge top-right when meaningful */}
        {event.likes && event.likes > 50 ? (
          <div className="absolute top-2 right-2 bg-black/60 text-white rounded-lg px-2 py-1 text-xs font-medium backdrop-blur">
            ❤ {formatCount(event.likes)}
          </div>
        ) : null}
        {/* Highlight badges bottom-left — follow/affinity moved to card-level ribbon (U1) */}
        {(event.highlights || []).length > 0 && (
          <div className="absolute bottom-2 left-2 right-2 flex flex-wrap gap-1">
            {(event.highlights || [])
              .filter((h) => h !== "free" && h !== "following" && h !== "affinity")
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
        {/* Recommendation provenance: when this account has been @-mentioned
            in event posts by accounts the user saves from, surface that. */}
        {event.affinityComentionSources && event.affinityComentionSources.length > 0 && (
          <div className="mt-1.5 text-[10px] text-fuchsia-700 flex items-center gap-1">
            <span>✨ recommended by</span>
            {event.affinityComentionSources.slice(0, 2).map((src, i) => (
              <button
                key={src}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onAccountClick?.(src);
                }}
                className="font-medium hover:underline"
              >
                @{src}{i < Math.min(1, event.affinityComentionSources!.length - 1) ? "," : ""}
              </button>
            ))}
            {event.affinityComentionSources.length > 2 && (
              <span className="text-gray-400">+{event.affinityComentionSources.length - 2}</span>
            )}
          </div>
        )}
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
      trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl, event.startTime, event.date);
    }
  };
  const handleHide = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    hideEvent(event.id, {
      account: event.instagramAccount,
      categories: event.categories,
      sourceUrl: event.sourceUrl,
    });
    onHide?.(event.id);
  };
  const handleSaveF = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setSavedF(toggleSavedLocal(event.id, { account: event.instagramAccount, categories: event.categories, sourceUrl: event.sourceUrl, stub: { id: event.id, title: event.title, date: event.date, sourceUrl: event.sourceUrl, imageUrl: event.imageUrl, instagramAccount: event.instagramAccount, accountVerified: event.accountVerified, startTime: event.startTime, locationName: event.location?.name } }));
  };
  // Show description only if it's high-signal (not just a fragment of a larger caption)
  const desc = event.description?.trim();
  const showDesc =
    desc && desc.length > 30 && desc.length < 300 &&
    !desc.toLowerCase().startsWith("link in bio") &&
    !desc.toLowerCase().startsWith("photo by");

  const openedFeed = isEventOpened(event.id);
  const convictionFollow = !!event.userFollowing;
  const convictionAffinity = !convictionFollow && !!event.userAffinity;
  const convictionAccount = event.account || event.instagramAccount || "";
  const feedChrome = convictionFollow
    ? "ring-1 ring-sky-300 shadow-[inset_3px_0_0_0_#0ea5e9]"
    : convictionAffinity
    ? "ring-1 ring-amber-300 shadow-[inset_3px_0_0_0_#f59e0b]"
    : "border border-gray-200 hover:border-gray-300";
  return (
    <a
      href={event.sourceUrl}
      onClick={handleCardClick}
      target="_blank"
      rel="noopener noreferrer"
      className={`block bg-white rounded-xl ${feedChrome} hover:shadow-sm transition-all overflow-hidden ${
        openedFeed ? "opacity-60" : ""
      }`}
    >
      {(convictionFollow || convictionAffinity) && convictionAccount && (
        <div
          className={`px-3 py-1 text-[11px] font-semibold flex items-center gap-1 ${
            convictionFollow ? "bg-sky-50 text-sky-800" : "bg-amber-50 text-amber-800"
          }`}
        >
          <span>{convictionFollow ? "Because you follow" : "From accounts you save from"}</span>
          <span className="font-bold">@{convictionAccount}</span>
        </div>
      )}
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
            {event.location.name ? (
              <span className="flex items-center gap-1 truncate">
                <PinIcon />
                <span className="truncate">{event.location.name}</span>
                {event.location.neighborhood && (
                  <span className="text-gray-400 shrink-0">· {event.location.neighborhood}</span>
                )}
              </span>
            ) : event.instagramAccount && !event.location.neighborhood ? (
              <span className="flex items-center gap-1 truncate text-gray-400">
                <PinIcon />
                <span className="truncate italic">location in caption</span>
              </span>
            ) : null}
          </div>

          {showDesc && (
            <p className="mt-1.5 text-xs text-gray-600 line-clamp-2 leading-relaxed">
              {desc}
            </p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            {/* Highlight badges first — most important signals.
                following/affinity now surface via card-level ribbon (U1). */}
            {(event.highlights || [])
              .filter((h) => h !== "free" && h !== "following" && h !== "affinity")
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
