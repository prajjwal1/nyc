"use client";
import { useEffect, useMemo, useState } from "react";
import CommunityCard from "../components/CommunityCard";
import { loadCommunities, followedCommunityIds } from "../lib/communities";
import { Community } from "../lib/types";

const AVAIL_KEY = "nyc-community-availability-v1";
const DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
const BANDS = ["morning", "afternoon", "evening"];

function timeBand(value?: string) {
  if (!value) return "";
  const lower = value.toLowerCase();
  if (BANDS.includes(lower)) return lower;
  const hour = Number.parseInt(lower.slice(0, 2), 10);
  if (Number.isNaN(hour)) return "";
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

function matchesPhrase(community: Community, query: string) {
  const tokens = query.toLowerCase().match(/[a-z0-9]+/g) || [];
  if (!tokens.length) return true;
  const text = [community.name, community.tagline, community.description, ...community.categories,
    ...(community.tags || []), ...(community.neighborhoods || [])].join(" ").toLowerCase();
  const days = (community.schedule?.typicalDays || []).map((day) => day.toLowerCase());
  const band = timeBand(community.schedule?.typicalTime);
  return tokens.every((token) => {
    if (["near", "in", "on", "at", "the", "nyc", "community", "club"].includes(token)) return true;
    if (["beginner", "newcomer", "first", "solo"].includes(token)) return !!community.newcomerFriendly;
    if (BANDS.includes(token)) return band === token;
    const matchingDay = DAYS.find((day) => day.toLowerCase().startsWith(token.slice(0, 3)));
    if (matchingDay) return days.some((day) => day.startsWith(matchingDay.toLowerCase().slice(0, 3)));
    return text.includes(token);
  });
}
export default function CommunitiesPage() {
  const [communities,setCommunities] = useState<Community[]>([]), [loading,setLoading] = useState(true);
  const [q,setQ] = useState(""), [category,setCategory] = useState("all"), [neighborhood,setNeighborhood] = useState("all");
  const [firstTimers,setFirstTimers] = useState(false), [followedOnly,setFollowedOnly] = useState(false);
  const [availability,setAvailability] = useState<string[]>([]), [showAvailability,setShowAvailability] = useState(false);
  useEffect(() => { loadCommunities().then(d => setCommunities(d.communities || [])).finally(() => setLoading(false)); try { setAvailability(JSON.parse(localStorage.getItem(AVAIL_KEY) || "[]")); } catch {} }, []);
  const categories = useMemo(() => [...new Set(communities.flatMap(c=>c.categories))].sort(),[communities]);
  const neighborhoods = useMemo(() => [...new Set(communities.flatMap(c=>c.neighborhoods || []))].sort(),[communities]);
  const visible = useMemo(() => {
    const followed=followedCommunityIds();
    return communities.filter(c => matchesPhrase(c, q) && (category==="all" || c.categories.includes(category)) && (neighborhood==="all" || c.neighborhoods?.includes(neighborhood)) && (!firstTimers || c.newcomerFriendly) && (!followedOnly || followed.includes(c.id)) && (!availability.length || availability.some((slot) => {
      const [day, band] = slot.split("-");
      return c.schedule?.typicalDays?.some(d => d.toLowerCase().startsWith(day.toLowerCase().slice(0, 3))) && timeBand(c.schedule?.typicalTime) === band;
    }))).sort((a,b)=>(a.activity?.state==="active"?-1:0)-(b.activity?.state==="active"?-1:0));
  },[communities,q,category,neighborhood,firstTimers,followedOnly,availability]);
  const toggleDay=(d:string)=>{const n=availability.includes(d)?availability.filter(x=>x!==d):[...availability,d];setAvailability(n);localStorage.setItem(AVAIL_KEY,JSON.stringify(n));};
  return <main className="min-h-screen bg-[#f8f3e8] px-4 py-10 sm:px-6"><div className="mx-auto max-w-7xl">
    <div className="max-w-3xl"><p className="mb-3 text-xs font-bold uppercase tracking-[.22em] text-[#bd4f34]">Find your people</p><h1 className="font-editorial text-5xl font-bold leading-[.95] text-[#173c35] sm:text-7xl">A field guide to NYC communities.</h1><p className="mt-5 max-w-2xl text-lg text-[#52645e]">Discover the clubs, collectives, rituals, and recurring gatherings that make the city feel smaller.</p></div>
    <section className="sticky top-[53px] z-30 -mx-4 mt-10 border-y border-[#d8d0c1] bg-[#f8f3e8]/95 px-4 py-4 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border">
      <div className="grid gap-3 md:grid-cols-3"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Try ‘beginner chess Tuesday’" className="rounded-xl border border-[#cfc5b4] bg-white px-4 py-3 outline-none focus:ring-2 focus:ring-[#bd4f34]"/><select value={category} onChange={e=>setCategory(e.target.value)} className="rounded-xl border border-[#cfc5b4] bg-white px-3"><option value="all">Every interest</option>{categories.map(x=><option key={x}>{x}</option>)}</select><select value={neighborhood} onChange={e=>setNeighborhood(e.target.value)} className="rounded-xl border border-[#cfc5b4] bg-white px-3"><option value="all">Every neighborhood</option>{neighborhoods.map(x=><option key={x}>{x}</option>)}</select></div>
      <div className="mt-3 flex flex-wrap gap-2">{[[firstTimers,setFirstTimers,"First-timer friendly"],[followedOnly,setFollowedOnly,"Following"]] .map(([v,s,l])=><button key={l as string} onClick={()=> (s as (x:boolean)=>void)(!(v as boolean))} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${v?"bg-[#bd4f34] text-white":"border border-[#cfc5b4] bg-white"}`}>{l as string}</button>)}<button onClick={()=>setShowAvailability(!showAvailability)} className="rounded-full border border-[#cfc5b4] bg-white px-3 py-1.5 text-xs font-semibold">When I&apos;m free {availability.length?`· ${availability.length}`:""}</button></div>
      {showAvailability&&<div className="mt-3 overflow-x-auto border-t border-[#ddd4c5] pt-3"><div className="grid min-w-[620px] grid-cols-[6rem_repeat(7,1fr)] gap-1 text-center text-[11px]"><span />{DAYS.map(day=><b key={day}>{day.slice(0,3)}</b>)}{BANDS.map(band=><div className="contents" key={band}><span className="py-2 text-left capitalize text-[#52645e]">{band}</span>{DAYS.map(day=>{const slot=`${day}-${band}`;return <button aria-pressed={availability.includes(slot)} key={slot} onClick={()=>toggleDay(slot)} className={`rounded-lg px-2 py-2 ${availability.includes(slot)?"bg-[#173c35] text-white":"bg-[#ece5d8] hover:bg-[#ddd4c5]"}`}>{availability.includes(slot)?"✓":"·"}</button>})}</div>)}</div></div>}
    </section>
    <div className="my-6 flex items-center justify-between"><h2 className="font-editorial text-2xl font-bold">{loading?"Looking around the city…":`${visible.length} communities`}</h2><span className="text-xs text-[#6c766e]">Verified sources · Updated regularly</span></div>
    {!loading&&!visible.length?<div className="rounded-3xl border border-dashed border-[#b8ad9c] p-12 text-center"><h2 className="font-editorial text-2xl font-bold">No exact match yet</h2><p className="mt-2 text-[#52645e]">Try a broader neighborhood or clear your availability.</p></div>:<div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">{visible.map(c=><CommunityCard key={c.id} community={c}/>)}</div>}
  </div></main>;
}
