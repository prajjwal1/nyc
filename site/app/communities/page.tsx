"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import CommunityCard from "../components/CommunityCard";
import { followedCommunityIds, loadCommunities } from "../lib/communities";
import { Community } from "../lib/types";

const AVAIL_KEY = "nyc-community-availability-v1";
const FOLLOW_EVENT = "nyc-community-follow-change";
const PAGE_SIZE = 48;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const BANDS = ["morning", "afternoon", "evening"];
type CollectionFilter = "all" | "event_backed" | "directory_reference";

function timeBand(value?: string) {
  if (!value) return "";
  const lower = value.toLowerCase();
  if (BANDS.includes(lower)) return lower;
  const hour = Number.parseInt(lower.slice(0, 2), 10);
  if (Number.isNaN(hour)) return "";
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

function matchesPhrase(community: Community, query: string) {
  const tokens = query.toLowerCase().match(/[a-z0-9]+/g) || [];
  if (!tokens.length) return true;
  const text = [
    community.name,
    community.tagline,
    community.description,
    ...community.categories,
    ...(community.tags || []),
    ...(community.neighborhoods || []),
  ].join(" ").toLowerCase();
  const days = (community.schedule?.typicalDays || []).map((day) => day.toLowerCase());
  const band = timeBand(community.schedule?.typicalTime);
  return tokens.every((token) => {
    if (["near", "in", "on", "at", "the", "nyc", "community", "club"].includes(token)) return true;
    if (["beginner", "newcomer", "first", "solo"].includes(token)) return !!community.newcomerFriendly;
    if (BANDS.includes(token)) return band === token;
    const matchingDay = DAYS.find((day) => day.toLowerCase().startsWith(token.slice(0, 3)));
    if (matchingDay) return days.some((day) => day.startsWith(matchingDay.toLowerCase().slice(0, 3)));
    return text.includes(token);
  });
}

function isEventBacked(community: Community) {
  return community.profileStatus !== "directory_reference";
}

export default function CommunitiesPage() {
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [q, setQ] = useState("");
  const deferredQuery = useDeferredValue(q);
  const [category, setCategory] = useState("all");
  const [neighborhood, setNeighborhood] = useState("all");
  const [collection, setCollection] = useState<CollectionFilter>("event_backed");
  const [firstTimers, setFirstTimers] = useState(false);
  const [followedOnly, setFollowedOnly] = useState(false);
  const [availability, setAvailability] = useState<string[]>([]);
  const [showAvailability, setShowAvailability] = useState(false);
  const [displayLimit, setDisplayLimit] = useState(PAGE_SIZE);
  const [followedIds, setFollowedIds] = useState<string[]>([]);

  useEffect(() => {
    loadCommunities()
      .then((data) => setCommunities(data.communities || []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
    queueMicrotask(() => {
      try { setAvailability(JSON.parse(localStorage.getItem(AVAIL_KEY) || "[]")); } catch {}
      setFollowedIds(followedCommunityIds());
    });
    const refreshFollows = () => setFollowedIds(followedCommunityIds());
    window.addEventListener(FOLLOW_EVENT, refreshFollows);
    return () => window.removeEventListener(FOLLOW_EVENT, refreshFollows);
  }, []);

  const categories = useMemo(
    () => [...new Set(communities.flatMap((community) => community.categories))].sort(),
    [communities],
  );
  const neighborhoods = useMemo(
    () => [...new Set(communities.flatMap((community) => community.neighborhoods || []))].sort(),
    [communities],
  );
  const eventBackedCount = useMemo(() => communities.filter(isEventBacked).length, [communities]);
  const discoveryCount = communities.length - eventBackedCount;

  const visible = useMemo(() => {
    return communities
      .filter((community) => {
        const profileMatches = collection === "all"
          || (collection === "event_backed" && isEventBacked(community))
          || (collection === "directory_reference" && !isEventBacked(community));
        return profileMatches
          && matchesPhrase(community, deferredQuery)
          && (category === "all" || community.categories.includes(category))
          && (neighborhood === "all" || community.neighborhoods?.includes(neighborhood))
          && (!firstTimers || community.newcomerFriendly)
          && (!followedOnly || followedIds.includes(community.id))
          && (!availability.length || availability.some((slot) => {
            const [day, band] = slot.split("-");
            return community.schedule?.typicalDays?.some((item) => item.toLowerCase().startsWith(day.toLowerCase().slice(0, 3)))
              && timeBand(community.schedule?.typicalTime) === band;
          }));
      })
      .sort((a, b) => {
        const sourceDifference = Number(isEventBacked(b)) - Number(isEventBacked(a));
        if (sourceDifference) return sourceDifference;
        const activityDifference = Number(b.activity?.state === "active") - Number(a.activity?.state === "active");
        return activityDifference || a.name.localeCompare(b.name);
      });
  }, [communities, deferredQuery, category, neighborhood, collection, firstTimers, followedOnly, availability, followedIds]);

  const displayed = visible.slice(0, displayLimit);
  const filtersActive = !!q || category !== "all" || neighborhood !== "all" || collection !== "event_backed"
    || firstTimers || followedOnly || availability.length > 0;

  const restartList = () => setDisplayLimit(PAGE_SIZE);
  const clearFilters = () => {
    setQ("");
    setCategory("all");
    setNeighborhood("all");
    setCollection("event_backed");
    setFirstTimers(false);
    setFollowedOnly(false);
    setAvailability([]);
    setDisplayLimit(PAGE_SIZE);
    localStorage.setItem(AVAIL_KEY, "[]");
  };
  const toggleDay = (day: string) => {
    const next = availability.includes(day) ? availability.filter((item) => item !== day) : [...availability, day];
    setAvailability(next);
    setDisplayLimit(PAGE_SIZE);
    localStorage.setItem(AVAIL_KEY, JSON.stringify(next));
  };

  return (
    <main className="min-h-screen bg-[#f4f3ee] px-4 pb-24 pt-12 text-[#182923] sm:px-6 sm:pt-16">
      <div className="mx-auto max-w-7xl">
        <header className="grid gap-10 border-b border-[#d8d7d0] pb-12 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
          <div className="max-w-4xl">
            <p className="mb-5 text-[11px] font-semibold uppercase tracking-[0.28em] text-[#99704d]">Communities you can join</p>
            <h1 className="font-editorial text-[clamp(3.3rem,8vw,7.6rem)] font-medium leading-[0.83] tracking-[-0.055em] text-[#15372f]">
              Find your people<br /><span className="italic text-[#ad5b3d]">in New York.</span>
            </h1>
            <p className="mt-7 max-w-xl text-base leading-7 text-[#5d6964] sm:text-lg">
              Start with communities that have real upcoming events. Search the wider directory when you want to explore beyond what is happening this week.
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-6 border-t border-[#d8d7d0] pt-5 lg:border-t-0 lg:pt-0">
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7b837f]">With upcoming events</dt>
              <dd className="mt-2 font-editorial text-4xl text-[#15372f]">{loading ? "—" : eventBackedCount.toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7b837f]">More to explore</dt>
              <dd className="mt-2 font-editorial text-4xl text-[#15372f]">{loading ? "—" : discoveryCount.toLocaleString()}</dd>
            </div>
          </dl>
        </header>

        <section className="sticky top-[85px] z-30 -mx-4 border-b border-[#d8d7d0] bg-[#f4f3ee]/95 px-4 py-4 backdrop-blur-xl sm:top-[53px] sm:mx-0">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <label className="relative block min-w-0 flex-1">
              <span className="sr-only">Search communities</span>
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[#78817d]"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
              <input
                value={q}
                onChange={(event) => { setQ(event.target.value); if (event.target.value.trim()) setCollection("all"); restartList(); }}
                placeholder="Search chess, running, book clubs…"
                className="h-12 w-full rounded-full border border-[#cfcec6] bg-[#fbfaf7] pl-11 pr-4 text-sm outline-none transition placeholder:text-[#8b918e] focus:border-[#8a9c94] focus:ring-2 focus:ring-[#15372f]/10"
              />
            </label>
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <select value={category} onChange={(event) => { setCategory(event.target.value); restartList(); }} aria-label="Filter by interest" className="h-12 min-w-0 rounded-full border border-[#cfcec6] bg-[#fbfaf7] px-4 text-sm outline-none focus:border-[#8a9c94]">
                <option value="all">All interests</option>
                {categories.map((item) => <option key={item}>{item}</option>)}
              </select>
              <select value={neighborhood} onChange={(event) => { setNeighborhood(event.target.value); restartList(); }} aria-label="Filter by neighborhood" className="h-12 min-w-0 rounded-full border border-[#cfcec6] bg-[#fbfaf7] px-4 text-sm outline-none focus:border-[#8a9c94]">
                <option value="all">All neighborhoods</option>
                {neighborhoods.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {([
              ["event_backed", "With upcoming events"],
              ["all", "All communities"],
              ["directory_reference", "Wider directory"],
            ] as const).map(([value, label]) => (
              <button key={value} onClick={() => { setCollection(value); restartList(); }} aria-pressed={collection === value} className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition ${collection === value ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c] hover:border-[#9fa8a4]"}`}>{label}</button>
            ))}
            <span className="mx-1 h-5 w-px shrink-0 bg-[#d8d7d0]" />
            <button onClick={() => { setFirstTimers(!firstTimers); restartList(); }} aria-pressed={firstTimers} className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition ${firstTimers ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c]"}`}>First-timer friendly</button>
            <button onClick={() => { setFollowedOnly(!followedOnly); restartList(); }} aria-pressed={followedOnly} className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition ${followedOnly ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c]"}`}>Following</button>
            <button onClick={() => setShowAvailability(!showAvailability)} aria-expanded={showAvailability} className={`shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition ${showAvailability || availability.length ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c]"}`}>When I&apos;m free{availability.length ? ` · ${availability.length}` : ""}</button>
            {filtersActive && <button onClick={clearFilters} className="shrink-0 px-2 py-2 text-xs font-medium text-[#a05238] hover:underline">Clear</button>}
          </div>

          {showAvailability && (
            <div className="mt-4 overflow-x-auto border-t border-[#d8d7d0] pt-4">
              <div className="grid min-w-[620px] grid-cols-[6rem_repeat(7,1fr)] gap-1 text-center text-[10px] uppercase tracking-wider text-[#68736e]">
                <span />
                {DAYS.map((day) => <b key={day} className="py-1 font-medium">{day.slice(0, 3)}</b>)}
                {BANDS.map((band) => (
                  <div className="contents" key={band}>
                    <span className="py-2.5 text-left capitalize tracking-normal">{band}</span>
                    {DAYS.map((day) => {
                      const slot = `${day}-${band}`;
                      const selected = availability.includes(slot);
                      return <button aria-label={`${day} ${band}`} aria-pressed={selected} key={slot} onClick={() => toggleDay(slot)} className={`rounded-lg px-2 py-2 transition ${selected ? "bg-[#15372f] text-white" : "bg-[#e7e6df] hover:bg-[#dcdad2]"}`}>{selected ? "✓" : "·"}</button>;
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <div className="flex items-end justify-between gap-4 py-8">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#8a918e]">{collection === "event_backed" ? "Ready to join" : collection === "directory_reference" ? "Search the wider directory" : "Search results"}</p>
            <h2 className="mt-1 font-editorial text-3xl tracking-[-0.02em] text-[#15372f]">
              {loading ? "Looking around the city…" : `${visible.length.toLocaleString()} ${visible.length === 1 ? "community" : "communities"}`}
            </h2>
          </div>
          {!loading && visible.length > PAGE_SIZE && <p className="hidden text-xs text-[#737c78] sm:block">Showing {displayed.length.toLocaleString()} of {visible.length.toLocaleString()}</p>}
        </div>

        {loadError ? (
          <div className="border-y border-[#d8d7d0] py-20 text-center">
            <h2 className="font-editorial text-3xl text-[#15372f]">The index is taking a moment.</h2>
            <p className="mt-2 text-sm text-[#65706b]">Refresh the page to try again.</p>
          </div>
        ) : !loading && !visible.length ? (
          <div className="border-y border-[#d8d7d0] py-20 text-center">
            <h2 className="font-editorial text-3xl text-[#15372f]">No exact match yet.</h2>
            <p className="mt-2 text-sm text-[#65706b]">Try another interest, neighborhood, or time.</p>
            <button onClick={clearFilters} className="mt-6 rounded-full border border-[#15372f] px-5 py-2.5 text-xs font-semibold text-[#15372f]">Reset filters</button>
          </div>
        ) : (
          <>
            <div className="grid gap-x-5 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
              {displayed.map((community, index) => <CommunityCard key={community.id} community={community} priority={index < 6} />)}
            </div>
            {displayed.length < visible.length && (
              <div className="mt-12 border-t border-[#d8d7d0] pt-8 text-center">
                <button onClick={() => setDisplayLimit((limit) => limit + PAGE_SIZE)} className="rounded-full bg-[#15372f] px-7 py-3 text-sm font-semibold text-white transition hover:bg-[#204b40]">Show {Math.min(PAGE_SIZE, visible.length - displayed.length)} more</button>
                <p className="mt-3 text-xs text-[#7d8581]">{(visible.length - displayed.length).toLocaleString()} still to explore</p>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
