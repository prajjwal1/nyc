"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CommunityCard from "./CommunityCard";
import { loadCommunities } from "../lib/communities";
import { Community } from "../lib/types";

export default function CommunitySpotlight() {
  const [items, setItems] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCommunities()
      .then((d) =>
        setItems((d.communities || []).filter((c) => c.activity?.state === "active").slice(0, 3))
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (!loading && items.length === 0) return null;

  return (
    <section className="mb-8">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9a684e]">More than one night</p>
          <h2 className="font-editorial mt-1 text-2xl font-bold tracking-[-0.02em] text-[#173c35] sm:text-[27px]">
            Find a community to return to
          </h2>
        </div>
        <Link
          href="/communities"
          className="shrink-0 rounded-full border border-[#d7d5cd] bg-white px-3.5 py-1.5 text-xs font-semibold text-[#52645e] hover:border-[#173c35] hover:text-[#173c35] transition"
        >
          Explore all →
        </Link>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-[220px] animate-pulse rounded-[1.35rem] border border-[#dddcd5] bg-[#fbfaf7]" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {items.map((c) => (
            <CommunityCard community={c} key={c.id} />
          ))}
        </div>
      )}
    </section>
  );
}
