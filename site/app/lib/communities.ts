import { CommunitiesData, Community } from "./types";

let cache: CommunitiesData | null = null;
const COMMUNITY_DIRECTORY_STATE_KEY = "nyc-community-directory-state-v1";

export type CommunityCollectionFilter = "all" | "event_backed" | "directory_reference";

export interface CommunityDirectoryState {
  q: string;
  category: string;
  neighborhood: string;
  collection: CommunityCollectionFilter;
  firstTimers: boolean;
  followedOnly: boolean;
  availability: string[];
  showAvailability: boolean;
  displayLimit: number;
  scrollY: number;
  restoreOnReturn: boolean;
}

export function readCommunityDirectoryState(): Partial<CommunityDirectoryState> {
  if (typeof window === "undefined") return {};
  try {
    const value = JSON.parse(sessionStorage.getItem(COMMUNITY_DIRECTORY_STATE_KEY) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

export function writeCommunityDirectoryState(update: Partial<CommunityDirectoryState>) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(
      COMMUNITY_DIRECTORY_STATE_KEY,
      JSON.stringify({ ...readCommunityDirectoryState(), ...update }),
    );
  } catch {
    // Browsing still works when storage is unavailable.
  }
}

export async function loadCommunities(): Promise<CommunitiesData> {
  if (cache) return cache;
  const base = process.env.NODE_ENV === "production" ? "/nyc" : "";
  const res = await fetch(`${base}/communities.json`);
  if (!res.ok) throw new Error("Communities are not available yet");
  const body = await res.json();
  cache = Array.isArray(body) ? { communities: body } : body;
  return cache!;
}
export const communityHref = (c: Community | string) => `/communities/${typeof c === "string" ? c : c.slug}`;
export const followedCommunityIds = (): string[] => {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem("nyc-community-follows-v1") || "[]"); } catch { return []; }
};
export function toggleCommunityFollow(id: string): string[] {
  const ids = followedCommunityIds();
  const next = ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id];
  localStorage.setItem("nyc-community-follows-v1", JSON.stringify(next));
  return next;
}
