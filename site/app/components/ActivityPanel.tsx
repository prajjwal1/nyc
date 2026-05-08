"use client";

import { useEffect, useState } from "react";
import {
  loadProfile,
  topCategories,
  topAccounts,
  totalEngagementCount,
  getSavedCount,
  getHiddenCount,
  clearAllLocalState,
  isSavedLocal,
  loadSavedStubs,
  SavedEventStub,
  InterestProfile,
} from "../lib/interests";
import { downloadIcsBundle } from "../lib/ics";
import { CATEGORY_CONFIG, Event } from "../lib/types";

interface Props {
  onAccountClick: (username: string) => void;
  events?: Event[];  // for bulk-export of saved events
}

// "Your Activity" panel — surfaces what the system has learned from the
// user's clicks/saves/hides so they understand the personalization, plus
// a reset button so they can clear and start fresh. Builds trust + control.
export default function ActivityPanel({ onAccountClick, events = [] }: Props) {
  const [profile, setProfile] = useState<InterestProfile | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const [hiddenCount, setHiddenCount] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [pastSaves, setPastSaves] = useState<SavedEventStub[]>([]);
  const [pastOpen, setPastOpen] = useState(false);

  useEffect(() => {
    setProfile(loadProfile());
    setSavedCount(getSavedCount());
    setHiddenCount(getHiddenCount());
    // Past saves: stubs whose date < today, sorted most-recent first
    const today = new Date().toISOString().split("T")[0];
    const past = loadSavedStubs()
      .filter((s) => s.date && s.date < today)
      .sort((a, b) => b.date.localeCompare(a.date));
    setPastSaves(past);
  }, []);

  if (!profile) return null;

  const total = totalEngagementCount(profile);
  // Don't show until the user has any engagement OR has saved/hidden anything
  if (total === 0 && savedCount === 0 && hiddenCount === 0 && pastSaves.length === 0) return null;

  const cats = topCategories(profile, 5);
  const accts = topAccounts(profile, 5);

  const handleReset = () => {
    clearAllLocalState();
    setProfile({
      accounts: {},
      categories: {},
      hosts: {},
      updatedAt: new Date().toISOString(),
    });
    setSavedCount(0);
    setHiddenCount(0);
    setConfirming(false);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-3">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
          Your Activity
        </h3>
        {confirming ? (
          <div className="flex gap-1">
            <button
              onClick={handleReset}
              className="text-[10px] text-rose-600 hover:text-rose-800 underline"
            >
              confirm reset
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="text-[10px] text-gray-400 hover:text-gray-600"
            >
              cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="text-[10px] text-gray-400 hover:text-rose-600"
            title="Clear all local data (interests, saves, hides)"
          >
            reset
          </button>
        )}
      </div>

      {(savedCount > 0 || hiddenCount > 0) && (
        <div className="flex items-center justify-between gap-3 text-xs text-gray-600 mb-3">
          <div className="flex gap-3">
            {savedCount > 0 && (
              <span>
                <span className="font-medium text-amber-700">★</span>{" "}
                {savedCount} saved
              </span>
            )}
            {hiddenCount > 0 && (
              <span className="text-gray-400">
                ✕ {hiddenCount} hidden
              </span>
            )}
          </div>
          {savedCount > 0 && events.length > 0 && (
            <button
              onClick={() => {
                const today = new Date().toISOString().split("T")[0];
                const savedEvents = events.filter((e) =>
                  (e.userSaved || isSavedLocal(e.id)) && (e.date >= today)
                );
                if (savedEvents.length > 0) {
                  downloadIcsBundle(savedEvents, "saved-events");
                }
              }}
              className="text-[10px] text-amber-700 hover:text-amber-900 underline"
              title="Download all upcoming saved events as one calendar file"
            >
              Export to calendar
            </button>
          )}
        </div>
      )}

      {accts.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">
            Top accounts
          </p>
          <div className="flex flex-wrap gap-1">
            {accts.map((a) => (
              <button
                key={a}
                onClick={() => onAccountClick(a)}
                className="px-2 py-0.5 rounded bg-gray-100 hover:bg-gray-200 text-xs font-medium text-gray-700"
              >
                @{a}
              </button>
            ))}
          </div>
        </div>
      )}

      {cats.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">
            Top categories
          </p>
          <div className="flex flex-wrap gap-1">
            {cats.map(([cat]) => {
              const cfg = CATEGORY_CONFIG[cat];
              if (!cfg) return null;
              return (
                <span
                  key={cat}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium ${cfg.color}`}
                >
                  {cfg.label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {pastSaves.length > 0 && (
        <div className="pt-3 border-t border-gray-100">
          <button
            onClick={() => setPastOpen(!pastOpen)}
            className="w-full flex items-center justify-between text-[10px] uppercase tracking-wide text-gray-400 hover:text-gray-700"
          >
            <span>📅 Past saves ({pastSaves.length})</span>
            <span className="normal-case tracking-normal">
              {pastOpen ? "hide" : "show"}
            </span>
          </button>
          {pastOpen && (
            <div className="mt-2 space-y-1 max-h-64 overflow-y-auto">
              {pastSaves.slice(0, 30).map((s) => (
                <a
                  key={s.id}
                  href={s.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex gap-2 p-1.5 rounded hover:bg-gray-50 transition-colors"
                  title={s.title}
                >
                  {s.imageUrl && (
                    <img
                      src={s.imageUrl}
                      alt=""
                      loading="lazy"
                      className="shrink-0 w-9 h-9 rounded object-cover bg-gray-100"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-[10px] text-gray-500 line-clamp-1">
                      {formatPastDate(s.date)}
                      {s.instagramAccount ? <span className="text-gray-400"> · @{s.instagramAccount}</span> : null}
                    </div>
                    <div className="text-[11px] font-medium text-gray-700 line-clamp-1">
                      {s.title}
                    </div>
                  </div>
                </a>
              ))}
              {pastSaves.length > 30 && (
                <p className="text-[10px] text-gray-400 px-2">
                  +{pastSaves.length - 30} more older saves
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatPastDate(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 3600 * 24));
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}
