import { Event, EventsData } from "./types";

let cachedData: EventsData | null = null;

export async function loadEvents(): Promise<EventsData> {
  if (cachedData) return cachedData;

  const res = await fetch(`${process.env.NODE_ENV === "production" ? "/nyc" : ""}/events.json`);
  const payload: EventsData = await res.json();
  // Keep an explicit product opt-out from resurfacing through an older
  // published snapshot while the crawler transition rolls out.
  cachedData = {
    ...payload,
    events: payload.events.filter((event) => event.source !== "meetup"),
  };
  return cachedData!;
}

export function getEventsForDate(events: Event[], date: string): Event[] {
  return events.filter((e) => e.date === date);
}

export function getEventDates(events: Event[]): Set<string> {
  return new Set(events.map((e) => e.date));
}

export function filterEvents(
  events: Event[],
  filters: {
    account?: string;
  }
): Event[] {
  let filtered = events;

  if (filters.account) {
    const accountQuery = filters.account.trim().replace(/^@/, "").toLowerCase();
    filtered = filtered.filter((e) => {
      const accounts = [
        e.instagramAccount,
        e.account,
        e.organizer,
        ...(e.contributingAccounts || []),
      ];
      return accounts.some((account) =>
        (account || "").trim().replace(/^@/, "").toLowerCase() === accountQuery
      );
    });
  }

  return filtered;
}
