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
          // Sort each day's events by score, take top N
          const dayEvents = grouped
            .get(date)!
            .slice()
            .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
            .slice(0, MAX_PER_DAY);
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
