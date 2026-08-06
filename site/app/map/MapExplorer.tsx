"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import CommunityMap, { type MappableCommunity } from "./CommunityMap";

type CommunityPayload = { communities?: Community[] } | Community[];

interface Community {
  id: string;
  slug?: string;
  name: string;
  description?: string;
  tagline?: string;
  shortDescription?: string;
  type?: string;
  communityType?: string;
  kind?: string;
  categories?: string[];
  interests?: string[];
  neighborhood?: string;
  neighborhoods?: string[];
  location?: {
    name?: string;
    neighborhood?: string;
    latitude?: number;
    longitude?: number;
    lat?: number;
    lng?: number;
    approximate?: boolean;
    precision?: string;
  };
  coordinates?: { latitude?: number; longitude?: number; lat?: number; lng?: number };
  latitude?: number;
  longitude?: number;
  upcomingEventCount?: number;
  nextEvent?: { title?: string; date?: string };
  activityStatus?: string;
}

const DATA_URL = `${process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/nyc" : "")}/communities.json`;

// Neighborhood-level fallbacks deliberately trade precision for privacy. These
// are only used when a community publishes an area but not an exact venue.
const NEIGHBORHOOD_CENTERS: Record<string, [number, number]> = {
  "astoria": [40.7644, -73.9235], "bed-stuy": [40.6872, -73.9418], "bedford-stuyvesant": [40.6872, -73.9418],
  "bensonhurst": [40.6113, -73.9977], "boerum hill": [40.6857, -73.9842], "borough park": [40.6339, -73.9968],
  "brooklyn": [40.6782, -73.9442], "bushwick": [40.6944, -73.9213], "carroll gardens": [40.6800, -73.9991],
  "chelsea": [40.7465, -74.0014], "chinatown": [40.7158, -73.9970], "cobble hill": [40.6875, -73.9957],
  "crown heights": [40.6681, -73.9448], "ditmas park": [40.6409, -73.9624], "downtown brooklyn": [40.6960, -73.9845],
  "east village": [40.7265, -73.9815], "east williamsburg": [40.7142, -73.9387], "financial district": [40.7075, -74.0113],
  "flatbush": [40.6409, -73.9624], "flushing": [40.7675, -73.8331], "fort greene": [40.6914, -73.9758],
  "gowanus": [40.6733, -73.9903], "greenpoint": [40.7305, -73.9546], "harlem": [40.8116, -73.9465],
  "hell's kitchen": [40.7638, -73.9918], "jackson heights": [40.7557, -73.8831], "jersey city": [40.7178, -74.0431],
  "long island city": [40.7447, -73.9485], "lower east side": [40.7180, -73.9885], "manhattan": [40.7831, -73.9712],
  "park slope": [40.6710, -73.9814], "prospect heights": [40.6774, -73.9720], "queens": [40.7282, -73.7949],
  "ridgewood": [40.7044, -73.9018], "soho": [40.7233, -74.0030], "sunset park": [40.6455, -74.0124],
  "tribeca": [40.7163, -74.0086], "upper east side": [40.7736, -73.9566], "upper west side": [40.7870, -73.9754],
  "washington heights": [40.8417, -73.9394], "west village": [40.7340, -74.0067], "williamsburg": [40.7081, -73.9571],
};

function pointFor(community: Community): MappableCommunity | null {
  let latitude = community.location?.latitude ?? community.location?.lat
    ?? community.coordinates?.latitude ?? community.coordinates?.lat ?? community.latitude;
  let longitude = community.location?.longitude ?? community.location?.lng
    ?? community.coordinates?.longitude ?? community.coordinates?.lng ?? community.longitude;
  const neighborhood = community.location?.neighborhood || community.neighborhood || community.neighborhoods?.[0];
  let approximate = community.location?.approximate === true || community.location?.precision === "neighborhood";
  if ((!Number.isFinite(latitude) || !Number.isFinite(longitude)) && neighborhood) {
    const fallback = NEIGHBORHOOD_CENTERS[neighborhood.toLocaleLowerCase()];
    if (fallback) { [latitude, longitude] = fallback; approximate = true; }
  }
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if ((latitude as number) < 40.45 || (latitude as number) > 41.05
    || (longitude as number) < -74.35 || (longitude as number) > -73.55) return null;
  return {
    id: community.id,
    name: community.name,
    slug: community.slug || community.id,
    latitude: latitude as number,
    longitude: longitude as number,
    neighborhood: neighborhood || "New York City",
    type: community.communityType || community.type || community.kind || "community",
    approximate,
  };
}

function communityType(community: Community) {
  return community.communityType || community.type || community.kind || "community";
}

function searchableText(community: Community) {
  return [community.name, community.description, community.shortDescription, community.tagline,
    community.neighborhood, community.location?.neighborhood, ...(community.neighborhoods || []),
    ...(community.categories || []), ...(community.interests || [])]
    .filter(Boolean).join(" ").toLocaleLowerCase();
}

export default function MapExplorer() {
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(DATA_URL, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Communities returned ${response.status}`);
        return response.json() as Promise<CommunityPayload>;
      })
      .then((payload) => {
        const rows = Array.isArray(payload) ? payload : payload.communities || [];
        setCommunities(rows.filter((row) => row?.id && row?.name));
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) setError(true);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const types = useMemo(() => [...new Set(communities.map(communityType))].sort(), [communities]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return communities.filter((community) => (type === "all" || communityType(community) === type)
      && (!needle || searchableText(community).includes(needle)));
  }, [communities, query, type]);
  const points = useMemo(() => filtered.map(pointFor).filter((point): point is MappableCommunity => !!point), [filtered]);
  const selected = filtered.find((community) => community.id === selectedId) || null;
  const selectCommunity = useCallback((id: string) => {
    setSelectedId(id);
    requestAnimationFrame(() => document.getElementById(`community-${id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
  }, []);

  return (
    <div className="min-h-screen bg-[#f4f0e8] text-[#25231f]">
      <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:py-8">
        <div className="mb-6 max-w-3xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#a5422d]">Find your people</p>
          <h1 className="font-serif text-4xl leading-tight sm:text-5xl">The city, through its communities.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#665f54] sm:text-base">
            Browse gathering places and neighborhood clusters. Pins may be approximate to protect private meeting locations.
          </p>
        </div>

        <div className="mb-4 grid gap-3 rounded-2xl border border-[#d9d0c0] bg-[#fbf8f1] p-3 shadow-sm sm:grid-cols-[minmax(0,1fr)_14rem]">
          <label className="relative">
            <span className="sr-only">Search communities</span>
            <span aria-hidden className="absolute left-3 top-2.5 text-[#81786b]">⌕</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)}
              placeholder="Search interests, names, or neighborhoods"
              className="w-full rounded-xl border border-[#d9d0c0] bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-[#a5422d] focus:ring-2 focus:ring-[#a5422d]/15" />
          </label>
          <label>
            <span className="sr-only">Community type</span>
            <select value={type} onChange={(event) => setType(event.target.value)}
              className="w-full rounded-xl border border-[#d9d0c0] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#a5422d]">
              <option value="all">All community types</option>
              {types.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}
            </select>
          </label>
        </div>

        <noscript>
          <div className="mb-4 rounded-2xl border border-[#d9d0c0] bg-[#fbf8f1] p-5 text-sm text-[#665f54]">
            The interactive map needs JavaScript. <Link className="font-semibold text-[#a5422d] underline" href="/communities">Browse the static community profiles instead.</Link>
          </div>
        </noscript>

        {loading ? (
          <div className="grid min-h-[60vh] place-items-center rounded-3xl border border-[#d9d0c0] bg-[#e7e1d5] text-sm text-[#665f54]">Loading the community map…</div>
        ) : error ? (
          <section className="grid min-h-[55vh] place-items-center rounded-3xl border border-[#d9d0c0] bg-[#fbf8f1] px-6 text-center">
            <div><h2 className="font-serif text-2xl">The map is taking a pause.</h2><p className="mt-2 text-sm text-[#665f54]">Community data could not be loaded. Try the directory instead.</p><Link className="mt-5 inline-block rounded-full bg-[#25231f] px-5 py-2.5 text-sm text-white" href="/communities">Browse communities</Link></div>
          </section>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <CommunityMap communities={points} selectedId={selected?.id || null} onSelect={selectCommunity} />
            <aside aria-label="Communities in view" className="max-h-[68vh] overflow-y-auto rounded-3xl border border-[#d9d0c0] bg-[#fbf8f1] p-3 lg:h-[68vh]">
              <div className="sticky top-0 z-10 flex items-baseline justify-between bg-[#fbf8f1] px-2 pb-3 pt-1">
                <h2 className="font-serif text-xl">{filtered.length} communities</h2>
                <span className="text-xs text-[#81786b]">{points.length} mapped</span>
              </div>
              {filtered.length === 0 ? <p className="px-2 py-10 text-center text-sm text-[#665f54]">No communities match these filters.</p> : (
                <div className="space-y-2">
                  {filtered.map((community) => {
                    const point = pointFor(community);
                    const active = selected?.id === community.id;
                    return <article key={community.id} id={`community-${community.id}`} className={`rounded-2xl border p-4 transition ${active ? "border-[#a5422d] bg-[#fff8eb]" : "border-[#ded7ca] bg-white hover:border-[#b8ad9d]"}`}>
                      <button type="button" onClick={() => { setSelectedId(community.id); if (point) document.getElementById("community-map")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }} className="w-full text-left">
                        <div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] font-semibold uppercase tracking-wider text-[#a5422d]">{communityType(community).replaceAll("_", " ")}</span><span className="text-[11px] text-[#81786b]">{point ? (point.approximate ? "Approx. area" : point.neighborhood) : "Location private"}</span></div>
                        <h3 className="font-serif text-lg leading-snug">{community.name}</h3>
                        {(community.shortDescription || community.tagline || community.description) && <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#665f54]">{community.shortDescription || community.tagline || community.description}</p>}
                        {community.nextEvent?.title && <p className="mt-3 text-xs"><span className="text-[#81786b]">Next:</span> {community.nextEvent.title}</p>}
                      </button>
                      <Link href={`/communities/${community.slug || community.id}`} className="mt-3 inline-flex text-xs font-semibold text-[#a5422d] hover:underline">View community →</Link>
                    </article>;
                  })}
                </div>
              )}
              {filtered.length > points.length && <p className="px-3 pb-2 pt-5 text-xs leading-5 text-[#81786b]">Some communities keep their meeting point private or do not yet have public coordinates. They remain available in this list.</p>}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
