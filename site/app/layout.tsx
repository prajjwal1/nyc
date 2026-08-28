import type { Metadata } from "next";
import "./globals.css";
import SiteNav from "./components/SiteNav";
import { SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, SITE_URL } from "./lib/seo";

// SEO — goal: rank as the canonical "what's happening in NYC" hub.
// Targets the queries New Yorkers actually type: "events tonight nyc",
// "things to do this weekend brooklyn", "free events nyc this week",
// "[interest] events nyc", "events near me".
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: "%s — NYC Events",
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: [
    "nyc events", "things to do nyc", "events tonight nyc", "events this weekend nyc",
    "events this week nyc", "free events nyc", "brooklyn events", "manhattan events",
    "queens events", "williamsburg events", "live music nyc", "comedy nyc", "book club nyc",
    "run clubs nyc", "yoga nyc", "art openings nyc", "singles events nyc", "meet people nyc",
    "what's happening in nyc", "nyc nightlife", "rooftop events nyc", "food events nyc",
  ],
  authors: [{ name: SITE_NAME }],
  creator: SITE_NAME,
  publisher: SITE_NAME,
  formatDetection: { email: false, address: false, telephone: false },
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    siteName: SITE_NAME,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  category: "events",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        {/* JSON-LD structured data — helps Google understand this is an
            events directory for NYC. Site-level markup; per-event Event
            schema is in the events.json payload itself. */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "WebSite",
                  url: SITE_URL,
                  name: SITE_NAME,
                  description: SITE_DESCRIPTION,
                },
                {
                  "@type": "Organization",
                  url: SITE_URL,
                  name: SITE_NAME,
                  description:
                    "A curated, continuously-updated directory of NYC events across Instagram, Eventbrite, Lu.ma, and more.",
                  areaServed: {
                    "@type": "City",
                    name: "New York City",
                  },
                },
              ],
            }),
          }}
        />
        <SiteNav />
        {children}
      </body>
    </html>
  );
}
