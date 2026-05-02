"use client";

interface HeaderProps {
  totalEvents: number;
  lastUpdated?: string;
}

export default function Header({ totalEvents, lastUpdated }: HeaderProps) {
  const updatedStr = lastUpdated
    ? new Date(lastUpdated).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">NYC Events</h1>
            <p className="text-sm text-gray-500">
              {totalEvents} events from across the city
            </p>
          </div>
          {updatedStr && (
            <p className="text-xs text-gray-400">Updated {updatedStr}</p>
          )}
        </div>
      </div>
    </header>
  );
}
