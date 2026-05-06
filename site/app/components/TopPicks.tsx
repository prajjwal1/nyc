"use client";

import { format, parseISO } from "date-fns";
import { useState } from "react";
import { Event } from "../lib/types";
import EventCard from "./EventCard";
import { isHidden } from "../lib/interests";

// Series key — when the same recurring event title appears across many
// future dates (e.g., "Smorgasburg" weekly), collapse to the soonest
// occurrence per (title, account) pair so the feed shows variety.
function seriesKey(e: Event): string {
  const title = (e.title || "").toLowerCase().slice(0, 50);
  const acct = (e.instagramAccount || e.source || "").toLowerCase();
  return `${acct}::${title}`;
}

function collapseRecurring(events: Event[], maxPerSeries = 1): Event[] {
  const counts = new Map<string, number>();
  // Sort by date ascending so the SOONEST occurrence is kept.
  const sorted = [...events].sort((a, b) =>
    a.date.localeCompare(b.date)
  );
  const out: Event[] = [];
  for (const e of sorted) {
    if (!e.recurring) {
      out.push(e);
      continue;
    }
    const k = seriesKey(e);
    const n = counts.get(k) || 0;
    if (n < maxPerSeries) {
      out.push(e);
      counts.set(k, n + 1);
    }
  }
  return out;
}

interface TopPicksProps {
  events: Event[];
  onSelectDate: (date: string) => void;
  onAccountClick?: (account: string) => void;
}

const MAX_PER_DAY = 8;
const MAX_DAYS = 30;
const MAX_SAVED = 6;

// Source identifier for organizer/account-level cap. IG events use the
// account; Eventbrite events use organizer host; otherwise fall back to source.
function organizerKey(e: Event): string {
  if (e.instagramAccount) return "ig:" + e.instagramAccount.toLowerCase();
  if (e.source === "eventbrite") {
    // Eventbrite event URLs include organizer in slug; group by approximate
    // organizer-token (the trailing numeric ID is per-event, not organizer).
    try {
      const u = new URL(e.sourceUrl);
      // /e/<slug>-<eventid>?... ; bucket by first 3 path tokens
      const path = u.pathname.split("/").filter(Boolean).slice(0, 2).join("/");
      return "eb:" + path;
    } catch {
      return "eb:" + e.sourceUrl;
    }
  }
  return e.source + ":" + (e.location.name || "");
}

/**
 * Order events by rank with category AND source diversity.
 *
 * Top-K events (default 2) are pure score-order — the highest-ranked
 * events always show first regardless of category. After that, we
 * round-robin across categories for variety, and cap how many events a
 * single IG account / Eventbrite organizer can occupy in the result so
 * one prolific source can't crowd out the feed.
 */
function diversifyByCategory(events: Event[], n: number, topK = 2, maxPerOrganizer = 2): Event[] {
  if (events.length <= n) return events;

  // 1. Take top-K strictly by score
  const sorted = [...events].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const result: Event[] = [];
  const seen = new Set<string>();
  const orgCounts = new Map<string, number>();

  for (const e of sorted) {
    if (result.length >= topK) break;
    result.push(e);
    seen.add(e.id);
    const k = organizerKey(e);
    orgCounts.set(k, (orgCounts.get(k) || 0) + 1);
  }

  if (result.length >= n) return result;

  // 2. For the rest, round-robin across primary categories with org cap
  const buckets = new Map<string, Event[]>();
  for (const e of sorted) {
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
      // Pick the next event from this bucket that doesn't bust the org cap.
      let i = 0;
      while (i < bucket.length) {
        const cand = bucket[i];
        const k = organizerKey(cand);
        if ((orgCounts.get(k) || 0) < maxPerOrganizer) {
          bucket.splice(i, 1);
          if (!seen.has(cand.id)) {
            result.push(cand);
            seen.add(cand.id);
            orgCounts.set(k, (orgCounts.get(k) || 0) + 1);
            exhausted = false;
          }
          break;
        }
        i++;
      }
    }
  }

  // 3. If we couldn't fill n under the cap, fill remaining slots ignoring it.
  if (result.length < n) {
    for (const e of sorted) {
      if (result.length >= n) break;
      if (!seen.has(e.id)) {
        result.push(e);
        seen.add(e.id);
      }
    }
  }
  return result;
}

export default function TopPicks({ events, onSelectDate, onAccountClick }: TopPicksProps) {
  const todayStr = format(new Date(), "yyyy-MM-dd");
  const now = new Date();
  // Force-rerender token bumped when user hides an event so the card
  // disappears immediately without a page reload.
  const [hideTick, setHideTick] = useState(0);
  const onHide = () => setHideTick((t) => t + 1);

  // Drop user-hidden events from the feed (localStorage signal).
  const visible = events.filter((e) => !isHidden(e.id));
  // Collapse recurring same-event occurrences: keep just the soonest one
  // per (title, account) pair so Smorgasburg doesn't dominate 6 cards.
  const upcoming = collapseRecurring(
    visible.filter((e) => e.date >= todayStr),
  );

  // 🔥 Tonight — events happening today, evening start (after 4pm) or no time set
  const tonightEvents = upcoming
    .filter((e) => e.date === todayStr)
    .filter((e) => {
      if (!e.startTime) return true;
      const [h] = e.startTime.split(":").map(Number);
      return h >= 16; // 4pm onward
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 6);
  const tonightIds = new Set(tonightEvents.map((e) => e.id));

  // ✨ Just Added — events first seen in the last 30 hours, sorted by date
  const recentlyAdded = upcoming
    .filter((e) => {
      if (tonightIds.has(e.id)) return false;
      const fs = (e as Event & { firstSeenAt?: string }).firstSeenAt;
      if (!fs) return false;
      try {
        const t = new Date(fs).getTime();
        return now.getTime() - t < 30 * 3600 * 1000;
      } catch {
        return false;
      }
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 6);
  const recentIds = new Set(recentlyAdded.map((e) => e.id));

  // ★ User-saved events — bookmarked by user, highest signal
  const savedUpcoming = upcoming
    .filter((e) => e.userSaved && !tonightIds.has(e.id) && !recentIds.has(e.id))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, MAX_SAVED);
  const savedIds = new Set(savedUpcoming.map((e) => e.id));

  // Group remaining by date — exclude events already shown in hero sections
  const grouped = new Map<string, Event[]>();
  for (const e of upcoming) {
    if (savedIds.has(e.id) || tonightIds.has(e.id) || recentIds.has(e.id)) continue;
    const list = grouped.get(e.date) ?? [];
    list.push(e);
    grouped.set(e.date, list);
  }

  const sortedDates = [...grouped.keys()].sort().slice(0, MAX_DAYS);

  if (sortedDates.length === 0 && savedUpcoming.length === 0
      && tonightEvents.length === 0 && recentlyAdded.length === 0) return null;

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

      {/* 🔥 Tonight — happening today, evening events */}
      {tonightEvents.length > 0 && (
        <div className="mb-8 -mx-1 px-1 py-3 bg-rose-50/60 rounded-2xl border border-rose-200">
          <h3 className="text-sm font-semibold text-rose-900 uppercase tracking-wide mb-2 px-2">
            🔥 Tonight
          </h3>
          <div className="space-y-2">
            {tonightEvents.map((event) => (
              <EventCard key={event.id} event={event} onAccountClick={onAccountClick} onHide={onHide} />
            ))}
          </div>
        </div>
      )}

      {/* ✨ Just Added — events first seen in last 30 hours */}
      {recentlyAdded.length > 0 && (
        <div className="mb-8 -mx-1 px-1 py-3 bg-sky-50/60 rounded-2xl border border-sky-200">
          <h3 className="text-sm font-semibold text-sky-900 uppercase tracking-wide mb-2 px-2 flex items-center justify-between">
            <span>✨ Just Added</span>
            <span className="text-[10px] font-normal text-sky-700 normal-case tracking-normal">
              new in the last day
            </span>
          </h3>
          <div className="space-y-2">
            {recentlyAdded.map((event) => (
              <EventCard key={event.id} event={event} onAccountClick={onAccountClick} onHide={onHide} />
            ))}
          </div>
        </div>
      )}

      {/* ★ Saved hero */}
      {savedUpcoming.length > 0 && (
        <div className="mb-8 -mx-1 px-1 py-3 bg-amber-50/50 rounded-2xl border border-amber-200">
          <h3 className="text-sm font-semibold text-amber-900 uppercase tracking-wide mb-2 px-2">
            ★ Saved by you
          </h3>
          <div className="space-y-2">
            {savedUpcoming.map((event) => (
              <EventCard key={event.id} event={event} onAccountClick={onAccountClick} onHide={onHide} />
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
                  <EventCard key={event.id} event={event} onAccountClick={onAccountClick} onHide={onHide} />
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
