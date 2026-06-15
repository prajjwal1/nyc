"use client";

import { Event, TopAccount } from "../lib/types";

interface Props {
  account: string;
  events: Event[];
  topAccount?: TopAccount;
  onClear: () => void;
}

// When the user is filtering by @account, show a small header with stats
// + a direct "Open on Instagram" link. Replicates the experience of
// tapping a profile in IG without leaving the site.
export default function AccountBanner({ account, events, topAccount, onClear }: Props) {
  const lc = account.toLowerCase();
  const upcoming = events.filter((e) =>
    e.instagramAccount?.toLowerCase() === lc || e.account?.toLowerCase() === lc
  );
  // Only offer "Open on IG" when this handle is an actual IG account — the
  // cross-source-enriched handles (bookclubbar, nycforfree, readingrhythms-…)
  // have no IG profile, so an IG link would 404.
  const isIg = upcoming.some((e) => e.instagramAccount?.toLowerCase() === lc);
  const verified = topAccount?.verified || upcoming.some((e) => e.accountVerified);
  const igUrl = `https://www.instagram.com/${account}/`;
  const yieldPct = topAccount?.yield && topAccount.yield > 0
    ? Math.min(100, Math.round(topAccount.yield * 100))
    : null;

  // Even with 0 in-feed events, render the banner if topAccount data exists —
  // tells the user "this is a real account we know about" + lets them open
  // it on IG. Without this, clicking a "Suggested for you" account with 0
  // current events would open an empty page (confusing).
  if (upcoming.length === 0 && !topAccount) return null;

  return (
    <div className="mb-4 bg-gradient-to-br from-fuchsia-50 to-purple-50 border border-fuchsia-200 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base font-semibold text-gray-900">@{account}</span>
            {verified && (
              <span className="text-blue-500 text-sm" title="Verified">✓</span>
            )}
          </div>
          <p className="text-sm text-gray-600">
            <span className="font-medium text-gray-900">{upcoming.length}</span>{" "}
            upcoming {upcoming.length === 1 ? "event" : "events"}
            {topAccount?.yield && topAccount.yield >= 0.1
              ? ` · ${Math.round(topAccount.yield * 100)}% of recent posts are events`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {isIg && (
            <a
              href={igUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-gray-200 hover:border-gray-300 text-xs font-medium text-gray-700 hover:text-gray-900 transition-colors"
              title={`Open @${account} on Instagram`}
            >
              <span>Open on IG</span>
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}
          <button
            onClick={onClear}
            className="px-2 py-1.5 rounded-lg text-xs text-gray-500 hover:text-gray-900 hover:bg-white/60 transition-colors"
            title="Clear filter"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
