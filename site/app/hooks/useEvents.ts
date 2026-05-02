"use client";

import { useState, useEffect, useMemo } from "react";
import { Event, EventsData } from "../lib/types";
import { loadEvents, filterEvents, getEventDates } from "../lib/events";

export type SortMode = "relevance" | "time";

export function useEvents() {
  const [data, setData] = useState<EventsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [categories, setCategories] = useState<string[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [priceFilter, setPriceFilter] = useState<"all" | "free" | "paid">("all");
  const [sortMode, setSortMode] = useState<SortMode>("relevance");

  useEffect(() => {
    loadEvents()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    return filterEvents(data.events, { categories, sources, search, priceFilter });
  }, [data, categories, sources, search, priceFilter]);

  const eventDates = useMemo(() => getEventDates(filteredEvents), [filteredEvents]);

  const selectedDayEvents = useMemo(() => {
    const dayEvents = filteredEvents.filter((e) => e.date === selectedDate);
    if (sortMode === "relevance") {
      return [...dayEvents].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    }
    return [...dayEvents].sort((a, b) =>
      (a.startTime || "99:99").localeCompare(b.startTime || "99:99")
    );
  }, [filteredEvents, selectedDate, sortMode]);

  const allSources = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.events.map((e) => e.source))].sort();
  }, [data]);

  const allCategories = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.events.flatMap((e) => e.categories))].sort();
  }, [data]);

  return {
    loading,
    events: filteredEvents,
    selectedDate,
    setSelectedDate,
    selectedDayEvents,
    eventDates,
    categories,
    setCategories,
    sources,
    setSources,
    search,
    setSearch,
    priceFilter,
    setPriceFilter,
    sortMode,
    setSortMode,
    allSources,
    allCategories,
    lastUpdated: data?.lastUpdated,
    totalEvents: data?.events.length ?? 0,
  };
}
