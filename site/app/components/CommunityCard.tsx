"use client";

import Link from "next/link";
import { useState } from "react";
import { followedCommunityIds, toggleCommunityFollow } from "../lib/communities";
import { Community } from "../lib/types";

const FOLLOW_EVENT = "nyc-community-follow-change";

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function CommunityCard({ community, priority = false }: { community: Community; priority?: boolean }) {
  const [following, setFollowing] = useState(() => followedCommunityIds().includes(community.id));
  const isDiscovery = community.profileStatus === "directory_reference";
  const activity = community.activity?.state || "unverified";
  const category = community.categories[0] ? formatLabel(community.categories[0]) : "Community";
  const place = community.neighborhoods?.[0] ? formatLabel(community.neighborhoods[0]) : "New York City";
  const upcomingCount = community.upcomingEventIds?.length || 0;
  const summary = isDiscovery
    ? `An NYC community we're currently mapping. Follow to keep it on your list as details are added.`
    : community.tagline || community.description || `${community.name} is part of New York City's community landscape.`;

  const toggleFollow = () => {
    const next = toggleCommunityFollow(community.id);
    setFollowing(next.includes(community.id));
    window.dispatchEvent(new Event(FOLLOW_EVENT));
  };

  return (
    <article className="group flex min-h-[310px] flex-col overflow-hidden rounded-[1.35rem] border border-[#d4d3cb] bg-[#fbfaf7] transition duration-300 hover:-translate-y-0.5 hover:border-[#b9bbb4] hover:shadow-[0_18px_45px_rgba(34,55,47,0.07)]">
      <div className="relative h-32 overflow-hidden border-b border-[#e1e0d9] bg-[#e7e5dc]">
        {!isDiscovery && community.imageUrl ? (
          <img src={community.imageUrl} alt="" loading={priority ? "eager" : "lazy"} className="h-full w-full object-cover saturate-[0.72] transition duration-700 group-hover:scale-[1.025] group-hover:saturate-100" />
        ) : (
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_25%,rgba(173,91,61,0.16),transparent_38%),linear-gradient(135deg,#e5e7df,#efebe3)]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#162e27]/25 to-transparent" />
        <div className="absolute left-4 top-4 rounded-full border border-white/60 bg-[#fbfaf7]/90 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-[#475852] backdrop-blur">
          {isDiscovery ? "Discovery profile" : upcomingCount ? `${upcomingCount} upcoming` : "Events tracked"}
        </div>
        {isDiscovery && <span aria-hidden="true" className="absolute bottom-3 right-4 font-editorial text-5xl italic text-[#15372f]/25">{community.name.charAt(0)}</span>}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[#9a684e]">{category}</p>
            {isDiscovery ? (
              <h3 className="mt-1.5 font-editorial text-[1.55rem] font-medium leading-tight tracking-[-0.02em] text-[#173a31]">{community.name}</h3>
            ) : (
              <h3 className="mt-1.5 font-editorial text-[1.55rem] font-medium leading-tight tracking-[-0.02em] text-[#173a31]">
                <Link href={`/communities/${community.slug}`} className="decoration-1 underline-offset-4 outline-none transition hover:text-[#a95136] focus-visible:underline">{community.name}</Link>
              </h3>
            )}
          </div>
          <button onClick={toggleFollow} aria-label={`${following ? "Unfollow" : "Follow"} ${community.name}`} aria-pressed={following} className={`shrink-0 rounded-full px-3 py-1.5 text-[10px] font-semibold transition ${following ? "bg-[#173a31] text-white" : "border border-[#b8beb9] text-[#43564f] hover:border-[#173a31]"}`}>{following ? "Following" : "Follow"}</button>
        </div>

        <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#66716c]">{summary}</p>

        <div className="mt-auto flex items-end justify-between gap-4 border-t border-[#e3e1da] pt-4 text-[11px] text-[#69736f]">
          <div className="min-w-0">
            <p className="truncate font-medium text-[#41534c]">{place}</p>
            <p className="mt-0.5 truncate">{isDiscovery ? "Details in progress" : community.schedule?.cadence || "Schedule varies"}</p>
          </div>
          {isDiscovery ? (
            <span className="shrink-0 text-[#8a918d]">Profile in progress</span>
          ) : (
            <Link href={`/communities/${community.slug}`} className="shrink-0 font-semibold text-[#9f4f36] transition hover:text-[#713625]">View profile <span aria-hidden="true">→</span></Link>
          )}
        </div>
        {!isDiscovery && <span className="sr-only">Activity status: {activity}</span>}
      </div>
    </article>
  );
}
