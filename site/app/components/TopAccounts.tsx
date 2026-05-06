"use client";

import { TopAccount } from "../lib/types";

interface Props {
  accounts: TopAccount[] | undefined;
  onAccountClick: (username: string) => void;
}

export default function TopAccounts({ accounts, onAccountClick }: Props) {
  if (!accounts || accounts.length === 0) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-3">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
          Top NYC Accounts
        </h3>
        <span className="text-[10px] text-gray-400">by upcoming events</span>
      </div>
      <div className="space-y-1">
        {accounts.slice(0, 8).map((a) => (
          <button
            key={a.username}
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
        ))}
      </div>
    </div>
  );
}
