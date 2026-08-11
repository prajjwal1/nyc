"use client";

import { useState } from "react";
import { followedCommunityIds, toggleCommunityFollow } from "../lib/communities";

export default function FollowButton({ id, name = "this community" }: { id: string; name?: string }) {
  const [following, setFollowing] = useState(() => followedCommunityIds().includes(id));

  return (
    <button
      type="button"
      onClick={() => setFollowing(toggleCommunityFollow(id).includes(id))}
      aria-label={`${following ? "Unfollow" : "Follow"} ${name}`}
      aria-pressed={following}
      className={`min-h-12 w-full rounded-full px-5 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ad5b3d] focus-visible:ring-offset-2 ${following ? "bg-[#e4e8e2] text-[#173a31] hover:bg-[#d9dfd8]" : "bg-[#173a31] text-white hover:bg-[#214d42]"}`}
    >
      {following ? "Following ✓" : "Follow community"}
    </button>
  );
}
