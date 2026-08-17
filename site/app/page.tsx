"use client";

import { useEffect, useMemo, useState } from "react";
import { format, endOfWeek, eachDayOfInterval } from "date-fns";
import { useEvents } from "./hooks/useEvents";
import Header from "./components/Header";
import Calendar from "./components/Calendar";
import EventList from "./components/EventList";
import EventCard from "./components/EventCard";
import TopPicks from "./components/TopPicks";
import EventModal from "./components/EventModal";
import { Event } from "./lib/types";
import { readAndAdvanceLastVisited } from "./lib/interests";
import SearchBar from "./components/SearchBar";
import Footer from "./components/Footer";

type View = "for-you" | "calendar";

export default function Home() {
  const {
    loading,
    loadError,
    events,
    selectedDate,
    setSelectedDate,
    selectedDayEvents,
    eventDates,
    search,
    setSearch,
    lastUpdated,
    totalEvents,
    topAccounts,
  } = useEvents();

  const [view, setView] = useState<View>("for-you");
  const [openEvent, setOpenEvent] = useState<Event | null>(null);
  const [lastVisitedAt, setLastVisitedAt] = useState<string | null>(null);

  // On first load, read previous-visit timestamp THEN advance it. This way
  // the current session sees the prior visit's stamp for "new since" math.
  useEffect(() => {
    queueMicrotask(() => setLastVisitedAt(readAndAdvanceLastVisited()));
  }, []);

  // URL permalinks: read ?date=YYYY-MM-DD&view=for-you|calendar&account=X
  // on mount so users can bookmark + share specific date / account views.
  // Iter 104 added the &account=X param so per-account views are
  // shareable (no static-route generation needed; query-param-only).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const p = new URLSearchParams(window.location.search);
    const d = p.get("date");
    const v = p.get("view");
    const acct = p.get("account");
    queueMicrotask(() => {
      if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) {
        setSelectedDate(d);
        if (!v || v === "calendar") setView("calendar");
      }
      if (v === "for-you" || v === "calendar") setView(v);
      if (acct && /^[A-Za-z0-9_.\-]{1,40}$/.test(acct)) {
        setSearch("@" + acct.toLowerCase());
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reflect view + selectedDate + account filter in the URL so they're
  // bookmarkable / shareable.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const p = new URLSearchParams(window.location.search);
    if (view === "calendar" && selectedDate) {
      p.set("date", selectedDate);
      p.set("view", "calendar");
    } else if (view === "for-you") {
      p.set("view", "for-you");
      p.delete("date");
    }
    // Account filter (iter 104): persist when search starts with @.
    if (search.startsWith("@") && search.length > 1) {
      p.set("account", search.slice(1).toLowerCase());
    } else {
      p.delete("account");
    }
    const q = p.toString();
    const newUrl = window.location.pathname + (q ? "?" + q : "") + window.location.hash;
    if (newUrl !== window.location.pathname + window.location.search + window.location.hash) {
      window.history.replaceState(null, "", newUrl);
    }
  }, [view, selectedDate, search]);

  const newSinceLastVisit = useMemo(() => {
    if (!lastVisitedAt) return 0;
    const cutoff = new Date(lastVisitedAt).getTime();
    return events.filter((e) => {
      const fs = (e as Event & { firstSeenAt?: string }).firstSeenAt;
      if (!fs) return false;
      try {
        return new Date(fs).getTime() > cutoff;
      } catch {
        return false;
      }
    }).length;
  }, [events, lastVisitedAt]);

  const eventCountByDate = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) {
      map.set(e.date, (map.get(e.date) || 0) + 1);
    }
    return map;
  }, [events]);

  // Count events within the next 7 days (inclusive of today) — gives the
  // user a sense of immediately-relevant volume without scanning. Different
  // from `totalEvents` which spans months out.
  const thisWeekCount = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const cutoff = new Date(today);
    cutoff.setDate(today.getDate() + 7);
    const toStr = (d: Date) => format(d, "yyyy-MM-dd");
    const start = toStr(today);
    const end = toStr(cutoff);
    return events.filter((e) => e.date >= start && e.date < end).length;
  }, [events]);

  // iter 215: dropped igCaptureStats, presetEvents, handleQuickFilter —
  // FilterBar (search/categories/price/quick-filters) and the IG-stats
  // header line all removed per user direction. Heroes in TopPicks
  // already provide the time-based + signal-based slicing the quick
  // filters used to offer.

  const handleSelectDate = (date: string) => {
    setSelectedDate(date);
    setView("calendar");
  };

  const weekEvents = useMemo(() => {
    if (search) return null;
    const today = new Date();
    const weekEnd = endOfWeek(today);
    const days = eachDayOfInterval({ start: today, end: weekEnd });
    return days
      .map((d) => {
        const dateStr = format(d, "yyyy-MM-dd");
        return {
          date: dateStr,
          label: format(d, "EEE, MMM d"),
          events: events.filter((e) => e.date === dateStr),
        };
      })
      .filter((d) => d.events.length > 0);
  }, [events, search]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f8f3e8]">
        <Header totalEvents={0} thisWeekCount={0} lastUpdated={undefined} newSinceLastVisit={0} />
        <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
          <div className="mb-8 animate-pulse">
            <div className="h-7 w-48 rounded bg-[#e7e1d2]" />
            <div className="mt-3 h-4 w-64 rounded bg-[#e7e1d2]" />
          </div>
          <div className="mb-6 h-11 w-full max-w-md rounded-full bg-white border border-gray-200" />
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-gray-200 bg-white p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="h-20 w-20 rounded-lg bg-[#ece7d8]" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 rounded bg-[#ece7d8]" />
                    <div className="h-3 w-1/2 rounded bg-[#f0ebe0]" />
                    <div className="h-3 w-2/3 rounded bg-[#f0ebe0]" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </main>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3 px-6 text-center">
        <div className="text-gray-700 text-lg font-semibold">Couldn&apos;t load events</div>
        <p className="text-sm text-gray-500 max-w-sm">
          The events feed failed to load. It may be a temporary network issue —
          please refresh. If it persists, the scraper may not have published yet.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-1 px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700"
        >
          Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8f3e8]">
      <Header
        totalEvents={totalEvents}
        thisWeekCount={thisWeekCount}
        lastUpdated={lastUpdated}
        newSinceLastVisit={newSinceLastVisit}
      />

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        <SearchBar value={search} onChange={setSearch} />
        <div className="mb-8 flex items-end justify-between gap-3 border-b border-[#d8d0c1]">
          <div className="flex gap-6" role="tablist" aria-label="Event view">
            <button
              id="feed-tab"
              onClick={() => setView("for-you")}
              role="tab"
              aria-selected={view === "for-you"}
              aria-controls="event-view-panel"
              className={`-mb-px border-b-2 pb-3 text-sm font-medium transition-colors ${
                view === "for-you" ? "border-[#173c35] text-[#173c35]" : "border-transparent text-[#66716c] hover:text-[#173c35]"
              }`}
            >
              Feed
            </button>
            <button
              id="calendar-tab"
              onClick={() => setView("calendar")}
              role="tab"
              aria-selected={view === "calendar"}
              aria-controls="event-view-panel"
              className={`-mb-px border-b-2 pb-3 text-sm font-medium transition-colors ${
                view === "calendar" ? "border-[#173c35] text-[#173c35]" : "border-transparent text-[#66716c] hover:text-[#173c35]"
              }`}
            >
              Calendar
            </button>
          </div>
          {search && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#8b918e]">{events.length} result{events.length !== 1 ? "s" : ""}</span>
              <button
                onClick={() => setSearch("")}
                className="text-xs font-medium text-[#9a684e] hover:underline"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        <div className="flex flex-col lg:flex-row gap-6">
          {view === "calendar" && (
            <aside className="lg:w-80 shrink-0 order-2 lg:order-1">
              <Calendar
                selectedDate={selectedDate}
                onSelectDate={setSelectedDate}
                eventDates={eventDates}
                eventCountByDate={eventCountByDate}
              />
            </aside>
          )}

          <section
            id="event-view-panel"
            role="tabpanel"
            aria-labelledby={view === "for-you" ? "feed-tab" : "calendar-tab"}
            className="flex-1 min-w-0 order-3 lg:order-2"
          >
            {view === "for-you" ? (
              <TopPicks
                events={events}
                onSelectDate={handleSelectDate}
                onAccountClick={(acct) => setSearch("@" + acct)}
                accountFilter={search.startsWith("@") ? search.slice(1) : undefined}
                topAccounts={topAccounts}
                onClearAccountFilter={() => setSearch("")}
                onSelectEvent={setOpenEvent}
              />
            ) : (
              <>
                <EventList
                  events={selectedDayEvents}
                  selectedDate={selectedDate}
                  onAccountClick={(acct) => setSearch("@" + acct)}
                />

                {selectedDayEvents.length === 0 &&
                  weekEvents &&
                  weekEvents.length > 0 && (
                    <div className="mt-8">
                      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide mb-4">
                        Coming up this week
                      </h3>
                      <div className="space-y-6">
                        {weekEvents.slice(0, 4).map((day) => (
                          <div key={day.date}>
                            <button
                              onClick={() => setSelectedDate(day.date)}
                              className="text-sm font-semibold text-gray-700 mb-2 hover:text-gray-900"
                            >
                              {day.label} ({day.events.length})
                            </button>
                            <div className="space-y-2">
                              {day.events.slice(0, 3).map((event) => (
                                <EventCard
                                  key={event.id}
                                  event={event}
                                  onAccountClick={(acct) => setSearch("@" + acct)}
                                />
                              ))}
                              {day.events.length > 3 && (
                                <button
                                  onClick={() => setSelectedDate(day.date)}
                                  className="text-sm text-gray-400 hover:text-gray-600 pl-1"
                                >
                                  +{day.events.length - 3} more
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </>
            )}
          </section>
        </div>
      </main>
      <EventModal
        event={openEvent}
        onClose={() => setOpenEvent(null)}
        onAccountClick={(acct) => setSearch("@" + acct)}
        relatedEvents={events}
        onSelectEvent={setOpenEvent}
      />
      <Footer lastUpdated={lastUpdated} totalEvents={totalEvents} />
    </div>
  );
}
