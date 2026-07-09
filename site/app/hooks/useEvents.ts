"use client";

import { useState, useEffect, useMemo } from "react";
import { EventsData } from "../lib/types";
import { loadEvents, filterEvents, getEventDates } from "../lib/events";
import { loadProfile, interestBoost, InterestProfile } from "../lib/interests";

export function useEvents() {
  const [data, setData] = useState<EventsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [priceFilter, setPriceFilter] = useState<"all" | "free" | "paid">("all");
  const [profile, setProfile] = useState<InterestProfile | null>(null);

  useEffect(() => {
    loadEvents()
      .then(setData)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
    setProfile(loadProfile());
  }, []);

  // Re-rank events with the user's learned interest profile so the feed
  // adapts to what they actually engage with. Server-side score is the
  // base; interestBoost is small (max +0.15) so saved/tagged still win.
  // Also drop today's events whose start time clearly passed (>3h ago) —
  // a 7am yoga class shouldn't be shown at 2pm. Multi-hour events with
  // unknown end stay if they started within the last 3 hours.
  const personalizedEvents = useMemo(() => {
    if (!data) return [];
    const today = new Date().toISOString().split("T")[0];
    const now = new Date();
    const cutoffMin = now.getHours() * 60 + now.getMinutes() - 180; // 3h buffer
    const stillUpcoming = (e: typeof data.events[number]): boolean => {
      if (e.date !== today) return true;       // not today — irrelevant
      if (!e.startTime) return true;           // no time — keep
      const parts = e.startTime.split(":");
      if (parts.length < 2) return true;
      const eMin = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      if (Number.isNaN(eMin)) return true;
      return eMin >= cutoffMin;                // started <3h ago or later
    };
    const upcoming = data.events.filter(stillUpcoming);
    if (!profile) return upcoming;
    return upcoming.map((e) => ({
      ...e,
      score: (e.score ?? 0) + interestBoost(e, profile),
    }));
  }, [data, profile]);

  const filteredEvents = useMemo(() => {
    return filterEvents(personalizedEvents, { categories, search, priceFilter });
  }, [personalizedEvents, categories, search, priceFilter]);

  const eventDates = useMemo(() => getEventDates(filteredEvents), [filteredEvents]);

  const selectedDayEvents = useMemo(() => {
    const dayEvents = filteredEvents.filter((e) => e.date === selectedDate);
    return [...dayEvents].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  }, [filteredEvents, selectedDate]);

  const allCategories = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.events.flatMap((e) => e.categories))].sort();
  }, [data]);

  const refreshProfile = () => setProfile(loadProfile());

  return {
    loading,
    loadError,
    events: filteredEvents,
    selectedDate,
    setSelectedDate,
    selectedDayEvents,
    eventDates,
    categories,
    setCategories,
    search,
    setSearch,
    priceFilter,
    setPriceFilter,
    allCategories,
    lastUpdated: data?.lastUpdated,
    totalEvents: data?.events.length ?? 0,
    topAccounts: data?.topAccounts,
    refreshProfile,
  };
}
