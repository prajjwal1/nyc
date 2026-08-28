import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import FollowButton from "../../components/FollowButton";
import { Community, CommunitiesData, Event, EventsData } from "../../lib/types";
import { absoluteUrl, DEFAULT_OG_IMAGE, DEFAULT_TWITTER_IMAGE, eventPath, plainText } from "../../lib/seo";

function readJson<T>(name: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", name), "utf8"));
  } catch {
    return fallback;
  }
}

function communityList(): Community[] {
  const data = readJson<CommunitiesData | Community[]>("communities.json", []);
  return Array.isArray(data) ? data : data.communities || [];
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function eventDate(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function shortMonth(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-US", { month: "short" });
}

function dayNumber(date: string) {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-US", { day: "numeric" });
}

function eventTime(value: string | null) {
  if (!value) return "Time on event page";
  const [hourString, minuteString] = value.split(":");
  const hour = Number.parseInt(hourString, 10);
  if (Number.isNaN(hour)) return value;
  const suffix = hour >= 12 ? "PM" : "AM";
  const standardHour = hour % 12 || 12;
  return `${standardHour}:${minuteString || "00"} ${suffix}`;
}

function checkedDate(value?: string) {
  if (!value) return "recently";
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(date.valueOf())) return "recently";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function todayInNewYork() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

export function generateStaticParams() {
  const params = communityList()
    .filter((community) => community.profileStatus !== "directory_reference")
    .map((community) => ({ slug: community.slug }));
  return params.length ? params : [{ slug: "preview" }];
}

export const dynamicParams = false;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const community = communityList().find(
    (item) => item.slug === slug && item.profileStatus !== "directory_reference",
  );
  if (!community) return {};

  const title = `${community.name}: NYC Community and Upcoming Events`;
  const description = plainText(
    community.description || community.tagline || `Learn about ${community.name}, an active community in New York City.`,
    155,
  );
  const canonical = `/communities/${community.slug}/`;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      type: "website",
      url: canonical,
      title,
      description,
      images: [{ url: community.imageUrl || DEFAULT_OG_IMAGE, alt: community.name }],
    },
    twitter: {
      card: community.imageUrl ? "summary_large_image" : "summary",
      title,
      description,
      images: [community.imageUrl || DEFAULT_TWITTER_IMAGE],
    },
  };
}

export default async function CommunityProfile({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const communities = communityList();
  const community = communities.find((item) => item.slug === slug && item.profileStatus !== "directory_reference");

  if (!community) {
    return (
      <main className="min-h-[70vh] bg-[#f4f3ee] px-5 py-20 text-center text-[#173a31]">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#9a684e]">Community directory</p>
        <h1 className="mt-4 font-editorial text-4xl">We couldn&apos;t find that profile.</h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#66716c]">It may have moved or is still being prepared.</p>
        <Link href="/communities" className="mt-7 inline-flex min-h-12 items-center rounded-full bg-[#173a31] px-6 text-sm font-semibold text-white">Back to communities</Link>
      </main>
    );
  }

  const eventData = readJson<EventsData>("events.json", { events: [], lastUpdated: "" });
  const today = todayInNewYork();
  const events = eventData.events
    .filter((event: Event) => event.primaryCommunityId === community.id || event.communityIds?.includes(community.id))
    .filter((event: Event) => event.date >= today)
    .sort((a: Event, b: Event) => `${a.date}${a.startTime || ""}`.localeCompare(`${b.date}${b.startTime || ""}`))
    .slice(0, 8);
  const similar = (community.similarCommunityIds || [])
    .map((id) => communities.find((item) => item.id === id))
    .filter((item): item is Community => !!item && item.profileStatus !== "directory_reference")
    .slice(0, 6);
  const official = community.links?.find((link) => link.type !== "web_search") || community.links?.[0];
  const labels = [...new Set([...community.categories, ...(community.tags || [])])].slice(0, 8);
  const activity = titleCase(community.activity?.state || "unverified");
  const jsonLd = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Organization",
    name: community.name,
    url: absoluteUrl(`/communities/${community.slug}/`),
    description: community.description || community.tagline,
    image: community.imageUrl || undefined,
    areaServed: { "@type": "City", name: "New York City" },
    sameAs: community.links?.map((link) => link.url).filter(Boolean),
  }).replace(/</g, "\\u003c");

  return (
    <main className="min-h-screen bg-[#f4f3ee] pb-24 text-[#182923]">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd }} />
      <div className="mx-auto max-w-6xl px-4 pt-5 sm:px-6 sm:pt-7">
        <Link href="/communities" scroll={false} className="inline-flex min-h-11 items-center gap-2 rounded-full pr-4 text-sm font-semibold text-[#52645e] outline-none transition hover:text-[#ad5b3d] focus-visible:ring-2 focus-visible:ring-[#ad5b3d]">
          <span aria-hidden="true">←</span> Back to communities
        </Link>

        <section className="mt-3 overflow-hidden rounded-[1.75rem] border border-[#d4d2ca] bg-[#fbfaf7] shadow-[0_18px_60px_rgba(34,55,47,0.07)] sm:mt-5 md:grid md:min-h-[390px] md:grid-cols-[0.88fr_1.12fr]">
          <div className="relative min-h-52 overflow-hidden bg-[#dfe5de] sm:min-h-64 md:min-h-full">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_25%,rgba(224,156,120,0.45),transparent_35%),linear-gradient(145deg,#31564c,#173a31)]" />
            {community.imageUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={community.imageUrl} alt={community.name} className="relative h-full min-h-52 w-full object-cover saturate-[0.82] sm:min-h-64 md:absolute md:inset-0 md:min-h-full" />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-[#122d25]/50 via-transparent to-transparent" />
            <span className="absolute bottom-4 left-4 rounded-full border border-white/30 bg-[#122d25]/60 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.18em] text-white backdrop-blur">
              {events.length ? `${events.length} upcoming` : "Recurring community"}
            </span>
          </div>

          <div className="flex min-w-0 flex-col justify-end p-6 sm:p-8 md:p-10 lg:p-12">
            <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#9a684e]">{titleCase(community.kind || "NYC community")}</p>
            <h1 className="mt-3 break-words font-editorial text-[clamp(2.55rem,11vw,5.5rem)] font-medium leading-[0.88] tracking-[-0.045em] text-[#173a31] [overflow-wrap:anywhere] md:text-[clamp(3rem,5.5vw,5.5rem)]">
              {community.name}
            </h1>
            {community.tagline && <p className="mt-5 max-w-xl text-[15px] leading-6 text-[#5f6d67] sm:text-base sm:leading-7">{community.tagline}</p>}
            <div className="mt-6 flex flex-wrap gap-2">
              {community.newcomerFriendly && <span className="rounded-full bg-[#e2eadf] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#31564c]">First-timer friendly</span>}
              {labels.slice(0, 3).map((label) => <span key={label} className="rounded-full border border-[#d6d5ce] px-3 py-1.5 text-[10px] font-medium text-[#5e6b66]">{titleCase(label)}</span>)}
            </div>
          </div>
        </section>

        <div className="mt-7 grid gap-8 md:mt-10 md:grid-cols-[minmax(0,1fr)_300px] md:items-start lg:gap-12">
          <div className="order-2 min-w-0 md:order-1">
            <section aria-labelledby="about-community">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#9a684e]">About</p>
              <h2 id="about-community" className="mt-2 font-editorial text-3xl font-medium tracking-[-0.02em] text-[#173a31] sm:text-4xl">What this community is</h2>
              <p className="mt-5 whitespace-pre-line text-[15px] leading-7 text-[#5f6d67] sm:text-base sm:leading-8">{community.description || community.tagline || `Learn more about ${community.name} and its gatherings in New York City.`}</p>
              {labels.length > 0 && <div className="mt-6 flex flex-wrap gap-2">{labels.map((label) => <span className="rounded-full bg-[#e5e8e1] px-3 py-1.5 text-xs text-[#41574f]" key={label}>{titleCase(label)}</span>)}</div>}
            </section>

            <section aria-labelledby="upcoming-community-events" className="mt-14 sm:mt-16">
              <div className="flex items-end justify-between gap-4 border-b border-[#d8d7d0] pb-4">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#9a684e]">Upcoming</p>
                  <h2 id="upcoming-community-events" className="mt-2 font-editorial text-3xl font-medium tracking-[-0.02em] text-[#173a31] sm:text-4xl">Next chance to join</h2>
                </div>
                {events.length > 0 && <span className="shrink-0 text-xs text-[#77817d]">{events.length} listed</span>}
              </div>

              {events.length ? (
                <div className="mt-4 space-y-3">
                  {events.map((event) => (
                    <Link href={eventPath(event.id)} key={event.id} aria-label={`${event.title}, ${eventDate(event.date)}`} className="group/event grid min-h-24 grid-cols-[3.35rem_minmax(0,1fr)_1.5rem] items-center gap-3 rounded-2xl border border-[#d6d5ce] bg-[#fbfaf7] p-3.5 outline-none transition hover:border-[#b9bbb4] hover:shadow-[0_10px_30px_rgba(34,55,47,0.06)] focus-visible:ring-2 focus-visible:ring-[#ad5b3d] sm:grid-cols-[4rem_minmax(0,1fr)_2rem] sm:gap-4 sm:p-4">
                      <time dateTime={event.date} className="rounded-xl bg-[#ece9e1] py-2 text-center">
                        <b className="block font-editorial text-2xl font-medium leading-none text-[#ad5b3d]">{dayNumber(event.date)}</b>
                        <span className="mt-1 block text-[9px] font-semibold uppercase tracking-[0.12em] text-[#6c7772]">{shortMonth(event.date)}</span>
                      </time>
                      <div className="min-w-0">
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-[#7a837f]">{eventDate(event.date)} · {eventTime(event.startTime)}</p>
                        <h3 className="mt-1 break-words text-sm font-semibold leading-5 text-[#263d35] group-hover/event:text-[#9f4f36] sm:text-base">{event.title}</h3>
                        <p className="mt-1 truncate text-xs text-[#68746f]">{event.location?.name || event.location?.neighborhood || "Location on event page"}{event.price ? ` · ${event.price}` : ""}</p>
                      </div>
                      <span aria-hidden="true" className="text-lg text-[#9f4f36]">→</span>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-dashed border-[#cbc9c0] bg-[#ebe9e2]/65 p-6 sm:p-8">
                  <h3 className="font-editorial text-2xl text-[#173a31]">Nothing announced right now.</h3>
                  <p className="mt-2 max-w-lg text-sm leading-6 text-[#65716c]">Follow the community to keep it close, or visit its official page for the latest schedule.</p>
                  {official && <a href={official.url} target="_blank" rel="noopener noreferrer" className="mt-5 inline-flex min-h-11 items-center rounded-full border border-[#173a31] px-4 text-xs font-semibold text-[#173a31]">Visit official page <span aria-hidden="true" className="ml-1">↗</span></a>}
                </div>
              )}
            </section>

            {similar.length > 0 && (
              <section aria-labelledby="similar-communities" className="mt-14 sm:mt-16">
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#9a684e]">Keep exploring</p>
                <h2 id="similar-communities" className="mt-2 font-editorial text-3xl font-medium tracking-[-0.02em] text-[#173a31] sm:text-4xl">Communities like this</h2>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {similar.map((item) => (
                    <Link href={`/communities/${item.slug}`} key={item.id} className="group/similar flex min-h-24 items-center justify-between gap-4 rounded-2xl border border-[#d6d5ce] bg-[#fbfaf7] p-4 outline-none transition hover:border-[#b9bbb4] focus-visible:ring-2 focus-visible:ring-[#ad5b3d]">
                      <div className="min-w-0">
                        <h3 className="break-words font-editorial text-xl font-medium leading-tight text-[#173a31] group-hover/similar:text-[#9f4f36]">{item.name}</h3>
                        <p className="mt-1 truncate text-xs text-[#68746f]">{item.neighborhoods?.[0] ? titleCase(item.neighborhoods[0]) : "New York City"} · {item.categories[0] ? titleCase(item.categories[0]) : "Community"}</p>
                      </div>
                      <span aria-hidden="true" className="shrink-0 text-[#9f4f36]">→</span>
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </div>

          <aside className="order-1 md:order-2">
            <div className="rounded-[1.5rem] border border-[#d4d2ca] bg-[#fbfaf7] p-5 shadow-[0_12px_35px_rgba(34,55,47,0.05)] md:sticky md:top-20 sm:p-6">
              <FollowButton id={community.id} name={community.name} />
              {official && <a href={official.url} target="_blank" rel="noopener noreferrer" className="mt-3 flex min-h-12 items-center justify-center rounded-full border border-[#173a31] px-5 text-sm font-semibold text-[#173a31] outline-none transition hover:bg-[#edf0eb] focus-visible:ring-2 focus-visible:ring-[#ad5b3d]">Official page <span aria-hidden="true" className="ml-1">↗</span></a>}

              <dl className="mt-6 divide-y divide-[#e2e0d8] border-y border-[#e2e0d8] text-sm">
                <div className="py-4">
                  <dt className="text-[9px] font-semibold uppercase tracking-[0.18em] text-[#858c88]">Usual rhythm</dt>
                  <dd className="mt-1.5 font-medium leading-5 text-[#354a43]">{community.schedule?.cadence ? titleCase(community.schedule.cadence) : "Varies"}{community.schedule?.typicalDays?.length ? ` · ${community.schedule.typicalDays.join(", ")}` : ""}</dd>
                </div>
                <div className="py-4">
                  <dt className="text-[9px] font-semibold uppercase tracking-[0.18em] text-[#858c88]">Home turf</dt>
                  <dd className="mt-1.5 font-medium leading-5 text-[#354a43]">{community.homeVenue || community.neighborhoods?.map(titleCase).join(", ") || "Across New York City"}</dd>
                </div>
                <div className="py-4">
                  <dt className="text-[9px] font-semibold uppercase tracking-[0.18em] text-[#858c88]">Activity</dt>
                  <dd className="mt-1.5 flex items-center gap-2 font-medium text-[#354a43]"><span aria-hidden="true" className={`h-2 w-2 rounded-full ${community.activity?.state === "active" ? "bg-[#4f806c]" : "bg-[#ba8a62]"}`} />{activity}</dd>
                </div>
                {(community.cost || community.accessNotes) && <div className="py-4">
                  <dt className="text-[9px] font-semibold uppercase tracking-[0.18em] text-[#858c88]">Good to know</dt>
                  <dd className="mt-1.5 font-medium leading-5 text-[#354a43]">{[community.cost, community.accessNotes].filter(Boolean).join(" · ")}</dd>
                </div>}
              </dl>
              <p className="mt-4 text-[10px] leading-4 text-[#858c88]">Information last checked {checkedDate(community.lastVerifiedAt)}.</p>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
