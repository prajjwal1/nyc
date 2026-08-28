# Applied changes

- [x] ingestion-P1: canonical venue aliases now feed neighborhood inference — `scrapers/normalize.py`
- [x] ingestion-P2: ordinal-street matching no longer confuses 31st Avenue with 1st Avenue — `scrapers/utils/event_parser.py`
- [x] ingestion-P3: Bookmanager events retain credible event-specific offsite addresses — `scrapers/utils/bookmanager.py`
- [x] ingestion-P4: Eventbrite organizer promotion is exclusion-aware, deduplicated, taste-first, and preserves curated provenance — `scrapers/sources/eventbrite.py`, `scrapers/utils/platform_discovery.py`, `scrapers/normalize.py`
- [x] ingestion-P5: stable Eventbrite organizer IDs match slugged URLs, and structured Bookmanager titles bypass only the generic caption-fragment rule — `scrapers/ranking.py`, `scrapers/utils/bookmanager.py`, `scrapers/normalize.py`
- [x] ingestion-P6: equal Eventbrite start/end times are emitted as an unknown end time — `scrapers/sources/eventbrite.py`
- [x] ingestion-P7: Substack date-range headings using “through” are rejected — `scrapers/sources/substack.py`
- [x] ingestion-P8: explicit nearby-state addresses and Edmonton events are rejected — `scrapers/quality.py`
- [x] source-pool-S1: added the user-requested Liz's Book Bar organizer `83466825333` as a deterministic fallback — `scrapers/data/user_curated_sources.json`
- [x] source-pool-S2: restored `folk-dance` as a personal-dance supplemental Eventbrite query, behind normal quality gates — `scrapers/sources/eventbrite.py`
- [x] source-pool-S3: added High Line Programs as inferred taste, without floor bypass — `scrapers/data/user_curated_sources.json`
- [x] source-pool-S4: added The Ripped Bodice Brooklyn as inferred taste, without floor bypass — `scrapers/data/user_curated_sources.json`
- [x] source-pool-S5: added Strand Bookstore as an inferred bookstore preference, without floor bypass — `scrapers/data/user_curated_sources.json`
- [x] source-pool-S6: added the vetted Caveat, Union Hall, Book Club Bar fallback, Book Hoes, and National Arts Club organizers with conservative provenance and normal score floors — `scrapers/data/user_curated_sources.json`
- [x] source-pool-S7: added the exact `ai apocalypse` exclusion and withheld the low-fit After 5 organizer — `scrapers/data/user_excluded_sources.json`, `scrapers/data/user_curated_sources.json`
- [x] ui-U1: attendance answers now retain event examples, are idempotent, and reverse prior profile effects when changed — `site/app/lib/interests.ts`
- [x] ui-U2: restored a local, download-only taste export with separate saved, hidden, attended-yes, and attended-no evidence — `site/app/lib/tasteExport.ts`, `site/app/components/Header.tsx`
- [x] ui-U3: crawlable event pages now expose provenance plus Save, Add to calendar, and Hide actions — `site/app/events/[id]/page.tsx`, `site/app/components/EventDetailActions.tsx`
- [x] ui-U4: cards show neighborhood when venue is absent and grouped listings avoid redundant day labels — `site/app/components/EventCard.tsx`, `site/app/events/page.tsx`
- [x] dream-D1: sanity checks now report active-feed follow coverage separately from lifetime source yield — `scrapers/sanity_check.py`
- [x] user-SEO: added canonical metadata, crawlable event/category pages, Event and ItemList JSON-LD, sitemap, robots, social images, and internal links — `site/app/`
- [ ] source-pool-S7 organizer: After 5 was not added because only about 42% of its probed calendar was useful, below the 80% organizer-quality bar.
- Deferred to backlog: D2 as fb-209 (learn an Eventbrite organizer quality score over time).

