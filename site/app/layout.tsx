import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// SEO — goal: rank as the canonical "what's happening in NYC" hub.
// Targets the queries New Yorkers actually type: "events tonight nyc",
// "things to do this weekend brooklyn", "free events nyc this week",
// "[interest] events nyc", "events near me".
const SITE_URL = "https://prajjwal1.github.io/nyc";
const SITE_TITLE = "NYC Events — Things to do tonight, this weekend, this week in New York City";
const SITE_DESCRIPTION =
  "The most comprehensive guide to NYC events: live music, parties, free events, book clubs, "
  + "art openings, comedy shows, run clubs, yoga, food festivals, and more. Curated and "
  + "verified across Instagram, Eventbrite, Lu.ma, Substack, and more — updated continuously. "
  + "Find things to do tonight, this weekend, or this week across Brooklyn, Manhattan, Queens "
  + "and beyond.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: "%s — NYC Events",
  },
  description: SITE_DESCRIPTION,
  applicationName: "NYC Events",
  keywords: [
    "nyc events", "things to do nyc", "events tonight nyc", "events this weekend nyc",
    "events this week nyc", "free events nyc", "brooklyn events", "manhattan events",
    "queens events", "williamsburg events", "live music nyc", "comedy nyc", "book club nyc",
    "run clubs nyc", "yoga nyc", "art openings nyc", "singles events nyc", "meet people nyc",
    "what's happening in nyc", "nyc nightlife", "rooftop events nyc", "food events nyc",
  ],
  authors: [{ name: "NYC Events" }],
  creator: "NYC Events",
  publisher: "NYC Events",
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
    siteName: "NYC Events",
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
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
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
                  name: "NYC Events",
                  description: SITE_DESCRIPTION,
                  potentialAction: {
                    "@type": "SearchAction",
                    target: `${SITE_URL}/?q={search_term_string}`,
                    "query-input": "required name=search_term_string",
                  },
                },
                {
                  "@type": "Organization",
                  url: SITE_URL,
                  name: "NYC Events",
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
        {children}
      </body>
    </html>
  );
}
