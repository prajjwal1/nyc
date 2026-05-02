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
  scrapedAt: string;
}

export interface EventsData {
  events: Event[];
  lastUpdated: string;
}

export const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  books: { label: "Books & Reading", color: "bg-amber-100 text-amber-800" },
  art: { label: "Art & Museums", color: "bg-purple-100 text-purple-800" },
  music: { label: "Live Music", color: "bg-pink-100 text-pink-800" },
  parties: { label: "Parties & Social", color: "bg-rose-100 text-rose-800" },
  outdoors: { label: "Parks & Outdoors", color: "bg-green-100 text-green-800" },
  food: { label: "Food & Drink", color: "bg-orange-100 text-orange-800" },
  games: { label: "Games & Activities", color: "bg-blue-100 text-blue-800" },
  theater: { label: "Theater & Film", color: "bg-indigo-100 text-indigo-800" },
  free: { label: "Free", color: "bg-emerald-100 text-emerald-800" },
  special: { label: "Special Events", color: "bg-yellow-100 text-yellow-800" },
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
};
