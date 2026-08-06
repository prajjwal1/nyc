"use client";
import Link from "next/link";
import { useState } from "react";
import { Community } from "../lib/types";
import { followedCommunityIds, toggleCommunityFollow } from "../lib/communities";

export default function CommunityCard({ community }: { community: Community }) {
  const [following, setFollowing] = useState(() => followedCommunityIds().includes(community.id));
  const activity = community.activity?.state || "unverified";
  return <article className="group overflow-hidden rounded-[1.5rem] border border-[#d8d0c1] bg-[#fffdf8] shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
    {community.imageUrl && <img src={community.imageUrl} alt="" className="h-36 w-full object-cover" loading="lazy" />}
    <div className="p-5">
      <div className="mb-3 flex items-start gap-3"><div className="min-w-0 flex-1">
        <Link href={`/communities/${community.slug}`} className="font-editorial text-xl font-bold text-[#173c35] group-hover:text-[#bd4f34]">{community.name}</Link>
        <p className="mt-1 line-clamp-2 text-sm text-[#52645e]">{community.tagline || community.description}</p>
      </div><button onClick={() => setFollowing(toggleCommunityFollow(community.id).includes(community.id))} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${following ? "bg-[#173c35] text-white" : "border border-[#173c35] text-[#173c35]"}`}>{following ? "Following" : "Follow"}</button></div>
      <div className="flex flex-wrap gap-1.5">{community.categories.slice(0,3).map(x => <span key={x} className="rounded-full bg-[#e4eadf] px-2.5 py-1 text-[11px] text-[#31554c]">{x}</span>)}</div>
      <div className="mt-4 flex justify-between border-t border-[#ebe4d7] pt-3 text-xs text-[#6c766e]"><span>{community.neighborhoods?.[0] || "New York City"}</span><span className="capitalize">● {activity}</span><span>{community.schedule?.cadence || "See upcoming"}</span></div>
    </div>
  </article>;
}
