"use client";

import { useEffect, useState } from "react";
import { Event, CATEGORY_CONFIG, SOURCE_LABELS, HIGHLIGHT_CONFIG } from "../lib/types";
import { trackAccountClick, trackEventOpen, hideEvent, toggleSavedLocal, isSavedLocal, markEventOpened, getAttendedState, markAttended } from "../lib/interests";
import { downloadIcs } from "../lib/ics";

interface Props {
  event: Event | null;
  onClose: () => void;
  onAccountClick: (account: string) => void;
  relatedEvents?: Event[];
  onSelectEvent?: (event: Event) => void;
}

// Full-screen modal that lets the user evaluate an event without leaving
// the site. Mirrors the IG-post-tap experience: big image, full caption,
// action buttons, and a single explicit "Open original" link for when
// they want to actually buy tickets / see the source.
export default function EventModal({ event, onClose, onAccountClick, relatedEvents = [], onSelectEvent }: Props) {
  const [saved, setSaved] = useState(false);
  const [imgIdx, setImgIdx] = useState(0);
  const [heroImgFailed, setHeroImgFailed] = useState(false);
  const [attended, setAttended] = useState<"yes" | "no" | undefined>(undefined);

  useEffect(() => {
    if (event) {
      setSaved(isSavedLocal(event.id));
      setAttended(getAttendedState(event.id));
      setImgIdx(0);
      // Opening the modal is a strong "I considered this event" signal —
      // mark it as opened so the card dims on next visit.
      markEventOpened(event.id);
    }
  }, [event]);

  // Keyboard navigation: ESC to close, arrows for carousel
  useEffect(() => {
    if (!event) return;
    const totalImgs = 1 + (event.extraImages?.length || 0);
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" && totalImgs > 1) {
        setImgIdx((i) => Math.min(totalImgs - 1, i + 1));
      } else if (e.key === "ArrowLeft" && totalImgs > 1) {
        setImgIdx((i) => Math.max(0, i - 1));
      }
    };
    window.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [event, onClose]);

  if (!event) return null;

  const dateLabel = formatDate(event.date);
  const timeStr = event.startTime
    ? formatTime(event.startTime) +
      (event.endTime ? ` – ${formatTime(event.endTime)}` : "")
    : null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-6 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-2xl max-h-[95vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-white/95 hover:bg-white flex items-center justify-center text-gray-700 shadow-md transition-colors"
          aria-label="Close"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Hero image — IG-style carousel when multi-image */}
        {(() => {
          const images = [event.imageUrl, ...(event.extraImages || [])].filter(Boolean) as string[];
          if (images.length === 0 || heroImgFailed) return null;
          const current = images[Math.min(imgIdx, images.length - 1)];
          return (
            <div className="relative w-full bg-gray-100 max-h-[70vh] overflow-hidden">
              <img
                src={current}
                alt=""
                className="w-full h-auto object-contain max-h-[70vh]"
                onError={() => setHeroImgFailed(true)}
              />
              {images.length > 1 && (
                <>
                  {imgIdx > 0 && (
                    <button
                      onClick={() => setImgIdx((i) => Math.max(0, i - 1))}
                      className="absolute left-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 hover:bg-white flex items-center justify-center shadow-md transition-colors"
                      aria-label="Previous image"
                    >
                      <svg className="w-5 h-5 text-gray-800" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                  )}
                  {imgIdx < images.length - 1 && (
                    <button
                      onClick={() => setImgIdx((i) => Math.min(images.length - 1, i + 1))}
                      className="absolute right-2 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 hover:bg-white flex items-center justify-center shadow-md transition-colors"
                      aria-label="Next image"
                    >
                      <svg className="w-5 h-5 text-gray-800" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  )}
                  {/* Dot indicator */}
                  <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5 px-2 py-1 rounded-full bg-black/40 backdrop-blur">
                    {images.map((_, i) => (
                      <span
                        key={i}
                        className={`block w-1.5 h-1.5 rounded-full transition-colors ${
                          i === imgIdx ? "bg-white" : "bg-white/40"
                        }`}
                      />
                    ))}
                  </div>
                  <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/50 text-white text-[10px] font-semibold backdrop-blur">
                    {imgIdx + 1} / {images.length}
                  </div>
                </>
              )}
            </div>
          );
        })()}

        <div className="p-5 space-y-4">
          {/* Date pill + highlights — or "Spot" for evergreen */}
          <div className="flex flex-wrap items-center gap-2">
            {event.evergreen ? (
              <span className="px-2.5 py-1 rounded-lg bg-teal-100 text-teal-900 text-xs font-semibold">
                🗺 Cool Spot · always-current
              </span>
            ) : (
              <span className="px-2.5 py-1 rounded-lg bg-gray-900 text-white text-xs font-semibold">
                {dateLabel}
                {timeStr ? ` · ${timeStr}` : ""}
              </span>
            )}
            {(event.highlights || []).slice(0, 4).map((h) => {
              const config = HIGHLIGHT_CONFIG[h];
              if (!config) return null;
              return (
                <span
                  key={h}
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${config.color}`}
                >
                  {config.label}
                </span>
              );
            })}
            {event.price === "free" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                FREE
              </span>
            )}
            {event.price && event.price !== "free" && event.price !== "unknown" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700">
                {event.price}
              </span>
            )}
          </div>

          {/* Title */}
          <h2 className="text-xl font-semibold text-gray-900 leading-tight">
            {event.title}
          </h2>

          {/* Location */}
          {event.location.name && (
            <div className="flex items-start gap-2 text-sm text-gray-700">
              <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <div>
                <div className="font-medium">{event.location.name}</div>
                {event.location.address && (
                  <div className="text-xs text-gray-500">{event.location.address}</div>
                )}
                {event.location.neighborhood && (
                  <div className="text-xs text-gray-500">{event.location.neighborhood}</div>
                )}
              </div>
            </div>
          )}

          {/* Categories */}
          {event.categories.filter((c) => c !== "free" && c !== "other").length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {event.categories
                .filter((c) => c !== "free" && c !== "other")
                .map((cat) => {
                  const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.other;
                  return (
                    <span
                      key={cat}
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${config.color}`}
                    >
                      {config.label}
                    </span>
                  );
                })}
            </div>
          )}

          {/* Description */}
          {event.description && (
            <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
              {event.description}
            </p>
          )}

          {/* Source attribution */}
          <div className="flex items-center gap-2 text-xs text-gray-500 pt-2 border-t border-gray-100">
            {event.instagramAccount ? (
              <button
                onClick={() => {
                  trackAccountClick(event.instagramAccount);
                  onAccountClick(event.instagramAccount!);
                  onClose();
                }}
                className="font-medium text-gray-700 hover:text-gray-900 hover:underline"
              >
                @{event.instagramAccount}
              </button>
            ) : (
              <span className="font-medium text-gray-700">
                {SOURCE_LABELS[event.source] || event.source}
              </span>
            )}
            {event.accountVerified && (
              <span className="text-blue-500" title="Verified">✓</span>
            )}
            {event.likes && event.likes > 30 ? (
              <span>· ❤ {formatCount(event.likes)}</span>
            ) : null}
            {event.contributingSources && event.contributingSources.length >= 2 && (
              <span title="Cross-source verified">
                · seen on {event.contributingSources.length} sources
              </span>
            )}
          </div>

          {/* Cross-IG-account confirmation: 2+ DIFFERENT IG accounts
              promoted this same event. Strong "definitely happening" signal
              that surfaces editorial consensus across the IG sphere. */}
          {event.contributingAccounts && event.contributingAccounts.length >= 2 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 text-xs text-emerald-900 flex flex-wrap items-center gap-1">
              <span className="font-medium">📣 Promoted by</span>
              {event.contributingAccounts.slice(0, 4).map((acct, i, arr) => (
                <button
                  key={acct}
                  onClick={() => {
                    onAccountClick(acct);
                    onClose();
                  }}
                  className="font-semibold hover:underline"
                >
                  @{acct}{i < arr.length - 1 ? "," : ""}
                </button>
              ))}
              {event.contributingAccounts.length > 4 && (
                <span className="text-emerald-700">+{event.contributingAccounts.length - 4} more</span>
              )}
              <span className="text-emerald-700">— multiple IG accounts cross-promoted this</span>
            </div>
          )}

          {/* Recommendation provenance — accounts you save from have
              @-mentioned this account in event posts. */}
          {event.affinityComentionSources && event.affinityComentionSources.length > 0 && (
            <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg px-3 py-2 text-xs text-fuchsia-900 flex flex-wrap items-center gap-1">
              <span className="font-medium">✨ Recommended by</span>
              {event.affinityComentionSources.slice(0, 4).map((src, i, arr) => (
                <button
                  key={src}
                  onClick={() => {
                    onAccountClick(src);
                    onClose();
                  }}
                  className="font-semibold hover:underline"
                >
                  @{src}{i < arr.length - 1 ? "," : ""}
                </button>
              ))}
              {event.affinityComentionSources.length > 4 && (
                <span className="text-fuchsia-700">+{event.affinityComentionSources.length - 4} more</span>
              )}
              <span className="text-fuchsia-700">— accounts you save from tag this in event posts</span>
            </div>
          )}

          {/* Action row */}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <a
              href={event.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackEventOpen(event.instagramAccount, event.categories, event.sourceUrl, event.startTime, event.date)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 transition-colors"
            >
              Open original
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
            <button
              onClick={() => {
                setSaved(toggleSavedLocal(event.id, { account: event.instagramAccount, categories: event.categories, sourceUrl: event.sourceUrl, stub: { id: event.id, title: event.title, date: event.date, sourceUrl: event.sourceUrl, imageUrl: event.imageUrl, instagramAccount: event.instagramAccount, accountVerified: event.accountVerified, startTime: event.startTime, locationName: event.location?.name } }));
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                saved
                  ? "border-amber-300 bg-amber-50 text-amber-800"
                  : "border-gray-200 text-gray-700 hover:bg-gray-50"
              }`}
            >
              <svg className="w-4 h-4" fill={saved ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
              {saved ? "Saved" : "Save"}
            </button>
            <button
              onClick={() => downloadIcs(event)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Add to calendar
            </button>
            <ShareButton event={event} />
            <button
              onClick={() => {
                hideEvent(event.id, {
                  account: event.instagramAccount,
                  categories: event.categories,
                  sourceUrl: event.sourceUrl,
                });
                onClose();
              }}
              className="ml-auto inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-gray-500 hover:bg-gray-50 text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Hide
            </button>
          </div>

          {/* "Did you go?" — only on past events, regardless of saved state.
              The strongest calibration signal we collect: saves are intent,
              attendance is reality. Answer persists + bumps interest profile
              (yes = strong +; no = soft clamp-to-zero downweight). */}
          {(() => {
            const todayStr = new Date().toISOString().split("T")[0];
            if (!event.date || event.date >= todayStr) return null;
            const hint = {
              account: event.instagramAccount,
              categories: event.categories,
              sourceUrl: event.sourceUrl,
            };
            return (
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
                <span className="text-gray-700 font-medium">Did you go?</span>
                <button
                  onClick={() => {
                    markAttended(event.id, "yes", hint);
                    setAttended("yes");
                  }}
                  className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    attended === "yes"
                      ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300"
                      : "bg-white text-gray-700 hover:bg-emerald-50 border border-gray-200"
                  }`}
                  aria-pressed={attended === "yes"}
                >
                  Yes, I went
                </button>
                <button
                  onClick={() => {
                    markAttended(event.id, "no", hint);
                    setAttended("no");
                  }}
                  className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    attended === "no"
                      ? "bg-gray-200 text-gray-800 ring-1 ring-gray-300"
                      : "bg-white text-gray-700 hover:bg-gray-100 border border-gray-200"
                  }`}
                  aria-pressed={attended === "no"}
                >
                  No, I didn&apos;t
                </button>
                {attended && (
                  <span className="text-xs text-gray-500 ml-auto">
                    Thanks — this trains your recommendations.
                  </span>
                )}
              </div>
            );
          })()}

          {/* More from @account / source — IG-profile-equivalent strip */}
          {(() => {
            const todayStr = new Date().toISOString().split("T")[0];
            const more = relatedEvents
              .filter((e) =>
                e.id !== event.id
                && (e.date >= todayStr)
                && (
                  (event.instagramAccount && e.instagramAccount === event.instagramAccount)
                  || (!event.instagramAccount && e.source === event.source && e.location?.name === event.location?.name && !!e.location?.name)
                )
              )
              .sort((a, b) => a.date.localeCompare(b.date))
              .slice(0, 4);
            if (more.length === 0) return null;
            const heading = event.instagramAccount
              ? `More from @${event.instagramAccount}`
              : event.location?.name
                ? `More at ${event.location.name}`
                : `More from ${SOURCE_LABELS[event.source] || event.source}`;
            return (
              <div className="pt-3 border-t border-gray-100">
                <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
                  {heading}
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  {more.map((e) => (
                    <button
                      key={e.id}
                      onClick={() => {
                        if (onSelectEvent) {
                          onSelectEvent(e);
                        } else {
                          onClose();
                        }
                      }}
                      className="text-left p-2 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors flex gap-2"
                    >
                      {e.imageUrl && (
                        <img
                          src={e.imageUrl}
                          alt=""
                          loading="lazy"
                          className="shrink-0 w-12 h-12 rounded object-cover bg-gray-100"
                          onError={(ev) => { (ev.currentTarget as HTMLImageElement).style.display = 'none'; }}
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="text-[11px] font-semibold text-gray-700 line-clamp-1">
                          {formatDateLabel(e.date)}
                          {e.startTime ? " · " + formatTime(e.startTime) : ""}
                        </div>
                        <div className="text-xs font-medium text-gray-900 line-clamp-2 leading-tight">
                          {e.title}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* More like this — same primary category, DIFFERENT account.
              IG-explore-equivalent: serendipitous discovery from new sources. */}
          {(() => {
            const todayStr = new Date().toISOString().split("T")[0];
            const primary = (event.categories || []).find((c) => c !== "free" && c !== "other");
            if (!primary) return null;
            const sameAcct = (event.instagramAccount || "").toLowerCase();
            const sameVenue = (event.location?.name || "").toLowerCase();
            const more = relatedEvents
              .filter((e) =>
                e.id !== event.id
                && (e.date >= todayStr)
                && (e.categories || []).includes(primary)
                // Exclude same account / same venue — that's covered by the
                // "More from @account" strip above. We want fresh sources.
                && (!sameAcct || (e.instagramAccount || "").toLowerCase() !== sameAcct)
                && (!sameVenue || (e.location?.name || "").toLowerCase() !== sameVenue)
              )
              .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
              .slice(0, 4);
            if (more.length === 0) return null;
            const cfg = CATEGORY_CONFIG[primary] || CATEGORY_CONFIG.other;
            return (
              <div className="pt-3 border-t border-gray-100">
                <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
                  More <span className={`inline-block px-1.5 py-0.5 rounded ${cfg.color} normal-case tracking-normal`}>{cfg.label}</span> like this
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  {more.map((e) => (
                    <button
                      key={e.id}
                      onClick={() => {
                        if (onSelectEvent) {
                          onSelectEvent(e);
                        } else {
                          onClose();
                        }
                      }}
                      className="text-left p-2 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors flex gap-2"
                    >
                      {e.imageUrl && (
                        <img
                          src={e.imageUrl}
                          alt=""
                          loading="lazy"
                          className="shrink-0 w-12 h-12 rounded object-cover bg-gray-100"
                          onError={(ev) => { (ev.currentTarget as HTMLImageElement).style.display = 'none'; }}
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="text-[11px] font-semibold text-gray-700 line-clamp-1">
                          {formatDateLabel(e.date)}
                          {e.startTime ? " · " + formatTime(e.startTime) : ""}
                          {e.instagramAccount ? <span className="text-gray-400 font-normal"> · @{e.instagramAccount}</span> : null}
                        </div>
                        <div className="text-xs font-medium text-gray-900 line-clamp-2 leading-tight">
                          {e.title}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

function formatDateLabel(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function ShareButton({ event }: { event: Event }) {
  const [copied, setCopied] = useState(false);
  const handle = async () => {
    const dt = (() => {
      try {
        const d = new Date(event.date + "T00:00:00");
        return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
      } catch {
        return event.date;
      }
    })();
    const tm = event.startTime ? formatTime(event.startTime) : "";
    const where = event.location.name || "";
    const body = `${event.title}\n${dt}${tm ? " · " + tm : ""}${where ? " · " + where : ""}\n${event.sourceUrl}`;
    try {
      // Use Web Share API when available (mobile), else clipboard.
      if (typeof navigator !== "undefined" && (navigator as Navigator & { share?: (data: ShareData) => Promise<void> }).share) {
        await (navigator as Navigator & { share: (data: ShareData) => Promise<void> }).share({
          title: event.title,
          text: body,
          url: event.sourceUrl,
        });
        return;
      }
      await navigator.clipboard.writeText(body);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };
  return (
    <button
      onClick={handle}
      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-medium transition-colors"
      title="Share / copy link"
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
      </svg>
      {copied ? "Copied!" : "Share"}
    </button>
  );
}

function formatTime(t: string): string {
  const [h, m] = t.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return m === 0 ? `${hour} ${ampm}` : `${hour}:${m.toString().padStart(2, "0")} ${ampm}`;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + "k";
  return String(n);
}
