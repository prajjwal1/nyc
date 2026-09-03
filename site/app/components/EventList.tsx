"use client";

import { format, parseISO } from "date-fns";
import { Event } from "../lib/types";
import EventCard from "./EventCard";

interface EventListProps {
  events: Event[];
  selectedDate: string;
  onAccountClick?: (account: string) => void;
}

export default function EventList({ events, selectedDate, onAccountClick }: EventListProps) {
  const dateObj = parseISO(selectedDate + "T12:00:00");
  const dateLabel = format(dateObj, "EEEE, MMMM d");

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3 border-b border-[#d8d0c1] pb-3">
        <h2 className="font-editorial text-xl font-bold text-[#173c35] sm:text-2xl">{dateLabel}</h2>
        <span className="shrink-0 rounded-full bg-[#eee8da] px-2.5 py-1 text-xs font-medium text-[#66716c]">
          {events.length} event{events.length !== 1 ? "s" : ""}
        </span>
      </div>

      {events.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No events on this day</p>
          <p className="text-sm mt-1">Try another date — scroll the calendar for busier days</p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event, index) => (
            <div
              key={event.id}
              data-event-id={event.id}
              data-calendar-section={selectedDate}
              data-rank={index + 1}
            >
              <EventCard event={event} onAccountClick={onAccountClick} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
