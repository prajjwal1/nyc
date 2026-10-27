# UI audit

Single-agent code audit. No independent browser/visual pass is claimed.

## Current behavior
The calendar remains the homepage, with the September responsive design already present. Events carry time, venue/neighborhood, price, organizer links, saved/follow signals, and detail navigation. Full descriptions are visible in detail pages and index quick views. The removed Feed/search/Hide/prose-follow UI remains absent. Storage keys stay at :v1.

## U1: Defer visual redesign until visual QA is available
- Directive: fb-212.
- Proposed action: retain the existing layout this run; no speculative UI change.
- Evidence: local Playwright Chromium fails during startup at the macOS Mach-port registration step, including the unrestricted retry. Meta browser navigation has no server annotation and provides no ready local browser alternative. Neither failure is a product assertion.
- Existing detail enrichment directly supplies the frontend without changing layout. The full production build and CI desktop/mobile suite will still run.
- Limitation: this does not close the user's design request. Keep fb-212 open.

## Directives
- fb-222: descriptions already render on the decision surfaces; no new widget required.
- fb-217: source warnings belong in pipeline diagnostics, not the product UI.
- fb-212: explicit deferral for critique.
