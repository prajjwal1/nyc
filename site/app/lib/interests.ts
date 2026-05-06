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

export function topAccounts(profile: InterestProfile, n = 5): string[] {
  return Object.entries(profile.accounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([k]) => k);
}
