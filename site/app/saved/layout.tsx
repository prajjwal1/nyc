import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Your Saved Events",
  description: "Events saved privately in this browser.",
  alternates: { canonical: "/saved/" },
  robots: { index: false, follow: false },
};

export default function SavedLayout({ children }: { children: React.ReactNode }) {
  return children;
}
