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
  highlights?: string[];
  userSaved?: boolean;
  userAffinity?: boolean;
  likes?: number;
  comments?: number;
  accountFollowers?: number;
  accountVerified?: boolean;
  recurring?: boolean;
  ocrEnriched?: boolean;
}

export const HIGHLIGHT_CONFIG: Record<string, { label: string; color: string }> = {
  saved: { label: "★ Saved", color: "bg-amber-200 text-amber-900" },
  affinity: { label: "From accounts you save", color: "bg-amber-50 text-amber-700" },
  free: { label: "Free", color: "bg-emerald-100 text-emerald-800" },
  special: { label: "Premiere", color: "bg-yellow-100 text-yellow-800" },
  festival: { label: "Festival", color: "bg-orange-100 text-orange-800" },
  "meet-people": { label: "Meet people", color: "bg-fuchsia-100 text-fuchsia-800" },
  vibes: { label: "Rooftop / Sunset", color: "bg-purple-100 text-purple-800" },
  jazz: { label: "Jazz", color: "bg-pink-100 text-pink-800" },
  nightlife: { label: "Nightlife", color: "bg-indigo-100 text-indigo-800" },
  nearby: { label: "Williamsburg", color: "bg-teal-100 text-teal-800" },
};

export interface EventsData {
  events: Event[];
  lastUpdated: string;
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
};
