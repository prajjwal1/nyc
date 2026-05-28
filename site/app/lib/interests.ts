// Client-side interest tracking. Compounds across visits without any backend.
//
// Tracks three signals from user behavior:
//   - account clicks: which @-accounts the user clicks to filter by
//   - category clicks: which category chips the user toggles on
//   - card opens: which event sourceUrls the user clicks through to
//
// The aggregated profile re-ranks events client-side: events matching
// learned signals get a small boost on top of the server-side score, so
// the feed adapts to what the user actually engages with over time.

const STORAGE_KEY = "nyc-events:interests:v1";

export interface InterestProfile {
  accounts: Record<string, number>;
  categories: Record<string, number>;
  // Track distinct event domains/hosts to learn source preferences
  hosts: Record<string, number>;
  // Negative signals: counts of hides per account/category/host. Symmetric
  // with the positive maps so a user's "no thanks" on one event from
  // @somenightclub deboosts other events from that same account.
  negAccounts: Record<string, number>;
  negCategories: Record<string, number>;
  negHosts: Record<string, number>;
  // Schedule learning: count of events the user has opened by start-time
  // bucket (key: "morning" | "midday" | "afternoon" | "evening" | "late")
  // and by day-of-week (key: "0".."6", Sunday=0). Lets the feed adapt to
  // a 7am-runner profile vs a 10pm-show-goer.
  timeBuckets: Record<string, number>;
  dayOfWeek: Record<string, number>;
  // When was this profile last updated (ISO)
  updatedAt: string;
}

const empty = (): InterestProfile => ({
  accounts: {},
  categories: {},
  hosts: {},
  negAccounts: {},
  negCategories: {},
  negHosts: {},
  timeBuckets: {},
  dayOfWeek: {},
  updatedAt: new Date().toISOString(),
});

export function loadProfile(): InterestProfile {
  if (typeof window === "undefined") return empty();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return empty();
    const parsed = JSON.parse(raw);
    return {
      accounts: parsed.accounts || {},
      categories: parsed.categories || {},
      hosts: parsed.hosts || {},
      negAccounts: parsed.negAccounts || {},
      negCategories: parsed.negCategories || {},
      negHosts: parsed.negHosts || {},
      timeBuckets: parsed.timeBuckets || {},
      dayOfWeek: parsed.dayOfWeek || {},
      updatedAt: parsed.updatedAt || new Date().toISOString(),
    };
  } catch {
    return empty();
  }
}

export function saveProfile(p: InterestProfile): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    // localStorage may be full / disabled — silently no-op
  }
}

function bump(map: Record<string, number>, key: string, by = 1): void {
  if (!key) return;
  map[key] = (map[key] || 0) + by;
}

export function trackAccountClick(account: string | undefined): void {
  if (!account) return;
  const p = loadProfile();
  bump(p.accounts, account.toLowerCase(), 2);
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

export function trackCategoryClick(category: string): void {
  const p = loadProfile();
  bump(p.categories, category, 1);
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

// Search query terms that map to category labels — when the user searches
// for these words, treat it as a category-interest signal too.
const _SEARCH_CATEGORY_HINTS: Record<string, string> = {
  jazz: "music",
  concert: "music",
  music: "music",
  comedy: "comedy",
  yoga: "wellness",
  run: "fitness",
  running: "fitness",
  "run club": "fitness",
  fitness: "fitness",
  art: "art",
  gallery: "art",
  museum: "art",
  book: "books",
  books: "books",
  reading: "books",
  bookclub: "books",
  "book club": "books",
  film: "film",
  movie: "film",
  screening: "film",
  food: "food",
  brunch: "food",
  dinner: "food",
  rooftop: "outdoors",
  park: "outdoors",
  hike: "outdoors",
  outdoor: "outdoors",
  outdoors: "outdoors",
  dance: "dance",
  workshop: "workshop",
  class: "workshop",
};

// Treat a committed search as a soft engagement signal: an @-handle
// becomes a strong account-interest bump, and category-keyword queries
// fold into the category map. Lower weights than clicks so a stray
// search doesn't dominate.
export function trackSearchSignal(query: string): void {
  const q = (query || "").trim().toLowerCase();
  if (!q || q.length < 2) return;
  const p = loadProfile();
  if (q.startsWith("@")) {
    // @-handle — explicit account interest. Strong signal (user typed it).
    const handle = q.slice(1).split(/[\s/]/)[0];
    if (handle) bump(p.accounts, handle, 2);
  } else {
    // Free-text — see if it maps to a known category. Multi-word matches first.
    for (const [phrase, cat] of Object.entries(_SEARCH_CATEGORY_HINTS)) {
      if (q.includes(phrase)) {
        bump(p.categories, cat, 1);
        break;
      }
    }
  }
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

function timeBucket(startTime: string | null | undefined): string | null {
  if (!startTime || !startTime.includes(":")) return null;
  const h = parseInt(startTime.split(":")[0], 10);
  if (Number.isNaN(h)) return null;
  if (h < 11) return "morning";       // <11am
  if (h < 14) return "midday";        // 11am-2pm
  if (h < 17) return "afternoon";     // 2-5pm
  if (h < 22) return "evening";       // 5-10pm
  return "late";                      // 10pm+
}

function dayOfWeekKey(dateStr: string | undefined): string | null {
  if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null;
  try {
    const d = new Date(dateStr + "T00:00:00");
    return String(d.getDay());
  } catch {
    return null;
  }
}

export function trackEventOpen(
  account: string | undefined,
  categories: string[],
  sourceUrl: string,
  startTime?: string | null,
  date?: string,
): void {
  const p = loadProfile();
  if (account) bump(p.accounts, account.toLowerCase(), 3); // strongest signal
  for (const c of categories || []) bump(p.categories, c, 1);
  try {
    const u = new URL(sourceUrl);
    bump(p.hosts, u.hostname.toLowerCase(), 1);
  } catch {
    // ignore unparseable URLs
  }
  // Schedule learning — track when the user is actually opening events.
  // A 7am-runner and a 10pm-show-goer should see very different defaults.
  const tb = timeBucket(startTime);
  if (tb) bump(p.timeBuckets, tb, 1);
  const dow = dayOfWeekKey(date);
  if (dow) bump(p.dayOfWeek, dow, 1);
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

// Compute a -0.25..+0.15 adjustment for an event given a learned profile.
// Positive cap is small (saved/tagged still trump it); negative cap is
// larger because explicit hides are a stronger no-confidence signal.
export function interestBoost(
  event: {
    instagramAccount?: string;
    categories?: string[];
    sourceUrl?: string;
    startTime?: string | null;
    date?: string;
  },
  profile: InterestProfile,
): number {
  let boost = 0;
  const acct = (event.instagramAccount || "").toLowerCase();
  if (acct && profile.accounts[acct]) {
    const n = profile.accounts[acct];
    // saturating: 1 click +0.04, 3 clicks +0.07, 10+ +0.10
    boost += Math.min(0.10, 0.03 + Math.log2(n + 1) * 0.02);
  }
  for (const c of event.categories || []) {
    const n = profile.categories[c];
    if (n) boost += Math.min(0.04, n * 0.005);
  }
  if (event.sourceUrl) {
    try {
      const host = new URL(event.sourceUrl).hostname.toLowerCase();
      const n = profile.hosts[host];
      if (n) boost += Math.min(0.03, n * 0.005);
    } catch {
      // ignore
    }
  }
  // Schedule match: small boost for events at times the user actually opens.
  // Compute the user's preferred bucket share; if this event's bucket is
  // dominant in their history (>=40% of opens), nudge it up.
  const tb = timeBucket(event.startTime);
  if (tb && profile.timeBuckets) {
    const total = Object.values(profile.timeBuckets).reduce((a, b) => a + b, 0);
    if (total >= 5) {
      const share = (profile.timeBuckets[tb] || 0) / total;
      if (share >= 0.4) boost += 0.04;
      else if (share >= 0.25) boost += 0.02;
      else if (share <= 0.05) boost -= 0.02; // user almost never opens this slot
    }
  }
  const dow = dayOfWeekKey(event.date);
  if (dow && profile.dayOfWeek) {
    const total = Object.values(profile.dayOfWeek).reduce((a, b) => a + b, 0);
    if (total >= 5) {
      const share = (profile.dayOfWeek[dow] || 0) / total;
      if (share >= 0.30) boost += 0.03;
      else if (share >= 0.20) boost += 0.015;
    }
  }
  const positive = Math.min(0.18, boost);

  // Negative signals — explicit hides translate to deboost on other events
  // from the same account/category/host. One hide is a soft signal; 3+ on
  // the same account = "stop showing me this".
  let neg = 0;
  if (acct && profile.negAccounts?.[acct]) {
    const n = profile.negAccounts[acct];
    // 1 hide -0.04, 3 hides -0.10, 5+ -0.15 (effectively buries).
    neg += Math.min(0.15, 0.03 + Math.log2(n + 1) * 0.04);
  }
  for (const c of event.categories || []) {
    const n = profile.negCategories?.[c];
    if (n) neg += Math.min(0.05, n * 0.01);
  }
  if (event.sourceUrl) {
    try {
      const host = new URL(event.sourceUrl).hostname.toLowerCase();
      const n = profile.negHosts?.[host];
      if (n) neg += Math.min(0.04, n * 0.008);
    } catch {
      // ignore
    }
  }
  const negative = Math.min(0.25, neg);

  return positive - negative;
}

// Last-visited timestamp — tracked on page load so we can show "X new
// since your last visit" badges. Updated AFTER reading so the current
// session sees the previous-visit timestamp.
const LAST_VISITED_KEY = "nyc-events:lastVisitedAt:v1";

export function readAndAdvanceLastVisited(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const prev = window.localStorage.getItem(LAST_VISITED_KEY);
    window.localStorage.setItem(LAST_VISITED_KEY, new Date().toISOString());
    return prev;
  } catch {
    return null;
  }
}

// Locally-saved events — explicit positive signal the user controls. The
// IG-saved signal already exists for IG events the user bookmarked on IG
// itself; this is the equivalent for non-IG events (Eventbrite, Luma, etc.)
// where there's no platform "save". Stored in localStorage.
const SAVED_KEY = "nyc-events:saved:v1";

// Saved-event content cache — the core event data per saved ID, so the
// user can still see what they saved AFTER the event date has passed
// (the source events.json drops past events). Keyed by event id.
const SAVED_CACHE_KEY = "nyc-events:savedCache:v1";

export interface SavedEventStub {
  id: string;
  title: string;
  date: string;
  sourceUrl: string;
  imageUrl: string | null;
  instagramAccount?: string;
  accountVerified?: boolean;
  startTime?: string | null;
  locationName?: string;
}

function loadSavedCache(): Record<string, SavedEventStub> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(SAVED_CACHE_KEY);
    if (!raw) return {};
    const obj = JSON.parse(raw);
    return obj && typeof obj === "object" ? obj : {};
  } catch {
    return {};
  }
}

function saveSavedCache(cache: Record<string, SavedEventStub>): void {
  if (typeof window === "undefined") return;
  try {
    // Cap at 200 most-recent (by save order — we trust insertion order)
    const ids = Object.keys(cache);
    if (ids.length > 200) {
      const trimmed: Record<string, SavedEventStub> = {};
      for (const id of ids.slice(-200)) trimmed[id] = cache[id];
      cache = trimmed;
    }
    window.localStorage.setItem(SAVED_CACHE_KEY, JSON.stringify(cache));
  } catch {
    // ignore quota
  }
}

export function loadSavedStubs(): SavedEventStub[] {
  return Object.values(loadSavedCache());
}

function loadSavedSet(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(SAVED_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveSavedSet(s: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(Array.from(s).slice(-500)));
  } catch {
    // ignore quota errors
  }
}

export function toggleSavedLocal(
  eventId: string,
  hint?: {
    account?: string;
    categories?: string[];
    sourceUrl?: string;
    // Full stub for cache so saved events survive past their date
    stub?: SavedEventStub;
  }
): boolean {
  const s = loadSavedSet();
  const cache = loadSavedCache();
  let saved: boolean;
  if (s.has(eventId)) {
    s.delete(eventId);
    delete cache[eventId];
    saved = false;
  } else {
    s.add(eventId);
    saved = true;
    if (hint?.stub) {
      cache[eventId] = hint.stub;
    }
    // Saving is the strongest explicit positive signal — feed it heavily
    // into the interest profile so other events from the same account/
    // categories/source rise in subsequent rankings. 5x the per-click bump.
    if (hint) {
      const p = loadProfile();
      if (hint.account) bump(p.accounts, hint.account.toLowerCase(), 5);
      for (const c of hint.categories || []) bump(p.categories, c, 3);
      if (hint.sourceUrl) {
        try {
          const host = new URL(hint.sourceUrl).hostname.toLowerCase();
          bump(p.hosts, host, 2);
        } catch {
          // ignore
        }
      }
      p.updatedAt = new Date().toISOString();
      saveProfile(p);
    }
  }
  saveSavedSet(s);
  saveSavedCache(cache);
  return saved;
}

export function isSavedLocal(eventId: string): boolean {
  return loadSavedSet().has(eventId);
}

// "Did you go?" attendance feedback — the strongest calibration signal we
// can collect. Saves are intent; attendance is reality. Stored as
// {eventId: "yes" | "no"} so we can render the answer on subsequent opens
// and use it to adjust the interest profile.
const ATTENDED_KEY = "nyc-events:attended:v1";

type AttendedState = "yes" | "no" | undefined;

function loadAttended(): Record<string, "yes" | "no"> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(ATTENDED_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed ? parsed : {};
  } catch {
    return {};
  }
}

function saveAttended(map: Record<string, "yes" | "no">): void {
  if (typeof window === "undefined") return;
  try {
    // Cap at 500 most recent to bound localStorage growth.
    const entries = Object.entries(map);
    const trimmed = entries.length > 500 ? Object.fromEntries(entries.slice(-500)) : map;
    window.localStorage.setItem(ATTENDED_KEY, JSON.stringify(trimmed));
  } catch {
    // ignore quota errors
  }
}

export function getAttendedState(eventId: string): AttendedState {
  return loadAttended()[eventId];
}

export function markAttended(
  eventId: string,
  answer: "yes" | "no",
  hint: { account?: string; categories?: string[]; sourceUrl?: string },
): void {
  const map = loadAttended();
  map[eventId] = answer;
  saveAttended(map);
  // Profile bump: "yes" is the strongest positive signal (attended >
  // saved > opened). "no" is a soft negative (planned but didn't make it
  // — small downweight, not a hide).
  const p = loadProfile();
  if (answer === "yes") {
    if (hint.account) bump(p.accounts, hint.account.toLowerCase(), 8);
    for (const c of hint.categories || []) bump(p.categories, c, 5);
    if (hint.sourceUrl) {
      try {
        bump(p.hosts, new URL(hint.sourceUrl).hostname.toLowerCase(), 3);
      } catch {
        // ignore unparseable
      }
    }
  } else {
    // "no" — soft downweight. Clamp to 0 so interestBoost's Math.log2 path
    // can't NaN. "No" still differs from "yes" because future events from
    // the same account/category don't accumulate further positive bumps.
    const decAcct = (k: string, by: number) => {
      const next = (p.accounts[k] || 0) + by;
      p.accounts[k] = next < 0 ? 0 : next;
    };
    const decCat = (k: string, by: number) => {
      const next = (p.categories[k] || 0) + by;
      p.categories[k] = next < 0 ? 0 : next;
    };
    if (hint.account) decAcct(hint.account.toLowerCase(), -2);
    for (const c of hint.categories || []) decCat(c, -1);
  }
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

// Hidden-events memory — explicit negative signal. Stored separately from
// the interest profile so user can clear interests without un-hiding.
const HIDDEN_KEY = "nyc-events:hidden:v1";

function loadHidden(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(HIDDEN_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveHidden(s: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    // Cap at 500 most recent to bound localStorage growth.
    const arr = Array.from(s).slice(-500);
    window.localStorage.setItem(HIDDEN_KEY, JSON.stringify(arr));
  } catch {
    // ignore quota errors
  }
}

export function hideEvent(
  eventId: string,
  hint?: {
    account?: string;
    categories?: string[];
    sourceUrl?: string;
  }
): void {
  const s = loadHidden();
  if (s.has(eventId)) return; // already hidden — don't double-bump negatives
  s.add(eventId);
  saveHidden(s);

  // Feed the hide into the negative profile so other events from the
  // same account/categories/host get deboosted in subsequent rankings.
  if (!hint) return;
  const p = loadProfile();
  if (hint.account) bump(p.negAccounts, hint.account.toLowerCase(), 1);
  for (const c of hint.categories || []) bump(p.negCategories, c, 1);
  if (hint.sourceUrl) {
    try {
      const host = new URL(hint.sourceUrl).hostname.toLowerCase();
      bump(p.negHosts, host, 1);
    } catch {
      // ignore
    }
  }
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

export function isHidden(eventId: string): boolean {
  return loadHidden().has(eventId);
}

export function unhideAll(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(HIDDEN_KEY);
}

export function topAccounts(profile: InterestProfile, n = 5): string[] {
  return Object.entries(profile.accounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([k]) => k);
}

export function topCategories(profile: InterestProfile, n = 5): Array<[string, number]> {
  return Object.entries(profile.categories)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n);
}

export function totalEngagementCount(profile: InterestProfile): number {
  const sum = (m: Record<string, number>) =>
    Object.values(m).reduce((a, b) => a + b, 0);
  return sum(profile.accounts) + sum(profile.categories) + sum(profile.hosts);
}

export function clearAllLocalState(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem(SAVED_KEY);
    window.localStorage.removeItem(SAVED_CACHE_KEY);
    window.localStorage.removeItem(HIDDEN_KEY);
    window.localStorage.removeItem(OPENED_KEY);
    window.localStorage.removeItem(SEARCH_HISTORY_KEY);
    window.localStorage.removeItem("nyc-events:lastVisitedAt:v1");
    window.localStorage.removeItem("nyc-events:viewMode");
  } catch {
    // ignore
  }
}

export function getSavedCount(): number {
  return loadSavedSet().size;
}

export function getHiddenCount(): number {
  return loadHidden().size;
}

// Search history — last 8 distinct queries the user has typed. Surfaces
// in the search bar dropdown so they can re-issue without retyping.
const SEARCH_HISTORY_KEY = "nyc-events:searchHistory:v1";

export function loadSearchHistory(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(SEARCH_HISTORY_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((s) => typeof s === "string") : [];
  } catch {
    return [];
  }
}

export function pushSearchHistory(query: string): void {
  if (typeof window === "undefined") return;
  const q = (query || "").trim();
  if (!q || q.length < 2) return;
  try {
    const existing = loadSearchHistory();
    // Move-to-front: drop existing match (case-insensitive), prepend
    const lower = q.toLowerCase();
    const dedup = existing.filter((s) => s.toLowerCase() !== lower);
    const next = [q, ...dedup].slice(0, 8);
    window.localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(next));
  } catch {
    // ignore
  }
}

export function clearSearchHistory(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(SEARCH_HISTORY_KEY);
  } catch {
    // ignore
  }
}

// Already-opened events: fade-out signal so the user can scan for what's
// NEW vs what they've already explored. Mirrors IG's "seen" indicators.
const OPENED_KEY = "nyc-events:opened:v1";

function loadOpenedSet(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(OPENED_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveOpenedSet(s: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    // Cap at 1000 most-recent to bound storage.
    const arr = Array.from(s).slice(-1000);
    window.localStorage.setItem(OPENED_KEY, JSON.stringify(arr));
  } catch {
    // ignore
  }
}

export function markEventOpened(eventId: string): void {
  if (!eventId) return;
  const s = loadOpenedSet();
  s.add(eventId);
  saveOpenedSet(s);
}

export function isEventOpened(eventId: string): boolean {
  if (!eventId) return false;
  return loadOpenedSet().has(eventId);
}
