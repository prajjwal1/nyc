import hashlib
import os
import re
from datetime import date, datetime, timezone


def deduplicate(events: list[dict]) -> list[dict]:
    seen = {}
    for ev in events:
        key = _dedup_key(ev)
        if key not in seen:
            seen[key] = ev
        else:
            existing = seen[key]
            seen[key] = _merge(existing, ev)
    out = list(seen.values())

    # Second pass: image-URL based merge across DIFFERENT title-keys.
    # When the same flyer image is shared by N posts on the same date, they
    # are the same event regardless of who wrote the caption. This catches
    # cross-source duplicates (e.g., Eventbrite event re-posted on IG and
    # picked up by Reddit) that the title-based dedup misses due to subtle
    # wording differences.
    out = _dedup_by_image(out)

    # Third pass: fuzzy-title-overlap merge for events that share a date AND
    # a venue/account AND have high token-overlap in titles. Catches
    # "Sips & Stories at Cafe Erzulie" vs "Sips & Stories NYC: The Social
    # Room at Cafe Erzulie" — same event, two sources, different wording.
    out = _dedup_fuzzy_title(out)

    # Fourth pass: cross-IG-account merge. When @theskint + @nycforfree +
    # @secretnyc all promote the same event, the existing fuzzy pass
    # CANNOT merge them because _venue_key returns "ig:<account>" which is
    # unique per account. Image-URL dedup also misses since the same flyer
    # reposted gets different CDN URLs. This pass keys on (date, normalized
    # venue) regardless of which IG account posted, and merges when titles
    # have strong token overlap. Yields one event with contributingAccounts
    # = [theskint, nycforfree, secretnyc] — strong cross-account validation.
    out = _dedup_cross_ig_account(out)

    # 4b. Same-account recurring posts: an IG account posting weekly about
    # the same series creates duplicate cards across multiple dates. Collapse
    # to the earliest occurrence and mark recurring=True.
    out = _dedup_same_account_recurring(out)

    # Fifth pass: perceptual-hash dedup. Catches residual same-flyer reposts
    # where the title differs enough to escape fuzzy-token-match (e.g.,
    # one account writes "PICKLEBALL @ McCarren!", another writes "Open
    # play tonight at McCarren") AND the image URLs differ (CDN tokens).
    # Lazy: only computes hashes for events bucketed by (date, venue) where
    # there's actually a chance of collision — never hashes events in
    # singleton buckets. Disable via DEDUP_PHASH=0.
    if os.environ.get("DEDUP_PHASH", "1") != "0":
        out = _dedup_perceptual_hash(out)
    return out


def _dedup_perceptual_hash(events: list[dict]) -> list[dict]:
    """Merge events whose flyer images perceptually match (Hamming ≤ 5)
    AND share a date AND share a normalized venue/account scope.

    This is the LAST resort dedup — catches reposts where:
      - Title diverges enough to escape fuzzy-token match
      - Image URLs differ (CDN tokens) so exact-URL dedup misses
      - Same flyer image (≤ 5 bit diff after aHash)

    Lazy: only computes hashes inside buckets that have ≥2 candidates with
    image URLs, so we never download images for singletons. Hard cap on
    network calls per run to bound cost on first-run cache miss. After the
    first run, hashes are cached on disk and revisits are free.
    """
    try:
        from .utils.image_hash import compute_phash, hamming_distance, flush_cache
    except Exception:
        return events  # PIL/httpx import path failed — degrade gracefully

    MAX_HASHES_PER_RUN = int(os.environ.get("DEDUP_PHASH_MAX", "300"))
    HAMMING_THRESHOLD = 5  # tolerance for compression / minor edits

    # Bucket by (date, venue_key). Reuse _venue_key — already normalized.
    by_bucket: dict[tuple[str, str], list[int]] = {}
    for i, ev in enumerate(events):
        d = ev.get("date") or ""
        # For p-hash we want a SOFT venue scope so cross-account flyers
        # bucket together. Use just the location name (no ig:account prefix)
        # so events from different IG accounts at the same venue can match.
        loc = ((ev.get("location") or {}).get("name") or "")
        loc_norm = _normalize_venue_name(loc)
        if not d or not loc_norm or len(loc_norm) < 3:
            continue
        # Skip events without an image — nothing to hash
        img = (ev.get("imageUrl") or "").strip()
        if not img or len(img) < 30:
            continue
        by_bucket.setdefault((d, loc_norm), []).append(i)

    hashes_computed = 0
    merges = 0
    merged_into: dict[int, int] = {}

    for indices in by_bucket.values():
        if len(indices) < 2:
            continue
        # Compute hashes for this bucket up to the hash budget.
        idx_to_hash: dict[int, str] = {}
        for i in indices:
            if hashes_computed >= MAX_HASHES_PER_RUN:
                break
            img = events[i].get("imageUrl") or ""
            h = compute_phash(img)
            hashes_computed += 1
            if h:
                idx_to_hash[i] = h
        if len(idx_to_hash) < 2:
            continue
        # Greedy merge within bucket.
        idx_list = list(idx_to_hash.keys())
        for a in range(len(idx_list)):
            ia = idx_list[a]
            if ia in merged_into:
                continue
            for b in range(a + 1, len(idx_list)):
                ib = idx_list[b]
                if ib in merged_into:
                    continue
                if hamming_distance(idx_to_hash[ia], idx_to_hash[ib]) <= HAMMING_THRESHOLD:
                    events[ia] = _merge(events[ia], events[ib])
                    merged_into[ib] = ia
                    merges += 1

    # Persist new hash cache entries so next run is cheaper.
    try:
        flush_cache()
    except Exception:
        pass

    if merges:
        print(f"[normalize] Perceptual-hash merged {merges} same-flyer duplicates "
              f"(hashed {hashes_computed} images)")

    out = [ev for i, ev in enumerate(events) if i not in merged_into]
    return out


def _dedup_same_account_recurring(events: list[dict]) -> list[dict]:
    """Collapse events from the SAME publisher that share a near-identical
    title across multiple dates. These are usually the same recurring series
    captured from multiple weekly posts/listings. Keeping all of them
    inflates the feed with duplicate cards.

    Key by (source, account/sourceUrl-base). Triggers when:
      - Same publisher
      - Jaccard >= 0.75 on title tokens (or >=4 shared distinctive tokens)
      - Dates are different (otherwise the regular dedup already handled it)

    Covers: IG (instagramAccount), meetup (organizer URL), songkick (artist
    in URL), eventbrite (organizer slug), bookclubbar/lizsbookbar venues.
    """
    from urllib.parse import urlparse
    by_acct: dict[str, list[dict]] = {}
    out: list[dict] = []
    for ev in events:
        # Build a publisher key per source. For non-IG: just source+netloc.
        # Trying to include path-prefix backfires when ticketing platforms
        # embed dates/IDs in the slug (e.g. ticketmaster.com/why-are-you-
        # single-...-05-21-2026/event/<id>) — same recurring show on
        # different nights gets different path-prefixes and never merges.
        # Same publisher key + strict title Jaccard (>=0.75) gives the
        # right balance: different shows at the same venue have distinct
        # titles → low Jaccard → no false merge.
        src = ev.get("source", "")
        if src == "instagram":
            key = "ig:" + (ev.get("instagramAccount") or "").lower()
        else:
            try:
                p = urlparse(ev.get("sourceUrl") or "")
                key = f"{src}:{p.netloc}" if p.netloc else ""
            except Exception:
                key = ""
        if not key:
            out.append(ev)
            continue
        by_acct.setdefault(key, []).append(ev)

    merges = 0
    for acct, group in by_acct.items():
        if len(group) <= 1:
            out.extend(group)
            continue
        token_sets = [_title_token_set(e.get("title", "")) for e in group]
        merged_into: dict[int, int] = {}
        for i in range(len(group)):
            if i in merged_into:
                continue
            for j in range(i + 1, len(group)):
                if j in merged_into:
                    continue
                if group[i].get("date") == group[j].get("date"):
                    continue
                a, b = token_sets[i], token_sets[j]
                if not a or not b:
                    continue
                jacc = len(a & b) / len(a | b)
                # Same publisher is itself strong signal — relax the
                # min-token-count constraint. Generic recurring-show titles
                # like 'New York Comedy Club Presents' have just 2 distinctive
                # tokens after stopwords (presents/live/show all stripped),
                # but we still want to collapse repeated nights of the same
                # generic show.
                if jacc >= 0.75 or len(a & b) >= 4 or (jacc >= 0.9 and len(a) >= 2):
                    # Keep the earlier-dated one; merge later into earlier
                    earlier, later = i, j
                    if group[j].get("date","") < group[i].get("date",""):
                        earlier, later = j, i
                    group[earlier] = _merge(group[earlier], group[later])
                    group[earlier]["recurring"] = True
                    merged_into[later] = earlier
                    merges += 1
        for i, e in enumerate(group):
            if i not in merged_into:
                out.append(e)
    if merges:
        print(f"[normalize] Same-account recurring merged {merges} duplicate posts")
    return out


def _dedup_cross_ig_account(events: list[dict]) -> list[dict]:
    """Merge IG events across DIFFERENT accounts when same date + venue +
    high title-token overlap. Strict thresholds to avoid mismerging unrelated
    events: Jaccard >= 0.60 AND >= 3 shared distinctive tokens."""
    by_bucket: dict[tuple[str, str], list[dict]] = {}
    out: list[dict] = []
    for ev in events:
        if ev.get("source") != "instagram":
            out.append(ev)
            continue
        d = ev.get("date") or ""
        loc = ((ev.get("location") or {}).get("name") or "")
        if not d or not loc:
            out.append(ev)
            continue
        loc_norm = _normalize_venue_name(loc)
        if len(loc_norm) < 3:
            out.append(ev)
            continue
        by_bucket.setdefault((d, loc_norm), []).append(ev)

    cross_merges = 0
    for bucket in by_bucket.values():
        if len(bucket) == 1:
            out.append(bucket[0])
            continue
        # Skip if all events are from the SAME IG account — the fuzzy pass
        # would have handled them; this pass only adds value across accounts.
        accounts_in_bucket = {(e.get("instagramAccount") or "").lower() for e in bucket}
        accounts_in_bucket.discard("")
        if len(accounts_in_bucket) <= 1:
            out.extend(bucket)
            continue

        token_sets = [_title_token_set(e.get("title", "")) for e in bucket]
        merged_into: dict[int, int] = {}
        keep_indices: list[int] = []
        for i in range(len(bucket)):
            if i in merged_into:
                continue
            keep_indices.append(i)
            for j in range(i + 1, len(bucket)):
                if j in merged_into:
                    continue
                a, b = token_sets[i], token_sets[j]
                if not a or not b:
                    continue
                jacc = len(a & b) / len(a | b)
                # Constraint: (same date) + (same normalized location) +
                # >= 3 distinctive shared tokens already strongly implies
                # the same event. Jaccard threshold is set lower than the
                # same-account fuzzy pass would suggest because cross-account
                # captions naturally have more vocabulary variation (different
                # writers describing the same event) — a stricter bar would
                # systematically miss legitimate cross-promotion merges.
                if jacc >= 0.50 and len(a & b) >= 3:
                    bucket[i] = _merge(bucket[i], bucket[j])
                    merged_into[j] = i
                    cross_merges += 1
        for k in keep_indices:
            out.append(bucket[k])
    if cross_merges:
        print(f"[normalize] Cross-IG-account merged {cross_merges} duplicate promotions")
    return out


def _title_token_set(title: str) -> set[str]:
    title_clean = "".join(c if c.isalnum() or c == " " else " " for c in (title or "").lower())
    return {w for w in title_clean.split() if w not in _STOPWORDS and len(w) > 2}


_NEIGHBORHOOD_SUFFIX_RE = re.compile(
    r"\s+(?:bushwick|williamsburg|greenpoint|east\s+village|west\s+village|"
    r"lower\s+east\s+side|upper\s+east\s+side|upper\s+west\s+side|"
    r"financial\s+district|chelsea|midtown|harlem|astoria|long\s+island\s+city|"
    r"crown\s+heights|fort\s+greene|prospect\s+heights|park\s+slope|"
    r"chinatown|tribeca|soho|noho|nolita|dumbo|boerum\s+hill|"
    r"red\s+hook|sunset\s+park|gowanus|carroll\s+gardens|cobble\s+hill|"
    r"hells?\s+kitchen|gramercy|union\s+square|flatiron|nomad|"
    r"manhattan|brooklyn|queens|bronx|nyc|ny|new\s+york)\b\s*$",
    re.IGNORECASE,
)


# Venue-name abbreviation expansions — common NYC shorthand that splits
# the same venue across multiple cross-source events (README §354 gap).
# Tested against word boundaries to avoid false-positives on tokens that
# happen to contain the abbreviation as a substring.
_VENUE_SYNONYMS = {
    r"\bbk\b": "brooklyn",
    r"\bbma\b": "brooklyn museum",
    r"\bmoma\b": "museum of modern art",
    r"\bbam\b": "brooklyn academy of music",
    r"\bkdc\b": "knockdown center",
    r"\bhoy\b": "house of yes",
    r"\bthe met\b": "metropolitan museum",
}
_VENUE_SYNONYM_RES = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in _VENUE_SYNONYMS.items()]


def _normalize_venue_name(loc: str) -> str:
    """Canonicalize a venue name so 'Book Club Bar Bushwick' and 'Book
    Club Bar' map to the same key. Steps:
      1. Drop everything after the first comma (street address)
      2. Expand venue-name abbreviations (BK → Brooklyn, MoMA → Museum of
         Modern Art, etc.) so cross-source variants merge.
      3. Strip well-known NYC neighborhood/borough suffixes
      4. Lowercase + collapse whitespace
    Lets cross-source dedup catch events at the same venue when one
    source includes the neighborhood and another doesn't.
    """
    if not loc:
        return ""
    s = loc.split(",")[0].strip()
    # Expand venue abbreviations BEFORE neighborhood-suffix stripping so
    # patterns like "Brooklyn Bowl" (synonym target) survive intact.
    for rx, repl in _VENUE_SYNONYM_RES:
        s = rx.sub(repl, s)
    # Strip trailing neighborhood/borough (e.g. "Book Club Bar Bushwick").
    # Repeat to handle "Book Club Bar Bushwick Brooklyn".
    prev = None
    while s != prev:
        prev = s
        s = _NEIGHBORHOOD_SUFFIX_RE.sub("", s).strip()
    return re.sub(r"\s+", " ", s.lower())


def _venue_key(ev: dict) -> str:
    """Soft venue identifier: IG account, or normalized location name, or
    Eventbrite organizer slug. Used to gate the fuzzy-title merge so we
    don't accidentally merge unrelated events that happen on the same day.
    """
    acct = (ev.get("instagramAccount") or "").lower()
    if acct:
        return "ig:" + acct
    loc = ((ev.get("location") or {}).get("name") or "").strip()
    if loc:
        return "loc:" + _normalize_venue_name(loc)
    if ev.get("source") == "eventbrite":
        try:
            from urllib.parse import urlparse
            p = urlparse(ev.get("sourceUrl") or "")
            tokens = (p.path or "").split("/")[:3]
            return "eb:" + "/".join(tokens)
        except Exception:
            pass
    return ""  # no soft venue → skip fuzzy merge for this event


def _dedup_fuzzy_title(events: list[dict]) -> list[dict]:
    """Merge events that share (date, venue) + token-set Jaccard >= 0.55.

    Conservative threshold: events truly identical-titled merged in pass 1.
    This pass picks up the cross-source variants where the same event has
    been described slightly differently (extra prefix, suffix, or word).
    """
    # Bucket by (date, venue_key) so we only compare events that are
    # plausibly the same event.
    by_bucket: dict[tuple[str, str], list[dict]] = {}
    out: list[dict] = []
    for ev in events:
        d = ev.get("date") or ""
        v = _venue_key(ev)
        if not d or not v:
            out.append(ev)
            continue
        by_bucket.setdefault((d, v), []).append(ev)

    merges = 0
    for bucket in by_bucket.values():
        if len(bucket) == 1:
            out.append(bucket[0])
            continue
        # Each event has a token set; greedy merge with first compatible peer.
        # Prefer keeping the event with the longer description (more info).
        token_sets = [_title_token_set(e.get("title", "")) for e in bucket]
        keep_indices: list[int] = []
        merged_into: dict[int, int] = {}
        for i in range(len(bucket)):
            if i in merged_into:
                continue
            keep_indices.append(i)
            for j in range(i + 1, len(bucket)):
                if j in merged_into:
                    continue
                a, b = token_sets[i], token_sets[j]
                if not a or not b:
                    continue
                jacc = len(a & b) / len(a | b)
                # Also require at least 2 shared distinctive tokens to avoid
                # matching short titles by accident.
                should_merge = jacc >= 0.55 and len(a & b) >= 2
                # Cross-source same-venue same-date with 2+ distinctive
                # shared tokens — e.g., songkick's "Charlie Puth @ Madison
                # Square Garden" vs allevents's "Charlie Puth, Daniel Seavey,
                # Ally Salort in New York". Token-set jaccard is low because
                # each title has extras the other doesn't, but the shared
                # tokens are the actual artist name. Only enable for non-IG
                # venues (loc:*) since IG bucket already collapses by account.
                if not should_merge and len(a & b) >= 2:
                    # Cross-source same-venue: when two different scrapers
                    # produce events at the same venue+date with 2+ shared
                    # tokens, they're almost always the same event with
                    # different framing (one lists the headliner alone,
                    # the other lists the opener too). The venue match is
                    # the strong signal; token overlap just confirms the
                    # subject. Only fires on non-IG venues (loc:*) and
                    # only when at least one shared token is reasonably
                    # distinctive (>=4 chars, not a stopword).
                    src_a = bucket[i].get("source")
                    src_b = bucket[j].get("source")
                    if src_a != src_b:
                        distinctive = [t for t in (a & b) if len(t) >= 4]
                        if len(distinctive) >= 2:
                            should_merge = True
                if should_merge:
                    bucket[i] = _merge(bucket[i], bucket[j])
                    merged_into[j] = i
                    merges += 1
        for k in keep_indices:
            out.append(bucket[k])
    if merges:
        print(f"[normalize] Fuzzy-title merged {merges} cross-source duplicates")
    return out


def _dedup_by_image(events: list[dict]) -> list[dict]:
    """Collapse events that share the same image_url + date into one merged
    event. Skip events with no image or with low-information image URLs
    (default avatars, etc.)."""
    by_image: dict[tuple[str, str], list[dict]] = {}
    no_image: list[dict] = []
    for ev in events:
        img = (ev.get("imageUrl") or "").strip()
        d = ev.get("date") or ""
        if not img or not d or len(img) < 30:
            no_image.append(ev)
            continue
        # Normalize: drop CDN query params that vary by load
        norm = img.split("?")[0]
        key = (norm, d)
        by_image.setdefault(key, []).append(ev)

    merged: list[dict] = list(no_image)
    for group in by_image.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        # Merge all into the first one using existing _merge
        result = group[0]
        for other in group[1:]:
            result = _merge(result, other)
        merged.append(result)
    return merged


_STOPWORDS = {
    "a", "an", "the", "at", "in", "on", "of", "for", "with", "to", "and",
    "or", "is", "are", "by", "from", "this", "that", "your", "our", "my",
    "presents", "presented", "live", "show", "event", "ticket", "tickets",
    "free", "nyc", "ny", "new", "york", "brooklyn", "manhattan",
}


def _dedup_key(ev: dict) -> str:
    """Build a normalized key for dedup.

    - Lowercase, alphanumeric only
    - Drop stopwords (so 'a night at the moma' = 'night moma')
    - Take first 6 distinctive words, sorted
    - Combine with date
    """
    title = ev.get("title", "").lower().strip()
    title_clean = "".join(c if c.isalnum() or c == " " else " " for c in title)
    words = title_clean.split()
    distinctive = [w for w in words if w not in _STOPWORDS and len(w) > 1][:6]
    title_norm = " ".join(sorted(distinctive))
    d = ev.get("date", "")
    return hashlib.md5(f"{title_norm}:{d}".encode()).hexdigest()


def _merge(a: dict, b: dict) -> dict:
    """Merge duplicate events, taking the best fields from both."""
    merged = dict(a)

    # Prefer the longer description
    if (b.get("description") or "") > (merged.get("description") or ""):
        merged["description"] = b["description"]

    # Prefer specific time over none, AND prefer the fresher scrape's
    # times when both have them. Reason: stale carryover may carry a
    # time produced under a now-fixed bug (e.g. iter 43 UTC->ET fix);
    # the fresh scrape's time reflects the current code path.
    def _newer(x: dict, y: dict) -> bool:
        return (x.get("scrapedAt") or "") > (y.get("scrapedAt") or "")
    if not merged.get("startTime"):
        if b.get("startTime"):
            merged["startTime"] = b["startTime"]
    elif b.get("startTime") and _newer(b, merged):
        merged["startTime"] = b["startTime"]
    if not merged.get("endTime"):
        if b.get("endTime"):
            merged["endTime"] = b["endTime"]
    elif b.get("endTime") and _newer(b, merged):
        merged["endTime"] = b["endTime"]

    # Prefer non-empty image
    if not merged.get("imageUrl") and b.get("imageUrl"):
        merged["imageUrl"] = b["imageUrl"]

    # Merge location fields
    loc_a = merged.get("location", {})
    loc_b = b.get("location", {})
    if not loc_a.get("name") and loc_b.get("name"):
        merged["location"]["name"] = loc_b["name"]
    if not loc_a.get("address") and loc_b.get("address"):
        merged["location"]["address"] = loc_b["address"]
    if not loc_a.get("neighborhood") and loc_b.get("neighborhood"):
        merged["location"]["neighborhood"] = loc_b["neighborhood"]

    # Union of categories
    cats = set(merged.get("categories", []) + b.get("categories", []))
    if "other" in cats and len(cats) > 1:
        cats.discard("other")
    merged["categories"] = sorted(cats)

    # Preserve user signals from either side
    merged["userSaved"] = bool(a.get("userSaved") or b.get("userSaved"))
    merged["userTagged"] = bool(a.get("userTagged") or b.get("userTagged"))
    merged["userAffinity"] = bool(a.get("userAffinity") or b.get("userAffinity"))
    merged["userFollowing"] = bool(a.get("userFollowing") or b.get("userFollowing"))
    merged["recurring"] = bool(a.get("recurring") or b.get("recurring"))
    merged["ocrEnriched"] = bool(a.get("ocrEnriched") or b.get("ocrEnriched"))

    # Track all sources contributing to this event (cross-source validation).
    a_sources = set(a.get("contributingSources", [a.get("source")] if a.get("source") else []))
    b_sources = set(b.get("contributingSources", [b.get("source")] if b.get("source") else []))
    merged["contributingSources"] = sorted(a_sources | b_sources)

    # Track which IG accounts mentioned this event (cross-account validation).
    # Crucial for IG: when @theskint, @nycforfree, @secretnyc all promote
    # the same event, that's a strong "definitely happening" signal that
    # should boost ranking AND surface "Recommended by @theskint, @secretnyc"
    # in the UI.
    a_accts = set(a.get("contributingAccounts", []))
    if a.get("instagramAccount"):
        a_accts.add(a["instagramAccount"].lower())
    b_accts = set(b.get("contributingAccounts", []))
    if b.get("instagramAccount"):
        b_accts.add(b["instagramAccount"].lower())
    if a_accts | b_accts:
        merged["contributingAccounts"] = sorted(a_accts | b_accts)

    # Prefer real ticket URL over IG post URL
    a_url = merged.get("sourceUrl", "")
    b_url = b.get("sourceUrl", "")
    if "instagram.com/p/" in a_url and "instagram.com/p/" not in b_url and b_url:
        merged["sourceUrl"] = b_url

    # Engagement: take the higher count
    merged["likes"] = max(a.get("likes", 0) or 0, b.get("likes", 0) or 0)
    merged["comments"] = max(a.get("comments", 0) or 0, b.get("comments", 0) or 0)

    return merged


def filter_future(events: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    # Evergreen events (spot recommendations from accounts like
    # @wherethefuckdowego) survive — they're place picks, not dated events.
    # We rewrite their date to today so they sort with current content.
    out = []
    for ev in events:
        if ev.get("evergreen"):
            ev["date"] = today
            out.append(ev)
            continue
        if ev.get("date", "") >= today:
            out.append(ev)
    return out


_FAR_FUTURE_DAYS = 180

# Sources that publish authoritative venue calendars with explicit dates.
# The far-future misparsed-date heuristic doesn't apply to them — when an
# author tour is booked 8 months out, that's a real date, not a date-parser
# defaulting to next year.
_TRUSTED_FAR_FUTURE_SOURCES = frozenset({
    "bookclubbar",
    "lizsbookbar",
    "mcnallyjackson",       # iter 102: dedicated month-pagination scraper
    "powerhousearena",      # iter 110: Squarespace eventlist with explicit dates
    "centerforfiction",     # iter 110: WordPress event pages with explicit dates
    "brooklyncomedy",       # iter 106: Squarespace eventlist with explicit dates
    "nycforfree",           # iter 100: Squarespace eventlist with explicit dates
    "museums",
    "music_venues",
    "greenwoodcemetery",    # iter 103: dedicated scraper
})


_COMEDY_LINEUP_SOURCES = frozenset({
    "newyorkcomedyclub", "eastvillecomedy", "thebellhouseny",
    "brooklyncomedy",   # iter 169: brooklyncomedy.py (iter 106) — verified
                        # source value is 'brooklyncomedy', matches the check
    # (Removed iter 169: 'comedycellar', 'ucbtheatre', 'thecaveatnyc' —
    # these are IG account handles, not source-field values. The check
    # `ev.get("source") not in ...` would never fire on them since IG
    # events have source='instagram'. They were dead set entries.)
})
# A title is a "comedian lineup" when it's 3+ comma-separated person-name
# tokens (First [Middle] Last) and contains no event-format keyword.
_COMEDIAN_NAME_RE = re.compile(
    r"^[A-Z][a-zA-Z'’\-\.]+(?:\s+[A-Z][a-zA-Z'’\-\.]+){1,3}$"
)
_COMEDY_KEYWORDS = frozenset({
    "comedy", "stand-up", "standup", "stand up", "show", "presents",
    "lineup", "live", "tour", "special", "headliner", "podcast",
    "open mic", "roast", "improv", "sketch", "showcase", "series",
})


_BOOK_TITLE_RE = re.compile(r"[\"“][^\"”]{2,80}[\"”]")


_VENUE_NAME_TO_NEIGHBORHOOD = {
    "liz's book bar": "carroll gardens",
    "book club bar": "east village",
    "mcnally jackson": "soho",
    "national sawdust": "williamsburg",
    "music hall of williamsburg": "williamsburg",
    "brooklyn bowl": "williamsburg",
    "rough trade nyc": "williamsburg",
    "elsewhere": "bushwick",
    "the bell house": "gowanus",
    "house of yes": "bushwick",
    "knockdown center": "ridgewood",
    "brooklyn steel": "east williamsburg",
    "kings theatre": "flatbush",
    "kings theatre brooklyn": "flatbush",
    "brooklyn academy of music": "fort greene",
    "bam": "fort greene",
    "the box": "lower east side",
    "the strand": "east village",
    "moma": "midtown",
    "the met": "upper east side",
    "metropolitan museum of art": "upper east side",
    "guggenheim": "upper east side",
    "whitney museum": "meatpacking",
    "brooklyn museum": "prospect heights",
    "new museum": "lower east side",
    "comedy cellar": "west village",
    "new york comedy club": "east village",
    "eastville comedy club": "east village",
}


def _backfill_neighborhood_from_venue(events: list[dict]) -> None:
    """Re-derive neighborhoods on every normalize pass:
    1. If a venue NAME maps to a known neighborhood, use that (most
       reliable — fixed-venue scrapers like Liz's Book Bar lack addresses).
    2. If an address is present, re-run infer_neighborhood with the
       current keyword list — catches stale tags from older keyword sets
       (e.g. "broadway" used to falsely tag Times Square as SoHo).
    3. Leave the existing tag alone only if nothing better can be derived.
    """
    from .utils.event_parser import infer_neighborhood
    for ev in events:
        loc = ev.get("location") or {}
        name = (loc.get("name") or "").lower().strip()
        addr = (loc.get("address") or "").strip()
        existing = loc.get("neighborhood")
        new_hood: str | None = None
        # Step 1: venue-name lookup (strongest signal)
        for venue, hood in _VENUE_NAME_TO_NEIGHBORHOOD.items():
            if venue in name:
                new_hood = hood
                break
        # Step 2: address inference (always re-runs, can override stale tags).
        # Also fold in title + location.name so titles like
        # "The 9:30 Comedy Show - Williamsburg" recover their neighborhood
        # even when the address has no neighborhood keyword (iter 72).
        if new_hood is None:
            title = (ev.get("title") or "")
            if addr or name or title:
                new_hood = infer_neighborhood(addr, name, title)
        # If the existing tag was derivable from current address keywords, keep
        # it; otherwise it's stale (e.g. neighborhood keyword removed since
        # last scrape) and gets cleared so the filter doesn't lie.
        if new_hood != existing:
            loc["neighborhood"] = new_hood
            ev["location"] = loc


# Re-export event_parser's authoritative tuples. Both lists used to be
# duplicated (iter 167 dedup'd the indoor-arena list; iter 168 dedup'd the
# strong-signals list — the categorizer's inline tuple had 14 entries vs
# normalize's 19, so 'garden party' / 'outdoors' / 'outdoor ' / ' park'
# survived only in normalize). Single source of truth.
from .utils.event_parser import (  # noqa: E402
    _OUTDOORS_FALSE_POSITIVE_VENUES as _OUTDOORS_INDOOR_ARENAS,
    _OUTDOORS_STRONG_SIGNALS,
)


def _strip_outdoors_indoor_arena(events: list[dict]) -> None:
    for ev in events:
        cats = ev.get("categories") or []
        if "outdoors" not in cats:
            continue
        text = f"{ev.get('title','')} {ev.get('description','')} {(ev.get('location') or {}).get('name','')}".lower()
        if any(v in text for v in _OUTDOORS_INDOOR_ARENAS) and not any(s in text for s in _OUTDOORS_STRONG_SIGNALS):
            ev["categories"] = [c for c in cats if c != "outdoors"] or ["other"]


def _prefix_book_club_lists(events: list[dict]) -> list[dict]:
    """Meetup book clubs sometimes ship a title that's just 2+ quoted book
    names ('"Siren’s Call", "Midnight Library" and "Washington"'),
    leaving the user with no context. Prepend "Book Club:" when we can
    confirm the source URL is a book-club meetup.
    """
    for ev in events:
        title = (ev.get("title") or "").strip()
        if not title or title.lower().startswith("book club"):
            continue
        # Need 2+ quoted titles in the displayed title.
        if len(_BOOK_TITLE_RE.findall(title)) < 2:
            continue
        # Source-specific gating: meetup URL contains "/books" group, or
        # description contains "book club".
        url = (ev.get("sourceUrl") or "").lower()
        desc = (ev.get("description") or "").lower()
        if "/books" in url or "/book-" in url or "book club" in desc:
            ev["title"] = f"Book Club: {title}"
    return events


def _prefix_comedian_lineups(events: list[dict]) -> list[dict]:
    for ev in events:
        if ev.get("source") not in _COMEDY_LINEUP_SOURCES:
            continue
        title = (ev.get("title") or "").strip()
        if not title or title.lower().startswith(("stand-up", "standup", "comedy")):
            continue
        title_lower = title.lower()
        if any(kw in title_lower for kw in _COMEDY_KEYWORDS):
            continue
        # Split on comma; each token should look like a person name.
        tokens = [t.strip() for t in title.split(",") if t.strip()]
        if len(tokens) < 3:
            continue
        # Drop trailing parenthetical from final token before regex check.
        last = re.sub(r"\s*\([^)]*\)\s*$", "", tokens[-1])
        tokens[-1] = last
        if not all(_COMEDIAN_NAME_RE.match(t) for t in tokens):
            continue
        ev["title"] = f"Stand-Up Comedy: {title}"
    return events


def collapse_title_spam(events: list[dict]) -> list[dict]:
    """Collapse repeated (title, sourceUrl) pairs that span weekly intervals
    without an explicit recurring marker. These are almost always a prior
    buggy recurring expansion of a one-shot event.

    Keep the earliest occurrence; drop the rest.
    """
    from collections import defaultdict
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for ev in events:
        key = (
            (ev.get("title", "") or "").strip().lower()[:80],
            (ev.get("sourceUrl", "") or "").split("?")[0],
        )
        groups[key].append(ev)

    keep: list[dict] = []
    dropped = 0
    for key, group in groups.items():
        if len(group) < 4:
            keep.extend(group)
            continue
        # 4+ events with same (title, sourceUrl). Only collapse if we have
        # NO evidence this is a legit recurring series. Trust signals:
        #   - event.recurring set by the recurring detector → keep all
        #   - description has explicit weekly/monthly/every-X marker
        #   - title contains weekday + day-of-week pattern indicating
        #     "this Tuesday" series (e.g. "Tuesday Run Club")
        if any(ev.get("recurring") for ev in group):
            # Already detected as recurring upstream — trust it
            keep.extend(group)
            continue
        desc = (group[0].get("description", "") or "").lower()
        title = (group[0].get("title", "") or "").lower()
        recurring_markers = (
            "every ", "weekly", "each week", "monthly", "each month",
            "first ", "second ", "third ", "fourth ", "last ",
            "biweekly", "fortnightly", "every other",
        )
        if any(m in desc or m in title for m in recurring_markers):
            keep.extend(group)
            continue
        # Title contains a day-of-week followed by a noun → likely series
        # (e.g. "Tuesday Run Club", "Saturday Brunch Club", "Sunday Yoga")
        day_series_re = re.compile(
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b\s+\w+",
            re.IGNORECASE,
        )
        if day_series_re.search(title):
            keep.extend(group)
            continue
        # Sort by date and keep only the earliest one.
        group.sort(key=lambda e: e.get("date", ""))
        keep.append(group[0])
        dropped += len(group) - 1

    if dropped:
        print(f"[normalize] Collapsed {dropped} title-spam events (suspected bad recurring expansion)")
    return keep


_TIME_IN_TEXT_RE = re.compile(
    r"\b(?:doors?(?:\s+(?:open|at))?|starts?(?:\s+at)?|"
    r"kicks?\s+off(?:\s+at)?|show)\s*:?\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?",
    re.I,
)


def _infer_time_from_text(title: str, description: str) -> str | None:
    """Infer an HH:MM start time from caption/body text like 'doors at 7pm'
    or 'show starts at 8'. Returns the EARLIEST plausible 06:00–23:59 match
    (doors usually precede show). Used only to fill an absent startTime —
    never to overwrite a parsed one. Source-agnostic; no IG session needed.
    """
    text = f"{title or ''}  {description or ''}"
    best = None
    for m in _TIME_IN_TEXT_RE.finditer(text):
        try:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
        except (TypeError, ValueError):
            continue
        ampm = m.group(3).lower()
        if hour == 12:
            hour = 0
        if ampm == "p":
            hour += 12
        if not (6 <= hour <= 23) or not (0 <= minute <= 59):
            continue
        if best is None or (hour, minute) < best:
            best = (hour, minute)
    if best is None:
        return None
    return f"{best[0]:02d}:{best[1]:02d}"


def _likely_past_midnight(event: dict) -> bool:
    """Detect events expected to run past midnight. User explicitly
    excluded these — the site is for events worth attending to meet
    people, not late-night nightlife where everyone's already drunk.

    Signals (any one):
      - endTime is later (lexicographically) than '23:59'
      - endTime is earlier than startTime (overnight wrap)
      - startTime is 23:00 or later (most likely runs past midnight)
      - title or description mentions overnight markers ('1am', 'after
        midnight', 'open until 2am', etc.) — covers cases where
        the structured times aren't set
    """
    start = (event.get("startTime") or "").strip()
    end = (event.get("endTime") or "").strip()

    # Structured time signals
    if start and len(start) >= 4 and ":" in start:
        try:
            sh = int(start.split(":")[0])
            if sh >= 23:
                return True
        except Exception:
            pass
    if end and len(end) >= 4 and ":" in end:
        try:
            eh = int(end.split(":")[0])
            em = int(end.split(":")[1]) if ":" in end and len(end.split(":")) > 1 else 0
            # Many sources emit endTime="00:00" as a "not set" sentinel
            # rather than literal midnight. Skip the next-day-wrap check
            # in that case to avoid over-pruning.
            is_zero_sentinel = (eh == 0 and em == 0)
            if not is_zero_sentinel:
                # End-time wrap: end < start = overnight
                if start and ":" in start:
                    sh = int(start.split(":")[0])
                    if eh < sh:
                        return True
                # Explicit late end: 01:00-04:59 is past midnight.
                # NOT 00:00 because it's typically a sentinel.
                if 1 <= eh <= 4:
                    return True
        except Exception:
            pass

    # Text signals — limit to title + FIRST 200 CHARS of description so
    # we don't false-match phrases buried deep in long descriptions
    # (e.g., "open from 11pm to 1am" mentioned as venue trivia).
    text = (event.get("title", "") + " " + (event.get("description", "") or "")[:200]).lower()
    overnight_patterns = [
        r"\b(?:1|2|3|4|5)\s*am\b",            # "1am", "2 am" etc.
        r"\bpast midnight\b", r"\bafter midnight\b",
        r"\btill\s*(?:1|2|3|4|5)\s*am\b",
        r"\buntil\s*(?:1|2|3|4|5)\s*am\b",
        r"\btil\s*(?:1|2|3|4|5)\s*am\b",
        r"\bopen\s*(?:until|till|til)\s*(?:1|2|3|4|5)\s*am\b",
        r"\bclosing\s*at\s*(?:1|2|3|4|5)\s*am\b",
        r"\b(?:doors?|show)\s*(?:at|until)\s*1[12]\s*pm",  # late doors
        # Nightclub culture markers — these events typically run 4-5 AM
        r"\bnightclub\b", r"\bnight\s*club\b",
        r"\bbottle\s*service\b", r"\bvip\s*table\b", r"\bvip\s*booth\b",
        r"\btable\s*service\b", r"\bbottle\s*package\b",
        r"\bafter\s*hours?\b", r"\bafterhours?\b",
        # Late-night DJ sets in club venues
        r"\b(?:edm|techno|house)\s*(?:rave|warehouse|club)\b",
        r"\bwarehouse\s*(?:party|set|rave)\b",
    ]
    for p in overnight_patterns:
        if re.search(p, text):
            return True
    return False


# Per-source fallback images for venues that publish events without flyer
# photos. Keeps the card UI consistent (no blank rectangles) without
# dropping legit literary / nature / civic content.
_SOURCE_DEFAULT_IMAGES = {
    "greenwoodcemetery": "https://www.green-wood.com/wp-content/uploads/2021/02/cemetery-aerial.jpg",
    "nyc_parks": "https://www.nycgovparks.org/pagefiles/180/Bryant-Park.jpg",
    "substack": "https://substack.com/img/substack_logo_dark.svg",
    "lizsbookbar": "https://images.squarespace-cdn.com/content/v1/65a2eba6c0fe5b4af96a3cc7/d2eb6b48-7c5a-4ed0-b3a8-37e7c69e6b95/IMG_5283.jpeg",
}


# Glued-handle title leak (iter 81 audit): IG-Stories OCR sometimes glues
# an @handle into the title as a single 14+ char token, single-capital +
# all-lowercase ("Glibertybagelsny grand opening", "Ggretavanfleet gave
# fans quite"). Iter 1 P5's camelCase regex didn't catch these — they
# have no internal uppercase. This post-filter purges them on every
# normalize() pass so already-stored leaks self-clean without a re-scrape.
#
# Length floor 14 + all-lowercase-after-first keeps the FP rate near zero
# — the deployed feed has 0 legitimate words of this shape; the only 2
# hits are real OCR junk.
_GLUED_HANDLE_TITLE_RE = re.compile(r"^[A-Z][a-z]{12,}$")


def _is_glued_handle_title(title: str) -> bool:
    words = (title or "").split()
    if len(words) < 2:
        return False
    first = words[0]
    if len(first) < 14:
        return False
    return bool(_GLUED_HANDLE_TITLE_RE.match(first))


def _apply_default_images(events: list[dict]) -> None:
    for ev in events:
        if (ev.get("imageUrl") or "").strip():
            continue
        fallback = _SOURCE_DEFAULT_IMAGES.get(ev.get("source", ""))
        if fallback:
            ev["imageUrl"] = fallback


# URL patterns that carry a curator/host handle. These cross-source
# handles often map to accounts the user follows on IG. Extracting them
# lets us extend the follow-graph signal (userFollowing) to non-IG events.
import re as _re
_LUMA_HANDLE_RE = _re.compile(r"^https?://(?:lu\.ma|luma\.com)/([A-Za-z0-9_.\-]+)/?$")
_PARTIFUL_HANDLE_RE = _re.compile(r"^https?://(?:www\.)?partiful\.com/@([A-Za-z0-9_.\-]+)")


# Hosts that are generic aggregators / event platforms — their second-level
# domain is NOT a curator handle. Don't extract a "handle" from these.
_AGGREGATOR_HOSTS = {
    "eventbrite", "meetup", "lu", "luma", "songkick", "allevents",
    "instagram", "facebook", "twitter", "linktr", "partiful", "ticketmaster",
    "dice", "ra", "shotgun", "posh", "tixr", "substack", "youtube", "spotify",
    "google", "apple", "linkedin", "tiktok",
}


def _extract_handle_from_url(url: str) -> str | None:
    if not url:
        return None
    for rx in (_LUMA_HANDLE_RE, _PARTIFUL_HANDLE_RE):
        m = rx.match(url)
        if m:
            handle = m.group(1)
            # Bare /nyc / event-id patterns aren't handles.
            if handle.lower() in {"nyc", "event", "events", "home"}:
                return None
            return handle
    # Host-based fallback: a venue/curator that runs their own site
    # (bookclubbar.com, theskint.com, etc.) — the second-level domain
    # often is their canonical handle. Skip aggregators.
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower().replace("www.", "")
        if not host or "." not in host:
            return None
        sld = host.split(".")[0]
        if sld in _AGGREGATOR_HOSTS or len(sld) < 3:
            return None
        return sld
    except Exception:
        return None


def _load_user_following_set() -> set[str]:
    """Lower-cased usernames the user follows on IG (from discover.py).
    Used by _enrich_provenance_from_url to set userFollowing on non-IG
    events whose curator handle matches one of these."""
    import json as _json
    import os as _os
    path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "data",
        "discovered_accounts.json",
    )
    if not _os.path.isfile(path):
        return set()
    try:
        with open(path) as f:
            data = _json.load(f)
        return {
            a["username"].lower()
            for a in data.get("accounts", [])
            if isinstance(a, dict) and a.get("discovered_via") == "user_following"
            and a.get("username")
        }
    except Exception:
        return set()


_HANDLE_LOCATION_SUFFIX_RE = _re.compile(r"-(?:manhattan|brooklyn|queens|bronx|bk|nyc|ny|williamsburg)$")


def _handle_candidates(handle: str) -> list[str]:
    """Variants of a curator handle to test against the user_following set.
    Catches `readingrhythms-manhattan` ↔ `reading_rhythms`, `bk-` prefixes,
    `_` ↔ `-` separator differences, and the alphanumeric-only collapse
    so `readingrhythms-manhattan` → `readingrhythms` ↔ `reading_rhythms`
    → `readingrhythms`."""
    h = handle.lower()
    stripped = _HANDLE_LOCATION_SUFFIX_RE.sub("", h)
    out = {
        h,
        stripped,
        h.replace("-", "_"),
        h.replace("_", "-"),
        stripped.replace("-", "_"),
        stripped.replace("_", "-"),
        # Alphanumeric-only fold — bridges `_` / `-` / `.` differences
        # like `readingrhythms-manhattan` ↔ `reading_rhythms`.
        _re.sub(r"[^a-z0-9]", "", h),
        _re.sub(r"[^a-z0-9]", "", stripped),
    }
    return [v for v in out if v]


from scrapers.utils.user_excluded import load_excluded_account_set as _load_user_excluded_accounts  # noqa: E402


def _user_following_normalized() -> set[str]:
    """User following set (minus excluded handles) extended with
    alphanumeric-only normalized variants so handles like `reading_rhythms`
    match `readingrhythms`. Excluded handles (fb-106 personal accounts,
    user-rejected clubs) are dropped here so the URL/organizer/location
    enrichment paths won't tag events with userFollowing for them."""
    base = _load_user_following_set() - _load_user_excluded_accounts()
    out = set(base)
    for h in base:
        out.add(_re.sub(r"[^a-z0-9]", "", h))
    # Location-suffix-stripped fold: many curators run a lu.ma/Eventbrite
    # calendar at the bare host slug (lu.ma/philosophy) while the IG handle
    # carries an NYC suffix (philosophy.nyc). Strip a trailing nyc/ny/bk so
    # the bare slug matches the followed handle. (iter 2026-06-04, fb S1)
    for h in list(out):
        stripped = _re.sub(r"(nyc|ny|bk)$", "", h)
        if stripped and stripped != h and len(stripped) >= 4:
            out.add(stripped)
    return out


def _load_account_quality_map() -> dict:
    """Load scrapers/data/account_quality.json keyed by handle (alphanumeric
    fold variant AND original handle so callers can match either form).

    iter 208: discovered via real-data trace that 'reading_rhythms' (the
    quality file's key) was unreachable via the alphanumeric-fold lookup
    path. Indexing by both forms means a folded match-candidate like
    'readingrhythms' resolves to the underscore-keyed record.
    """
    import json as _json, os as _os
    path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "data",
        "account_quality.json",
    )
    if not _os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            raw = _json.load(f)
    except Exception:
        return {}
    out = {}
    for handle, info in raw.items():
        if not isinstance(info, dict):
            continue
        h_lower = handle.lower()
        out[h_lower] = info
        fold = _re.sub(r"[^a-z0-9]", "", h_lower)
        if fold != h_lower:
            out.setdefault(fold, info)
    return out


def _apply_quality_for(ev: dict, handle: str, quality: dict) -> None:
    """Stamp accountEventYield + accountPostsSeen from the IG account_quality
    record onto an enriched non-IG event so it gets the same yield-based
    ranking lift as native-IG events from the same account.

    Defensive: skip if accountEventYield is already set (e.g. by a future
    scraper that does its own per-account quality tracking). Don't
    silently overwrite scraper-provided signals.
    """
    if not quality or not handle:
        return
    if ev.get("accountEventYield") is not None:
        return
    h = handle.lower()
    info = quality.get(h) or quality.get(_re.sub(r"[^a-z0-9]", "", h))
    if not info:
        return
    posts = info.get("posts_scraped", 0) or 0
    evs = info.get("events_emitted", 0) or 0
    if posts >= 5:
        ev["accountEventYield"] = round(evs / posts, 3)
        ev["accountPostsSeen"] = posts


def _enrich_provenance_from_url(events: list[dict]) -> None:
    """Set `account` + `userFollowing` on non-IG events whose sourceUrl
    encodes a curator handle that the user follows on IG. The audit at
    iter 73 found that Lu.ma URLs like `lu.ma/litclub.nyc` and
    `lu.ma/nycbackgammonclub` are signal-account handles — currently
    those events are invisible to the follow-graph metric.

    Iter 77 extends this to the JSON-LD `organizer.name` field — many
    Eventbrite events carry an organizer name like "Vital Run Club"
    that, normalized to `vitalrunclub`, matches an IG signal_account.
    """
    following = _user_following_normalized()
    if not following:
        return
    # iter 205: load account_quality so enriched non-IG events inherit
    # the IG-side accountEventYield. A Lu.ma event from @bookclubbar
    # (yield 0.83) should get the same yield boost in ranking as an IG
    # event from that account would.
    quality = _load_account_quality_map()
    matched = 0
    organizer_matched = 0
    for ev in events:
        if ev.get("account") or ev.get("instagramAccount"):
            continue  # already has provenance
        # 1) URL handle match (Lu.ma, Partiful, venue-domain hosts)
        handle = _extract_handle_from_url(ev.get("sourceUrl") or "")
        if handle:
            for cand in _handle_candidates(handle):
                if cand in following:
                    ev["account"] = handle  # preserve original handle
                    ev["userFollowing"] = True
                    _apply_quality_for(ev, cand, quality)
                    matched += 1
                    break
            if ev.get("userFollowing"):
                continue
        # 1b) Meetup group slug lives in the URL path, not the host SLD
        #     (meetup.com/<slug>/events/...). _extract_handle_from_url reads
        #     only the host, so Meetup groups never matched. Fold the path
        #     slug and check membership. (iter 2026-06-04: silentbookclub.nyc)
        mu = _re.search(r"meetup\.com/([^/?#]+)", ev.get("sourceUrl") or "", _re.I)
        if mu:
            slug = mu.group(1)
            fold = _re.sub(r"[^a-z0-9]", "", slug.lower())
            if fold and len(fold) >= 5 and fold in following:
                ev["account"] = slug
                ev["userFollowing"] = True
                _apply_quality_for(ev, fold, quality)
                matched += 1
                continue
        # 2) Organizer-name match (JSON-LD organizer.name → alphanumeric fold)
        # 3) Location-name match (iter 109): for Eventbrite venue-search events
        #    (iter 107-108), the organizer is a per-event promoter ("DJ Opapi")
        #    while the venue is in location.name ("House of Yes"). The venue
        #    is the user-follow target — `houseofyes` → `houseofyesnyc` via
        #    suffix-strip → matches `houseofyesnyc` in user_following.
        for candidate_field in ("organizer", "_location_name"):
            if candidate_field == "_location_name":
                loc = ev.get("location") or {}
                candidate = (loc.get("name") or "").strip() if isinstance(loc, dict) else ""
            else:
                candidate = (ev.get(candidate_field) or "").strip()
            if not candidate or len(candidate) < 3:
                continue
            cand_norm = _re.sub(r"[^a-z0-9]", "", candidate.lower())
            if not cand_norm or len(cand_norm) < 5:
                continue
            cand_variants = {cand_norm}
            # Suffix-strip
            for suffix in ("nyc", "ny", "brooklyn", "manhattan", "bk"):
                if cand_norm.endswith(suffix) and len(cand_norm) - len(suffix) >= 5:
                    cand_variants.add(cand_norm[:-len(suffix)])
            # Suffix-add (venues often drop "nyc"/"bk" but the IG handle has
            # it). "houseofyes" → also try "houseofyesnyc"; "franklinpark"
            # → "franklinparkbk".
            for suffix in ("nyc", "ny", "bk"):
                if not cand_norm.endswith(suffix):
                    cand_variants.add(cand_norm + suffix)
            matched_handle = next((c for c in cand_variants if c in following), None)
            if matched_handle:
                ev["account"] = matched_handle
                ev["userFollowing"] = True
                _apply_quality_for(ev, matched_handle, quality)
                organizer_matched += 1
                break  # don't double-count if both organizer + location match
    if matched:
        print(f"[normalize] Enriched {matched} non-IG events with userFollowing via curator-handle URL match")
    if organizer_matched:
        print(f"[normalize] Enriched {organizer_matched} non-IG events with userFollowing via organizer/venue-name match")


_IMAGE_REQUIRED_SOURCES = frozenset({
    # Partiful events without images are usually private-event placeholders
    # with bare titles — drop them. Generic JSON-LD without an image is
    # often a bare listing-page entry. Substack newsletters legitimately
    # publish text-only event roundups (theskint, onefinedaynyc) — losing
    # them to an image filter silences high-signal content. Keep substack
    # OUT of the strict set and instead trust the source-level quality
    # score + caption-fragment filters to weed out news commentary.
    "partiful", "generic",
})


_DESCRIPTION_REQUIRED_SOURCES = frozenset({
    # Non-IG sources where an event with empty description is a bare
    # listing — no context for the user, can't be categorized properly,
    # and signals the upstream page lacked real content. IG captions
    # are the description so IG isn't in this set.
    "luma", "eventbrite", "partiful", "allevents", "songkick",
})


def _is_curated_host(event: dict) -> bool:
    """True if the event's sourceUrl matches a host in
    user_curated_sources.json, OR title/desc matches a title_hint.
    Curated hosts/hints are user-explicit high-signal sources — they
    should bypass aggregator-style filters (description-required,
    image-required) that target generic-listing noise.

    Title-hint matching extends bypass to events scraped from organizer
    pages that lose the original host context after the slug-based event
    URL is the only URL kept (e.g. Lululemon's eventbrite organizer
    'No Regrets Runners' event URL is /e/no-regrets-runners-tickets-X,
    not /o/14861961557, but the title hint 'no regrets runners' fires).
    """
    try:
        from .ranking import _load_user_curated_sources
        cfg = _load_user_curated_sources()
        # Check both sourceUrl AND organizerUrl (events scraped from
        # organizer pages keep the org URL in organizerUrl while sourceUrl
        # points to the specific event slug).
        urls = (
            (event.get("sourceUrl") or "").lower(),
            (event.get("organizerUrl") or "").lower(),
        )
        for url in urls:
            if url and any(h in url for h in cfg.get("hosts", {})):
                return True
        title = (event.get("title") or "").lower()
        desc = (event.get("description") or "")[:300].lower()
        text = title + " " + desc
        if any(h in text for h in cfg.get("title_hints", {})):
            return True
        return False
    except Exception:
        return False


def _is_shell_event(event: dict) -> bool:
    """An event with no description, no image, AND no venue is a placeholder
    that adds no information. Drop these so the feed isn't padded with empty
    tiles.

    Also drop events from listing-aggregator sources that have no image —
    they render as blank cards and ruin the visual feed quality.

    Exception: user-saved events and events from user-curated hosts
    (litclub.nyc, Lululemon, etc.) are always kept regardless — the user
    has explicitly signaled these are high-priority.
    """
    if event.get("userSaved") or event.get("userTagged"):
        return False
    # User-curated hosts bypass the aggregator-style filters. A litclub
    # luma event with no description still belongs in the feed because
    # the host itself is a positive signal.
    if _is_curated_host(event):
        return False
    desc = (event.get("description") or "").strip()
    img = (event.get("imageUrl") or "").strip()
    loc = (event.get("location") or {}).get("name", "").strip()
    addr = (event.get("location") or {}).get("address", "").strip()
    # Stricter: image required for listing-aggregator sources.
    if not img and event.get("source") in _IMAGE_REQUIRED_SOURCES:
        return True
    # Empty descriptions on listing aggregators are bare placeholder rows.
    # IG captions are the description, so IG events aren't checked.
    if (len(desc) < 15
            and event.get("source") in _DESCRIPTION_REQUIRED_SOURCES):
        return True
    if not desc and not img and not loc and not addr:
        return True
    # Also drop events with very short descriptions, no image, AND no location.
    if len(desc) < 15 and not img and not loc:
        return True
    return False


def filter_far_future_misparsed(events: list[dict]) -> list[dict]:
    """Drop events dated >180 days out unless the description explicitly
    mentions a year. Most >6-month-out IG events are misparsed (caption
    said "April 12" with no year, parser defaulted to next year when
    current year had passed).
    """
    today = date.today()
    out = []
    for ev in events:
        d = ev.get("date", "")
        try:
            ev_date = date.fromisoformat(d)
        except Exception:
            out.append(ev)
            continue
        days_out = (ev_date - today).days
        if days_out <= _FAR_FUTURE_DAYS:
            out.append(ev)
            continue
        # Trusted venue calendars publish authoritative dates months ahead —
        # the misparsed-relative-date heuristic doesn't apply.
        if ev.get("source") in _TRUSTED_FAR_FUTURE_SOURCES:
            out.append(ev)
            continue
        # IG date parsing is unreliable past ~180d — the year exemption
        # below is too loose for it. Drop IG events that far out unconditionally.
        if ev.get("source") == "instagram":
            continue
        # Far-future: keep only if the event's actual year is mentioned in
        # title or description (not just any 4-digit year — the description
        # can mention an unrelated year and let a misparsed date through).
        text = (ev.get("title", "") + " " + ev.get("description", ""))[:600]
        import re as _re
        if _re.search(rf"\b{ev_date.year}\b", text):
            out.append(ev)
    return out


def sort_by_date(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e.get("date", ""), e.get("startTime", "") or ""))


_TITLE_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _is_phantom_recurring(event: dict) -> bool:
    """Detect events where title mentions a specific date that doesn't match
    the event's date — symptom of a buggy past recurring expansion.
    """
    if not event.get("recurring"):
        return False
    title = event.get("title", "")
    date_str = event.get("date", "")
    if not date_str:
        return False
    m = _TITLE_DATE_RE.search(title)
    if not m:
        return False
    title_month = _MONTHS.get(m.group(1)[:3].lower())
    title_day = int(m.group(2))
    try:
        from datetime import date as _date
        ev_date = _date.fromisoformat(date_str)
        # If title specifies a date and the event date doesn't match, it's phantom
        if (ev_date.month, ev_date.day) != (title_month, title_day):
            return True
    except Exception:
        pass
    return False


def _load_previous_events_index(path: str) -> dict:
    """Load previous events.json keyed by event id, for firstSeenAt preservation."""
    import json, os
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            d = json.load(f)
        return {e["id"]: e for e in d.get("events", []) if "id" in e}
    except Exception:
        return {}


def _learn_excluded_from_hidden(events: list[dict]) -> None:
    """Promote accounts/hosts of user-hidden events into
    user_excluded_sources.json. Symmetric to _learn_curated_from_saved.

    Triggers when an event carries userHidden=true. After 3 hides of the
    same account, the account is auto-added with source='engagement_hidden'.
    The user can still manually edit the JSON to override.
    """
    import os as _os, json as _json
    from datetime import datetime as _dt

    hidden = [e for e in events if e.get("userHidden")]
    if not hidden:
        return
    path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "data", "user_excluded_sources.json",
    )
    if _os.path.isfile(path):
        try:
            with open(path) as f:
                cfg = _json.load(f)
        except Exception:
            cfg = {"accounts": {}, "hosts": {}, "title_hints": {}}
    else:
        cfg = {"accounts": {}, "hosts": {}, "title_hints": {}}
    cfg.setdefault("accounts", {})

    changed = False
    for ev in hidden:
        acct = (ev.get("instagramAccount") or "").lower()
        if not acct:
            continue
        entry = cfg["accounts"].setdefault(acct, {
            "reason": "engagement_hidden",
            "added_at": _dt.utcnow().date().isoformat(),
            "hide_count": 0,
        })
        entry["hide_count"] = (entry.get("hide_count") or 0) + 1
        changed = True

    if changed:
        cfg["lastUpdated"] = _dt.utcnow().isoformat() + "Z"
        try:
            with open(path, "w") as f:
                _json.dump(cfg, f, indent=2)
        except Exception as exc:
            print(f"[normalize] Failed to persist user_excluded_sources: {exc}")


def _learn_curated_from_saved(events: list[dict]) -> None:
    """Promote hosts of user-saved events into scrapers/data/user_curated_sources.json.

    Every time an event is `userSaved`, the URL host (e.g. 'litclub.nyc',
    'nypl.org') and any literary-series title token gets a small score bump.
    The auto-learning loop: user clicks/saves → host gets a higher curated
    score → future events from the same host rank higher → user sees more
    of what they like → more saves. No code changes needed when a new
    host enters the user's interest set.
    """
    import os as _os, json as _json
    from datetime import datetime as _dt
    from urllib.parse import urlparse as _urlparse

    saved = [e for e in events if e.get("userSaved")]
    if not saved:
        return
    path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "data", "user_curated_sources.json",
    )
    if _os.path.isfile(path):
        try:
            with open(path) as f:
                cfg = _json.load(f)
        except Exception:
            cfg = {"hosts": {}, "title_hints": {}}
    else:
        cfg = {"hosts": {}, "title_hints": {}}
    cfg.setdefault("hosts", {})
    cfg.setdefault("title_hints", {})

    changed = False
    for ev in saved:
        url = ev.get("sourceUrl") or ""
        try:
            host = _urlparse(url).hostname or ""
        except Exception:
            host = ""
        host = host.lower().replace("www.", "")
        if not host:
            continue
        entry = cfg["hosts"].setdefault(host, {
            "score": 0.0,
            "added_at": _dt.utcnow().date().isoformat(),
            "source": "engagement_saved",
            "save_count": 0,
        })
        entry["save_count"] = (entry.get("save_count") or 0) + 1
        # Score saturates at 1.0; each save adds 0.2 (capped). After 5
        # saves from a host it's "fully curated".
        entry["score"] = min(1.0, 0.2 * entry["save_count"])
        changed = True

    if changed:
        cfg["lastUpdated"] = _dt.utcnow().isoformat() + "Z"
        try:
            with open(path, "w") as f:
                _json.dump(cfg, f, indent=2)
        except Exception as exc:
            print(f"[normalize] Failed to persist user_curated_sources: {exc}")


def process(events: list[dict], previous_index: dict | None = None) -> list[dict]:
    from .ranking import rank_events
    from .quality import is_blocked
    from .utils.event_parser import detect_recurring_weekday, expand_recurring_event

    events = [ev for ev in events if ev.get("title") and ev.get("date")]
    events = filter_future(events)

    # Fill missing startTime from body text ("doors at 7pm", "show starts at
    # 8") — only when absent, never overwriting a parsed time. Runs before the
    # late-night filter so an inferred time can still be range-checked.
    time_filled = 0
    for ev in events:
        if not (ev.get("startTime") or "").strip():
            inferred = _infer_time_from_text(ev.get("title", ""), ev.get("description", ""))
            if inferred:
                ev["startTime"] = inferred
                time_filled += 1
    if time_filled:
        print(f"[normalize] Inferred startTime from text for {time_filled} events")

    # Stamp per-source default images BEFORE _is_shell_event so that
    # venues like greenwoodcemetery / nyc_parks survive the image filter.
    _apply_default_images(events)

    # Drop suspiciously far-future events without an explicit year mention.
    before = len(events)
    events = filter_far_future_misparsed(events)
    far_future_dropped = before - len(events)
    if far_future_dropped:
        print(f"[normalize] Dropped {far_future_dropped} far-future misparsed events (>{_FAR_FUTURE_DAYS}d, no year mention)")

    # Hard-filter blocked events (kids/utility/services/non-NYC/captions)
    before = len(events)
    events = [ev for ev in events if not is_blocked(ev)]
    blocked = before - len(events)
    if blocked:
        print(f"[normalize] Blocked {blocked} low-quality events")

    # Purge already-stored events whose title is a glued-handle OCR leak
    # ("Ggretavanfleet gave fans quite", "Glibertybagelsny grand opening").
    # Iter 1 P5 catches these at IG extraction; this pass catches old
    # rows already in the feed before the fix landed.
    before = len(events)
    events = [ev for ev in events if not _is_glued_handle_title(ev.get("title", ""))]
    glued = before - len(events)
    if glued:
        print(f"[normalize] Purged {glued} glued-handle title leaks")

    # User-excluded sources (data-driven, no hardcoded list) — accounts /
    # hosts / title-hints the user has explicitly said no to via
    # scrapers/data/user_excluded_sources.json. Auto-grows from hides.
    try:
        from .ranking import is_user_excluded
        before = len(events)
        events = [ev for ev in events if not is_user_excluded(ev)]
        excluded = before - len(events)
        if excluded:
            print(f"[normalize] Dropped {excluded} user-excluded events")
    except Exception as exc:
        print(f"[normalize] user-exclusion filter failed: {exc}")

    # Drop "shell" events — no description AND no image AND no location.
    # These are typically placeholder rows from listing scrapes that didn't
    # extract any useful detail. They waste rank slots without informing.
    before = len(events)
    events = [ev for ev in events if not _is_shell_event(ev)]
    shells = before - len(events)
    if shells:
        print(f"[normalize] Dropped {shells} shell events (no description/image/location)")

    # Drop events likely to run past midnight — user explicitly excluded
    # these. Not appropriate for the meet-people-at-events use case.
    before = len(events)
    events = [ev for ev in events if not _likely_past_midnight(ev)]
    midnight = before - len(events)
    if midnight:
        print(f"[normalize] Dropped {midnight} late-night events (past midnight)")

    # Drop phantom recurring expansions: events where the title contains a
    # specific date that doesn't match the event date (likely from a past
    # buggy expansion). Title-date is the source of truth.
    before = len(events)
    events = [ev for ev in events if not _is_phantom_recurring(ev)]
    phantom = before - len(events)
    if phantom:
        print(f"[normalize] Dropped {phantom} phantom recurring events (title-date mismatch)")

    # Expand recurring events ("every Saturday at Smorgasburg" → 3 weeks of
    # dates). Skip events already marked recurring=True (already an expanded
    # clone) — otherwise re-processing the events.json snowballs each clone
    # into another 3 copies and the feed fills with duplicate titles.
    expanded: list[dict] = []
    recurring_count = 0
    for ev in events:
        if ev.get("recurring"):
            expanded.append(ev)
            continue
        text = (ev.get("title", "") + " " + ev.get("description", "")).lower()
        weekday = detect_recurring_weekday(text)
        if weekday is not None:
            occurrences = expand_recurring_event(ev, weekday, weeks_ahead=3)
            expanded.extend(occurrences)
            recurring_count += 1
        else:
            expanded.append(ev)
    if recurring_count:
        print(f"[normalize] Expanded {recurring_count} recurring events into {len(expanded) - len(events) + recurring_count} total occurrences")
    events = expanded

    events = deduplicate(events)

    # Collapse repeated (title, sourceUrl) groups without explicit recurring
    # markers — these are stale bad-expansion artifacts from prior runs.
    events = collapse_title_spam(events)

    # Prefix bare comedian-lineup titles. Comedy-club scrapers ingest the
    # raw lineup ("Caitlin Peluffo, Judah Friedlander, Dante Nero, ...")
    # as the title, leaving the user with no idea what kind of show it
    # is. Detect titles that are 3+ comma-separated First-Last names
    # with no event-format keyword and prepend "Stand-Up Comedy:".
    events = _prefix_comedian_lineups(events)

    # Same pattern for meetup book clubs that ship a list of quoted
    # book titles as the event title.
    events = _prefix_book_club_lists(events)

    # _strip_outdoors_indoor_arena moved BELOW re-categorize (iter 166):
    # iter 132's re-derive pass overwrites the cats list, undoing the
    # strip. Running it after re-categorize keeps the location.name-based
    # check honest (the categorizer's own check only scans title+desc).

    # Re-derive missing neighborhoods from venue name / re-run address
    # inference. Bookmanager-powered scrapers (lizsbookbar, bookclubbar)
    # don't carry addresses, and the keyword list grows over time, so
    # cached events benefit from a refresh pass.
    _backfill_neighborhood_from_venue(events)

    # Re-run title cleanup so the iterated clean_title rules apply to
    # cached events too — otherwise caption-fragment fixes only help new
    # scrapes, and titles like "GETTING UNSTUCK: On Sunday, ..." linger
    # for weeks in the feed.
    from .utils.event_parser import clean_title as _clean_title
    for ev in events:
        t = ev.get("title") or ""
        cleaned = _clean_title(t)
        if cleaned and cleaned != t:
            ev["title"] = cleaned

    # Re-categorize moved DOWN past _enrich_provenance_from_url so the
    # IG-handle topic-hint fallback can use the enriched `account` field
    # (set when a non-IG event's URL/organizer/location matches a follow).

    # Preserve firstSeenAt across runs. Three layers, most specific first:
    #   1. If the event already carries firstSeenAt (e.g. an ad-hoc re-run
    #      of normalize on an already-processed feed), keep it as-is —
    #      otherwise re-running this function silently clobbers freshness
    #      data and breaks the "Just Added" hero.
    #   2. If `previous_index` (from prior events.json) has this id, carry
    #      its firstSeenAt forward — this is the normal full-pipeline path.
    #   3. Otherwise stamp `now`.
    # UTC + tz-aware so JS / Python both see an unambiguous instant.
    if previous_index is None:
        previous_index = {}
    now_iso = datetime.now(timezone.utc).isoformat()
    velocity_count = 0
    for ev in events:
        if ev.get("firstSeenAt"):
            pass  # layer 1: trust event's own stamp
        else:
            prev = previous_index.get(ev.get("id"))
            if prev and prev.get("firstSeenAt"):
                ev["firstSeenAt"] = prev["firstSeenAt"]
            else:
                ev["firstSeenAt"] = now_iso
        prev = previous_index.get(ev.get("id"))

        # Engagement velocity: when an event's likes/comments grew since
        # the previous scrape, that's a "trending" signal. Stash the delta
        # for the ranking layer to consume.
        if prev:
            try:
                prev_likes = int(prev.get("likes", 0) or 0)
                prev_comments = int(prev.get("comments", 0) or 0)
                cur_likes = int(ev.get("likes", 0) or 0)
                cur_comments = int(ev.get("comments", 0) or 0)
                # Combined engagement delta (comments weighted 5x, same as
                # _popularity_score logic).
                delta = (cur_likes - prev_likes) + 5 * (cur_comments - prev_comments)
                if delta > 0:
                    ev["engagementDelta"] = delta
                    velocity_count += 1
            except Exception:
                pass
    if velocity_count:
        print(f"[normalize] {velocity_count} events have positive engagement velocity since last scrape")

    # Promote hosts of saved events into user_curated_sources.json so the
    # next run ranks them higher. Auto-learning, no code changes needed.
    _learn_curated_from_saved(events)
    # Symmetric on the negative side: hidden events grow the excluded list.
    _learn_excluded_from_hidden(events)

    # Rebuild the auto-derived interest profile so the ranker reflects the
    # latest IG follow graph + affinity engagement. Cheap (reads ~5 JSON
    # files, writes 1) but invalidates the in-process cache so ranking
    # uses fresh signals.
    try:
        from .utils.interest_profile import build_profile
        import scrapers.utils.interest_profile as _ip
        build_profile()
        _ip._CACHE = None
    except Exception as exc:
        print(f"[normalize] interest_profile rebuild failed: {exc}")

    _enrich_provenance_from_url(events)

    # Re-derive categories on every run. Stale categories from older
    # categorizer versions (e.g. iter 82's bare "premiere" → movies bug,
    # or cross-promo descriptions falsely matching "run club" → fitness on
    # a book club event) linger in cached events otherwise. The current
    # categorizer is the source of truth. Runs AFTER provenance enrichment
    # so the IG-handle topic-hint fallback can use the enriched `account`.
    from .utils.event_parser import infer_categories as _infer_categories
    for ev in events:
        # Prefer `account` (set by iter 1 P2 mirror, or by enrichment) but
        # fall back to `instagramAccount` for events emitted by older
        # scraper versions — the field used by the IG-handle topic path.
        ig_acct = ev.get("account") or ev.get("instagramAccount") or ""
        new_cats = _infer_categories(
            ev.get("title") or "",
            ev.get("description") or "",
            ig_account=ig_acct,
            source=ev.get("source") or "",
        )
        if new_cats:
            ev["categories"] = new_cats

    # Strip the "outdoors" tag from events whose only nature signal is an
    # indoor-arena name (Madison Square Garden, Barclays Center) — the
    # categorizer's own outdoor check only scans title+desc, so an event
    # at MSG that title-mentions 'garden' but doesn't mention 'indoor'
    # still gets tagged outdoors. This pass scans location.name too.
    _strip_outdoors_indoor_arena(events)

    events = rank_events(events)

    # Drop low-score events — every event must justify its position.
    # Quality bar — when combined with all the per-source filters
    # (shell-event filter, recap rejection, fragment-title filter,
    # recurring-spam collapse, far-future filter, late-night filter,
    # hard-blocks for nightclubs/professionals/language-mixers), this
    # is the safety net for what slipped through with weak signal.
    #
    # Per-source floors: Instagram from CURATED or AFFINITY accounts gets
    # a lower bar (0.20) because the user has explicitly designated IG
    # as the primary discovery channel — the curator's pick is itself
    # quality signal. Random hashtag-discovered or unknown-account IG
    # events still meet the default 0.30 floor.
    # User explicitly: "it's okay to see less events than to see events
    # which are not useful". Iter 7 raises floors again now that the
    # interest_profile_boost (+0.15 for signal accounts) compensates for
    # events the user genuinely cares about. Marginal-quality long tail
    # in 0.45-0.55 was 133 events; trimming that.
    DEFAULT_MIN_SCORE = 0.55
    IG_CURATED_MIN_SCORE = 0.40
    from .config import IG_ACCOUNTS
    _curated_ig = {a.lower() for a in IG_ACCOUNTS}

    def _floor_for(ev: dict) -> float:
        if ev.get("source") != "instagram":
            return DEFAULT_MIN_SCORE
        # Curator-signal IG events: from accounts in the curated seed list
        # OR from accounts the user explicitly follows / has saved-from /
        # was tagged in / has built up affinity with.
        acct = (ev.get("instagramAccount") or "").lower()
        if acct in _curated_ig:
            return IG_CURATED_MIN_SCORE
        if (ev.get("userSaved") or ev.get("userTagged")
                or ev.get("userAffinity") or ev.get("userFollowing")):
            return IG_CURATED_MIN_SCORE
        return DEFAULT_MIN_SCORE

    before = len(events)
    kept = []
    ig_kept_curated = 0
    for ev in events:
        floor = _floor_for(ev)
        if ev.get("score", 0) >= floor:
            kept.append(ev)
            if ev.get("source") == "instagram" and floor < DEFAULT_MIN_SCORE:
                ig_kept_curated += 1
    events = kept
    dropped = before - len(events)
    if dropped:
        msg = f"[normalize] Dropped {dropped} low-score events (below {DEFAULT_MIN_SCORE})"
        if ig_kept_curated:
            msg += f" (kept {ig_kept_curated} IG curated events at lower {IG_CURATED_MIN_SCORE} floor)"
        print(msg)

    # Per-source volume caps. Aggregator sources (allevents, songkick,
    # comedy clubs) ship hundreds of events that crowd out IG and other
    # user-relevant content. Keep top-N by score per capped source so
    # the For You feed has real diversity.
    from .config import SOURCE_VOLUME_CAPS
    if SOURCE_VOLUME_CAPS:
        by_source: dict[str, list] = {}
        for ev in events:
            by_source.setdefault(ev.get("source", ""), []).append(ev)
        capped: list[dict] = []
        cap_drops = 0
        for src, src_events in by_source.items():
            cap = SOURCE_VOLUME_CAPS.get(src)
            if cap is None or len(src_events) <= cap:
                capped.extend(src_events)
                continue
            src_events.sort(key=lambda e: e.get("score", 0), reverse=True)
            capped.extend(src_events[:cap])
            cap_drops += len(src_events) - cap
        if cap_drops:
            print(f"[normalize] Volume-capped {cap_drops} events from heavy aggregator sources")
        events = capped

    events = sort_by_date(events)
    return events
