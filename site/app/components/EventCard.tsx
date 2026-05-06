"use client";

import { Event, CATEGORY_CONFIG, SOURCE_LABELS, HIGHLIGHT_CONFIG } from "../lib/types";

interface EventCardProps {
  event: Event;
  variant?: "compact" | "feed";
  onAccountClick?: (account: string) => void;
}

export default function EventCard({ event, variant = "feed", onAccountClick }: EventCardProps) {
  const timeStr = event.startTime
    ? formatTime(event.startTime) +
      (event.endTime ? ` – ${formatTime(event.endTime)}` : "")
    : null;

  if (variant === "compact") {
    return <CompactCard event={event} timeStr={timeStr} />;
  }

  // IG events are inherently visual — when we have a usable image, lead with
  // a large flyer like an IG grid post so the user can scan visually rather
  // than reading metadata.
  if (event.source === "instagram" && event.imageUrl) {
    return <MediaFirstCard event={event} timeStr={timeStr} onAccountClick={onAccountClick} />;
  }

  return <FeedCard event={event} timeStr={timeStr} onAccountClick={onAccountClick} />;
}

function MediaFirstCard({
  event,
  timeStr,
  onAccountClick,
}: {
  event: Event;
  timeStr: string | null;
  onAccountClick?: (account: string) => void;
}) {
  const dateLabel = formatDateLabel(event.date);
  return (
    <a
      href={event.sourceUrl}
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
          {event.price === "free" && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
              FREE
            </span>
          )}
        </div>
      </div>
    </a>
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
}: {
  event: Event;
  timeStr: string | null;
  onAccountClick?: (account: string) => void;
}) {
  // Show description only if it's high-signal (not just a fragment of a larger caption)
  const desc = event.description?.trim();
  const showDesc =
    desc && desc.length > 30 && desc.length < 300 &&
    !desc.toLowerCase().startsWith("link in bio") &&
    !desc.toLowerCase().startsWith("photo by");

  return (
    <a
      href={event.sourceUrl}
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
