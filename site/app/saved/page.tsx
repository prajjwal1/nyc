"use client";

import { useEffect, useMemo, useState } from "react";
import CommunityCard from "../components/CommunityCard";
import EventCard from "../components/EventCard";
import { loadCommunities, followedCommunityIds } from "../lib/communities";
import { loadEvents } from "../lib/events";
import { loadSavedStubs } from "../lib/interests";
import type { Community, Event } from "../lib/types";

export default function SavedPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([loadEvents(), loadCommunities()])
      .then(([eventData, communityData]) => {
        const saved = new Set(loadSavedStubs().map((event) => event.id));
        setEvents(eventData.events.filter((event) => saved.has(event.id)));
        const followed = new Set(followedCommunityIds());
        setCommunities((communityData.communities || []).filter((community) => followed.has(community.id)));
      })
      .finally(() => setLoading(false));
  }, []);

  const upcoming = useMemo(
    () => [...events].sort((a, b) => `${a.date}${a.startTime || ""}`.localeCompare(`${b.date}${b.startTime || ""}`)),
    [events],
  );

  return (
    <main className="min-h-screen bg-[#f8f3e8] px-4 py-10 sm:px-6">
      <div className="mx-auto max-w-5xl">
        <p className="text-xs font-bold uppercase tracking-[.22em] text-[#bd4f34]">Your city</p>
        <h1 className="font-editorial mt-3 text-5xl font-bold text-[#173c35] sm:text-6xl">Saved for later.</h1>
        <p className="mt-4 max-w-xl text-[#52645e]">Private to this browser: communities you follow and events you saved.</p>

        {loading ? <p className="mt-12 text-[#52645e]">Gathering your saves…</p> : (
          <>
            <section className="mt-12">
              <h2 className="font-editorial text-3xl font-bold">Followed communities</h2>
              {communities.length ? (
                <div className="mt-5 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                  {communities.map((community) => <CommunityCard key={community.id} community={community} />)}
                </div>
              ) : <p className="mt-4 rounded-2xl bg-[#ece5d8] p-5 text-[#52645e]">Follow communities to build a personal rhythm across the city.</p>}
            </section>

            <section className="mt-14">
              <h2 className="font-editorial text-3xl font-bold">Saved events</h2>
              {upcoming.length ? (
                <div className="mt-5 space-y-3">{upcoming.map((event) => <EventCard key={event.id} event={event} showDay />)}</div>
              ) : <p className="mt-4 rounded-2xl bg-[#ece5d8] p-5 text-[#52645e]">Events you star will appear here.</p>}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
