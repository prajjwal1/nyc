"use client";

import { format, parseISO } from "date-fns";
import { Event } from "../lib/types";
import EventCard from "./EventCard";

interface TopPicksProps {
  events: Event[];
  onSelectDate: (date: string) => void;
}

const MAX_PER_DAY = 8;
const MAX_DAYS = 30;

/**
 * Round-robin events across primary categories so the user sees variety.
 * Take the top-scored event from each distinct category, then cycle back.
 * Falls back to score order when all categories exhausted.
 */
function diversifyByCategory(events: Event[], n: number): Event[] {
  if (events.length <= n) return events;

  // Bucket by primary category (skip "free" / "other" which are not really categories)
  const buckets = new Map<string, Event[]>();
  for (const e of events) {
    const primary = (e.categories || []).find(
      (c) => c !== "free" && c !== "other"
    ) || "_other";
    if (!buckets.has(primary)) buckets.set(primary, []);
    buckets.get(primary)!.push(e);
  }

  // Sort buckets by their top event's score (descending)
  const orderedBuckets = [...buckets.entries()].sort(
    (a, b) => (b[1][0].score ?? 0) - (a[1][0].score ?? 0)
  );

  const result: Event[] = [];
  const seen = new Set<string>();
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

export default function TopPicks({ events, onSelectDate }: TopPicksProps) {
  const todayStr = format(new Date(), "yyyy-MM-dd");

  // Filter to upcoming events
  const upcoming = events.filter((e) => e.date >= todayStr);

  // Group by date
  const grouped = new Map<string, Event[]>();
  for (const e of upcoming) {
    const list = grouped.get(e.date) ?? [];
    list.push(e);
    grouped.set(e.date, list);
  }

  // Sort dates chronologically
  const sortedDates = [...grouped.keys()].sort().slice(0, MAX_DAYS);

  if (sortedDates.length === 0) return null;

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

      <div className="space-y-6">
        {sortedDates.map((date) => {
          const dateObj = parseISO(date + "T12:00:00");
          const isToday = date === todayStr;
          // Diversify: round-robin top events across categories so user
          // gets variety (not 8 jazz events on one day).
          const dayEvents = diversifyByCategory(
            grouped.get(date)!.slice().sort((a, b) => (b.score ?? 0) - (a.score ?? 0)),
            MAX_PER_DAY
          );
          const total = grouped.get(date)!.length;

          return (
            <div key={date}>
              <button
                onClick={() => onSelectDate(date)}
                className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 hover:text-gray-900 flex items-baseline gap-2"
              >
                <span>{isToday ? "Today" : format(dateObj, "EEEE, MMM d")}</span>
                <span className="text-gray-400 font-normal normal-case tracking-normal">
                  · {total} event{total !== 1 ? "s" : ""}
                </span>
              </button>
              <div className="space-y-2">
                {dayEvents.map((event) => (
                  <EventCard key={event.id} event={event} />
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
