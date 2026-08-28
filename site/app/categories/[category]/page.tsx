import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CATEGORY_CONFIG } from "../../lib/types";
import { getEventsData } from "../../lib/server-data";
import {
  absoluteUrl,
  categoryPath,
  DEFAULT_OG_IMAGE,
  DEFAULT_TWITTER_IMAGE,
  eventPath,
  plainText,
} from "../../lib/seo";

export const dynamicParams = false;

type Props = { params: Promise<{ category: string }> };

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  music: "Find upcoming concerts, DJ sets, jazz nights, and live music across New York City.",
  parties: "Discover upcoming parties, dance nights, and social events across New York City.",
  singles: "Find upcoming singles events, mixers, and social gatherings for meeting people in NYC.",
  art: "Explore upcoming art openings, exhibitions, gallery events, and museum programs in NYC.",
  food: "Discover food festivals, tastings, pop-ups, and drink events across New York City.",
  books: "Find author talks, readings, book clubs, and literary events across New York City.",
  outdoors: "Explore outdoor events, walks, markets, and activities across New York City.",
  exploration: "Find tours, neighborhood discoveries, and unusual things to do across New York City.",
  comedy: "Find upcoming stand-up, improv, and comedy shows across New York City.",
  dance: "Discover dance classes, performances, and social dance events across New York City.",
  movies: "Find upcoming screenings, movie nights, and film events across New York City.",
  film: "Find upcoming screenings, festivals, and independent film events across New York City.",
  fitness: "Find run clubs, group workouts, and fitness events across New York City.",
  wellness: "Discover yoga, meditation, and wellness events across New York City.",
  games: "Find game nights, trivia, competitions, and playful social events across New York City.",
  theater: "Find upcoming theater, stage, and performance events across New York City.",
  celebrities: "Discover live talks, interviews, and appearances across New York City.",
  design: "Find design talks, exhibitions, workshops, and creative events across New York City.",
  photography: "Find photography exhibitions, walks, workshops, and talks across New York City.",
  free: "Find free events and free things to do across New York City.",
  special: "Discover festivals, premieres, pop-ups, and special events across New York City.",
};

function availableCategories(): string[] {
  const categories = new Set(getEventsData().events.flatMap((event) => event.categories));
  return [...categories].filter((category) => category !== "other" && CATEGORY_CONFIG[category]);
}

export function generateStaticParams() {
  return availableCategories().map((category) => ({ category }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { category } = await params;
  const config = CATEGORY_CONFIG[category];
  if (!config || category === "other") return {};
  const title = `${config.label} Events in NYC`;
  const description = CATEGORY_DESCRIPTIONS[category] || `Find upcoming ${config.label.toLowerCase()} events across New York City.`;

  return {
    title,
    description,
    alternates: { canonical: categoryPath(category) },
    openGraph: {
      type: "website",
      url: categoryPath(category),
      title,
      description,
      images: [{ url: DEFAULT_OG_IMAGE, alt: `${config.label} events in NYC` }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [DEFAULT_TWITTER_IMAGE],
    },
  };
}

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(`${date}T12:00:00-04:00`));
}

export default async function CategoryPage({ params }: Props) {
  const { category } = await params;
  const config = CATEGORY_CONFIG[category];
  if (!config || category === "other") notFound();

  const data = getEventsData();
  const events = data.events
    .filter((event) => event.categories.includes(category))
    .sort((a, b) => a.date.localeCompare(b.date) || (b.score || 0) - (a.score || 0));
  const description = CATEGORY_DESCRIPTIONS[category] || `Find upcoming ${config.label.toLowerCase()} events across New York City.`;
  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `${config.label} events in NYC`,
    numberOfItems: events.length,
    itemListElement: events.slice(0, 100).map((event, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: event.title,
      url: absoluteUrl(eventPath(event.id)),
    })),
  };

  return (
    <main className="min-h-screen bg-[#f8f3e8] px-4 py-8 text-[#182923] sm:px-6 sm:py-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemList).replace(/</g, "\\u003c") }}
      />
      <div className="mx-auto max-w-5xl">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-[#66716c]">
          <Link href="/events" className="hover:text-[#173c35] hover:underline">NYC events</Link>
          <span aria-hidden="true"> / </span>
          <span>{config.label}</span>
        </nav>

        <header className="border-b border-[#d8d0c1] pb-7">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9a684e]">Things to do in New York</p>
          <h1 className="mt-2 font-editorial text-4xl font-bold leading-tight text-[#173c35] sm:text-6xl">
            {config.label} events in NYC
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[#52645e]">{description}</p>
          <p className="mt-2 text-sm text-[#7b837f]">{events.length} upcoming events · updated continuously</p>
        </header>

        {events.length ? (
          <section aria-label={`${config.label} event listings`} className="mt-8 grid gap-4 md:grid-cols-2">
            {events.map((event) => (
              <article key={event.id} className="rounded-xl border border-[#ded7c9] bg-[#fffdf8] p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-[#9a684e]">
                  {formatDate(event.date)}{event.startTime ? ` · ${event.startTime}` : ""}
                </p>
                <h2 className="mt-2 font-editorial text-xl font-bold leading-snug text-[#173c35]">
                  <Link href={eventPath(event.id)} className="hover:underline">{event.title}</Link>
                </h2>
                {(event.location?.name || event.location?.neighborhood) && (
                  <p className="mt-2 text-sm text-[#66716c]">
                    {event.location.name || event.location.neighborhood}
                    {event.location.name && event.location.neighborhood ? ` · ${event.location.neighborhood}` : ""}
                  </p>
                )}
                {event.description && (
                  <p className="mt-3 text-sm leading-6 text-[#52645e]">{plainText(event.description, 180)}</p>
                )}
              </article>
            ))}
          </section>
        ) : (
          <p className="mt-10 rounded-xl border border-dashed border-[#cfc8ba] p-8 text-center text-[#66716c]">
            No upcoming events in this category right now. Check back after the next refresh.
          </p>
        )}

        <div className="mt-10">
          <Link href="/events" className="font-semibold text-[#173c35] hover:underline">Browse every NYC event →</Link>
        </div>
      </div>
    </main>
  );
}
