"use client";

import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
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
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => canGoBack && setCurrentMonth(subMonths(currentMonth, 1))}
          disabled={!canGoBack}
          aria-label="Previous month"
          className={`p-1.5 rounded-lg focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none ${
            canGoBack
              ? "hover:bg-gray-100 text-gray-600"
              : "text-gray-200 cursor-not-allowed"
          }`}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 className="text-lg font-semibold text-gray-900">
          {format(currentMonth, "MMMM yyyy")}
        </h2>
        <button
          onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          aria-label="Next month"
          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-600 focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-7 gap-0">
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <div key={d} className="text-center text-xs font-medium text-gray-400 py-2">
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
          // Past dates aren't selectable — the feed is today-onwards only.
          const isPast = dateStr < todayStr;

          return (
            <button
              key={dateStr}
              onClick={() => !isPast && onSelectDate(dateStr)}
              disabled={isPast}
              aria-label={isPast ? `${dateStr} (past)` : dateStr}
              className={`
                relative py-2 text-sm rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-sky-500 focus:outline-none
                ${isPast ? "text-gray-200 cursor-not-allowed" : !inMonth ? "text-gray-300" : "text-gray-700"}
                ${isSelected ? "bg-gray-900 text-white font-semibold" : isPast ? "" : "hover:bg-gray-50"}
                ${isToday && !isSelected ? "font-bold text-gray-900 ring-1 ring-gray-300" : ""}
              `}
            >
              {format(day, "d")}
              {hasEvents && (
                <span
                  className={`absolute bottom-0.5 left-1/2 -translate-x-1/2 flex gap-0.5 ${
                    isSelected ? "text-white" : ""
                  }`}
                >
                  {count <= 3 ? (
                    Array.from({ length: Math.min(count, 3) }).map((_, i) => (
                      <span
                        key={i}
                        className={`w-1 h-1 rounded-full ${
                          isSelected ? "bg-white" : "bg-gray-900"
                        }`}
                      />
                    ))
                  ) : (
                    <span
                      className={`text-[9px] leading-none font-medium ${
                        isSelected ? "text-white/80" : "text-gray-500"
                      }`}
                    >
                      {count}
                    </span>
                  )}
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
        className="mt-3 w-full text-center text-sm text-gray-500 hover:text-gray-900 py-1"
      >
        Today
      </button>
    </div>
  );
}
