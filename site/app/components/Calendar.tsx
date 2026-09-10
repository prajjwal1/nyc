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
  // Don't let the user browse into the past — the calendar only shows events from
  // today onwards, so backward calendar navigation would land on empty months.
  const thisMonthStart = startOfMonth(today);
  const canGoBack = isAfter(currentMonth, thisMonthStart);

  return (
    <div className="rounded-[22px] border border-[#dedbd3] bg-[#fbfaf7] p-4 shadow-[0_18px_45px_-34px_rgba(20,45,37,0.48)] sm:p-5">
      <div className="mb-4 flex items-center justify-between sm:mb-5">
        <button
          onClick={() => canGoBack && setCurrentMonth(subMonths(currentMonth, 1))}
          disabled={!canGoBack}
          aria-label="Previous month"
          className={`grid h-9 w-9 place-items-center rounded-full border transition focus-visible:ring-2 focus-visible:ring-[#173c35]/20 focus:outline-none ${
            canGoBack
              ? "border-transparent bg-[#efeee9] text-[#5d6964] hover:bg-[#e4e6e0] hover:text-[#173c35]"
              : "border-transparent text-[#d6d3c9] cursor-not-allowed"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 className="font-editorial text-[21px] leading-none tracking-[-0.025em] text-[#173c35]">
          {format(currentMonth, "MMMM yyyy")}
        </h2>
        <button
          onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          aria-label="Next month"
          className="grid h-9 w-9 place-items-center rounded-full border border-transparent bg-[#efeee9] text-[#5d6964] transition hover:bg-[#e4e6e0] hover:text-[#173c35] focus-visible:ring-2 focus-visible:ring-[#173c35]/20 focus:outline-none"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-7 gap-0">
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <div key={d} className="py-2 text-center text-[9px] font-semibold uppercase tracking-[0.13em] text-[#989e99]">
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
                relative grid h-9 w-full place-items-center rounded-[11px] text-[13px] font-medium transition focus-visible:ring-2 focus-visible:ring-[#173c35]/20 focus:outline-none sm:h-10
                ${isPast ? "text-[#d6d3c9] cursor-not-allowed" : !inMonth ? "text-[#c1beb6]" : "text-[#3a4d48]"}
                ${isSelected ? "bg-[#173c35] text-white font-semibold shadow-[0_7px_16px_-8px_rgba(23,60,53,0.8)]" : isPast ? "" : "hover:bg-[#edeee9]"}
                ${isToday && !isSelected ? "font-semibold text-[#173c35] ring-1 ring-[#89a097]/55" : ""}
              `}
            >
              {format(day, "d")}
              {hasEvents && !isSelected && (
                <span className="absolute bottom-0.5 left-1/2 flex -translate-x-1/2 gap-0.5">
                  {count <= 3 ? (
                    Array.from({ length: Math.min(count, 3) }).map((_, i) => (
                      <span key={i} className="h-1 w-1 rounded-full bg-[#ad5b3d]/75" />
                    ))
                  ) : (
                    <span className="text-[8px] font-semibold leading-none text-[#6b7570]">{count}</span>
                  )}
                </span>
              )}
              {hasEvents && isSelected && count > 0 && (
                <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full border border-[#173c35] bg-[#fbfaf7] px-1 text-[9px] font-bold text-[#173c35]">
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
        className="mt-4 w-full rounded-full border border-[#d8d8d1] bg-transparent py-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5d6964] transition hover:border-[#9caaa4] hover:bg-white hover:text-[#173c35]"
      >
        Today
      </button>
    </div>
  );
}
