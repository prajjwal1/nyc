# Refreshing the Instagram session (the #1 recurring IG failure)

The IG scraper authenticates with an `instaloader` **session file**. It expires
roughly every ~25–30 days; once stale, the account-sweep returns
`feedback_required` / `checkpoint_required` / `login_required` / `429` and the
sweep silently yields nothing (saved/tagged still work for a while). This is the
dominant cause of low IG share — it is **user-action, not a code bug** (see
`feedback-backlog.md` fb-174).

## Symptoms
- `sanity_check` prints `IG session file MISSING` or `session … Nd ago` at 25d+.
- `sanity_check` WARNING "Instagram share (≥50 …)" under 50.
- `freshness-monitor.yml` fires; feed IG count drops while `CARRYOVER_SOURCES`
  keeps stale IG events alive.

## Refresh (local, ~2 min)
```bash
# 1. Log in locally to (re)create the session file
instaloader --login "$IG_USERNAME"        # default user: prajfb
# session written to ~/.config/instaloader/session-<user>

# 2. Sanity-check it loads + a saved-only scrape works
cd /Users/prajj/nyc-events && source venv/bin/activate
IG_SAVED_ONLY=1 python -m scrapers.run_all   # should print saved/tagged events

# 3. Update the CI secret so scheduled scrapes use the fresh session
base64 -i ~/.config/instaloader/session-"$IG_USERNAME" | pbcopy
gh secret set IG_SESSION_B64 --repo prajjwal1/nyc   # paste when prompted
```

## Notes
- Event **data** is increasingly IG-independent: the scraper harvests
  event-platform URLs (lu.ma/eventbrite/partiful/posh/ra.co/dice/…) from bios +
  captions into `discovered_urls.json`, which the generic scraper turns into
  structured events even when the sweep is blocked. So a stale session degrades
  discovery, not the whole feed.
- Do NOT lower the session-staleness thresholds in `sanity_check.py` to hide the
  warning — the warning is the reminder to run this runbook.
- If instaloader breaks fleet-wide (not just session age), the fallbacks are
  Playwright browser-automation or the official Graph API (business account) —
  see the plan's Workstream 3; both are larger and deferred.
