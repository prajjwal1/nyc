"use client";

import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import EventCard from "../components/EventCard";
import Footer from "../components/Footer";
import { loadEvents } from "../lib/events";
import { isSavedLocal, loadSavedStubs, savedStubToEvent } from "../lib/interests";
import type { Event } from "../lib/types";
import EventModal from "../components/EventModal";

export default function SavedPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [openEvent, setOpenEvent] = useState<Event | null>(null);

  useEffect(() => {
    loadEvents()
      .then((eventData) => {
        const savedStubs = loadSavedStubs();
        // Prefer live event data, but keep stub data for past saves that fell out of events.json
        const liveMap = new Map(eventData.events.map((e) => [e.id, e]));
        const merged: Event[] = savedStubs.map((stub) => liveMap.get(stub.id) || savedStubToEvent(stub));
        // Also include any live events that are saved but not in stubs yet (race)
        for (const ev of eventData.events) {
          if (isSavedLocal(ev.id) && !merged.find((m) => m.id === ev.id)) merged.push(ev);
        }
        setEvents(merged);
      })
      .finally(() => setLoading(false));
  }, []);

  const todayStr = format(new Date(), "yyyy-MM-dd");
  const upcoming = useMemo(
    () => [...events].filter((e) => e.date >= todayStr).sort((a, b) => `${a.date}${a.startTime || ""}`.localeCompare(`${b.date}${b.startTime || ""}`)),
    [events, todayStr],
  );
  const past = useMemo(
    () => [...events].filter((e) => e.date < todayStr).sort((a, b) => b.date.localeCompare(a.date)),
    [events, todayStr],
  );

  return (
    <div className="min-h-screen bg-[#f8f3e8]">
      <main className="px-4 py-10 sm:px-6">
        <div className="mx-auto max-w-5xl">
          <p className="text-[10px] font-bold uppercase tracking-[.22em] text-[#bd4f34]">Your city — private to this browser</p>
          <h1 className="font-editorial mt-3 text-5xl font-bold tracking-[-0.03em] text-[#173c35] sm:text-6xl">Saved for later.</h1>
          <p className="mt-4 max-w-xl text-[15px] leading-6 text-[#5d6964]">
            Events you starred, kept privately in this browser.
          </p>

          {loading ? (
            <div className="mt-12 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-24 animate-pulse rounded-xl bg-[#ece5d8]" />
              ))}
            </div>
          ) : (
            <>
              <section className="mt-12">
                <div className="flex items-baseline justify-between">
                  <h2 className="font-editorial text-2xl font-bold tracking-[-0.01em] text-[#173c35] sm:text-3xl">
                    Saved events · upcoming
                  </h2>
                  <span className="text-xs text-[#8b918e]">{upcoming.length}</span>
                </div>
                {upcoming.length ? (
                  <div className="mt-5 space-y-3">
                    {upcoming.map((event) => (
                      <EventCard
                        key={event.id}
                        event={event}
                        showDay
                        onSaveChange={(eventId, saved) => {
                          if (!saved) setEvents((current) => current.filter((item) => item.id !== eventId));
                        }}
                        onSelect={setOpenEvent}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="mt-4 rounded-[1.25rem] border border-dashed border-[#d7d5cd] bg-[#fffef9] p-6">
                    <p className="text-sm font-medium text-[#173c35]">No upcoming saves.</p>
                    <p className="mt-1 text-sm text-[#66716c]">Events you star will appear here, with quick add-to-calendar.</p>
                  </div>
                )}
              </section>

              {past.length > 0 && (
                <section className="mt-14">
                  <h2 className="font-editorial text-2xl font-bold tracking-[-0.01em] text-[#3a4d48] sm:text-3xl">Past saves</h2>
                  <div className="mt-5 space-y-3">
                    {past.map((event) => (
                      <EventCard
                        key={event.id}
                        event={event}
                        showDay
                        onSaveChange={(eventId, saved) => {
                          if (!saved) setEvents((current) => current.filter((item) => item.id !== eventId));
                        }}
                        onSelect={setOpenEvent}
                      />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>
      <Footer />
      <EventModal event={openEvent} onClose={() => setOpenEvent(null)} onAccountClick={() => {}} relatedEvents={events} onSelectEvent={setOpenEvent} />
    </div>
  );
}
