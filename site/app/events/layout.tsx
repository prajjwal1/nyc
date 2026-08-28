import type { Metadata } from "next";
import { DEFAULT_OG_IMAGE, DEFAULT_TWITTER_IMAGE, SITE_DESCRIPTION } from "../lib/seo";

export const metadata: Metadata = {
  title: "Upcoming Events in NYC",
  description: SITE_DESCRIPTION,
  alternates: { canonical: "/events/" },
  openGraph: {
    type: "website",
    url: "/events/",
    title: "Upcoming Events in NYC",
    description: SITE_DESCRIPTION,
    images: [{ url: DEFAULT_OG_IMAGE, alt: "NYC Events guide" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Upcoming Events in NYC",
    description: SITE_DESCRIPTION,
    images: [DEFAULT_TWITTER_IMAGE],
  },
};

export default function EventsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
