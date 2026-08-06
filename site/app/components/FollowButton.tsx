"use client";
import { useState } from "react";
import { followedCommunityIds,toggleCommunityFollow } from "../lib/communities";
export default function FollowButton({id}:{id:string}){const [on,setOn]=useState(()=>followedCommunityIds().includes(id));return <button onClick={()=>setOn(toggleCommunityFollow(id).includes(id))} className={`w-full rounded-full px-4 py-3 text-sm font-bold ${on?"bg-[#bd4f34] text-white":"bg-[#173c35] text-white"}`}>{on?"Following ✓":"Follow this community"}</button>}
