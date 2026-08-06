import fs from "node:fs";
import path from "node:path";
import Link from "next/link";
import { Community, CommunitiesData, Event, EventsData } from "../../lib/types";
import FollowButton from "../../components/FollowButton";

function readJson<T>(name:string, fallback:T):T {
  try {
    return JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", name), "utf8"));
  } catch {
    return fallback;
  }
}
function communityList():Community[]{const d=readJson<CommunitiesData|Community[]>("communities.json",[]);return Array.isArray(d)?d:d.communities||[]}
export function generateStaticParams(){const params=communityList().filter(c=>c.profileStatus!=="directory_reference").map(c=>({slug:c.slug}));return params.length?params:[{slug:"preview"}]}
export const dynamicParams=false;
export default async function CommunityProfile({params}:{params:Promise<{slug:string}>}){
  const {slug}=await params, communities=communityList(), community=communities.find(c=>c.slug===slug);
  if(!community)return <main className="mx-auto max-w-3xl p-12"><h1 className="font-editorial text-4xl font-bold">Community not found</h1></main>;
  const ed=readJson<EventsData>("events.json",{events:[],lastUpdated:""});
  const events=ed.events.filter((e:Event)=>e.primaryCommunityId===community.id||e.communityIds?.includes(community.id)).filter((e:Event)=>e.date>=new Date().toISOString().slice(0,10)).slice(0,8);
  const similar=(community.similarCommunityIds||[]).map(id=>communities.find(c=>c.id===id)).filter(Boolean) as Community[];
  const official=community.links?.[0];
  return <main className="min-h-screen bg-[#f8f3e8] pb-20"><div className="relative h-64 overflow-hidden bg-[#173c35] sm:h-80">{community.imageUrl&&<img src={community.imageUrl} alt="" className="h-full w-full object-cover opacity-70"/>}<div className="absolute inset-0 bg-gradient-to-t from-[#173c35] to-transparent"/><div className="absolute bottom-0 mx-auto w-full p-6 text-white sm:p-10"><div className="mx-auto max-w-5xl"><p className="mb-2 text-xs font-bold uppercase tracking-[.22em] text-[#f3b65c]">{community.kind||"NYC community"}</p><h1 className="font-editorial text-5xl font-bold sm:text-7xl">{community.name}</h1><p className="mt-3 max-w-2xl text-lg text-white/85">{community.tagline}</p></div></div></div>
    <div className="mx-auto grid max-w-5xl gap-10 px-5 py-10 md:grid-cols-[1fr_280px]"><div><section><h2 className="font-editorial text-3xl font-bold">What this community is</h2><p className="mt-4 whitespace-pre-line leading-7 text-[#52645e]">{community.description||community.tagline}</p><div className="mt-5 flex flex-wrap gap-2">{[...community.categories,...(community.tags||[])].slice(0,8).map(t=><span className="rounded-full bg-[#e4eadf] px-3 py-1 text-xs" key={t}>{t}</span>)}</div></section>
      <section className="mt-12"><h2 className="font-editorial text-3xl font-bold">Next chance to join</h2>{events.length?<div className="mt-5 space-y-3">{events.map(e=><a href={e.sourceUrl} target="_blank" rel="noreferrer" key={e.id} className="flex items-center gap-4 rounded-2xl border border-[#d8d0c1] bg-white p-4 hover:border-[#bd4f34]"><div className="w-16 text-center"><b className="block text-xl text-[#bd4f34]">{new Date(e.date+"T12:00:00").toLocaleDateString("en-US",{day:"numeric"})}</b><span className="text-xs uppercase">{new Date(e.date+"T12:00:00").toLocaleDateString("en-US",{month:"short"})}</span></div><div><h3 className="font-semibold">{e.title}</h3><p className="text-sm text-[#52645e]">{e.location?.name} {e.startTime?`· ${e.startTime}`:""}</p></div><span className="ml-auto">↗</span></a>)}</div>:<p className="mt-4 rounded-2xl bg-[#ece5d8] p-5 text-[#52645e]">No announced event right now. Follow the community or check its official page for the next opening.</p>}</section>
      {similar.length>0&&<section className="mt-12"><h2 className="font-editorial text-3xl font-bold">Communities like this</h2><div className="mt-4 grid gap-3 sm:grid-cols-2">{similar.slice(0,6).map(c=><Link href={`/communities/${c.slug}`} key={c.id} className="rounded-2xl border border-[#d8d0c1] bg-white p-4 hover:border-[#bd4f34]"><b>{c.name}</b><p className="mt-1 text-xs text-[#52645e]">Similar interests · {c.neighborhoods?.[0]||"NYC"}</p></Link>)}</div></section>}
    </div><aside><div className="sticky top-20 rounded-3xl border border-[#d8d0c1] bg-[#fffdf8] p-5"><FollowButton id={community.id}/>{official&&<a href={official.url} target="_blank" rel="noreferrer" className="mt-3 block rounded-full border border-[#173c35] px-4 py-2.5 text-center text-sm font-semibold">Official page ↗</a>}<dl className="mt-6 space-y-4 text-sm"><div><dt className="text-xs uppercase text-[#8b887f]">Usual rhythm</dt><dd className="mt-1 font-medium">{community.schedule?.cadence||"Varies"}{community.schedule?.typicalDays?.length?` · ${community.schedule.typicalDays.join(", ")}`:""}</dd></div><div><dt className="text-xs uppercase text-[#8b887f]">Home turf</dt><dd className="mt-1 font-medium">{community.homeVenue||community.neighborhoods?.join(", ")||"Across NYC"}</dd></div><div><dt className="text-xs uppercase text-[#8b887f]">Activity</dt><dd className="mt-1 font-medium capitalize">● {community.activity?.state||"Unverified"}</dd></div></dl><p className="mt-6 border-t border-[#ddd4c5] pt-4 text-[11px] text-[#8b887f]">Sources: {community.sourceAttributions?.join(", ")||"official pages"}<br/>Last checked {community.lastVerifiedAt?new Date(community.lastVerifiedAt).toLocaleDateString():"recently"}</p></div></aside></div></main>;
}
