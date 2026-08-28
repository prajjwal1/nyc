import type { Metadata } from "next";
import { DEFAULT_OG_IMAGE, DEFAULT_TWITTER_IMAGE } from "../lib/seo";

const description =
  "Find active NYC communities, clubs, recurring meetups, and groups to join by interest, neighborhood, and schedule.";

export const metadata: Metadata = {
  title: "NYC Communities and Clubs to Join",
  description,
  alternates: { canonical: "/communities/" },
  openGraph: {
    type: "website",
    url: "/communities/",
    title: "NYC Communities and Clubs to Join",
    description,
    images: [{ url: DEFAULT_OG_IMAGE, alt: "NYC communities and events guide" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "NYC Communities and Clubs to Join",
    description,
    images: [DEFAULT_TWITTER_IMAGE],
  },
};

export default function CommunitiesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
