# Feedback for this run — 2026-07-20-1815

North Star: surface events the user would actually attend in NYC. This round is anchored on today's user-explicit verification: the feed works but the top is a one-venue wall, and the user asked us to check for missing sources.

## Top 3 directives (workers MUST address or justify deferral)

### 1. Top-of-feed diversity — per-source/per-organizer cap in ranking
- backlog item: fb-202
- best agent: ingestion
- "addressed" criterion: add a per-source/per-organizer diversity penalty in compute_score / rank_events so no single venue owns the top. Measurable: no single source/organizer holds >3 of the top-12; AND ≥1 music/underground-electronic AND ≥1 run-club/comedy/dance event surface in the top-12 on the current feed. No fb-001..009 hard rule relaxed. (Finding today: top-12 = 8 bookclubbar + 4 luma; music/electronic buried.)

### 2. Missing-sources audit across confirmed interests + chess=0 root cause
- backlog item: fb-203 (extends fb-196)
- best agent: source-curator
- "addressed" criterion: ≥1 live-probed parseable path (≥5 future events, exclusion-clean, fb-106-clean) added toward the thinnest confirmed-interest gaps (music/underground-electronic, run-clubs, contra/dance, singles/social, games, comedy, outdoors), OR a live-verified honest negative per probed gap with root cause recorded. Chess-0 root cause identified (fix OR documented negative). Constraints: HoY/KDC stay excluded; no personal IG handles; no IG-sweep-dependent paths.

### 3. UI a11y follow-ups (U1 non-color conviction cue + U2 aria/focus rings)
- backlog item: fb-192 thread / carried UI a11y items (U1, U2)
- best agent: ui
- "addressed" criterion: conviction shown by a non-color cue (glyph/label), not color alone; aria + visible focus rings on interactive card/hero/filter controls. Calendar already received aria/focus this session via c2be7e8 (fb-204) — extend the same pattern to the rest.

## Questions to ask the user this round

none — gate CLOSED. Newest user-explicit feedback is today (2026-07-20) and there are ≥3 open items (fb-202, fb-203, fb-195, fb-196, fb-189, fb-193, fb-199, fb-200 …). No user-facing questions.

## Backlog mutations applied

- Added fb-202: Top-of-feed saturated by one followed venue (Book Club Bar wall); other named tastes buried. [status: open]
- Added fb-203: Missing-sources audit across the user's confirmed interests + chess yields 0. [status: open]
- Added fb-204: Show only today-onwards; calendar must not allow navigating to the past. [status: addressed: c2be7e8]
- Re-ranked: fb-202 → fb-203 → fb-204 moved to top of the open list, ahead of fb-194/195/196.
- Closed (with sha): none newly closed from a prior-run journal this round. (fb-204 lands as addressed: c2be7e8 per the orchestrator's shipped-this-session note.)

## Guardrails (do-not-surface as actionable this round)
- fb-174 (IG account-sweep 400-blocked fleet-wide), fb-173 (CI runner IP 403/429), fb-139 (Reddit OAuth) — infra/user-action blocked, route around.
- fb-104 / fb-185 — additive-only prunes, need explicit user opt-in.
- HoY / KDC user-EXCLUDED — do NOT re-add for the electronic gap.
- fb-106 — no personal IG handles in any add-list.
- fb-001..fb-009 hard blocks (nightclub/late-night/networking blocks, drinking penalties, alcohol-free boosts) preserved regardless of taste model.

## Notes / uncertainty
- fb-202 and fb-196(b) (underground-electronic depth) are complementary: fb-196 adds source depth; fb-202 fixes ranking so that depth actually reaches the top. Both target the same buried-music symptom from different lanes.
- fb-203 chess-0 investigation overlaps fb-196(a) (backgammon/chess). If the Chess Place organizer parses but yields nothing downstream, that is a ranking/cap issue (ingestion), not a source gap (curator) — flag which lane owns the fix once root cause is known.
