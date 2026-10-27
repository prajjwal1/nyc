# Source pool audit

Single-agent audit; public source GET requests only. No internal data was uploaded and no authentication/session material was sent to publishers.

## Current supply
764 events across 18 sources; the next seven days contain 377 events and 161 organizers. Books 135, fitness 39, games 19, music 215. Historical follow yield is already 100%. Existing discovery lanes provide 228 personal and 536 explore rows.

## Probes
- Open Book Club RSS: HTTP 200, 20 items. Latest post is October 26, “What we're reading in November”. The production parser's latest-eight window emits four posts dated October 21, October 13, October 8, September 16; zero future events. It also exposes one Luma event link. URL persistence was disabled during this read-only audit.
- Four Eventbrite detail pages: HTTP 200; two ordinary book-club pages match the existing exact-date parser, two recurring pages require the occurrence proof in ingestion-P1.
- Exclusion configuration was read. No proposed account or venue bypasses it.

## Proposals
### S1: Retain current discovery configuration
No new source clears a demonstrated unmet-topic need plus >=5 future, exclusion-clean events. Do not add the lone Luma event as a calendar or turn newsletter publication dates into event dates. No source or account was removed/downgraded.

## Directives
- fb-222: live yoga/book-club proof supports P1.
- fb-217: history includes repeated checks; do not confuse them with separate scrape snapshots.
- fb-212: no source-side design change needed.
- fb-187 stays open: historical folk-dance URL failures provide no new >=5 landed participatory proof.
