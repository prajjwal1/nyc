"use client";

import { useState } from "react";
import { Event, CATEGORY_CONFIG, SOURCE_LABELS, HIGHLIGHT_CONFIG } from "../lib/types";
import { trackAccountClick, trackEventOpen, hideEvent, toggleSavedLocal, isSavedLocal, isEventOpened, getAttendedState } from "../lib/interests";
import { downloadIcs } from "../lib/ics";

interface EventCardProps {
  event: Event;
  variant?: "compact" | "feed";
  onAccountClick?: (account: string) => void;
  onHide?: (eventId: string) => void;
  onSelect?: (event: Event) => void;
  // Show a relative-day pill ("Today"/"Tomorrow"/"Sat"/"Jul 12") in the meta
  // row. Heroes (Tonight/Following/Saved/Just-Added) drop the date entirely,
  // so they pass true; grouped date-lists already have a day header and pass
  // false (the default) to avoid duplication.
  showDay?: boolean;
}

// Relative-day label for the card meta row. Returns null for past/unparseable
// dates (heroes only show upcoming events anyway).
function relDay(iso: string | undefined): string | null {
  if (!iso) return null;
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const d = new Date(iso + "T00:00:00");
    const diff = Math.round((d.getTime() - today.getTime()) / 86400000);
    if (isNaN(diff) || diff < 0) return null;
    if (diff === 0) return "Today";
    if (diff === 1) return "Tomorrow";
    if (diff <= 6) return d.toLocaleDateString("en-US", { weekday: "short" });
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return null;
  }
}

// iter 215: removed grid variant + MediaFirstCard variant. All events
// now render through FeedCard for uniform sizing — IG events no longer
// take 4-5x the vertical space of other sources.
export default function EventCard({ event, variant = "feed", onAccountClick, onHide, onSelect, showDay = false }: EventCardProps) {
  const timeStr = event.startTime
    ? formatTime(event.startTime) +
      (event.endTime ? ` – ${formatTime(event.endTime)}` : "")
    : null;

  if (variant === "compact") {
    return <CompactCard event={event} timeStr={timeStr} />;
  }

  return <FeedCard event={event} timeStr={timeStr} showDay={showDay} onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelect} />;
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
  showDay = false,
  onAccountClick,
  onHide,
  onSelect,
}: {
  event: Event;
  timeStr: string | null;
  showDay?: boolean;
  onAccountClick?: (account: string) => void;
  onHide?: (eventId: string) => void;
  onSelect?: (event: Event) => void;
}) {
  const [savedF, setSavedF] = useState(() => isSavedLocal(event.id));
  const [imgFailedF, setImgFailedF] = useState(false);
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
  const dayLabel = relDay(event.date);
  const _nb = event.location?.neighborhood?.trim();
  const showNeighborhood = Boolean(
    _nb && !(event.location?.name || "").toLowerCase().includes(_nb.toLowerCase())
  );
  const convictionFollow = !!event.userFollowing;
  const convictionAffinity = !convictionFollow && !!event.userAffinity;
  const feedChrome = convictionFollow
    ? "ring-1 ring-sky-300 shadow-[inset_3px_0_0_0_#0ea5e9]"
    : convictionAffinity
    ? "ring-1 ring-amber-300 shadow-[inset_3px_0_0_0_#f59e0b]"
    : "border border-gray-200 hover:border-gray-300";
  const todayStrF = new Date().toISOString().split("T")[0];
  const isPastF = !!event.date && event.date < todayStrF;
  const attendedF = isPastF ? getAttendedState(event.id) : undefined;
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
      <div className="flex gap-3 p-3">
        {event.imageUrl && !imgFailedF && (
          <div className="shrink-0 w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-gray-100">
            <img
              src={event.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
              onError={() => setImgFailedF(true)}
            />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-sm leading-snug line-clamp-2">
            {event.title}
            {attendedF === "yes" && (
              <span
                className="ml-1.5 inline-flex items-center align-middle rounded-full bg-emerald-100 text-emerald-800 px-1.5 py-0.5 text-[10px] font-medium"
                title="You marked attended"
              >
                ✓ went
              </span>
            )}
          </h3>

          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500">
            {/* U1: relative-day scent for hero cards (which drop the date). */}
            {showDay && dayLabel && (
              <span className="font-semibold text-gray-700">{dayLabel}</span>
            )}
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
                {/* U2: only show the neighborhood suffix when the venue name
                    doesn't already contain it — avoids "…East Village · east
                    village" redundancy and stops amplifying name/neighborhood
                    conflicts. */}
                {showNeighborhood && (
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
            {/* U1 (a11y, WCAG 1.4.1): the follow-graph conviction signal was
                color-only (sky ring). A compact "★ following" label makes it
                perceivable without color. Following-tier only (affinity keeps
                its ring) to avoid badge clutter. Not the removed prose ribbon. */}
            {convictionFollow && (
              <span
                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-100 text-sky-800"
                title="From an account you follow"
              >
                ★ following
              </span>
            )}
            {/* WS2: "matches your taste" — the payoff of the learning loop.
                Shown only when the semantic taste model (fed by your synced
                saves/attends) scores this event highly AND it isn't already a
                save/follow conviction event (avoid stacking signals). Genuinely
                new info the ★ ring doesn't convey; absent until you sync. */}
            {(event.tasteScore ?? 0) >= 0.06 &&
              !event.userSaved &&
              !event.userFollowing &&
              !event.userAffinity && (
                <span
                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700"
                  title="Similar to events you've saved or attended"
                >
                  ✨ your taste
                </span>
              )}
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
            {/* U1 (run 2026-06-22-1501): surface a non-free price at a glance.
                The feed previously badged only FREE, so paid fitness/dance
                events (Brooklyn Contra $15, run-club drop-ins) showed no price
                until the modal. Digit-only guard avoids junk pills ("varies",
                "unknown"); qualitative words ("donation"/PWYC) deferred to D1. */}
            {event.price &&
              event.price !== "free" &&
              event.price !== "unknown" &&
              event.price !== "varies" &&
              /\d/.test(event.price) && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-700">
                  {event.price}
                </span>
              )}
            {/* fb-182 (run 2026-06-23-1816): qualitative low-commitment price
                words ("donation"/PWYC/"sliding scale") are POSITIVE attend
                signals — surface them as a subtle sky pill, lighter than the
                emerald FREE so it reads "cheap/flexible," not "free." Numeric
                wins: the !/\d/ guard means "sliding scale $10" shows only the
                numeric pill above (one price pill per card). */}
            {event.price &&
              !/\d/.test(event.price) &&
              /donation|pay what|pwyc|sliding scale|suggested/i.test(event.price) && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-sky-50 text-sky-700">
                  {event.price}
                </span>
              )}
            {/* iter 215: category chips removed — visual noise. Categories
                still drive ranking + diversity internally; the user does
                not need to see them on every card. */}
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
                  className="hover:text-gray-700 hover:underline rounded-sm focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none"
                  title={`See more from @${event.instagramAccount}`}
                >
                  @{event.instagramAccount}
                </button>
              ) : event.account && (event.userFollowing || event.userAffinity) ? (
                // Cross-source-enriched conviction event: surface WHICH follow
                // drove it, as a clickable per-account filter (fb-169). The
                // account filter now keys on event.account (lib/events.ts), and
                // AccountBanner suppresses the IG link for these non-IG handles.
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    trackAccountClick(event.account);
                    onAccountClick?.(event.account!);
                  }}
                  className="hover:text-gray-700 hover:underline rounded-sm focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none"
                  title={`See more from @${event.account}`}
                >
                  @{event.account}
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
  const [imgFailedC, setImgFailedC] = useState(false);
  return (
    <a
      href={event.sourceUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-all"
    >
      <div className="flex gap-4">
        {event.imageUrl && !imgFailedC && (
          <div className="shrink-0 w-16 h-16 rounded-lg overflow-hidden bg-gray-100">
            <img
              src={event.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
              onError={() => setImgFailedC(true)}
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
