# UI Report — 2026-10-01-1809

## Evidence

The default calendar day has 55 listings. Time and actionable-location completeness are both 98.2%, but description completeness is 47.3%. Event details cannot tell the user what to expect when the source payload is empty. Existing card/detail components already render descriptions; fixing ingestion reaches both surfaces.

## U1 — Populate existing description surfaces

- Metric: useful description coverage; no new storage or UI controls.
- Change: accept P1's data improvement and verify existing event cards/detail pages at mobile and desktop sizes.
- UI code: no change proposed unless browser verification reveals a regression.
- Preserve: calendar homepage, removed navigation/search/Hide controls, mobile back link, text-only missing-image cards, existing localStorage keys.

## Directives

- fb-220: consume source-written prose in the existing design.
- fb-210/fb-221: build and browser verification required.
- fb-212: defer a new design change; this round's measured deficiency is missing content. Leave the item open.
