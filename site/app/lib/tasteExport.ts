// Client → pipeline taste sync (WS1, Phase B).
//
// The browser accumulates a weighted InterestProfile from saves/opens/
// "did you go?"/hides (lib/interests.ts). This module serializes that into the
// snapshot the scraper reads (scrapers/data/user_engagement.json) so the
// pipeline LEARNS from real behavior instead of hand-edited config. See
// scrapers/utils/engagement.py::apply_engagement for the consuming side.
//
// Delivery is backend-free:
//  - Primary: commit the snapshot to the repo via the GitHub contents API with
//    a fine-grained PAT (contents:read+write on this one repo) the user pastes
//    once; stored in localStorage. Committing triggers CI → next scrape learns.
//  - Fallback: download the JSON to drop into scrapers/data/ manually.

import { loadProfile, loadSavedStubs } from "./interests";

const GH_TOKEN_KEY = "nyc-events:ghtoken:v1";
const REPO = "prajjwal1/nyc";
const BRANCH = "main";
const FILE_PATH = "scrapers/data/user_engagement.json";

export interface TasteSnapshot {
  updatedAt: string;
  accounts: Record<string, number>;
  categories: Record<string, number>;
  hosts: Record<string, number>;
  negAccounts: Record<string, number>;
  negHosts: Record<string, number>;
  // Liked-event TEXT — training examples for the semantic taste model (WS2,
  // scrapers/utils/taste.py). Derived from saved-event stubs.
  positiveTexts: string[];
  negativeTexts: string[];
}

export function buildTasteSnapshot(): TasteSnapshot {
  const p = loadProfile();
  const positiveTexts = loadSavedStubs()
    .map((s) =>
      [s.title, s.locationName, s.instagramAccount]
        .filter(Boolean)
        .join(" ")
        .trim(),
    )
    .filter((t) => t.length > 0);
  return {
    updatedAt: new Date().toISOString(),
    accounts: p.accounts || {},
    categories: p.categories || {},
    hosts: p.hosts || {},
    negAccounts: p.negAccounts || {},
    negHosts: p.negHosts || {},
    positiveTexts,
    negativeTexts: [],
  };
}

/** True when there's enough engagement to be worth syncing. */
export function hasTasteSignal(): boolean {
  const s = buildTasteSnapshot();
  const n = (o: Record<string, number>) => Object.keys(o).length;
  return n(s.accounts) + n(s.hosts) + n(s.negAccounts) + n(s.negHosts) > 0;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(GH_TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(GH_TOKEN_KEY, token.trim());
}

export function downloadTasteSnapshot(): void {
  const json = JSON.stringify(buildTasteSnapshot(), null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "user_engagement.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function b64(json: string): string {
  // UTF-8 safe base64 for the GitHub contents API.
  return btoa(unescape(encodeURIComponent(json)));
}

export interface SyncResult {
  ok: boolean;
  message: string;
}

/** Commit the taste snapshot to the repo via the GitHub contents API. */
export async function syncTasteToRepo(token: string): Promise<SyncResult> {
  const json = JSON.stringify(buildTasteSnapshot(), null, 2);
  const apiUrl = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  // Existing file's blob SHA is required to update it (omit to create).
  let sha: string | undefined;
  try {
    const getRes = await fetch(`${apiUrl}?ref=${BRANCH}`, { headers });
    if (getRes.ok) sha = (await getRes.json()).sha;
    else if (getRes.status === 401) return { ok: false, message: "Token rejected (401). Check the PAT has contents:write on this repo." };
  } catch {
    return { ok: false, message: "Network error reaching GitHub." };
  }

  try {
    const putRes = await fetch(apiUrl, {
      method: "PUT",
      headers,
      body: JSON.stringify({
        message: "chore: sync taste snapshot from app",
        content: b64(json),
        sha,
        branch: BRANCH,
      }),
    });
    if (putRes.ok) return { ok: true, message: "Taste synced — the next scrape will learn from it." };
    const status = putRes.status;
    let detail = "";
    try {
      detail = (await putRes.json()).message || "";
    } catch {
      // ignore
    }
    return { ok: false, message: `Sync failed (${status}). ${detail}`.trim() };
  } catch {
    return { ok: false, message: "Network error committing to GitHub." };
  }
}
