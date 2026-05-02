"use client";

import { format, parseISO } from "date-fns";
import { Event } from "../lib/types";
import EventCard from "./EventCard";

interface TopPicksProps {
  events: Event[];
  onSelectDate: (date: string) => void;
}

export default function TopPicks({ events, onSelectDate }: TopPicksProps) {
  const todayStr = format(new Date(), "yyyy-MM-dd");
  const upcoming = events
    .filter((e) => e.date >= todayStr)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 12);

  if (upcoming.length === 0) return null;

  const grouped = new Map<string, Event[]>();
  for (const e of upcoming) {
    const list = grouped.get(e.date) ?? [];
    list.push(e);
    grouped.set(e.date, list);
  }

  const sortedDates = [...grouped.keys()].sort();

  return (
    <div className="mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">For You</h2>
          <p className="text-sm text-gray-500">
            The best of NYC, picked for your interests
          </p>
        </div>
      </div>

      <div className="space-y-5">
        {sortedDates.map((date) => {
          const dateObj = parseISO(date + "T12:00:00");
          const isToday = date === todayStr;
          const dayEvents = grouped.get(date)!;
          return (
            <div key={date}>
              <button
                onClick={() => onSelectDate(date)}
                className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 hover:text-gray-700"
              >
                {isToday ? "Today" : format(dateObj, "EEEE, MMM d")}
              </button>
              <div className="space-y-2">
                {dayEvents.map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
