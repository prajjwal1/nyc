"use client";

import Link from "next/link";
import { useState } from "react";
import { followedCommunityIds, toggleCommunityFollow } from "../lib/communities";
import { Community } from "../lib/types";

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function scheduleLabel(community: Community) {
  const cadence = community.schedule?.cadence ? formatLabel(community.schedule.cadence) : "Schedule varies";
  const day = community.schedule?.typicalDays?.[0];
  return day ? `${cadence} · ${day}` : cadence;
}

export default function CommunityCard({
  community,
  priority = false,
  onOpen,
}: {
  community: Community;
  priority?: boolean;
  onOpen?: () => void;
}) {
  const [following, setFollowing] = useState(() => followedCommunityIds().includes(community.id));
  const isDiscovery = community.profileStatus === "directory_reference";
  const category = community.categories[0] ? formatLabel(community.categories[0]) : "NYC community";
  const place = community.neighborhoods?.[0] ? formatLabel(community.neighborhoods[0]) : "New York City";
  const upcomingCount = community.upcomingEventIds?.length || community.activity?.upcomingEventCount || 0;
  const externalLink = community.links?.find((link) => link.type === "web_search") || community.links?.[0];
  const summary = community.tagline || community.description || `Discover ${community.name} and learn how to get involved.`;

  const toggleFollow = () => {
    setFollowing(toggleCommunityFollow(community.id).includes(community.id));
  };

  if (isDiscovery) {
    return (
      <article className="group flex min-h-[216px] flex-col rounded-[1.35rem] border border-[#d7d5cd] bg-[#fbfaf7] p-5 shadow-[0_1px_0_rgba(23,58,49,0.03)] transition duration-300 hover:-translate-y-0.5 hover:border-[#b8bbb4] hover:shadow-[0_16px_36px_rgba(34,55,47,0.07)] sm:p-6">
        <div className="flex items-start gap-3.5">
          <div aria-hidden="true" className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[radial-gradient(circle_at_70%_25%,#f2ddd1,transparent_45%),#e4e8e1] font-editorial text-xl italic text-[#31564c]">
            {community.name.charAt(0)}
          </div>
          <div className="min-w-0 flex-1 pt-0.5">
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[#9a684e]">{category}</p>
            <h3 className="mt-1 break-words font-editorial text-[1.35rem] font-medium leading-[1.08] tracking-[-0.02em] text-[#173a31] [overflow-wrap:anywhere]">{community.name}</h3>
            <p className="mt-1.5 truncate text-xs text-[#74807b]">{place}</p>
          </div>
          <button type="button" onClick={toggleFollow} aria-label={`${following ? "Unfollow" : "Follow"} ${community.name}`} aria-pressed={following} className={`min-h-11 shrink-0 rounded-full px-3.5 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ad5b3d] ${following ? "bg-[#173a31] text-white" : "border border-[#b8beb9] text-[#43564f] hover:border-[#173a31]"}`}>
            {following ? "Following" : "Follow"}
          </button>
        </div>

        <p className="mt-4 line-clamp-2 text-sm leading-5 text-[#66716c]">{summary}</p>

        <div className="mt-auto flex items-center justify-between gap-3 border-t border-[#e3e1da] pt-3">
          <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#858c88]">Discovery profile</span>
          {externalLink ? (
            <a href={externalLink.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center rounded-full px-2 text-xs font-semibold text-[#9f4f36] outline-none transition hover:text-[#713625] focus-visible:ring-2 focus-visible:ring-[#ad5b3d]">
              Find official page <span aria-hidden="true" className="ml-1">↗</span>
            </a>
          ) : <span className="text-xs text-[#7a827e]">Details in progress</span>}
        </div>
      </article>
    );
  }

  return (
    <article className="group flex min-h-[350px] flex-col overflow-hidden rounded-[1.5rem] border border-[#d4d2ca] bg-[#fbfaf7] shadow-[0_1px_0_rgba(23,58,49,0.03)] transition duration-300 hover:-translate-y-0.5 hover:border-[#b9bbb4] hover:shadow-[0_18px_45px_rgba(34,55,47,0.08)]">
      <div className="relative h-36 overflow-hidden border-b border-[#e1dfd7] bg-[#e7e5dc] sm:h-40">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_25%,rgba(173,91,61,0.18),transparent_38%),linear-gradient(135deg,#e5e7df,#efebe3)]" />
        {community.imageUrl && (
          /* Remote community artwork has many hosts; the stable frame prevents layout shift. */
          // eslint-disable-next-line @next/next/no-img-element
          <img src={community.imageUrl} alt="" loading={priority ? "eager" : "lazy"} className="relative h-full w-full object-cover saturate-[0.78] transition duration-700 group-hover:scale-[1.025] group-hover:saturate-100" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#102720]/45 via-transparent to-transparent" />
        <div className="absolute left-4 top-4 rounded-full border border-white/60 bg-[#fbfaf7]/92 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#3d514a] shadow-sm backdrop-blur">
          {upcomingCount ? `${upcomingCount} upcoming` : "Events tracked"}
        </div>
      </div>

      <div className="flex flex-1 flex-col p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[#9a684e]">{category}</p>
            <h3 className="mt-1.5 break-words font-editorial text-[1.65rem] font-medium leading-[1.05] tracking-[-0.025em] text-[#173a31] [overflow-wrap:anywhere]">
              <Link href={`/communities/${community.slug}`} onNavigate={onOpen} className="rounded-sm outline-none transition hover:text-[#a95136] focus-visible:ring-2 focus-visible:ring-[#ad5b3d]">{community.name}</Link>
            </h3>
          </div>
          <button type="button" onClick={toggleFollow} aria-label={`${following ? "Unfollow" : "Follow"} ${community.name}`} aria-pressed={following} className={`min-h-11 shrink-0 rounded-full px-3.5 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ad5b3d] ${following ? "bg-[#173a31] text-white" : "border border-[#b8beb9] text-[#43564f] hover:border-[#173a31]"}`}>
            {following ? "Following" : "Follow"}
          </button>
        </div>

        <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#66716c]">{summary}</p>

        <div className="mt-auto flex items-end justify-between gap-4 border-t border-[#e3e1da] pt-4 text-xs text-[#69736f]">
          <div className="min-w-0">
            <p className="truncate font-medium text-[#41534c]">{place}</p>
            <p className="mt-1 truncate text-[11px]">{scheduleLabel(community)}</p>
          </div>
          <Link href={`/communities/${community.slug}`} onNavigate={onOpen} className="inline-flex min-h-11 shrink-0 items-center rounded-full px-2 text-xs font-semibold text-[#9f4f36] outline-none transition hover:text-[#713625] focus-visible:ring-2 focus-visible:ring-[#ad5b3d]">
            View profile <span aria-hidden="true" className="ml-1">→</span>
          </Link>
        </div>
      </div>
    </article>
  );
}
