"use client";

import { Event, CATEGORY_CONFIG, SOURCE_LABELS } from "../lib/types";

interface EventCardProps {
  event: Event;
}

export default function EventCard({ event }: EventCardProps) {
  const timeStr = event.startTime
    ? formatTime(event.startTime) + (event.endTime ? ` - ${formatTime(event.endTime)}` : "")
    : null;

  return (
    <a
      href={event.sourceUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-all"
    >
      <div className="flex gap-4">
        {event.imageUrl && (
          <div className="shrink-0 w-16 h-16 rounded-lg overflow-hidden bg-gray-100">
            <img
              src={event.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">{event.title}</h3>

          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
            {timeStr && (
              <span className="flex items-center gap-1">
                <ClockIcon />
                {timeStr}
              </span>
            )}
            {event.location.name && (
              <span className="flex items-center gap-1 truncate">
                <PinIcon />
                {event.location.name}
                {event.location.neighborhood && (
                  <span className="text-gray-400">
                    ({event.location.neighborhood})
                  </span>
                )}
              </span>
            )}
          </div>

          {event.description && (
            <p className="mt-1.5 text-sm text-gray-500 line-clamp-2">
              {event.description}
            </p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {event.price === "free" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                Free
              </span>
            )}
            {event.price !== "free" && event.price !== "unknown" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                {event.price}
              </span>
            )}
            {event.categories
              .filter((c) => c !== "free" && c !== "other")
              .slice(0, 2)
              .map((cat) => {
                const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
                return (
                  <span
                    key={cat}
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${config.color}`}
                  >
                    {config.label}
                  </span>
                );
              })}
            <span className="text-xs text-gray-400 ml-auto">
              {SOURCE_LABELS[event.source] || event.source}
            </span>
          </div>
        </div>
      </div>
    </a>
  );
}

function formatTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return m === 0 ? `${hour} ${ampm}` : `${hour}:${m.toString().padStart(2, "0")} ${ampm}`;
}

function ClockIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function PinIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}
