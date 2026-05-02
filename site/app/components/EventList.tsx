"use client";

import { format, parseISO } from "date-fns";
import { Event } from "../lib/types";
import EventCard from "./EventCard";

interface EventListProps {
  events: Event[];
  selectedDate: string;
}

export default function EventList({ events, selectedDate }: EventListProps) {
  const dateObj = parseISO(selectedDate + "T12:00:00");
  const dateLabel = format(dateObj, "EEEE, MMMM d");

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">{dateLabel}</h2>
        <span className="text-sm text-gray-500">
          {events.length} event{events.length !== 1 ? "s" : ""}
        </span>
      </div>

      {events.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No events on this day</p>
          <p className="text-sm mt-1">Try selecting another date or adjusting filters</p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
