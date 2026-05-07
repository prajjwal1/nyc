"use client";

import { TopAccount } from "../lib/types";

interface Props {
  accounts: TopAccount[] | undefined;
  onAccountClick: (username: string) => void;
}

function AccountRow({ a, onAccountClick }: { a: TopAccount; onAccountClick: (u: string) => void }) {
  return (
    <button
      onClick={() => onAccountClick(a.username)}
      className="w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors text-left group"
      title={`See events from @${a.username}`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm font-medium text-gray-900 truncate group-hover:text-gray-700">
          @{a.username}
        </span>
        {a.verified && (
          <span className="text-blue-500 text-xs" title="Verified">✓</span>
        )}
      </div>
      <span className="text-xs text-gray-500 shrink-0 tabular-nums">
        {a.events} {a.events === 1 ? "event" : "events"}
      </span>
    </button>
  );
}

export default function TopAccounts({ accounts, onAccountClick }: Props) {
  if (!accounts || accounts.length === 0) return null;

  // Split into "you save from" vs "suggested" so the user sees which
  // accounts they've engaged with vs which are new high-yield discoveries.
  const saved = accounts.filter((a) => a.userSaved).slice(0, 6);
  const suggested = accounts.filter((a) => !a.userSaved).slice(0, 6);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-3 space-y-3">
      {saved.length > 0 && (
        <div>
          <div className="flex items-baseline justify-between mb-2">
            <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
              From accounts you save
            </h3>
          </div>
          <div className="space-y-1">
            {saved.map((a) => (
              <AccountRow key={a.username} a={a} onAccountClick={onAccountClick} />
            ))}
          </div>
        </div>
      )}
      {suggested.length > 0 && (
        <div>
          <div className="flex items-baseline justify-between mb-2">
            <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
              {saved.length > 0 ? "Suggested for you" : "Top NYC accounts"}
            </h3>
            <span className="text-[10px] text-gray-400">by upcoming events</span>
          </div>
          <div className="space-y-1">
            {suggested.map((a) => (
              <AccountRow key={a.username} a={a} onAccountClick={onAccountClick} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
