import "server-only";

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CommunitiesData, Event, EventsData } from "./types";

let eventsCache: EventsData | undefined;
let communitiesCache: CommunitiesData | undefined;

export function getEventsData(): EventsData {
  if (!eventsCache) {
    eventsCache = JSON.parse(
      readFileSync(join(process.cwd(), "public", "events.json"), "utf8"),
    ) as EventsData;
  }
  return eventsCache;
}

export function getEventById(id: string): Event | undefined {
  return getEventsData().events.find((event) => event.id === id);
}

export function getCommunitiesData(): CommunitiesData {
  if (!communitiesCache) {
    communitiesCache = JSON.parse(
      readFileSync(join(process.cwd(), "public", "communities.json"), "utf8"),
    ) as CommunitiesData;
  }
  return communitiesCache;
}

