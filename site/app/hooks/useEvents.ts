"use client";

import { useState, useEffect, useMemo } from "react";
import { format } from "date-fns";
import { EventsData } from "../lib/types";
import { loadEvents, filterEvents, getEventDates } from "../lib/events";
import {
  loadProfile,
  interestBoost,
  interestReason,
  InterestProfile,
  loadHiddenIds,
  PROFILE_CHANGE_EVENT,
} from "../lib/interests";

export function useEvents() {
  const [data, setData] = useState<EventsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string>(
    format(new Date(), "yyyy-MM-dd")
  );
  const [accountFilter, setAccountFilter] = useState("");
  const [profile, setProfile] = useState<InterestProfile | null>(null);

  useEffect(() => {
    loadEvents()
      .then(setData)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
    queueMicrotask(() => setProfile(loadProfile()));
  }, []);

  useEffect(() => {
    const refresh = () => setProfile(loadProfile());
    window.addEventListener(PROFILE_CHANGE_EVENT, refresh);
    return () => window.removeEventListener(PROFILE_CHANGE_EVENT, refresh);
  }, []);

  // Re-rank events with the user's learned interest profile so the calendar
  // adapts to what they actually engage with. Server-side score is the
  // base; interestBoost is small (max +0.15) so saved/tagged still win.
  // Also drop today's events whose start time clearly passed (>3h ago) —
  // a 7am yoga class shouldn't be shown at 2pm. Multi-hour events with
  // unknown end stay if they started within the last 3 hours.
  const personalizedEvents = useMemo(() => {
    if (!data) return [];
    const today = format(new Date(), "yyyy-MM-dd");
    const now = new Date();
    const cutoffMin = now.getHours() * 60 + now.getMinutes() - 180; // 3h buffer
    const stillUpcoming = (e: typeof data.events[number]): boolean => {
      if (e.date < today) return false;        // past date — never show
      if (e.date !== today) return true;       // future date — keep
      if (!e.startTime) return true;           // no time — keep
      const parts = e.startTime.split(":");
      if (parts.length < 2) return true;
      const eMin = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      if (Number.isNaN(eMin)) return true;
      return eMin >= cutoffMin;                // started <3h ago or later
    };
    const hidden = loadHiddenIds();
    const upcoming = data.events
      .filter(stillUpcoming)
      .filter((event) => !hidden.has(event.id));
    if (!profile) return upcoming;
    return upcoming.map((e) => {
      const reason = interestReason(e, profile);
      return {
        ...e,
        score: (e.score ?? 0) + interestBoost(e, profile),
        recommendationReasons: reason
          ? [reason, ...(e.recommendationReasons || []).filter((item) => item !== reason)].slice(0, 3)
          : e.recommendationReasons,
      };
    });
  }, [data, profile]);

  const filteredEvents = useMemo(() => {
    return filterEvents(personalizedEvents, { account: accountFilter });
  }, [personalizedEvents, accountFilter]);

  const eventDates = useMemo(() => getEventDates(filteredEvents), [filteredEvents]);

  const selectedDayEvents = useMemo(() => {
    const dayEvents = filteredEvents.filter((e) => e.date === selectedDate);
    return [...dayEvents].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  }, [filteredEvents, selectedDate]);

  const refreshProfile = () => setProfile(loadProfile());

  return {
    loading,
    loadError,
    events: filteredEvents,
    selectedDate,
    setSelectedDate,
    selectedDayEvents,
    eventDates,
    accountFilter,
    setAccountFilter,
    lastUpdated: data?.lastUpdated,
    totalEvents: data?.events.length ?? 0,
    refreshProfile,
  };
}
