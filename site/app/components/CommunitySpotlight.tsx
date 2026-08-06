"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import CommunityCard from "./CommunityCard";
import { loadCommunities } from "../lib/communities";
import { Community } from "../lib/types";
export default function CommunitySpotlight(){const [items,setItems]=useState<Community[]>([]);useEffect(()=>{loadCommunities().then(d=>setItems((d.communities||[]).filter(c=>c.activity?.state==="active").slice(0,3))).catch(()=>{})},[]);if(!items.length)return null;return <section className="mb-8"><div className="mb-4 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-[#bd4f34]">More than one night</p><h2 className="font-editorial text-3xl font-bold text-[#173c35]">Find a community to return to</h2></div><Link href="/communities" className="text-sm font-semibold text-[#bd4f34]">Explore all →</Link></div><div className="grid gap-4 md:grid-cols-3">{items.map(c=><CommunityCard community={c} key={c.id}/>)}</div></section>}
