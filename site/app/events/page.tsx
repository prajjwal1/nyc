"use client";

import { useEffect, useMemo, useState } from "react";
import { format, parseISO } from "date-fns";
import { useEvents } from "../hooks/useEvents";
import EventCard from "../components/EventCard";
import Header from "../components/Header";
import SearchBar from "../components/SearchBar";
import Footer from "../components/Footer";
import EventModal from "../components/EventModal";
import { Event } from "../lib/types";
import { filterEvents } from "../lib/events";
import {
  isHidden,
  loadSavedStubs,
  readLastVisited,
  savedStubToEvent,
} from "../lib/interests";

export default function AllEventsPage() {
  const {
    loading,
    loadError,
    events,
    search,
    setSearch,
    lastUpdated,
    totalEvents,
  } = useEvents();

  const [openEvent, setOpenEvent] = useState<Event | null>(null);
  const [lastVisitedAt, setLastVisitedAt] = useState<string | null>(null);
  const [showPast, setShowPast] = useState(false);
  const [pastSavedEvents, setPastSavedEvents] = useState<Event[]>([]);
  const [hiddenEventIds, setHiddenEventIds] = useState<Set<string>>(() => new Set());
  const todayStr = format(new Date(), "yyyy-MM-dd");

  useEffect(() => {
    queueMicrotask(() => {
      setLastVisitedAt(readLastVisited());
      setPastSavedEvents(
        loadSavedStubs()
          .map(savedStubToEvent)
          .filter((event) => event.date < format(new Date(), "yyyy-MM-dd")),
      );
    });
  }, []);

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

  const grouped = useMemo(() => {
    const map = new Map<string, Event[]>();
    const candidates = showPast
      ? [...events, ...filterEvents(pastSavedEvents, { search })]
      : events;
    for (const e of candidates) {
      if (hiddenEventIds.has(e.id) || isHidden(e.id)) continue;
      const list = map.get(e.date) ?? [];
      list.push(e);
      map.set(e.date, list);
    }
    // Sort each day by score desc
    for (const [k, v] of map) {
      map.set(k, [...v].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)));
    }
    return [...map.entries()].sort(([dateA], [dateB]) => {
      const aIsPast = dateA < todayStr;
      const bIsPast = dateB < todayStr;
      if (aIsPast !== bIsPast) return aIsPast ? 1 : -1;
      return aIsPast ? dateB.localeCompare(dateA) : dateA.localeCompare(dateB);
    });
  }, [events, hiddenEventIds, pastSavedEvents, search, showPast, todayStr]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f8f3e8]">
        <Header totalEvents={0} thisWeekCount={0} lastUpdated={undefined} newSinceLastVisit={0} />
        <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
          <div className="space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-gray-200 bg-white p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="h-20 w-20 rounded-lg bg-[#ece7d8]" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 rounded bg-[#ece7d8]" />
                    <div className="h-3 w-1/2 rounded bg-[#f0ebe0]" />
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
      <div className="min-h-screen bg-[#f8f3e8]">
        <Header totalEvents={0} thisWeekCount={0} />
        <div className="mx-auto max-w-5xl px-4 py-20 text-center">
          <p className="font-semibold text-[#173c35]">Couldn&apos;t load events</p>
          <button onClick={() => window.location.reload()} className="mt-4 rounded-full bg-[#173c35] px-5 py-2 text-sm text-white">
            Refresh
          </button>
        </div>
      </div>
    );
  }

  const newSinceLastVisit = (() => {
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
  })();

  return (
    <div className="min-h-screen bg-[#f8f3e8]">
      <Header
        totalEvents={totalEvents}
        thisWeekCount={thisWeekCount}
        lastUpdated={lastUpdated}
        newSinceLastVisit={newSinceLastVisit}
      />

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        <div className="mb-6">
          <h1 className="font-editorial text-3xl font-bold tracking-[-0.02em] text-[#173c35] sm:text-4xl">
            Every upcoming event
          </h1>
          <p className="mt-2 text-sm text-[#66716c]">
            The full feed — {events.length} events sorted by date, ranked by curation signal. Search to narrow.
          </p>
        </div>

        <SearchBar value={search} onChange={setSearch} />

        <div className="mb-6 flex items-center gap-2">
          <button
            onClick={() => setShowPast(!showPast)}
            aria-pressed={showPast}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              showPast ? "bg-[#173c35] text-white" : "border border-[#d7d5cd] bg-white text-[#5d6964] hover:border-[#173c35]"
            }`}
          >
            {showPast ? "Hide past saves" : "Include past saves"}
          </button>
          {search && (
            <span className="text-xs text-[#8b918e]">
              {events.length} match{events.length !== 1 ? "es" : ""}
            </span>
          )}
        </div>

        {grouped.length === 0 ? (
          <div className="rounded-[1.5rem] border border-dashed border-[#d7d5cd] bg-white p-10 text-center">
            <p className="font-medium text-[#173c35]">No events match</p>
            <p className="mt-1 text-sm text-[#8b918e]">Try a different search or clear filters.</p>
            <button
              onClick={() => setSearch("")}
              className="mt-4 rounded-full border border-[#173c35] px-4 py-2 text-xs font-semibold text-[#173c35]"
            >
              Clear search
            </button>
          </div>
        ) : (
          <div className="space-y-10">
            {grouped.map(([date, dayEvents]) => {
              const dateObj = parseISO(date + "T12:00:00");
              const isToday = date === todayStr;
              return (
                <div key={date}>
                  <div className="sticky top-[56px] z-10 -mx-1 mb-3 flex items-baseline gap-3 bg-[#f8f3e8]/90 px-1 py-2 backdrop-blur supports-[backdrop-filter]:bg-[#f8f3e8]/70 sm:top-[53px]">
                    <h2 className={`font-editorial tracking-[-0.015em] ${isToday ? "text-[22px] font-bold text-[#173c35]" : "text-[18px] font-semibold text-[#3a4d48]"}`}>
                      {isToday ? `Today · ${format(dateObj, "EEEE, MMM d")}` : format(dateObj, "EEEE, MMM d")}
                    </h2>
                    <span className="text-[11px] text-[#8b918e]">{dayEvents.length} events</span>
                  </div>
                  <div className="space-y-2.5">
                    {dayEvents.map((event, rank) => (
                      <div key={event.id} data-event-id={event.id} data-rank={rank + 1}>
                        <EventCard
                          event={event}
                          showDay
                          onAccountClick={(acct) => setSearch("@" + acct)}
                          onHide={(eventId) => {
                            setHiddenEventIds((current) => new Set(current).add(eventId));
                          }}
                          onSaveChange={(eventId, saved) => {
                            if (!saved) {
                              setPastSavedEvents((current) => current.filter((item) => item.id !== eventId));
                            }
                          }}
                          onSelect={setOpenEvent}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      <Footer lastUpdated={lastUpdated} totalEvents={totalEvents} />

      <EventModal event={openEvent} onClose={() => setOpenEvent(null)} onAccountClick={(acct) => setSearch("@" + acct)} relatedEvents={events} onSelectEvent={setOpenEvent} />
    </div>
  );
}
