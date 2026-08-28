# Source Pool Report — 2026-08-28 1326

## Probe summary

- Lu.ma topics probed: 4 unique paths covering the meaningful `run`, `book`/`read`, `bk`/`brooklyn`, and `club` tokens | added: 0. All four returned the same 20-event generic `/nyc` payload. `ny`/`nyc` are geography rather than topics; `ai` was skipped because AI-themed events are explicitly excluded.
- Eventbrite folk-dance probe: 20 future events | strict participatory share 11/20 (55%) | inclusive share counting dance parties 15/20 (75%) | deployed URL matches: 0.
- Eventbrite organizer calendars probed: 27 | new additions recommended: 4 | staged additions endorsed: 5 of 6, with one additive guard required.
- URLs promoted from `discovered_urls`: 0. The numeric high-yield set is legacy duplication: dedicated-platform URLs, obsolete pagination, dynamic month pages, dedicated Bookmanager sources, or broad US-wide AllEvents pages.
- Accounts promoted: 0. No account outside `IG_ACCOUNTS` satisfies both `events_emitted >= 5` and discovery score `>= 0.45`; account-quality observations are also older than the requested ~30-day window.
- Dead-URL retests: 5 | resurrected: 0.
- Exclusion check: completed against all `accounts`, `hosts`, and `title_hints` in `user_excluded_sources.json` before every recommendation. No proposed host/account collides. Speed dating and AI remain explicit content exclusions.

## Highest-priority user-explicit check: Liz's Book Bar

Canonical Eventbrite organizer: `https://www.eventbrite.com/o/lizs-book-bar-83466825333` (organizer ID `83466825333`).

- **Eventbrite live probe**: 10 future events. Nine are exclusion-clean; `Speed Dating Book Club` is correctly rejected by the durable `speed dating` title hint.
- **Dedicated source live probe**: `scrapers/sources/lizsbookbar.py` returned 16 future events from the Bookmanager API.
- **Website check**: the deployed feed at `2026-08-28T17:07:01Z` contains 14 `lizsbookbar` events.
- **End-to-end simulation**: the Eventbrite organizer alone retains 9/10 after normalization. Combining its 10 rows with the 16 dedicated rows still produces 14 final events: duplicate variants collapse, both copies of the speed-dating event are excluded, and the thin `Celebrate Patricia Lockwood...` row remains below the score floor.
- **Coverage conclusion**: Liz's events do reach the website today through the dedicated source. The nine allowed Eventbrite organizer events are all represented by that source after title normalization; the only Eventbrite-only listing is the intentionally excluded speed-dating event. Adding the organizer is still useful as a user-requested fallback and gives Eventbrite organizer provenance, but it adds no currently allowed event by itself.

## Folk-dance directive (fb-187)

URL: `https://www.eventbrite.com/d/ny--new-york/folk-dance--events/`

- **Live state**: 20/20 returned records are future-dated as of 2026-08-28.
- **Strict participatory set, 11/20 (55%)**: No Lights No Lycra dance session; Brooklyn Contra Barn Dance; movement/theatre lab; Afrofusion workshop; Pacemakers workshop; Anime Gala dance lessons; Kompa class; African dance class; Bishop's Dance Academy; Hip Hop Dance; Dark Tease chair-dance class.
- **Inclusive participatory set, 15/20 (75%)**: the strict set plus four public dance parties. The five non-participatory rows are a staged dance performance/Q&A, Mid-Autumn Festival, Martha Graham gallery tour, dance-history talk, and live-music showcase.
- **Incremental value**: 12/20 URLs overlap the active broad `dance--events` search; the folk path contributes 8 distinct candidates, 4/8 strict participatory and 5/8 including the dance party.
- **Exclusions**: no account, host, or exact title-hint collision. Several party results are off-folk and should retain the normal score/late-night gates; this is not a source to grant a floor bypass.
- **Why health looks dead**: `url_health.json` says 7 failures / 0 successes, last failure 2026-07-23, but commit `8ee86c58` removed all fixed Eventbrite category URLs from `GENERIC_URLS`. The dedicated Eventbrite planner now schedules broad `dance`, not `folk-dance`, and the generic crawler intentionally skips Eventbrite URLs. The health record is stale configuration history, not evidence that today's endpoint is dead.
- **Landed quality**: 0 of the 20 live URLs appear in the deployed feed. Therefore the requested landed participatory ratio cannot yet be measured; the source is no longer scheduled.
- **Verdict**: the live set clears the >=50% participation bar. Restore it provisionally through the dedicated Eventbrite search plan, then keep fb-187 open until the next scrape measures actual survivors. No removal is proposed or needed; the source was already displaced by the platform-frontier refactor.

## Eventbrite organizer audit

The table separates raw future yield, user-clean/on-taste yield, projected normalized survival when treated as curated, and current website overlap. “Current overlap 0” means genuinely new coverage in the deployed 537-event feed.

| Organizer | ID | Future | User-clean / on-taste | Projected survivors | Current overlap | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Liz's Book Bar | `83466825333` | 10 | 9/10 | 9 alone; 0 net with dedicated source | 9 allowed events already represented | Add as explicit fallback |
| Caveat | `13580085802` | 12 | 12/12 | 5 | 0 | Endorse staged add |
| Union Hall | `17899496497` | 12 | 12/12 | 7 | 0 | Endorse staged add |
| Book Club Bar | `40513431663` | 12 | 12/12 | 11 | 10/11 already represented by 30-event dedicated source | Endorse as fallback; not new coverage |
| Book Club for the Book Hoes | `52255937823` | 10 | 10/10 | 9 | 0 | Endorse staged add |
| The National Arts Club | `6140247955` | 10 | 10/10 | 10 | 0 | Endorse staged add |
| After 5 Society | `120724085237` | 12 | 5/12 | 6 | 0 | Staged but needs guard; do not broaden |
| High Line Programs | `46113016283` | 12 | 12/12 | 7 | 0 | Recommend new add |
| The Ripped Bodice BK | `121441877858` | 12 | 12/12 | 9 | 0 | Recommend new add |
| Strand Bookstore | `30058841244` | 12 | 11/12 clean | 10 | 0 | Recommend new add |

The staged After 5 calendar is mixed-city: six of 12 rows are Houston/Boston/Chicago and are removed by the NYC gate. Of the six NYC rows, `After5NewYork- The AI Apocalypse: Separating Fear From Fact` violates the user's no-AI preference but is not caught by the current exact title hints. Preserve the staged source because this phase is additive-only, but add the exact `ai apocalypse` exclusion before deployment; then 5/12 raw rows remain useful NYC talks. Keep its existing `floor_bypass: false` setting.

## Proposals

### S1: Add Liz's Book Bar organizer `eventbrite.com/o/83466825333` to curated hosts

- **Metric moved**: source resilience and high-conviction provenance for an explicitly requested, already high-affinity venue.
- **Probe result**: 10 future, 9/10 exclusion-clean. Samples: "LBB Lit Fic Book Club: Riverwork by Lisa Robertson" (2026-09-09), "Ask A Literary Agent Anything" (2026-09-16), "Deesha Philyaw Launches The True Confessions of First Lady Freeman" (2026-09-28).
- **Existing coverage**: the dedicated Bookmanager source returns 16 future and currently lands 14 on the website. All nine allowed organizer rows are duplicates/variants of dedicated rows; this is a fallback, not claimed net-new inventory.
- **File**: `scrapers/data/user_curated_sources.json` — add stable organizer-ID host key `eventbrite.com/o/83466825333`, `source: user_mentioned`.
- **Risk**: low. Normalization kept 9/10 organizer rows alone and the combined direct+Eventbrite set stayed at 14 after exclusions/dedup.

### S2: Restore the folk-dance path to the dedicated Eventbrite plan, provisionally

- **Metric moved**: topic coverage and participatory dance depth.
- **Probe result**: 20 future; strict participatory 11/20 (55%), inclusive 15/20 (75%). Samples: "No Lights No Lycra NYC - Dance Session" (2026-09-02), "BROOKLYN CONTRA BARN DANCE" (2026-10-17), "KOMPA DANCE CLASS IN NYC" (2026-08-30).
- **Incremental result**: 8 URLs are absent from the active broad dance search; 4 are strict participatory.
- **File**: `scrapers/sources/eventbrite.py` — add as a supplemental search target owned by the Eventbrite adapter, not `GENERIC_URLS`.
- **Risk**: medium. It has off-folk performances and dance-party noise, so keep the normal floor/late-night/exclusion gates and re-measure landed share after the next scrape. Do not close fb-187 until that evidence exists.

### S3: Add High Line Programs organizer `eventbrite.com/o/46113016283`

- **Metric moved**: topic coverage (`outdoors`, `fitness`, `art`) and high-conviction ratio through an institution the user already follows.
- **Probe result**: 12 future, 12/12 exclusion-clean, 7 distinct survivors after recurring dedup. Samples: "Making Moves: Community Art Party" (2026-08-29), "Fit & Lit with Janeil Mason" (2026-09-14), "Tai Chi with Pin Pin Su" (2026-10-13).
- **Existing coverage**: genuinely new in the deployed feed. The configured High Line own-site URL has 15 failures / 0 successes and the deployed feed has no matching High Line events.
- **File**: `scrapers/data/user_curated_sources.json`.
- **Risk**: low — additive, institutional, NYC-only, and directly aligned with followed-account + outdoor-fitness taste.

### S4: Add The Ripped Bodice BK organizer `eventbrite.com/o/121441877858`

- **Metric moved**: high-conviction ratio and literary/social topic depth.
- **Probe result**: 12 future, 12/12 exclusion-clean, 9 distinct survivors after dedup. Samples: "Happily Everyone After Book Club" (2026-09-06), "Queer Lit Book Club" (2026-09-20), "Quest for Love Book Club" (2026-09-27).
- **Existing coverage**: genuinely new; zero matching deployed events.
- **File**: `scrapers/data/user_curated_sources.json`.
- **Risk**: low — additive, Brooklyn bookstore/social-club format, no family/nightlife/AI leakage in the live calendar.

### S5: Add Strand Bookstore organizer `eventbrite.com/o/30058841244`

- **Metric moved**: literary topic depth; recovers a source whose own events page is not parseable.
- **Probe result**: 12 future; 11/12 pass hard filters and 10 survive normalization. Samples: "Alice Hoffman + Adriana Trigiani: The Witches of Cambridge" (2026-09-08), "Malala Yousafzai + Hunter Harris: Finding My Way" (2026-09-16), "Harlan Coben + Amor Towles: Plot Twist" (2026-09-09).
- **Existing coverage**: genuinely new; zero matching deployed events. The old Strand page has 8 failures / 0 successes.
- **File**: `scrapers/data/user_curated_sources.json`.
- **Risk**: low-medium — one storytime row is already hard-blocked and one sold-out event falls below the score floor; the remaining adult literary calendar is strong.

### S6: Ship five already-staged organizer additions

- **Metric moved**: high-conviction ratio and breadth across comedy, literature, social clubs, arts, and talks.
- **Probe results**:
  - Caveat `13580085802`: 12 future / 12 clean / 5 projected survivors. Samples: "Talk Heavy Comedy", "Impossible New York Stories", "New York Groove: Labor Days".
  - Union Hall `17899496497`: 12 / 12 / 7. Samples: "CRANK THAT Comedy Show", "Honey Works It Out", "Cold Plunge with Kurt Braunohler".
  - Book Club Bar `40513431663`: 12 / 12 / 11; primarily fallback coverage because 10/11 are already represented by the 30-event dedicated calendar.
  - Book Club for the Book Hoes `52255937823`: 10 / 10 / 9. Samples: "Book Exchange Mixer", "IN TRANSLATION Book Club", "WELCOME Book Club".
  - The National Arts Club `6140247955`: 10 / 10 / 10. Samples: "Reflections in Black", "Judy Blume: A Life", "Art: Resistance and Restitution".
- **File**: already staged in `scrapers/data/user_curated_sources.json`; no additional source-file edit is needed.
- **Risk**: low. Caveat and Union Hall produce only 5 and 7 final rows respectively because the normal quality floor still removes thin listings; that is desirable bounded behavior.

### S7: Add an exact AI guard for the staged After 5 organizer

- **Metric moved**: high-conviction precision; enforces the user's explicit no-AI rule.
- **Probe result**: 12 future, six non-NYC rows filtered, leaving six NYC talks; one of those is "The AI Apocalypse: Separating Fear From Fact". Net user-fit set is 5/12 raw.
- **File**: `scrapers/data/user_excluded_sources.json` — add title hint `ai apocalypse` with the existing `user_mentioned_no_ai` reason.
- **Risk**: low and additive. Keep `eventbrite.com/o/120724085237` boost-only (`floor_bypass: false`); do not add broader AI matching from this one example.

## Validated but held (do not add this round)

- Love & Legends Books / ATOLYE `120654360557`: 12 future, 12 survivors, zero deployed overlap. Excellent extraction, but it is narrowly fantasy/romantasy and this round already adds substantial literary depth. Best reserve candidate.
- UrbanGlass `4279966505`: 12 future, 12 survivors, zero deployed overlap. Strong hands-on arts calendar, but mostly paid multi-session classes and no explicit user affinity; hold behind the higher-confidence social/literary/outdoor choices.
- Barnes & Noble Union Square `43013127903`: 12 future, 11 pass current filters, but at least three listings are family/children-oriented and the source is a mass retailer. Hold behind Strand and independent bookstores.
- Fit4Dance `14019215341`: 10 future and participatory, but only 4 survive normalization; below the meaningful landed-yield bar and its calendar includes two "After Dark"/lap-dance rows.
- Cucala Dance Company `53470389893`: 12 future, but same-day recurring/image dedup reduces the set to 3 distinct survivors. Do not add until it can land at least 5.
- Lectures on Tap `86136754923`: 12 future but only 6 NYC; the organizer is multi-city and clears just 50% of the platform's automatic quality test. Do not curate globally.
- Books Are Magic `17671794664`: 12 future but only 7 non-family rows; the entity is already represented in curated hosts and IG seeds. No extra Eventbrite pin this round.
- Brooklyn Comedy Collective `27620063469`: 12 future / 7 projected, but the dedicated source already supplies 40 deployed events. No duplicate organizer add.
- St. Mazie `5803675324`: 9 future, all clean, but it is already in the learned frontier through a `user_mentioned` discovered URL. No duplicate config entry.

## Account promotion / co-mention BFS

- Joined `account_quality.json` with `discovered_accounts.json`: zero unconfigured accounts meet both `events_emitted >= 5` and score `>= 0.45`.
- Reviewed the latest 10 score-qualified co-mentions from signal accounts. `paulacoopergallery`, `consuladobrnyc`, and `bamfilmbrooklyn` are entity-shaped; `cvall96` is person-shaped and was dropped immediately. Every reviewed candidate has 0 scraped posts / 0 emitted events, and discovery data is from May, so none is safe to promote.
- No IG account add is proposed. This also avoids pretending the stale/blocked IG crawl is live evidence.

## High-yield URL audit

- 94 `url_health` entries have at least three historical successes and a last yield of at least five while not appearing literally in today's `GENERIC_URLS`/`LUMA_PAGES`.
- 61 are Eventbrite/Luma URLs now owned by dedicated adapters, so putting them back into `GENERIC_URLS` would duplicate requests and split platform state.
- The 33 non-platform rows are old dynamic calendar months, duplicate aliases for dedicated Bookmanager/comedy/Green-Wood sources, obsolete Songkick/AllEvents pagination, or US-wide seasonal pages. None is a genuinely new, current, on-taste source.
- Result: no static URL promotion. Organizer IDs are the stable Eventbrite promotion unit under the current architecture.

## Dead-URL retests

- `https://www.92ny.org/calendar`: 0 events.
- `https://www.bricartsmedia.org/events`: 0 events.
- `https://www.brooklynbrewery.com/visit-the-brewery/events/`: 0 events.
- `https://lpr.com/calendar/`: 0 events.
- `https://www.bowerypoetry.com/events`: 404 / 0 events.

All five are already seed URLs, so no add/un-deadlist proposal follows. DICE/Tixr/RA/Time Out blocked-list URLs were not re-probed. `dead_accounts.json` is dominated by stale/transient Instagram failures; no account was reactivated without a fresh successful account scrape.

## Lu.ma probes that failed (don't add)

- `https://lu.ma/nyc/run`: 20 events, identical to `https://lu.ma/nyc`.
- `https://lu.ma/nyc/books`: 20, identical to `/nyc`.
- `https://lu.ma/nyc/brooklyn`: 20, identical to `/nyc`.
- `https://lu.ma/nyc/clubs`: 20, identical to `/nyc`.

These are fallback routes, not topic feeds. Adding them would multiply the same generic catalog and reintroduce off-vector founder/AI inventory. The dedicated Luma frontier already covers the city catalog and learned curator calendars.

## Directives addressed

- **fb-178 / fb-199**: formally deferred to the UI owner. Source curation cannot restore the browser-to-pipeline taste export; this report did apply the current inferred taste vector and explicit negative rules when selecting organizers.
- **fb-187**: live-probed and quantified. The endpoint is healthy at 20 future; strict participation is 55%, but landed yield is zero because the exact path is no longer scheduled. S2 restores it provisionally and requires a next-scrape landed audit before closure.
- **fb-193**: formally deferred to ingestion. Cross-source aliases/title variants were visible in the Liz's/Book Club Bar comparisons; source additions should rely on the canonical venue/dedup work rather than create parallel source-specific aliases.
- **User-explicit Liz's Book Bar request**: verified dedicated source -> normalization -> deployed website (14 live rows), probed Eventbrite organizer (10 future / 9 allowed), and proposed the organizer as a fallback.
- **User-explicit inferred-interest requirement**: organizer recommendations were ranked by demonstrated taste, not popularity: literary/social clubs, thoughtful talks, outdoor fitness, participatory experiences, comedy/art, Brooklyn, and meet-people value. Corporate training, generic nightlife, family/kids, AI, noisy mass listings, and low-landed-yield organizers were rejected or held.

## Open questions for the Critic

- Approve S2's additive restoration now, or require the organizer-based dance sources to improve first? The live folk path clears the strict 50% bar and adds 8 URLs beyond broad dance, but it has no landed evidence because it was removed from scheduling.
- The staged After 5 organizer has five good NYC talks but a 50% multi-city rejection rate and one uncaught AI event. Recommend preserving the staged source only with S7's exact exclusion and existing `floor_bypass: false`; otherwise defer it rather than broadening.
- The current full-run organizer budget is 20. The staged set plus S1/S3-S5 remains within that ceiling, but organizer-level diversity should be checked after the next scrape so literary additions do not displace fitness/dance exploration.
