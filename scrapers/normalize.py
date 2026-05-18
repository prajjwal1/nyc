import hashlib
import os
import re
from datetime import date, datetime


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
        # Build a publisher key per source
        src = ev.get("source", "")
        if src == "instagram":
            key = "ig:" + (ev.get("instagramAccount") or "").lower()
        else:
            try:
                # For URL-based publishers, use host + first path segment
                # so distinct event series under one venue don't collapse.
                p = urlparse(ev.get("sourceUrl") or "")
                # Drop trailing path component (event-specific slug). Take
                # path up to the second-to-last segment.
                parts = [x for x in (p.path or "").split("/") if x][:-1]
                key = f"{src}:{p.netloc}:{('/'.join(parts))[:80]}"
            except Exception:
                key = ""
        if not key or key.endswith(":") or key == src + ":" :
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
                if not a or not b or len(a) < 3:
                    continue
                jacc = len(a & b) / len(a | b)
                if jacc >= 0.75 or len(a & b) >= 4:
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


def _normalize_venue_name(loc: str) -> str:
    """Canonicalize a venue name so 'Book Club Bar Bushwick' and 'Book
    Club Bar' map to the same key. Steps:
      1. Drop everything after the first comma (street address)
      2. Strip well-known NYC neighborhood/borough suffixes
      3. Lowercase + collapse whitespace
    Lets cross-source dedup catch events at the same venue when one
    source includes the neighborhood and another doesn't.
    """
    if not loc:
        return ""
    s = loc.split(",")[0].strip()
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
                if jacc >= 0.55 and len(a & b) >= 2:
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

    # Prefer specific time over none
    if not merged.get("startTime") and b.get("startTime"):
        merged["startTime"] = b["startTime"]
    if not merged.get("endTime") and b.get("endTime"):
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
    "museums",
    "music_venues",
})


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


def _is_shell_event(event: dict) -> bool:
    """An event with no description, no image, AND no venue is a placeholder
    that adds no information. Drop these so the feed isn't padded with empty
    tiles.

    Also drop events from listing-aggregator sources that have no image —
    they render as blank cards and ruin the visual feed quality.

    Exception: user-saved events are always kept regardless — the user
    explicitly bookmarked them.
    """
    if event.get("userSaved") or event.get("userTagged"):
        return False
    desc = (event.get("description") or "").strip()
    img = (event.get("imageUrl") or "").strip()
    loc = (event.get("location") or {}).get("name", "").strip()
    addr = (event.get("location") or {}).get("address", "").strip()
    # Stricter: image required for listing-aggregator sources.
    if not img and event.get("source") in _IMAGE_REQUIRED_SOURCES:
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

    # Preserve firstSeenAt across runs — if an event existed in the previous
    # events.json, carry its original firstSeenAt forward; otherwise stamp now.
    if previous_index is None:
        previous_index = {}
    now_iso = datetime.now().isoformat()
    velocity_count = 0
    for ev in events:
        prev = previous_index.get(ev.get("id"))
        if prev and prev.get("firstSeenAt"):
            ev["firstSeenAt"] = prev["firstSeenAt"]
        else:
            ev["firstSeenAt"] = now_iso

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
    DEFAULT_MIN_SCORE = 0.30
    IG_CURATED_MIN_SCORE = 0.20
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
