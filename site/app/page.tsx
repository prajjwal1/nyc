"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { format } from "date-fns";
import { useEvents } from "./hooks/useEvents";
import Header from "./components/Header";
import Calendar from "./components/Calendar";
import EventList from "./components/EventList";
import { Event } from "./lib/types";
import { readAndAdvanceLastVisited } from "./lib/interests";
import Footer from "./components/Footer";

export default function Home() {
  const {
    loading,
    loadError,
    events,
    selectedDate,
    setSelectedDate,
    selectedDayEvents,
    eventDates,
    accountFilter,
    setAccountFilter,
    lastUpdated,
    totalEvents,
  } = useEvents();

  const [lastVisitedAt, setLastVisitedAt] = useState<string | null>(null);
  const explicitDateRef = useRef(false);
  const initialDateResolvedRef = useRef(false);

  useEffect(() => {
    queueMicrotask(() => setLastVisitedAt(readAndAdvanceLastVisited()));
  }, []);

  // Date and account views remain bookmarkable. The old `view` parameter is
  // deliberately ignored and removed because Calendar is now the homepage.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const date = params.get("date");
    const account = params.get("account");
    if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
      explicitDateRef.current = true;
    }
    queueMicrotask(() => {
      if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) setSelectedDate(date);
      if (account && account.trim().length <= 80) setAccountFilter(account.trim());
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // If today is empty, open the next date that actually has events. This
  // happens once only; later empty-date selections remain under user control.
  useEffect(() => {
    if (loading || initialDateResolvedRef.current) return;
    initialDateResolvedRef.current = true;
    if (explicitDateRef.current || eventDates.has(selectedDate)) return;
    const today = format(new Date(), "yyyy-MM-dd");
    const nextDate = [...eventDates].filter((date) => date >= today).sort()[0];
    if (nextDate) setSelectedDate(nextDate);
  }, [loading, eventDates, selectedDate, setSelectedDate]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    params.delete("view");
    params.set("date", selectedDate);
    if (accountFilter) params.set("account", accountFilter);
    else params.delete("account");

    const query = params.toString();
    const nextUrl = window.location.pathname + (query ? `?${query}` : "") + window.location.hash;
    const currentUrl = window.location.pathname + window.location.search + window.location.hash;
    if (nextUrl !== currentUrl) window.history.replaceState(null, "", nextUrl);
  }, [selectedDate, accountFilter]);

  const newSinceLastVisit = useMemo(() => {
    if (!lastVisitedAt) return 0;
    const cutoff = new Date(lastVisitedAt).getTime();
    return events.filter((event) => {
      const firstSeenAt = (event as Event & { firstSeenAt?: string }).firstSeenAt;
      if (!firstSeenAt) return false;
      const firstSeen = new Date(firstSeenAt).getTime();
      return Number.isFinite(firstSeen) && firstSeen > cutoff;
    }).length;
  }, [events, lastVisitedAt]);

  const eventCountByDate = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) counts.set(event.date, (counts.get(event.date) || 0) + 1);
    return counts;
  }, [events]);

  const thisWeekCount = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const cutoff = new Date(today);
    cutoff.setDate(today.getDate() + 7);
    const start = format(today, "yyyy-MM-dd");
    const end = format(cutoff, "yyyy-MM-dd");
    return events.filter((event) => event.date >= start && event.date < end).length;
  }, [events]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f8f3e8]">
        <Header totalEvents={0} thisWeekCount={0} lastUpdated={undefined} newSinceLastVisit={0} />
        <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
          <p className="mb-5 max-w-2xl text-sm leading-6 text-[#66716c]">
            Discover curated events and things to do today, tonight, and this weekend across Brooklyn, Manhattan, Queens, and the rest of New York City.
          </p>
          <div className="mb-6 h-14 animate-pulse rounded-lg bg-[#e7e1d2]" />
          <div className="grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
            <div className="h-[22rem] animate-pulse rounded-xl border border-[#ded7c9] bg-[#fffdf8]" />
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <div key={index} className="h-28 animate-pulse rounded-xl border border-[#ded7c9] bg-[#fffdf8]" />
              ))}
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
        <div className="text-lg font-semibold text-gray-700">Couldn&apos;t load events</div>
        <p className="max-w-sm text-sm text-gray-500">
          The calendar failed to load. It may be a temporary network issue — please refresh.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-1 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
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

      <main className="mx-auto max-w-5xl px-4 py-3 sm:px-6 sm:py-6">
        {accountFilter && (
          <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-[#c9d8d2] bg-[#edf5f1] px-3 py-2">
            <span className="truncate text-xs font-semibold text-[#31554c]">
              Showing @{accountFilter} · {events.length} events
            </span>
            <button
              onClick={() => setAccountFilter("")}
              className="shrink-0 rounded-full px-2 py-1 text-xs font-semibold text-[#9a684e] hover:bg-white/70"
            >
              Clear
            </button>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)] lg:gap-6">
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <Calendar
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
              eventDates={eventDates}
              eventCountByDate={eventCountByDate}
            />
          </aside>

          <section aria-label="Events for selected date" className="min-w-0">
            <EventList
              events={selectedDayEvents}
              selectedDate={selectedDate}
              onAccountClick={setAccountFilter}
            />
          </section>
        </div>
      </main>

      <Footer />
    </div>
  );
}
