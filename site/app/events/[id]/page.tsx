import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CATEGORY_CONFIG, Event, SOURCE_LABELS } from "../../lib/types";
import { getEventById, getEventsData } from "../../lib/server-data";
import {
  absoluteUrl,
  categoryPath,
  DEFAULT_OG_IMAGE,
  DEFAULT_TWITTER_IMAGE,
  eventPath,
  plainText,
} from "../../lib/seo";
import EventDetailActions from "../../components/EventDetailActions";
import { eventOrganizerDetails } from "../../lib/organizer";

export const dynamicParams = false;

type Props = { params: Promise<{ id: string }> };

export function generateStaticParams() {
  return getEventsData().events.map((event) => ({ id: event.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const event = getEventById(id);
  if (!event) return {};

  const description = event.description
    ? plainText(event.description, 155)
    : `${event.title}, an upcoming event in New York City on ${formatLongDate(event.date)}.`;
  const canonical = eventPath(event.id);

  return {
    title: `${event.title} in NYC`,
    description,
    alternates: { canonical },
    openGraph: {
      type: "website",
      url: canonical,
      title: event.title,
      description,
      images: [{
        url: event.imageUrl || DEFAULT_OG_IMAGE,
        alt: event.imageUrl ? `${event.title} event poster` : "NYC Events guide",
      }],
    },
    twitter: {
      card: event.imageUrl ? "summary_large_image" : "summary",
      title: event.title,
      description,
      images: [event.imageUrl || DEFAULT_TWITTER_IMAGE],
    },
  };
}

function formatLongDate(date: string): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(`${date}T12:00:00-04:00`));
}

function formatTime(time: string): string {
  const [hourValue, minuteValue] = time.split(":").map(Number);
  const suffix = hourValue >= 12 ? "PM" : "AM";
  const hour = hourValue % 12 || 12;
  return minuteValue ? `${hour}:${String(minuteValue).padStart(2, "0")} ${suffix}` : `${hour} ${suffix}`;
}

function eventDateTime(event: Event, time: string | null): string {
  return time ? `${event.date}T${time}:00` : event.date;
}

function eventJsonLd(event: Event) {
  const locationName = event.location?.name || "New York City";
  const price = event.price === "free" ? "0" : event.price?.match(/\d+(?:\.\d+)?/)?.[0];

  return {
    "@context": "https://schema.org",
    "@type": "Event",
    name: event.title,
    description: plainText(event.description || event.title, 5000),
    startDate: eventDateTime(event, event.startTime),
    endDate: event.endTime ? eventDateTime(event, event.endTime) : undefined,
    eventStatus: "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    url: absoluteUrl(eventPath(event.id)),
    image: event.imageUrl ? [event.imageUrl] : undefined,
    location: {
      "@type": "Place",
      name: locationName,
      address: {
        "@type": "PostalAddress",
        streetAddress: event.location?.address || undefined,
        addressLocality: "New York",
        addressRegion: "NY",
        addressCountry: "US",
      },
    },
    organizer: event.organizer
      ? {
          "@type": "Organization",
          name: event.organizer,
          url: event.organizerUrl || undefined,
        }
      : undefined,
    offers: price
      ? {
          "@type": "Offer",
          url: event.sourceUrl,
          availability: "https://schema.org/InStock",
          price,
          priceCurrency: "USD",
        }
      : undefined,
    keywords: event.categories.join(", "),
  };
}

export default async function EventPage({ params }: Props) {
  const { id } = await params;
  const event = getEventById(id);
  if (!event) notFound();

  const dateLabel = formatLongDate(event.date);
  const timeLabel = event.startTime
    ? `${formatTime(event.startTime)}${event.endTime ? ` – ${formatTime(event.endTime)}` : ""}`
    : null;
  const categories = event.categories.filter((category) => category !== "other");
  const preferenceAccount = event.account || event.instagramAccount || event.organizer;
  const preferenceLabel = event.account || event.instagramAccount
    ? `@${event.account || event.instagramAccount}`
    : event.organizer;
  const organizer = eventOrganizerDetails(event);
  const jsonLd = JSON.stringify(eventJsonLd(event)).replace(/</g, "\\u003c");

  return (
    <main className="min-h-screen bg-[#f8f3e8] px-4 py-8 text-[#182923] sm:px-6 sm:py-12">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd }} />
      <article className="mx-auto max-w-3xl">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-[#66716c]">
          <Link href="/events" className="hover:text-[#173c35] hover:underline">NYC events</Link>
          <span aria-hidden="true"> / </span>
          <span>{event.title}</span>
        </nav>

        {event.imageUrl && (
          <img
            src={event.imageUrl}
            alt={`${event.title} event poster`}
            className="mb-7 max-h-[34rem] w-full rounded-2xl border border-[#ded7c9] bg-white object-contain"
          />
        )}

        <div className="rounded-2xl border border-[#ded7c9] bg-[#fffdf8] p-5 shadow-sm sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9a684e]">NYC event</p>
          <h1 className="mt-2 font-editorial text-3xl font-bold leading-tight text-[#173c35] sm:text-5xl">
            {event.title}
          </h1>
          <a
            href={organizer.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center gap-1 text-sm text-[#52645e] hover:text-[#173c35] hover:underline"
          >
            <span className="text-[#8b918e]">{organizer.isOrganizer ? "By" : "More info"}</span>{" "}
            <span className="font-semibold">{organizer.label} ↗</span>
          </a>
          {event.userFollowing && preferenceAccount && (
            <p className="mt-3 text-sm font-semibold text-sky-800">★ Because you follow {preferenceLabel}</p>
          )}
          {!event.userFollowing && event.userAffinity && preferenceAccount && (
            <p className="mt-3 text-sm font-semibold text-amber-800">From an account you save from · {preferenceLabel}</p>
          )}

          <dl className="mt-6 grid gap-4 border-y border-[#e8e2d2] py-5 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">When</dt>
              <dd className="mt-1 font-medium text-[#253d36]">{dateLabel}{timeLabel ? ` · ${timeLabel}` : ""}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">Where</dt>
              <dd className="mt-1 font-medium text-[#253d36]">
                {event.location?.name || "New York City"}
                {event.location?.neighborhood ? ` · ${event.location.neighborhood}` : ""}
              </dd>
              {event.location?.address && <dd className="mt-0.5 text-[#66716c]">{event.location.address}</dd>}
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">Price</dt>
              <dd className="mt-1 font-medium capitalize text-[#253d36]">{event.price || "See event page"}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-[#8b918e]">Source</dt>
              <dd className="mt-1 font-medium text-[#253d36]">{SOURCE_LABELS[event.source] || event.source}</dd>
            </div>
          </dl>

          {event.description && (
            <div className="mt-6">
              <h2 className="font-editorial text-xl font-bold text-[#173c35]">About this event</h2>
              <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-[#52645e]">{event.description}</p>
            </div>
          )}

          {categories.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2" aria-label="Event categories">
              {categories.map((category) => (
                <Link
                  key={category}
                  href={categoryPath(category)}
                  className="rounded-full border border-[#c9d8d2] bg-[#edf5f1] px-3 py-1 text-xs font-semibold text-[#31554c] hover:border-[#719489]"
                >
                  {CATEGORY_CONFIG[category]?.label || category}
                </Link>
              ))}
            </div>
          )}

          <EventDetailActions event={event} />

          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href={event.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full bg-[#173c35] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#245449]"
            >
              View original event ↗
            </a>
            <Link
              href="/events"
              className="rounded-full border border-[#9bb7ae] px-5 py-2.5 text-sm font-semibold text-[#173c35] hover:bg-[#edf5f1]"
            >
              Browse more NYC events
            </Link>
          </div>
        </div>
      </article>
    </main>
  );
}
