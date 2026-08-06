import { CommunitiesData, Community } from "./types";

let cache: CommunitiesData | null = null;
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
