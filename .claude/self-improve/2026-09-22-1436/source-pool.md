# Source Pool Report — 2026-09-22 1436

## Probe summary

- Lu.ma topic URLs probed: 3; added: 0. `/nyc/run`, `/nyc/books`, and `/nyc/social` each returned the same generic NYC catalog rather than a topic-specific inventory.
- Pending independent calendars probed: 3; added: 0. Worlds Borough Bookshop returned 403; Brooklyn Running Co and NYCRUNS yielded zero parseable events.
- Eventbrite writing collection probed: 38 rows; added: 0. Samples were predominantly Sheffield, England, online, or children-oriented and fail the NYC/taste gate.
- Existing dynamic frontier verified: The Ripped Bodice BK 12/12 surviving, National Arts Club 12/12, Pioneer Works 9/9.

## Proposals

### S1: Add the seven probed candidate URLs
- **Metric moved**: proposed topic coverage expansion.
- **Verdict requested**: reject. None supplies a distinct, clean NYC calendar at the required threshold; the Lu.ma paths are duplicates and the Eventbrite collection is geographically wrong.
- **Risk**: adding them would create duplicate or off-topic volume.

## Directives addressed

- fb-216: the criterion is met by the already-shipped learned frontier in `344a2f0f`, not by lowering today’s gate. Three active, non-duplicate personal-lane organizers each yield at least nine fully surviving events across literary, art, music, science, and food interests; Eventbrite inventory is 155 versus 131 on 2026-09-17.

## Probes that failed (do not add)

- `https://theworldsboroughbookshop.com/events/list/upcoming-events`: 403.
- `https://www.brooklynrunningco.com/blogs/news/events-calendar/`: zero parsed.
- `https://nycruns.com/races`: zero parsed.
- `https://www.eventbrite.com/cc/writing-community-4261073`: non-NYC/online/kids inventory.
- `https://lu.ma/nyc/{run,books,social}`: duplicate generic catalog responses.

