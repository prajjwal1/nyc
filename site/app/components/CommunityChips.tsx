"use client";
import Link from "next/link";
import { useEffect,useState } from "react";
import { loadCommunities } from "../lib/communities";
import { Community } from "../lib/types";
export default function CommunityChips({ids}:{ids?:string[]}){const [items,setItems]=useState<Community[]>([]);useEffect(()=>{if(ids?.length)loadCommunities().then(d=>setItems(d.communities.filter(c=>ids.includes(c.id)))).catch(()=>{})},[ids]);if(!items.length)return null;return <div className="relative z-10 mt-1.5 flex flex-wrap gap-1">{items.slice(0,2).map(c=><Link onClick={e=>e.stopPropagation()} key={c.id} href={`/communities/${c.slug}`} className="rounded-full bg-[#e4eadf] px-2 py-0.5 text-[10px] font-semibold text-[#31554c] hover:bg-[#cfdbc8]">People behind this · {c.name}</Link>)}</div>}
