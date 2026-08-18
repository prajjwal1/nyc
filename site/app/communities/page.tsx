"use client";

import { useEffect, useMemo, useState } from "react";
import CommunityCard from "../components/CommunityCard";
import {
  COMMUNITY_FOLLOW_EVENT,
  CommunityCollectionFilter,
  followedCommunityIds,
  loadCommunities,
  readCommunityDirectoryState,
  writeCommunityDirectoryState,
} from "../lib/communities";
import { Community } from "../lib/types";

const AVAIL_KEY = "nyc-community-availability-v1";
const PAGE_SIZE = 48;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const BANDS = ["morning", "afternoon", "evening"];

function timeBand(value?: string) {
  if (!value) return "";
  const lower = value.toLowerCase();
  if (BANDS.includes(lower)) return lower;
  const hour = Number.parseInt(lower.slice(0, 2), 10);
  if (Number.isNaN(hour)) return "";
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

function isEventBacked(community: Community) {
  return community.profileStatus !== "directory_reference";
}

function saveAvailability(value: string[]) {
  try {
    localStorage.setItem(AVAIL_KEY, JSON.stringify(value));
  } catch {
    // Filters remain usable when browser storage is unavailable.
  }
}

export default function CommunitiesPage() {
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [category, setCategory] = useState("all");
  const [neighborhood, setNeighborhood] = useState("all");
  const [collection, setCollection] = useState<CommunityCollectionFilter>("event_backed");
  const [firstTimers, setFirstTimers] = useState(false);
  const [followedOnly, setFollowedOnly] = useState(false);
  const [availability, setAvailability] = useState<string[]>([]);
  const [showAvailability, setShowAvailability] = useState(false);
  const [displayLimit, setDisplayLimit] = useState(PAGE_SIZE);
  const [followedIds, setFollowedIds] = useState<string[]>([]);
  const [directoryStateReady, setDirectoryStateReady] = useState(false);

  useEffect(() => {
    loadCommunities()
      .then((data) => setCommunities(data.communities || []))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
    queueMicrotask(() => {
      const saved = readCommunityDirectoryState();
      let storedAvailability: string[] = [];
      try {
        const value = JSON.parse(localStorage.getItem(AVAIL_KEY) || "[]");
        if (Array.isArray(value)) storedAvailability = value.filter((slot): slot is string => typeof slot === "string");
      } catch {}
      if (typeof saved.category === "string") setCategory(saved.category);
      if (typeof saved.neighborhood === "string") setNeighborhood(saved.neighborhood);
      if (["all", "event_backed", "directory_reference"].includes(saved.collection || "")) {
        setCollection(saved.collection as CommunityCollectionFilter);
      }
      if (typeof saved.firstTimers === "boolean") setFirstTimers(saved.firstTimers);
      if (typeof saved.followedOnly === "boolean") setFollowedOnly(saved.followedOnly);
      setAvailability(Array.isArray(saved.availability) ? saved.availability : storedAvailability);
      if (typeof saved.showAvailability === "boolean") setShowAvailability(saved.showAvailability);
      if (typeof saved.displayLimit === "number" && Number.isFinite(saved.displayLimit)) {
        setDisplayLimit(Math.max(PAGE_SIZE, Math.min(saved.displayLimit, 5000)));
      }
      setFollowedIds(followedCommunityIds());
      setDirectoryStateReady(true);
    });
    const refreshFollows = () => setFollowedIds(followedCommunityIds());
    window.addEventListener(COMMUNITY_FOLLOW_EVENT, refreshFollows);
    return () => window.removeEventListener(COMMUNITY_FOLLOW_EVENT, refreshFollows);
  }, []);

  useEffect(() => {
    if (!directoryStateReady) return;
    writeCommunityDirectoryState({
      category,
      neighborhood,
      collection,
      firstTimers,
      followedOnly,
      availability,
      showAvailability,
      displayLimit,
    });
  }, [directoryStateReady, category, neighborhood, collection, firstTimers, followedOnly, availability, showAvailability, displayLimit]);

  useEffect(() => {
    if (!directoryStateReady || loading) return;
    const saved = readCommunityDirectoryState();
    if (!saved.restoreOnReturn || typeof saved.scrollY !== "number") return;
    const restorePosition = () => window.scrollTo(0, saved.scrollY || 0);
    const secondFrame = { id: 0 };
    const firstFrame = requestAnimationFrame(() => {
      secondFrame.id = requestAnimationFrame(restorePosition);
    });
    const afterImagesSettle = window.setTimeout(restorePosition, 300);
    writeCommunityDirectoryState({ restoreOnReturn: false });
    return () => {
      cancelAnimationFrame(firstFrame);
      cancelAnimationFrame(secondFrame.id);
      window.clearTimeout(afterImagesSettle);
    };
  }, [directoryStateReady, loading]);

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
  }, [communities, category, neighborhood, collection, firstTimers, followedOnly, availability, followedIds]);

  const displayed = visible.slice(0, displayLimit);
  const filtersActive = category !== "all" || neighborhood !== "all" || collection !== "event_backed"
    || firstTimers || followedOnly || availability.length > 0;

  const restartList = () => setDisplayLimit(PAGE_SIZE);
  const clearFilters = () => {
    setCategory("all");
    setNeighborhood("all");
    setCollection("event_backed");
    setFirstTimers(false);
    setFollowedOnly(false);
    setAvailability([]);
    setShowAvailability(false);
    setDisplayLimit(PAGE_SIZE);
    saveAvailability([]);
  };
  const toggleDay = (day: string) => {
    const next = availability.includes(day) ? availability.filter((item) => item !== day) : [...availability, day];
    setAvailability(next);
    setDisplayLimit(PAGE_SIZE);
    saveAvailability(next);
  };
  const rememberDirectoryPosition = () => {
    writeCommunityDirectoryState({
      category,
      neighborhood,
      collection,
      firstTimers,
      followedOnly,
      availability,
      showAvailability,
      displayLimit,
      scrollY: window.scrollY,
      restoreOnReturn: true,
    });
  };

  return (
    <main className="min-h-screen bg-[#f8f3e8] px-4 pb-24 pt-9 text-[#182923] sm:px-6 sm:pt-14">
      <div className="mx-auto max-w-7xl">
        <header className="grid gap-8 border-b border-[#d8d7d0] pb-9 sm:pb-12 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
          <div className="max-w-4xl">
            <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.28em] text-[#99704d] sm:mb-5 sm:text-[11px]">Communities you can join</p>
            <h1 className="font-editorial text-[clamp(3rem,12vw,7.6rem)] font-medium leading-[0.88] tracking-[-0.05em] text-[#15372f] sm:leading-[0.83]">
              Find your people<br /><span className="italic text-[#ad5b3d]">in New York.</span>
            </h1>
            <p className="mt-6 max-w-xl text-[15px] leading-6 text-[#5d6964] sm:mt-7 sm:text-lg sm:leading-7">
              Start with communities that have real upcoming events, then narrow by interest, neighborhood, or the times you are usually free.
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-5 border-t border-[#d8d7d0] pt-5 lg:border-t-0 lg:pt-0">
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7b837f]">With upcoming events</dt>
              <dd className="mt-1.5 font-editorial text-3xl text-[#15372f] sm:text-4xl">{loading ? "—" : eventBackedCount.toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7b837f]">More to explore</dt>
              <dd className="mt-1.5 font-editorial text-3xl text-[#15372f] sm:text-4xl">{loading ? "—" : discoveryCount.toLocaleString()}</dd>
            </div>
          </dl>
        </header>

        <section aria-label="Community filters" className="sticky top-[49px] z-30 -mx-4 border-b border-[#d8d7d0] bg-[#f8f3e8]/95 px-4 py-3 shadow-[0_8px_20px_rgba(23,58,49,0.03)] backdrop-blur-xl sm:top-[53px] sm:mx-0 sm:py-4 sm:shadow-none">
          <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center">
              <select value={category} onChange={(event) => { setCategory(event.target.value); restartList(); }} aria-label="Filter by interest" className="h-12 min-w-0 rounded-full border border-[#cfcec6] bg-[#fbfaf7] px-3 text-sm outline-none focus:border-[#8a9c94] sm:px-4">
                <option value="all">All interests</option>
                {categories.map((item) => <option key={item}>{item}</option>)}
              </select>
              <select value={neighborhood} onChange={(event) => { setNeighborhood(event.target.value); restartList(); }} aria-label="Filter by neighborhood" className="h-12 min-w-0 rounded-full border border-[#cfcec6] bg-[#fbfaf7] px-3 text-sm outline-none focus:border-[#8a9c94] sm:px-4">
                <option value="all">All neighborhoods</option>
                {neighborhoods.map((item) => <option key={item}>{item}</option>)}
              </select>
          </div>

          <div className="mt-2.5 flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:mt-3">
            {([
              ["event_backed", "With upcoming events"],
              ["all", "All communities"],
              ["directory_reference", "Wider directory"],
            ] as const).map(([value, label]) => (
              <button type="button" key={value} onClick={() => { setCollection(value); restartList(); }} aria-pressed={collection === value} className={`min-h-11 shrink-0 rounded-full px-4 text-xs font-medium transition ${collection === value ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c] hover:border-[#9fa8a4]"}`}>{label}</button>
            ))}
            <span className="mx-1 h-5 w-px shrink-0 bg-[#d8d7d0]" />
            <button type="button" onClick={() => { setFirstTimers(!firstTimers); restartList(); }} aria-pressed={firstTimers} className={`min-h-11 shrink-0 rounded-full px-4 text-xs font-medium transition ${firstTimers ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c]"}`}>First-timer friendly</button>
            <button type="button" onClick={() => { setFollowedOnly(!followedOnly); restartList(); }} aria-pressed={followedOnly} className={`min-h-11 shrink-0 rounded-full px-4 text-xs font-medium transition ${followedOnly ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c]"}`}>Following</button>
            <button type="button" onClick={() => setShowAvailability(!showAvailability)} aria-expanded={showAvailability} className={`min-h-11 shrink-0 rounded-full px-4 text-xs font-medium transition ${showAvailability || availability.length ? "bg-[#15372f] text-white" : "border border-[#cfcec6] bg-[#fbfaf7] text-[#53615c]"}`}>When I&apos;m free{availability.length ? ` · ${availability.length}` : ""}</button>
            {filtersActive && <button type="button" onClick={clearFilters} className="min-h-11 shrink-0 px-3 text-xs font-semibold text-[#a05238] hover:underline">Clear all</button>}
          </div>

          {showAvailability && (
            <div className="mt-3 max-h-[45vh] overflow-y-auto border-t border-[#d8d7d0] pt-3 sm:mt-4 sm:max-h-none sm:pt-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs text-[#65706b]">Choose any times that usually work.</p>
                {availability.length > 0 && <button type="button" onClick={() => { setAvailability([]); saveAvailability([]); restartList(); }} className="min-h-10 px-2 text-xs font-semibold text-[#a05238]">Clear times</button>}
              </div>
              <div className="grid grid-cols-[4.5rem_repeat(3,minmax(0,1fr))] gap-1.5 text-center text-[9px] uppercase tracking-wider text-[#68736e] sm:grid-cols-[6rem_repeat(3,minmax(0,8rem))]">
                <span />
                {BANDS.map((band) => <b key={band} className="py-1 font-medium capitalize tracking-normal">{band}</b>)}
                {DAYS.map((day) => (
                  <div className="contents" key={day}>
                    <span className="flex items-center text-left text-[10px] font-medium uppercase tracking-[0.08em]">{day.slice(0, 3)}</span>
                    {BANDS.map((band) => {
                      const slot = `${day}-${band}`;
                      const selected = availability.includes(slot);
                      return <button type="button" aria-label={`${day} ${band}`} aria-pressed={selected} key={slot} onClick={() => toggleDay(slot)} className={`min-h-11 rounded-lg transition ${selected ? "bg-[#15372f] text-white" : "bg-[#e7e6df] text-[#68736e] hover:bg-[#dcdad2]"}`}>{selected ? "✓" : "·"}</button>;
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <div className="flex items-end justify-between gap-4 py-7 sm:py-8">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#8a918e]">{collection === "event_backed" ? "Ready to join" : collection === "directory_reference" ? "Browse the wider directory" : "Filtered communities"}</p>
            <h2 aria-live="polite" className="mt-1 font-editorial text-[1.75rem] tracking-[-0.02em] text-[#15372f] sm:text-3xl">
              {loading ? "Looking around the city…" : `${visible.length.toLocaleString()} ${visible.length === 1 ? "community" : "communities"}`}
            </h2>
          </div>
          {!loading && visible.length > PAGE_SIZE && <p className="hidden text-xs text-[#737c78] sm:block">Showing {displayed.length.toLocaleString()} of {visible.length.toLocaleString()}</p>}
        </div>

        {loadError ? (
          <div className="border-y border-[#d8d7d0] py-20 text-center">
            <h2 className="font-editorial text-3xl text-[#15372f]">The index is taking a moment.</h2>
            <p className="mt-2 text-sm text-[#65706b]">Check your connection, then try once more.</p>
            <button type="button" onClick={() => window.location.reload()} className="mt-6 min-h-12 rounded-full bg-[#15372f] px-6 text-sm font-semibold text-white">Try again</button>
          </div>
        ) : loading ? (
          <div aria-label="Loading communities" className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }, (_, index) => <div key={index} className="h-[350px] animate-pulse overflow-hidden rounded-[1.5rem] border border-[#dddcd5] bg-[#fbfaf7]"><div className="h-36 bg-[#e7e5de] sm:h-40"/><div className="space-y-3 p-5 sm:p-6"><div className="h-2.5 w-20 rounded bg-[#e3e2db]"/><div className="h-7 w-2/3 rounded bg-[#dfded7]"/><div className="h-4 w-full rounded bg-[#e8e7e1]"/><div className="h-4 w-4/5 rounded bg-[#e8e7e1]"/></div></div>)}
          </div>
        ) : !loading && !visible.length ? (
          <div className="border-y border-[#d8d7d0] py-20 text-center">
            <h2 className="font-editorial text-3xl text-[#15372f]">No communities in this combination yet.</h2>
            <p className="mt-2 text-sm text-[#65706b]">Try another interest, neighborhood, or time.</p>
            <button type="button" onClick={clearFilters} className="mt-6 min-h-12 rounded-full border border-[#15372f] px-6 text-sm font-semibold text-[#15372f]">Reset filters</button>
          </div>
        ) : (
          <>
            <div className="grid gap-x-5 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
              {displayed.map((community, index) => <CommunityCard key={community.id} community={community} priority={index < 6} onOpen={rememberDirectoryPosition} />)}
            </div>
            {displayed.length < visible.length && (
              <div className="mt-12 border-t border-[#d8d7d0] pt-8 text-center">
                <button type="button" onClick={() => setDisplayLimit((limit) => limit + PAGE_SIZE)} className="min-h-12 rounded-full bg-[#15372f] px-7 text-sm font-semibold text-white transition hover:bg-[#204b40] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ad5b3d] focus-visible:ring-offset-2">Show {Math.min(PAGE_SIZE, visible.length - displayed.length)} more</button>
                <p className="mt-3 text-xs text-[#7d8581]">{(visible.length - displayed.length).toLocaleString()} still to explore</p>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
