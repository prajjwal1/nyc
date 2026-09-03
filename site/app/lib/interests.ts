import type { Event } from "./types";

// Client-side interest tracking. Compounds across visits without any backend.
//
// Tracks three signals from user behavior:
//   - account clicks: which @-accounts the user clicks to filter by
//   - category clicks: which category chips the user toggles on
//   - card opens: which event sourceUrls the user clicks through to
//
// The aggregated profile re-ranks events client-side: events matching
// learned signals get a small boost on top of the server-side score, so
// the calendar adapts to what the user actually engages with over time.

const STORAGE_KEY = "nyc-events:interests:v1";
export const PROFILE_CHANGE_EVENT = "nyc-events-profile-change";

export interface InterestProfile {
  accounts: Record<string, number>;
  categories: Record<string, number>;
  // Track distinct event domains/hosts to learn source preferences
  hosts: Record<string, number>;
  // Followed communities are a direct signal for linked events.
  communities: Record<string, number>;
  // Negative signals: counts of hides per account/category/host. Symmetric
  // with the positive maps so a user's "no thanks" on one event from
  // @somenightclub deboosts other events from that same account.
  negAccounts: Record<string, number>;
  negCategories: Record<string, number>;
  negHosts: Record<string, number>;
  // Schedule learning: count of events the user has opened by start-time
  // bucket (key: "morning" | "midday" | "afternoon" | "evening" | "late")
  // and by day-of-week (key: "0".."6", Sunday=0). Lets the calendar adapt to
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
  communities: {},
  negAccounts: {},
  negCategories: {},
  negHosts: {},
  timeBuckets: {},
  dayOfWeek: {},
  updatedAt: new Date().toISOString(),
});

function followedCommunityProfile(): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    const ids = JSON.parse(window.localStorage.getItem("nyc-community-follows-v1") || "[]");
    return Array.isArray(ids)
      ? Object.fromEntries(ids.filter((id): id is string => typeof id === "string").map((id) => [id, 5]))
      : {};
  } catch {
    return {};
  }
}

export function loadProfile(): InterestProfile {
  if (typeof window === "undefined") return empty();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...empty(), communities: followedCommunityProfile() };
    const parsed = JSON.parse(raw);
    return {
      accounts: parsed.accounts || {},
      categories: parsed.categories || {},
      hosts: parsed.hosts || {},
      communities: { ...followedCommunityProfile(), ...(parsed.communities || {}) },
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
    window.dispatchEvent(new Event(PROFILE_CHANGE_EVENT));
  } catch {
    // localStorage may be full / disabled — silently no-op
  }
}

function notifyProfileChange(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(PROFILE_CHANGE_EVENT));
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
    account?: string;
    organizer?: string;
    categories?: string[];
    sourceUrl?: string;
    startTime?: string | null;
    date?: string;
    communityIds?: string[];
    primaryCommunityId?: string;
  },
  profile: InterestProfile,
): number {
  let boost = 0;
  const acct = (event.account || event.organizer || event.instagramAccount || "").toLowerCase();
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
  const communityIds = event.communityIds || (event.primaryCommunityId ? [event.primaryCommunityId] : []);
  if (communityIds.some((id) => (profile.communities?.[id] || 0) > 0)) {
    boost += 0.08;
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

export function interestReason(
  event: {
    instagramAccount?: string;
    account?: string;
    organizer?: string;
    categories?: string[];
    sourceUrl?: string;
    communityIds?: string[];
    primaryCommunityId?: string;
  },
  profile: InterestProfile,
): string | null {
  const displayAccount = event.account || event.organizer || event.instagramAccount || "";
  const account = displayAccount.toLowerCase();
  if (account && (profile.accounts[account] || 0) > 0) return `More from ${displayAccount}`;

  const communityIds = event.communityIds || (event.primaryCommunityId ? [event.primaryCommunityId] : []);
  if (communityIds.some((id) => (profile.communities?.[id] || 0) > 0)) {
    return "From a community you follow";
  }

  const category = [...(event.categories || [])]
    .filter((item) => (profile.categories[item] || 0) > 0)
    .sort((a, b) => (profile.categories[b] || 0) - (profile.categories[a] || 0))[0];
  if (category) return `Matches your ${category} interests`;

  if (event.sourceUrl) {
    try {
      const host = new URL(event.sourceUrl).hostname.toLowerCase();
      if ((profile.hosts[host] || 0) > 0) return `More from ${host.replace(/^www\./, "")}`;
    } catch {
      // Ignore unparseable source URLs.
    }
  }
  return null;
}

export function trackCommunityFollow(communityId: string, following: boolean): void {
  if (!communityId) return;
  const profile = loadProfile();
  if (following) profile.communities[communityId] = 5;
  else delete profile.communities[communityId];
  profile.updatedAt = new Date().toISOString();
  saveProfile(profile);
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

export function readLastVisited(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LAST_VISITED_KEY);
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
  account?: string;
  organizer?: string;
  organizerUrl?: string;
  categories?: string[];
  description?: string;
  accountVerified?: boolean;
  startTime?: string | null;
  locationName?: string;
}

export function eventToSavedStub(event: Event): SavedEventStub {
  return {
    id: event.id,
    title: event.title,
    description: event.description,
    categories: event.categories,
    date: event.date,
    sourceUrl: event.sourceUrl,
    imageUrl: event.imageUrl,
    instagramAccount: event.instagramAccount,
    account: event.account,
    organizer: event.organizer,
    organizerUrl: event.organizerUrl,
    accountVerified: event.accountVerified,
    startTime: event.startTime,
    locationName: event.location?.name,
  };
}

export function savedStubToEvent(stub: SavedEventStub): Event {
  return {
    id: stub.id,
    title: stub.title,
    description: stub.description || "",
    date: stub.date,
    startTime: stub.startTime || null,
    endTime: null,
    location: { name: stub.locationName || "", address: "", neighborhood: null },
    categories: stub.categories || [],
    source: "saved",
    sourceUrl: stub.sourceUrl,
    imageUrl: stub.imageUrl,
    price: "unknown",
    score: 0,
    scrapedAt: new Date().toISOString(),
    instagramAccount: stub.instagramAccount,
    account: stub.account,
    organizer: stub.organizer,
    organizerUrl: stub.organizerUrl,
    accountVerified: stub.accountVerified,
  };
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
    // Saving is the strongest explicit positive signal — weight it heavily
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
  notifyProfileChange();
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
const ATTENDED_CACHE_KEY = "nyc-events:attendedCache:v1";

export type AttendedAnswer = "yes" | "no";
type AttendedState = AttendedAnswer | undefined;

interface AttendanceEffect {
  account?: { key: string; delta: number };
  categories: Record<string, number>;
  host?: { key: string; delta: number };
}

interface AttendedCacheEntry {
  stub?: SavedEventStub;
  effect?: AttendanceEffect;
}

export function loadAttendedStates(): Record<string, AttendedAnswer> {
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

function saveAttended(map: Record<string, AttendedAnswer>): void {
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
  return loadAttendedStates()[eventId];
}

export function getAttendedCount(): { yes: number; no: number } {
  const map = loadAttendedStates();
  let yes = 0;
  let no = 0;
  for (const v of Object.values(map)) {
    if (v === "yes") yes += 1;
    else if (v === "no") no += 1;
  }
  return { yes, no };
}

function loadAttendedCache(): Record<string, AttendedCacheEntry> {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(ATTENDED_CACHE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveAttendedCache(cache: Record<string, AttendedCacheEntry>): void {
  if (typeof window === "undefined") return;
  try {
    const entries = Object.entries(cache);
    const trimmed = entries.length > 500 ? Object.fromEntries(entries.slice(-500)) : cache;
    window.localStorage.setItem(ATTENDED_CACHE_KEY, JSON.stringify(trimmed));
  } catch {
    // ignore quota errors
  }
}

export function loadAttendedExamples(): Array<{
  id: string;
  state: AttendedAnswer;
  stub?: SavedEventStub;
}> {
  const states = loadAttendedStates();
  const cache = loadAttendedCache();
  const fallback = new Map<string, SavedEventStub>();
  for (const stub of [...loadSavedStubs(), ...loadHiddenStubs()]) fallback.set(stub.id, stub);
  return Object.entries(states).map(([id, state]) => ({
    id,
    state,
    stub: cache[id]?.stub || fallback.get(id),
  }));
}

function applyProfileDelta(
  bucket: Record<string, number>,
  key: string,
  requested: number,
): number {
  const before = bucket[key] || 0;
  const after = Math.max(0, before + requested);
  bucket[key] = after;
  return after - before;
}

function reverseAttendanceEffect(profile: InterestProfile, effect?: AttendanceEffect): void {
  if (!effect) return;
  if (effect.account) applyProfileDelta(profile.accounts, effect.account.key, -effect.account.delta);
  for (const [category, delta] of Object.entries(effect.categories || {})) {
    applyProfileDelta(profile.categories, category, -delta);
  }
  if (effect.host) applyProfileDelta(profile.hosts, effect.host.key, -effect.host.delta);
}

export function markAttended(
  eventId: string,
  answer: AttendedAnswer,
  hint: { account?: string; categories?: string[]; sourceUrl?: string; stub?: SavedEventStub },
): void {
  const map = loadAttendedStates();
  const cache = loadAttendedCache();
  const cached = cache[eventId] || {};
  if (hint.stub) cached.stub = hint.stub;
  cache[eventId] = cached;
  if (map[eventId] === answer) {
    saveAttendedCache(cache);
    return;
  }

  const p = loadProfile();
  reverseAttendanceEffect(p, cached.effect);

  const effect: AttendanceEffect = { categories: {} };
  const account = hint.account?.toLowerCase();
  let host: string | undefined;
  if (hint.sourceUrl) {
    try {
      host = new URL(hint.sourceUrl).hostname.toLowerCase();
    } catch {
      // ignore unparseable
    }
  }

  if (answer === "yes") {
    if (account) effect.account = { key: account, delta: applyProfileDelta(p.accounts, account, 8) };
    for (const category of hint.categories || []) {
      effect.categories[category] = applyProfileDelta(p.categories, category, 5);
    }
    if (host) effect.host = { key: host, delta: applyProfileDelta(p.hosts, host, 3) };
  } else {
    if (account) effect.account = { key: account, delta: applyProfileDelta(p.accounts, account, -2) };
    for (const category of hint.categories || []) {
      effect.categories[category] = applyProfileDelta(p.categories, category, -1);
    }
  }

  cached.effect = effect;
  map[eventId] = answer;
  saveAttended(map);
  saveAttendedCache(cache);
  p.updatedAt = new Date().toISOString();
  saveProfile(p);
  notifyProfileChange();
}

// Hidden-events memory — explicit negative signal. Stored separately from
// the interest profile so user can clear interests without un-hiding.
const HIDDEN_KEY = "nyc-events:hidden:v1";
const HIDDEN_CACHE_KEY = "nyc-events:hiddenCache:v1";

function loadHiddenCache(): Record<string, SavedEventStub> {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(HIDDEN_CACHE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function loadHiddenStubs(): SavedEventStub[] {
  return Object.values(loadHiddenCache());
}

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
    stub?: SavedEventStub;
  }
): void {
  const s = loadHidden();
  if (s.has(eventId)) return; // already hidden — don't double-bump negatives
  s.add(eventId);
  saveHidden(s);
  if (hint?.stub) {
    const cache = loadHiddenCache();
    cache[eventId] = hint.stub;
    try {
      window.localStorage.setItem(HIDDEN_CACHE_KEY, JSON.stringify(cache));
    } catch {
      // ignore quota errors
    }
  }

  // Apply the hide to the negative profile so other events from the
  // same account/categories/host get deboosted in subsequent rankings.
  if (!hint) {
    notifyProfileChange();
    return;
  }
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

export function loadHiddenIds(): Set<string> {
  return loadHidden();
}

export function unhideAll(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(HIDDEN_KEY);
  window.localStorage.removeItem(HIDDEN_CACHE_KEY);
  notifyProfileChange();
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
  return sum(profile.accounts) + sum(profile.categories) + sum(profile.hosts) + sum(profile.communities || {});
}

export function clearAllLocalState(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem(SAVED_KEY);
    window.localStorage.removeItem(SAVED_CACHE_KEY);
    window.localStorage.removeItem(HIDDEN_KEY);
    window.localStorage.removeItem(HIDDEN_CACHE_KEY);
    window.localStorage.removeItem(ATTENDED_KEY);
    window.localStorage.removeItem(ATTENDED_CACHE_KEY);
    window.localStorage.removeItem(OPENED_KEY);
    window.localStorage.removeItem("nyc-events:searchHistory:v1");
    window.localStorage.removeItem("nyc-events:lastVisitedAt:v1");
    window.localStorage.removeItem("nyc-events:viewMode");
    notifyProfileChange();
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
