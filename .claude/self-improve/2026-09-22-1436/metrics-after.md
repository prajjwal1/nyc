# Metrics after (snapshot replay)

- Event count: 693 → 687 after applying the new exclusions to the current snapshot.
- Follow-graph coverage: 50/50 (100.0%) → 50/50 (100.0%).
- Topic coverage remains complete: `ny=131`, `nyc=84`, `club=70`, `run=25`, `bk=67`, `brooklyn=67`, `read=38`; `book` moves 117 → 115 because two AI-themed literary rows are intentionally excluded.
- High-conviction ratio: 69/693 (9.96%) → 68/687 (9.90%); one false high-conviction AI row is removed.
- Explicit-exclusion/public-availability leaks: 6 → 0.

