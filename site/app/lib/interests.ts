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
  // When was this profile last updated (ISO)
  updatedAt: string;
}

const empty = (): InterestProfile => ({
  accounts: {},
  categories: {},
  hosts: {},
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

export function trackEventOpen(account: string | undefined, categories: string[], sourceUrl: string): void {
  const p = loadProfile();
  if (account) bump(p.accounts, account.toLowerCase(), 3); // strongest signal
  for (const c of categories || []) bump(p.categories, c, 1);
  try {
    const u = new URL(sourceUrl);
    bump(p.hosts, u.hostname.toLowerCase(), 1);
  } catch {
    // ignore unparseable URLs
  }
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
}

// Compute a 0..0.15 boost for an event given a learned profile. Capped low
// so it nudges; saved/tagged still trump it.
export function interestBoost(
  event: {
    instagramAccount?: string;
    categories?: string[];
    sourceUrl?: string;
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
  return Math.min(0.15, boost);
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

export function hideEvent(eventId: string): void {
  const s = loadHidden();
  s.add(eventId);
  saveHidden(s);
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
