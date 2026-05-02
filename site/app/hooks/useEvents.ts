"use client";

import { useState, useEffect, useMemo } from "react";
import { Event, EventsData } from "../lib/types";
import { loadEvents, filterEvents, getEventDates } from "../lib/events";

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

  const selectedDayEvents = useMemo(
    () => filteredEvents.filter((e) => e.date === selectedDate),
    [filteredEvents, selectedDate]
  );

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
    allSources,
    allCategories,
    lastUpdated: data?.lastUpdated,
    totalEvents: data?.events.length ?? 0,
  };
}
