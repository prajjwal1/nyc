"use client";

import { format, parseISO } from "date-fns";
import Link from "next/link";
import { useState } from "react";
import { Event } from "../lib/types";
import EventCard from "./EventCard";
import AccountBanner from "./AccountBanner";
import { isHidden, isSavedLocal, getAttendedCount } from "../lib/interests";

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
  accountFilter?: string;        // e.g. "theskint" when search is "@theskint"
  topAccounts?: import("../lib/types").TopAccount[];
  onClearAccountFilter?: () => void;
  onSelectEvent?: (event: Event) => void;
}

const MAX_PER_DAY = 4;
const MAX_DAYS = 10;
const MAX_SAVED = 6;
const MAX_FOLLOWING = 6;

function HeroSection({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-10">
      <div className="mb-3 flex items-baseline justify-between gap-3 border-b border-[#ddd9cc] pb-2">
        <h3 className="font-editorial text-[18px] font-semibold tracking-[-0.015em] text-[#173c35]">
          {title}
        </h3>
        <span className="text-[11px] font-medium text-[#8b918e]">
          {count}
        </span>
      </div>
      <div className="space-y-2.5">{children}</div>
    </section>
  );
}

const CAPTION_LIKE_TITLE = /^(if you(?:['’]re| are)|when you|the cutest little|pov\b|tag (?:a|your)|send this|who else|things to do\b)/i;
const GENERIC_TITLE = /^(event|untitled|tba|coming soon|meetup group\b)/i;

// The home feed is an editorial decision surface, not a dump of every parsed
// listing. Incomplete events remain available in Calendar/Events, but only
// actionable listings earn a featured card here.
function isFeatureReady(e: Event): boolean {
  const location = e.location || { name: "", address: "", neighborhood: null };
  const actionableLocation = [location.name, location.address, location.neighborhood]
    .some((value) => value && !["nyc", "new york", "tba", "online"].includes(value.toLowerCase().trim()));
  return Boolean(
    e.startTime
    && e.sourceUrl?.startsWith("http")
    && e.imageUrl
    && (e.description || "").trim().length >= 20
    && actionableLocation
    && !CAPTION_LIKE_TITLE.test((e.title || "").trim())
    && !GENERIC_TITLE.test((e.title || "").trim())
  );
}

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

  // 1. Take top-K — conviction-first with a score floor (U4 modified).
  // A high-conviction event (userFollowing / userAffinity / userSaved) jumps
  // ahead of a non-conviction event ONLY if its score is within 0.2 of the
  // day's max. This raises perceived high-conviction ratio in the visible
  // viewport without burying a great Eventbrite event under a mediocre IG one.
  // userSaved is currently only set client-side via localStorage and is null
  // in events.json — the read is intentional (effectively a no-op today, lights
  // up later when we wire saved-state into ranking).
  const maxScore = events.length ? Math.max(...events.map((e) => e.score ?? 0)) : 0;
  const convictionFloor = maxScore - 0.2;
  const sorted = [...events].sort((a, b) => {
    const aConv = !!(a.userFollowing || a.userAffinity || a.userSaved) && (a.score ?? 0) >= convictionFloor;
    const bConv = !!(b.userFollowing || b.userAffinity || b.userSaved) && (b.score ?? 0) >= convictionFloor;
    if (aConv !== bConv) return bConv ? 1 : -1;
    return (b.score ?? 0) - (a.score ?? 0);
  });
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

export default function TopPicks({
  events,
  onSelectDate,
  onAccountClick,
  accountFilter,
  topAccounts,
  onClearAccountFilter,
  onSelectEvent,
}: TopPicksProps) {
  const todayStr = format(new Date(), "yyyy-MM-dd");
  const now = new Date();
  // Force-rerender token bumped when user hides an event so the card
  // disappears immediately without a page reload.
  const [, setHideTick] = useState(0);
  const onHide = () => setHideTick((t) => t + 1);

  // Drop user-hidden events from the feed (localStorage signal).
  const visible = events.filter((e) => !isHidden(e.id));
  // Collapse recurring same-event occurrences: keep just the soonest one
  // per (title, account) pair so Smorgasburg doesn't dominate 6 cards.
  const upcoming = collapseRecurring(
    visible.filter((e) => e.date >= todayStr),
  );
  const featureReady = upcoming.filter(isFeatureReady);

  // 🔥 Tonight — feature-ready events happening today after 4pm
  const tonightEvents = featureReady
    .filter((e) => e.date === todayStr)
    .filter((e) => {
      if (!e.startTime) return true;
      const [h] = e.startTime.split(":").map(Number);
      return h >= 16; // 4pm onward
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 6);
  const tonightIds = new Set(tonightEvents.map((e) => e.id));

  // ✨ Just Added — events first seen in the last 72 hours, sorted by score.
  // Wide window (3 days) because most scrapers re-discover the same upcoming
  // events repeatedly; truly fresh additions trickle in slowly. A tight 30h
  // window left this hero empty on most visits, which made the site feel
  // stale. 72h keeps it consistently populated without becoming uninteresting.
  const recentlyAdded = featureReady
    .filter((e) => {
      if (tonightIds.has(e.id)) return false;
      const fs = (e as Event & { firstSeenAt?: string }).firstSeenAt;
      if (!fs) return false;
      try {
        const t = new Date(fs).getTime();
        return now.getTime() - t < 72 * 3600 * 1000;
      } catch {
        return false;
      }
    })
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    // U4 (critic): discovery heroes capped at 4 (vs 6 for the higher-
    // conviction Tonight/Following/Saved) so the ranked feed isn't buried
    // ~30 cards down on mobile. Heroes preserved, just leaner.
    .slice(0, 4);
  const recentIds = new Set(recentlyAdded.map((e) => e.id));

  // 🎉 This Weekend — low-key Saturday/Sunday social events.
  // User explicitly: 'currently everything in This Weekend is parties /
  // nightclub events, concerned about excessive drinking, not my style'.
  // So this hero filters AWAY parties/nightlife/drinks-heavy events and
  // FAVORS books, run-clubs, yoga, outdoors, comedy, art, supper-club,
  // workshops, brunch, dance-class style content. Saturday + Sunday
  // (not Friday — Friday usually skews to nightlife).
  const weekend = (() => {
    const today = new Date();
    const dow = today.getDay(); // 0=Sun..6=Sat
    // Hide on Sunday afternoon — weekend is winding down
    if (dow === 0) return { events: [], ids: new Set<string>() };
    const saturday = new Date(today);
    saturday.setDate(today.getDate() + ((6 - dow + 7) % 7));
    const sunday = new Date(saturday);
    sunday.setDate(saturday.getDate() + 1);
    const isWeekendDate = (d: string) =>
      d === saturday.toISOString().split("T")[0] || d === sunday.toISOString().split("T")[0];

    // POSITIVE signal — low-key social activities. Books, fitness,
    // outdoors, art, food, comedy, dance-class, and meet-people events.
    const POSITIVE_CATS = new Set([
      "books", "fitness", "wellness", "outdoors", "exploration",
      "art", "food", "comedy", "dance", "games", "design",
      "photography", "movies", "viewings", "theater", "celebrities",
    ]);
    const POSITIVE_HIGHLIGHTS = new Set([
      "meet-people", "festival",  // friendly social signals
    ]);
    // NEGATIVE — explicitly the heavy-drinking party scene the user
    // wants away from. ANY of these → exclude entirely from this hero.
    const NEGATIVE_CATS = new Set(["parties"]);
    const NEGATIVE_HIGHLIGHTS = new Set(["nightlife"]);
    const NEGATIVE_TEXT = /\b(open bar|all you can drink|all-you-can-drink|nightclub|bottle service|warehouse|rave|club night|after party|afterparty|edm|techno|free drinks all night)\b/i;

    const isLowKeySocial = (e: Event) => {
      const text = `${e.title} ${e.description || ""}`;
      // Hard exclude: drinking-party / nightclub
      if ((e.categories || []).some((c) => NEGATIVE_CATS.has(c))) return false;
      if ((e.highlights || []).some((h) => NEGATIVE_HIGHLIGHTS.has(h))) return false;
      if (NEGATIVE_TEXT.test(text)) return false;
      // Positive: at least one low-key social category OR meet-people
      if ((e.categories || []).some((c) => POSITIVE_CATS.has(c))) return true;
      if ((e.highlights || []).some((h) => POSITIVE_HIGHLIGHTS.has(h))) return true;
      return false;
    };
    // Time: anytime on weekends is fine (brunch, afternoon walks, evening
    // events all work). No 5pm-only filter.
    const ev = featureReady
      .filter((e) =>
        !tonightIds.has(e.id)
        && !recentIds.has(e.id)
        && isWeekendDate(e.date)
        && isLowKeySocial(e)
      )
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 4);  // U4: discovery hero capped at 4 (see Just Added)
    return { events: ev, ids: new Set(ev.map((e) => e.id)) };
  })();
  const weekendEvents = weekend.events;
  const weekendIds = weekend.ids;

  // 👤 From accounts you follow — IG userFollowing OR cross-source enriched
  // (Lu.ma/venue-domain/JSON-LD organizer matched against IG follows in
  // normalize._enrich_provenance_from_url). The highest-conviction signal
  // we have for "events the user would actually attend." Surfaced before
  // Saved because following is a broader / lower-friction signal than
  // explicit star.
  // Iter 122: also include userAffinity (accounts the user has saved-from
  // before). The iter-71 card ribbon already shows both with sky/amber
  // distinction; the hero filter should match. Affinity is rarer than
  // following, so this won't dominate.
  const followingUpcoming = featureReady
    .filter((e) =>
      (e.userFollowing || e.userAffinity)
      && !tonightIds.has(e.id)
      && !weekendIds.has(e.id)
      && !recentIds.has(e.id),
    )
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, MAX_FOLLOWING);
  const followingIds = new Set(followingUpcoming.map((e) => e.id));

  // ★ User-saved events — IG-saved (server) OR locally saved (browser).
  // Locally-saved is the user explicitly clicking the star on a non-IG event.
  const savedUpcoming = upcoming
    .filter((e) =>
      (e.userSaved || isSavedLocal(e.id))
      && !tonightIds.has(e.id)
      && !weekendIds.has(e.id)
      && !recentIds.has(e.id)
      && !followingIds.has(e.id),
    )
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, MAX_SAVED);
  const savedIds = new Set(savedUpcoming.map((e) => e.id));

  // Group remaining by date — exclude events already shown in hero sections
  const grouped = new Map<string, Event[]>();
  for (const e of featureReady) {
    if (savedIds.has(e.id) || tonightIds.has(e.id) || recentIds.has(e.id) || weekendIds.has(e.id) || followingIds.has(e.id)) continue;
    const list = grouped.get(e.date) ?? [];
    list.push(e);
    grouped.set(e.date, list);
  }

  const sortedDates = [...grouped.keys()].sort().slice(0, MAX_DAYS);

  if (sortedDates.length === 0 && savedUpcoming.length === 0
      && tonightEvents.length === 0 && recentlyAdded.length === 0
      && weekendEvents.length === 0 && followingUpcoming.length === 0) return null;

  return (
    <div className="mb-8">
      {accountFilter && (
        <AccountBanner
          account={accountFilter}
          events={events}
          topAccount={topAccounts?.find((a) => a.username.toLowerCase() === accountFilter.toLowerCase())}
          onClear={onClearAccountFilter || (() => {})}
        />
      )}

      {/* iter 215: dropped 'For You' heading + Detail/Grid toggle entirely.
          User: 'remove For You I know its for me' + 'we don't want grid
          option'. Attended count surfaces inline near the first hero only
          when non-zero, so it doesn't take a full row on a fresh visit. */}
      {(() => {
        const { yes } = getAttendedCount();
        if (yes <= 0) return null;
        return (
          <p className="text-xs text-emerald-700 mb-3 px-2">
            ✓ {yes} attended
          </p>
        );
      })()}

      {/* Shared hero shell — editorial, subtle, consistent. */}
      {tonightEvents.length > 0 && (
        <HeroSection title="Tonight" count={tonightEvents.length}>
          {tonightEvents.map((event, rank) => (
            <div key={event.id} data-event-id={event.id} data-feed-section="tonight" data-rank={rank + 1}>
              <EventCard event={event} showDay onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelectEvent} />
            </div>
          ))}
        </HeroSection>
      )}

      {weekendEvents.length > 0 && (
        <HeroSection title="This Weekend" count={weekendEvents.length}>
          {weekendEvents.map((event, rank) => (
            <div key={event.id} data-event-id={event.id} data-feed-section="weekend" data-rank={rank + 1}>
              <EventCard event={event} showDay onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelectEvent} />
            </div>
          ))}
        </HeroSection>
      )}

      {recentlyAdded.length > 0 && (
        <HeroSection title="Just Added" count={recentlyAdded.length}>
          {recentlyAdded.map((event, rank) => (
            <div key={event.id} data-event-id={event.id} data-feed-section="just-added" data-rank={rank + 1}>
              <EventCard event={event} showDay onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelectEvent} />
            </div>
          ))}
        </HeroSection>
      )}

      {followingUpcoming.length > 0 && (
        <HeroSection title="From accounts you follow" count={followingUpcoming.length}>
          {followingUpcoming.map((event, rank) => (
            <div key={event.id} data-event-id={event.id} data-feed-section="following" data-rank={rank + 1}>
              <EventCard event={event} showDay onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelectEvent} />
            </div>
          ))}
        </HeroSection>
      )}

      {savedUpcoming.length > 0 && (
        <HeroSection title="Saved by you" count={savedUpcoming.length}>
          {savedUpcoming.map((event, rank) => (
            <div key={event.id} data-event-id={event.id} data-feed-section="saved" data-rank={rank + 1}>
              <EventCard event={event} showDay onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelectEvent} />
            </div>
          ))}
        </HeroSection>
      )}

      <div className="space-y-8">
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
                className="group mb-3 flex items-baseline gap-3 text-left"
              >
                <span
                  className={`font-editorial tracking-[-0.015em] ${
                    isToday ? "text-[22px] font-bold text-[#173c35]" : "text-[17px] font-semibold text-[#3a4d48]"
                  }`}
                >
                  {isToday ? `Today · ${format(dateObj, "EEEE, MMM d")}` : format(dateObj, "EEEE, MMM d")}
                </span>
                <span className="text-[11px] font-medium text-[#8b918e] group-hover:text-[#5d6964]">
                  {total} event{total !== 1 ? "s" : ""} →
                </span>
              </button>
              <div className="space-y-2.5">
                {dayEvents.map((event, rank) => (
                  <div key={event.id} data-event-id={event.id} data-feed-section={`date:${date}`} data-rank={rank + 1}>
                    <EventCard event={event} onAccountClick={onAccountClick} onHide={onHide} onSelect={onSelectEvent} />
                  </div>
                ))}
              </div>
              {total > MAX_PER_DAY && (
                <button
                  onClick={() => onSelectDate(date)}
                  className="mt-3 inline-flex rounded-full border border-[#d7d5cd] bg-white px-3 py-1 text-xs font-medium text-[#5d6964] hover:border-[#173c35] hover:text-[#173c35]"
                >
                  +{total - MAX_PER_DAY} more on {format(dateObj, "MMM d")}
                </button>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-10 flex justify-center">
        <Link
          href="/events"
          className="inline-flex items-center gap-1.5 rounded-full bg-[#173c35] px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-[#204b40] transition"
        >
          Browse every upcoming event
          <span aria-hidden="true">→</span>
        </Link>
      </div>
    </div>
  );
}
