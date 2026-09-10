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
      <div className="mb-5 flex items-end justify-between gap-3 border-b border-[#d8d8d1] pb-4">
        <h2 className="font-editorial text-[28px] leading-none tracking-[-0.025em] text-[#173c35] sm:text-[34px]">{dateLabel}</h2>
        <span className="shrink-0 pb-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#7b8580]">
          {events.length} event{events.length !== 1 ? "s" : ""}
        </span>
      </div>

      {events.length === 0 ? (
        <div className="rounded-[20px] border border-dashed border-[#cfcec7] bg-[#fbfaf7]/70 px-6 py-14 text-center text-[#8a918d]">
          <p className="font-editorial text-2xl text-[#3f514b]">No events have landed yet</p>
          <p className="mt-2 text-sm">Today stays selected while the feed refreshes.</p>
        </div>
      ) : (
        <div className="space-y-3.5">
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
