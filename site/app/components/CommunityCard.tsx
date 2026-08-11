"use client";

import Link from "next/link";
import { useState } from "react";
import { followedCommunityIds, toggleCommunityFollow } from "../lib/communities";
import { Community } from "../lib/types";

const FOLLOW_EVENT = "nyc-community-follow-change";

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function CommunityCard({ community, priority = false, onOpen }: { community: Community; priority?: boolean; onOpen?: () => void }) {
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

  if (isDiscovery) {
    const searchLink = community.links?.find((link) => link.type === "web_search") || community.links?.[0];
    return (
      <article className="group flex min-h-[190px] flex-col rounded-[1.15rem] border border-[#d7d6cf] bg-[#fbfaf7] p-5 transition hover:border-[#b8bbb4] hover:shadow-[0_14px_35px_rgba(34,55,47,0.06)]">
        <div className="flex items-start gap-4">
          <div aria-hidden="true" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#e5e7df] font-editorial text-xl italic text-[#31564c]">{community.name.charAt(0)}</div>
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[#9a684e]">{category}</p>
            <h3 className="mt-1 font-editorial text-xl font-medium leading-tight text-[#173a31]">{community.name}</h3>
            <p className="mt-1 text-xs text-[#74807b]">{place}</p>
          </div>
          <button onClick={toggleFollow} aria-label={`${following ? "Unfollow" : "Follow"} ${community.name}`} aria-pressed={following} className={`shrink-0 rounded-full px-3 py-1.5 text-[10px] font-semibold transition ${following ? "bg-[#173a31] text-white" : "border border-[#b8beb9] text-[#43564f] hover:border-[#173a31]"}`}>{following ? "Following" : "Follow"}</button>
        </div>
        <p className="mt-4 line-clamp-2 text-sm leading-5 text-[#66716c]">{community.description}</p>
        <div className="mt-auto flex items-center justify-between border-t border-[#e3e1da] pt-3 text-[11px]">
          <span className="text-[#7a827e]">Details not yet verified</span>
          {searchLink ? <a href={searchLink.url} target="_blank" rel="noreferrer" className="font-semibold text-[#9f4f36] hover:text-[#713625]">Find official page <span aria-hidden="true">↗</span></a> : null}
        </div>
      </article>
    );
  }

  return (
    <article className="group flex min-h-[310px] flex-col overflow-hidden rounded-[1.35rem] border border-[#d4d3cb] bg-[#fbfaf7] transition duration-300 hover:-translate-y-0.5 hover:border-[#b9bbb4] hover:shadow-[0_18px_45px_rgba(34,55,47,0.07)]">
      <div className="relative h-32 overflow-hidden border-b border-[#e1e0d9] bg-[#e7e5dc]">
        {community.imageUrl ? (
          <img src={community.imageUrl} alt="" loading={priority ? "eager" : "lazy"} className="h-full w-full object-cover saturate-[0.72] transition duration-700 group-hover:scale-[1.025] group-hover:saturate-100" />
        ) : (
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_25%,rgba(173,91,61,0.16),transparent_38%),linear-gradient(135deg,#e5e7df,#efebe3)]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#162e27]/25 to-transparent" />
        <div className="absolute left-4 top-4 rounded-full border border-white/60 bg-[#fbfaf7]/90 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-[#475852] backdrop-blur">
          {upcomingCount ? `${upcomingCount} upcoming` : "Events tracked"}
        </div>
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[#9a684e]">{category}</p>
            <h3 className="mt-1.5 font-editorial text-[1.55rem] font-medium leading-tight tracking-[-0.02em] text-[#173a31]">
              <Link href={`/communities/${community.slug}`} onNavigate={onOpen} className="decoration-1 underline-offset-4 outline-none transition hover:text-[#a95136] focus-visible:underline">{community.name}</Link>
            </h3>
          </div>
          <button onClick={toggleFollow} aria-label={`${following ? "Unfollow" : "Follow"} ${community.name}`} aria-pressed={following} className={`shrink-0 rounded-full px-3 py-1.5 text-[10px] font-semibold transition ${following ? "bg-[#173a31] text-white" : "border border-[#b8beb9] text-[#43564f] hover:border-[#173a31]"}`}>{following ? "Following" : "Follow"}</button>
        </div>

        <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#66716c]">{summary}</p>

        <div className="mt-auto flex items-end justify-between gap-4 border-t border-[#e3e1da] pt-4 text-[11px] text-[#69736f]">
          <div className="min-w-0">
            <p className="truncate font-medium text-[#41534c]">{place}</p>
            <p className="mt-0.5 truncate">{community.schedule?.cadence || "Schedule varies"}</p>
          </div>
          <Link href={`/communities/${community.slug}`} onNavigate={onOpen} className="shrink-0 font-semibold text-[#9f4f36] transition hover:text-[#713625]">View profile <span aria-hidden="true">→</span></Link>
        </div>
        <span className="sr-only">Activity status: {activity}</span>
      </div>
    </article>
  );
}
