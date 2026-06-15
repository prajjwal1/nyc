import { Event, EventsData } from "./types";

let cachedData: EventsData | null = null;

export async function loadEvents(): Promise<EventsData> {
  if (cachedData) return cachedData;

  const res = await fetch(`${process.env.NODE_ENV === "production" ? "/nyc" : ""}/events.json`);
  cachedData = await res.json();
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
    categories?: string[];
    search?: string;
    priceFilter?: "all" | "free" | "paid";
  }
): Event[] {
  let filtered = events;

  if (filters.categories && filters.categories.length > 0) {
    filtered = filtered.filter((e) =>
      e.categories.some((c) => filters.categories!.includes(c))
    );
  }

  if (filters.search) {
    const q = filters.search.toLowerCase();
    // Allow @username searches
    const accountQuery = q.startsWith("@") ? q.slice(1) : null;
    filtered = filtered.filter((e) => {
      if (accountQuery) {
        return (
          (e.instagramAccount || "").toLowerCase().includes(accountQuery) ||
          (e.account || "").toLowerCase().includes(accountQuery)
        );
      }
      return (
        e.title.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.location.name.toLowerCase().includes(q) ||
        (e.location.address || "").toLowerCase().includes(q) ||
        (e.location.neighborhood || "").toLowerCase().includes(q) ||
        (e.instagramAccount || "").toLowerCase().includes(q) ||
        e.categories.some((c) => c.toLowerCase().includes(q))
      );
    });
  }

  if (filters.priceFilter === "free") {
    filtered = filtered.filter((e) => e.price === "free");
  } else if (filters.priceFilter === "paid") {
    filtered = filtered.filter((e) => e.price !== "free" && e.price !== "unknown");
  }

  return filtered;
}
