export interface EventLocation {
  name: string;
  address: string;
  neighborhood: string | null;
}

export interface Event {
  id: string;
  title: string;
  description: string;
  date: string;
  startTime: string | null;
  endTime: string | null;
  location: EventLocation;
  categories: string[];
  source: string;
  sourceUrl: string;
  imageUrl: string | null;
  price: string;
  score: number;
  scrapedAt: string;
  instagramAccount?: string;
  account?: string;  // source-agnostic provenance alias (mirrors instagramAccount on IG)
  highlights?: string[];
  userSaved?: boolean;
  userTagged?: boolean;
  userAffinity?: boolean;
  userFollowing?: boolean;
  contributingSources?: string[];
  contributingAccounts?: string[];   // IG accounts that all promoted this event
  likes?: number;
  comments?: number;
  accountFollowers?: number;
  accountVerified?: boolean;
  recurring?: boolean;
  ocrEnriched?: boolean;
  extraImages?: string[];  // additional carousel slides (IG multi-photo posts)
  affinityComentions?: number;
  affinityComentionSources?: string[];  // affinity accounts that @-mentioned this account
  evergreen?: boolean;  // 'cool spot' rather than dated event — never expires
  // IG-channel provenance — set by specific scraper paths
  isStory?: boolean;       // 24h ephemeral; sourceUrl may expire
  isHighlight?: boolean;   // pinned story collection on profile
  isPinned?: boolean;      // pinned to top of feed by account
  isVideo?: boolean;       // post is a Reel/video (uses video_views for popularity)
  discoveredVia?: string;  // "ig_story" | "ig_highlight" | "venue_tagged" | etc.
  highlightTitle?: string; // e.g. "Upcoming Shows" when isHighlight=true
  venueTaggedFrom?: string;// venue account whose tagged-posts surfaced this
  attendanceSignal?: number;
}

export const HIGHLIGHT_CONFIG: Record<string, { label: string; color: string }> = {
  saved: { label: "★ Saved", color: "bg-amber-200 text-amber-900" },
  tagged: { label: "✨ You're tagged", color: "bg-pink-100 text-pink-800" },
  affinity: { label: "From accounts you save", color: "bg-amber-50 text-amber-700" },
  following: { label: "From accounts you follow", color: "bg-blue-50 text-blue-700" },
  verified: { label: "✓ Verified", color: "bg-green-100 text-green-800" },
  "multi-promoted": { label: "📣 Multi-promoted", color: "bg-emerald-100 text-emerald-800" },
  story: { label: "📲 Story (24h)", color: "bg-rose-100 text-rose-800" },
  trending: { label: "🔥 Trending now", color: "bg-orange-100 text-orange-800" },
  highlight: { label: "📌 Venue pick", color: "bg-violet-100 text-violet-800" },
  pinned: { label: "📍 Pinned post", color: "bg-indigo-100 text-indigo-800" },
  new: { label: "✨ Just Added", color: "bg-sky-100 text-sky-800" },
  free: { label: "Free", color: "bg-emerald-100 text-emerald-800" },
  special: { label: "Premiere", color: "bg-yellow-100 text-yellow-800" },
  festival: { label: "Festival", color: "bg-orange-100 text-orange-800" },
  "meet-people": { label: "Meet people", color: "bg-fuchsia-100 text-fuchsia-800" },
  vibes: { label: "Rooftop / Sunset", color: "bg-purple-100 text-purple-800" },
  jazz: { label: "Jazz", color: "bg-pink-100 text-pink-800" },
  nightlife: { label: "Nightlife", color: "bg-indigo-100 text-indigo-800" },
  nearby: { label: "Williamsburg", color: "bg-teal-100 text-teal-800" },
};

export interface TopAccount {
  username: string;
  events: number;
  yield: number;
  verified: boolean;
  image: string | null;
  userSaved?: boolean;  // user has previously saved from this account on IG
}

export interface EventsData {
  events: Event[];
  lastUpdated: string;
  topAccounts?: TopAccount[];
}

export const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  music: { label: "Live Music", color: "bg-pink-100 text-pink-800" },
  parties: { label: "Parties", color: "bg-rose-100 text-rose-800" },
  singles: { label: "Singles & Mixers", color: "bg-fuchsia-100 text-fuchsia-800" },
  art: { label: "Art & Museums", color: "bg-purple-100 text-purple-800" },
  food: { label: "Food & Drink", color: "bg-orange-100 text-orange-800" },
  books: { label: "Books & Reading", color: "bg-amber-100 text-amber-800" },
  outdoors: { label: "Outdoors", color: "bg-green-100 text-green-800" },
  exploration: { label: "NYC Exploration", color: "bg-teal-100 text-teal-800" },
  comedy: { label: "Comedy", color: "bg-yellow-100 text-yellow-800" },
  dance: { label: "Dance", color: "bg-rose-100 text-rose-800" },
  movies: { label: "Movies", color: "bg-slate-100 text-slate-800" },
  viewings: { label: "Watch Parties", color: "bg-slate-100 text-slate-800" },
  celebrities: { label: "Live Talks", color: "bg-violet-100 text-violet-800" },
  games: { label: "Games", color: "bg-blue-100 text-blue-800" },
  theater: { label: "Theater", color: "bg-indigo-100 text-indigo-800" },
  film: { label: "Film", color: "bg-indigo-100 text-indigo-800" },
  fitness: { label: "Fitness & Runs", color: "bg-lime-100 text-lime-800" },
  wellness: { label: "Wellness", color: "bg-cyan-100 text-cyan-800" },
  design: { label: "Design", color: "bg-stone-100 text-stone-800" },
  photography: { label: "Photography", color: "bg-zinc-100 text-zinc-800" },
  free: { label: "Free", color: "bg-emerald-100 text-emerald-800" },
  special: { label: "Special", color: "bg-yellow-100 text-yellow-800" },
  other: { label: "Other", color: "bg-gray-100 text-gray-800" },
};

export const SOURCE_LABELS: Record<string, string> = {
  luma: "Luma",
  bookclubbar: "Book Club Bar",
  lizsbookbar: "Liz's Book Bar",
  mcnallyjackson: "McNally Jackson",
  powerhousearena: "POWERHOUSE Arena",
  centerforfiction: "Center for Fiction",
  brooklyncomedy: "Brooklyn Comedy Collective",
  newyorkcomedyclub: "New York Comedy Club",
  eastvillecomedy: "EastVille Comedy",
  smorgasburg: "Smorgasburg",
  nypl: "NYPL",
  nycforfree: "NYC for Free",
  eventbrite: "Eventbrite",
  museums: "Museums",
  music_venues: "Music Venues",
  nyc_parks: "NYC Parks",
  theskint: "The Skint",
  meetup: "Meetup",
  dice: "Dice.fm",
  instagram: "Instagram",
  substack: "Substack",
  partiful: "Partiful",
  allevents: "AllEvents",
  songkick: "Songkick",
  reddit: "Reddit",
  greenwoodcemetery: "Green-Wood Cemetery",
  terminal5nyc: "Terminal 5",
  generic: "Web",
  // University event calendars (iter 164)
  nyu: "NYU",
  columbia: "Columbia",
  newschool: "The New School",
};
