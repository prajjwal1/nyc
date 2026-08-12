"use client";

import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameMonth,
  addMonths,
  subMonths,
  isAfter,
} from "date-fns";
import { useState } from "react";

interface CalendarProps {
  selectedDate: string;
  onSelectDate: (date: string) => void;
  eventDates: Set<string>;
  eventCountByDate: Map<string, number>;
}

export default function Calendar({
  selectedDate,
  onSelectDate,
  eventDates,
  eventCountByDate,
}: CalendarProps) {
  const [currentMonth, setCurrentMonth] = useState(
    startOfMonth(new Date(selectedDate + "T12:00:00"))
  );

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calStart = startOfWeek(monthStart);
  const calEnd = endOfWeek(monthEnd);
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const today = new Date();
  const todayStr = format(today, "yyyy-MM-dd");
  // Don't let the user browse into the past — the feed only shows events from
  // today onwards, so backward calendar navigation would land on empty months.
  const thisMonthStart = startOfMonth(today);
  const canGoBack = isAfter(currentMonth, thisMonthStart);

  return (
    <div className="rounded-[1.5rem] border border-[#ddd9cc] bg-[#fffef9] p-4 shadow-[0_1px_0_rgba(23,58,49,0.03)]">
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={() => canGoBack && setCurrentMonth(subMonths(currentMonth, 1))}
          disabled={!canGoBack}
          aria-label="Previous month"
          className={`grid h-8 w-8 place-items-center rounded-full border focus-visible:ring-2 focus-visible:ring-[#173c35]/20 focus:outline-none ${
            canGoBack
              ? "border-[#d7d5cd] bg-white text-[#5d6964] hover:border-[#173c35] hover:text-[#173c35]"
              : "border-transparent text-[#d6d3c9] cursor-not-allowed"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 className="font-editorial text-[16px] font-semibold text-[#173c35]">
          {format(currentMonth, "MMMM yyyy")}
        </h2>
        <button
          onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          aria-label="Next month"
          className="grid h-8 w-8 place-items-center rounded-full border border-[#d7d5cd] bg-white text-[#5d6964] hover:border-[#173c35] hover:text-[#173c35] focus-visible:ring-2 focus-visible:ring-[#173c35]/20 focus:outline-none"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-7 gap-0">
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <div key={d} className="py-2 text-center text-[10px] font-semibold uppercase tracking-wide text-[#9a9d98]">
            {d}
          </div>
        ))}

        {days.map((day) => {
          const dateStr = format(day, "yyyy-MM-dd");
          const isSelected = dateStr === selectedDate;
          const isToday = dateStr === todayStr;
          const inMonth = isSameMonth(day, currentMonth);
          const hasEvents = eventDates.has(dateStr);
          const count = eventCountByDate.get(dateStr) || 0;
          const isPast = dateStr < todayStr;

          return (
            <button
              key={dateStr}
              onClick={() => !isPast && onSelectDate(dateStr)}
              disabled={isPast}
              aria-label={isPast ? `${dateStr} (past)` : `${dateStr}, ${count} events`}
              className={`
                relative grid h-9 w-full place-items-center rounded-full text-sm transition focus-visible:ring-2 focus-visible:ring-[#173c35]/20 focus:outline-none
                ${isPast ? "text-[#d6d3c9] cursor-not-allowed" : !inMonth ? "text-[#c1beb6]" : "text-[#3a4d48]"}
                ${isSelected ? "bg-[#173c35] text-white font-semibold shadow-sm" : isPast ? "" : "hover:bg-[#f4f1e8]"}
                ${isToday && !isSelected ? "font-bold text-[#173c35] ring-1 ring-[#173c35]/30" : ""}
              `}
            >
              {format(day, "d")}
              {hasEvents && !isSelected && (
                <span className="absolute bottom-0.5 left-1/2 flex -translate-x-1/2 gap-0.5">
                  {count <= 3 ? (
                    Array.from({ length: Math.min(count, 3) }).map((_, i) => (
                      <span key={i} className="h-1 w-1 rounded-full bg-[#173c35]/60" />
                    ))
                  ) : (
                    <span className="text-[8px] font-semibold leading-none text-[#6b7570]">{count}</span>
                  )}
                </span>
              )}
              {hasEvents && isSelected && count > 0 && (
                <span className="absolute -top-1 -right-1 grid h-4 min-w-4 place-items-center rounded-full bg-white px-1 text-[9px] font-bold text-[#173c35] border border-[#173c35]">
                  {count > 9 ? "9+" : count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <button
        onClick={() => {
          setCurrentMonth(startOfMonth(today));
          onSelectDate(todayStr);
        }}
        className="mt-4 w-full rounded-full border border-[#d7d5cd] bg-white py-2 text-xs font-medium text-[#5d6964] hover:border-[#173c35] hover:text-[#173c35]"
      >
        Today
      </button>
    </div>
  );
}
