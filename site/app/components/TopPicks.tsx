"use client";

import { format, parseISO } from "date-fns";
import { Event } from "../lib/types";
import EventCard from "./EventCard";

interface TopPicksProps {
  events: Event[];
  onSelectDate: (date: string) => void;
  onAccountClick?: (account: string) => void;
}

const MAX_PER_DAY = 8;
const MAX_DAYS = 30;
const MAX_SAVED = 6;

/**
 * Order events by rank with category diversity.
 *
 * Top-K events (default 2) are pure score-order — the highest-ranked
 * events always show first regardless of category. After that, we
 * round-robin across categories for variety.
 */
function diversifyByCategory(events: Event[], n: number, topK = 2): Event[] {
  if (events.length <= n) return events;

  // 1. Take top-K strictly by score
  const sorted = [...events].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const result: Event[] = sorted.slice(0, topK);
  const seen = new Set(result.map((e) => e.id));

  if (result.length >= n) return result;

  // 2. For the rest, round-robin across primary categories
  const buckets = new Map<string, Event[]>();
  for (const e of sorted.slice(topK)) {
    if (seen.has(e.id)) continue;
    const primary = (e.categories || []).find(
      (c) => c !== "free" && c !== "other"
    ) || "_other";
    if (!buckets.has(primary)) buckets.set(primary, []);
    buckets.get(primary)!.push(e);
  }

  const orderedBuckets = [...buckets.entries()].sort(
    (a, b) => (b[1][0].score ?? 0) - (a[1][0].score ?? 0)
  );

  let exhausted = false;
  while (result.length < n && !exhausted) {
    exhausted = true;
    for (const [, bucket] of orderedBuckets) {
      if (result.length >= n) break;
      const next = bucket.shift();
      if (next && !seen.has(next.id)) {
        result.push(next);
        seen.add(next.id);
        exhausted = false;
      }
    }
  }
  return result;
}

export default function TopPicks({ events, onSelectDate, onAccountClick }: TopPicksProps) {
  const todayStr = format(new Date(), "yyyy-MM-dd");

  const upcoming = events.filter((e) => e.date >= todayStr);

  // ★ User-saved events — bookmarked by user, highest signal
  const savedUpcoming = upcoming
    .filter((e) => e.userSaved)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, MAX_SAVED);
  const savedIds = new Set(savedUpcoming.map((e) => e.id));

  // Group remaining by date
  const grouped = new Map<string, Event[]>();
  for (const e of upcoming) {
    if (savedIds.has(e.id)) continue; // shown in saved hero
    const list = grouped.get(e.date) ?? [];
    list.push(e);
    grouped.set(e.date, list);
  }

  const sortedDates = [...grouped.keys()].sort().slice(0, MAX_DAYS);

  if (sortedDates.length === 0 && savedUpcoming.length === 0) return null;

  return (
    <div className="mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">For You</h2>
          <p className="text-sm text-gray-500">
            The best of NYC each day, picked for your interests
          </p>
        </div>
      </div>

      {/* ★ Saved hero */}
      {savedUpcoming.length > 0 && (
        <div className="mb-8 -mx-1 px-1 py-3 bg-amber-50/50 rounded-2xl border border-amber-200">
          <h3 className="text-sm font-semibold text-amber-900 uppercase tracking-wide mb-2 px-2">
            ★ Saved by you
          </h3>
          <div className="space-y-2">
            {savedUpcoming.map((event) => (
              <EventCard key={event.id} event={event} onAccountClick={onAccountClick} />
            ))}
          </div>
        </div>
      )}

      <div className="space-y-6">
        {sortedDates.map((date) => {
          const dateObj = parseISO(date + "T12:00:00");
          const isToday = date === todayStr;
          const dayEvents = diversifyByCategory(
            grouped.get(date)!.slice().sort((a, b) => (b.score ?? 0) - (a.score ?? 0)),
            MAX_PER_DAY
          );
          const total = grouped.get(date)!.length;

          return (
            <div key={date}>
              <button
                onClick={() => onSelectDate(date)}
                className={`mb-2 hover:text-gray-900 flex items-baseline gap-2 ${
                  isToday
                    ? "text-base font-bold text-gray-900"
                    : "text-xs font-semibold text-gray-500 uppercase tracking-wide"
                }`}
              >
                <span>
                  {isToday
                    ? `🔥 Today · ${format(dateObj, "EEEE, MMM d")}`
                    : format(dateObj, "EEEE, MMM d")}
                </span>
                <span
                  className={`font-normal normal-case tracking-normal ${
                    isToday ? "text-gray-500 text-sm" : "text-gray-400"
                  }`}
                >
                  · {total} event{total !== 1 ? "s" : ""}
                </span>
              </button>
              <div className="space-y-2">
                {dayEvents.map((event) => (
                  <EventCard key={event.id} event={event} onAccountClick={onAccountClick} />
                ))}
                {total > MAX_PER_DAY && (
                  <button
                    onClick={() => onSelectDate(date)}
                    className="text-xs text-gray-400 hover:text-gray-700 pl-1"
                  >
                    +{total - MAX_PER_DAY} more on {format(dateObj, "MMM d")}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
