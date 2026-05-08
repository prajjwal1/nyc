"use client";

import { useEffect, useMemo, useState } from "react";
import { format, endOfWeek, eachDayOfInterval, nextSaturday } from "date-fns";
import { useEvents } from "./hooks/useEvents";
import Header from "./components/Header";
import Calendar from "./components/Calendar";
import FilterBar from "./components/FilterBar";
import EventList from "./components/EventList";
import EventCard from "./components/EventCard";
import TopPicks from "./components/TopPicks";
import EventModal from "./components/EventModal";
import { Event } from "./lib/types";
import { isSavedLocal, readAndAdvanceLastVisited } from "./lib/interests";

type View = "for-you" | "calendar";

export default function Home() {
  const {
    loading,
    events,
    selectedDate,
    setSelectedDate,
    selectedDayEvents,
    eventDates,
    categories,
    setCategories,
    sources,
    setSources,
    search,
    setSearch,
    priceFilter,
    setPriceFilter,
    sortMode,
    setSortMode,
    allSources,
    allCategories,
    lastUpdated,
    totalEvents,
    topAccounts,
  } = useEvents();

  const [view, setView] = useState<View>("for-you");
  const [presetFilter, setPresetFilter] = useState<"meet-people" | "saved" | null>(null);
  const [openEvent, setOpenEvent] = useState<Event | null>(null);
  const [lastVisitedAt, setLastVisitedAt] = useState<string | null>(null);

  // On first load, read previous-visit timestamp THEN advance it. This way
  // the current session sees the prior visit's stamp for "new since" math.
  useEffect(() => {
    setLastVisitedAt(readAndAdvanceLastVisited());
  }, []);

  // URL permalinks: read ?date=YYYY-MM-DD&view=for-you|calendar on mount
  // so users can bookmark + share specific date views.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const p = new URLSearchParams(window.location.search);
    const d = p.get("date");
    const v = p.get("view");
    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) {
      setSelectedDate(d);
      // If a date is in the URL, default to calendar view (since the
      // user is asking to see a specific day).
      if (!v || v === "calendar") setView("calendar");
    }
    if (v === "for-you" || v === "calendar") setView(v);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reflect view + selectedDate in the URL so it's bookmarkable / shareable.
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
    const q = p.toString();
    const newUrl = window.location.pathname + (q ? "?" + q : "") + window.location.hash;
    if (newUrl !== window.location.pathname + window.location.search + window.location.hash) {
      window.history.replaceState(null, "", newUrl);
    }
  }, [view, selectedDate]);

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

  const presetEvents = useMemo(() => {
    if (presetFilter === "meet-people") {
      return events.filter((e) =>
        (e.highlights || []).includes("meet-people") ||
        e.categories.includes("singles") ||
        (e.categories.includes("parties") && (e.highlights || []).some((h) => ["meet-people", "vibes", "nightlife"].includes(h)))
      );
    }
    if (presetFilter === "saved") {
      // Include both IG-saved (server signal) AND locally-saved
      // (user starred the event in browser via ★ button).
      return events.filter((e) => e.userSaved || isSavedLocal(e.id));
    }
    return events;
  }, [events, presetFilter]);

  const handleQuickFilter = (preset: string) => {
    const today = new Date();
    if (preset === "today") {
      setSelectedDate(format(today, "yyyy-MM-dd"));
      setView("calendar");
    } else if (preset === "weekend") {
      const dayOfWeek = today.getDay();
      if (dayOfWeek === 0 || dayOfWeek === 6) {
        setSelectedDate(format(today, "yyyy-MM-dd"));
      } else {
        setSelectedDate(format(nextSaturday(today), "yyyy-MM-dd"));
      }
      setView("calendar");
    } else if (preset === "week") {
      setSelectedDate(format(today, "yyyy-MM-dd"));
      setView("calendar");
    } else if (preset === "meet-people") {
      setPresetFilter(presetFilter === "meet-people" ? null : "meet-people");
      setView("for-you");
    } else if (preset === "saved") {
      setPresetFilter(presetFilter === "saved" ? null : "saved");
      setView("for-you");
    } else if (preset === "free") {
      setPriceFilter(priceFilter === "free" ? "all" : "free");
    }
  };

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
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400 text-lg">Loading events...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header totalEvents={totalEvents} lastUpdated={lastUpdated} newSinceLastVisit={newSinceLastVisit} />

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <aside className="lg:w-80 shrink-0 space-y-4 lg:space-y-6 order-2 lg:order-1">
            {/* View toggle pinned at top of sidebar (also moves to top on mobile via the sticky version below) */}
            <div className="bg-white rounded-xl border border-gray-200 p-1 flex hidden lg:flex">
              <button
                onClick={() => setView("for-you")}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  view === "for-you"
                    ? "bg-gray-900 text-white"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                For You
              </button>
              <button
                onClick={() => setView("calendar")}
                className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  view === "calendar"
                    ? "bg-gray-900 text-white"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                Calendar
              </button>
            </div>

            {view === "calendar" && (
              <Calendar
                selectedDate={selectedDate}
                onSelectDate={setSelectedDate}
                eventDates={eventDates}
                eventCountByDate={eventCountByDate}
              />
            )}
            <details className="bg-white rounded-xl border border-gray-200 lg:open lg:[&>summary]:hidden" open>
              <summary className="cursor-pointer list-none p-3 text-sm font-medium text-gray-700 flex items-center justify-between lg:hidden">
                <span>Search & Filters</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
              </summary>
              <div className="p-4 pt-0 lg:pt-4">
                <FilterBar
                  categories={categories}
                  setCategories={setCategories}
                  sources={sources}
                  setSources={setSources}
                  search={search}
                  setSearch={setSearch}
                  priceFilter={priceFilter}
                  setPriceFilter={setPriceFilter}
                  sortMode={sortMode}
                  setSortMode={setSortMode}
                  allSources={allSources}
                  allCategories={allCategories}
                  onQuickFilter={handleQuickFilter}
                />
              </div>
            </details>
          </aside>

          {/* Mobile-only view toggle, pinned above events */}
          <div className="bg-white rounded-xl border border-gray-200 p-1 flex order-1 lg:hidden">
            <button
              onClick={() => setView("for-you")}
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                view === "for-you"
                  ? "bg-gray-900 text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              For You
            </button>
            <button
              onClick={() => setView("calendar")}
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                view === "calendar"
                  ? "bg-gray-900 text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              Calendar
            </button>
          </div>

          <section className="flex-1 min-w-0 order-3 lg:order-2">
            {view === "for-you" ? (
              <>
                {presetFilter && (
                  <div className="mb-4 flex items-center justify-between bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                    <div className="text-sm">
                      <span className="font-medium text-amber-900">
                        {presetFilter === "meet-people" ? "Meet people" : "★ Saved"}
                      </span>
                      <span className="text-amber-700 ml-2">
                        — {presetEvents.length} events
                      </span>
                    </div>
                    <button
                      onClick={() => setPresetFilter(null)}
                      className="text-xs text-amber-700 hover:text-amber-900 underline"
                    >
                      clear
                    </button>
                  </div>
                )}
                <TopPicks
                  events={presetEvents}
                  onSelectDate={handleSelectDate}
                  onAccountClick={(acct) => setSearch("@" + acct)}
                  accountFilter={search.startsWith("@") ? search.slice(1) : undefined}
                  topAccounts={topAccounts}
                  onClearAccountFilter={() => setSearch("")}
                  onSelectEvent={setOpenEvent}
                />
              </>
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
    </div>
  );
}
