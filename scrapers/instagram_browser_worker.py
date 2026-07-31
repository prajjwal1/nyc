"""Authenticated local Instagram collector for the NYC events pipeline.

Instagram's unofficial GraphQL endpoints frequently reject Instaloader while
the normal logged-in website remains usable. This worker uses a dedicated
Playwright browser profile on the user's Mac, captures only rendered post
fields, and writes a sanitized snapshot consumed by sources/instagram.py.

First run:
  python -m scrapers.instagram_browser_worker --login
Hourly run:
  python -m scrapers.instagram_browser_worker --push
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import IG_ACCOUNTS, IG_USERNAME

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scrapers" / "data"
SNAPSHOT = DATA / "instagram_browser_snapshot.json"
PROFILE = Path(os.environ.get(
    "NYC_EVENTS_IG_PROFILE",
    str(Path.home() / "Library" / "Application Support" / "nyc-events" / "instagram-profile"),
))
STATE = Path(os.environ.get(
    "NYC_EVENTS_IG_STATE",
    str(Path.home() / "Library" / "Application Support" / "nyc-events" / "instagram-worker-state.json"),
))

LANE_PRIORITY = {"feed": 0, "highlight": 1, "story": 2, "tagged": 3, "saved": 4}
PROTECTED_PER_RUN = 6
ROTATING_PER_RUN = 10
POSTS_PER_PROFILE = 2
MAX_CAPTURED_PER_RUN = 40


def _browser_launch_options() -> dict:
    configured = os.environ.get("NYC_EVENTS_IG_BROWSER", "")
    mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    executable = configured or (mac_chrome if sys.platform == "darwin" and Path(mac_chrome).exists() else "")
    return {"executable_path": executable} if executable else {}


def _json(name: str, default):
    try:
        with open(DATA / name) as f:
            return json.load(f)
    except Exception:
        return default


def _state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _account_plan(rotation_cursor: int | None = None) -> tuple[list[str], list[str], int]:
    affinity = _json("user_affinity_accounts.json", {}).get("accounts", [])
    discovered = _json("discovered_accounts.json", {}).get("accounts", [])
    follows = [
        a.get("username") for a in discovered
        if isinstance(a, dict) and a.get("discovered_via") == "user_following"
    ]
    quality = _json("account_quality.json", {})

    def yield_score(account: str) -> float:
        row = quality.get((account or "").lower(), {})
        return (row.get("events_emitted", 0) or 0) / max(1, row.get("posts_scraped", 0) or 0)

    priority = list(dict.fromkeys(
        str(a).lower() for a in [*affinity, *follows, *IG_ACCOUNTS] if a
    ))
    priority.sort(key=lambda a: (a not in {str(x).lower() for x in affinity}, -yield_score(a)))
    protected = priority[:PROTECTED_PER_RUN]
    remaining = priority[PROTECTED_PER_RUN:]
    # Persist the rotation cursor across runs. Deriving it from hour-of-day
    # visited only chunks 0-3 forever, leaving most of a large account pool
    # completely unseen.
    chunks = max(1, (len(remaining) + ROTATING_PER_RUN - 1) // ROTATING_PER_RUN)
    cursor = int(_state().get("rotationCursor", 0) if rotation_cursor is None else rotation_cursor) % chunks
    rotating = remaining[cursor * ROTATING_PER_RUN:(cursor + 1) * ROTATING_PER_RUN]
    return protected, rotating, (cursor + 1) % chunks


def _post_links(page, url: str, limit: int) -> list[str]:
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(1800)
    hrefs = page.locator('a[href*="/p/"], a[href*="/reel/"]').evaluate_all(
        "els => els.map(e => e.href)"
    )
    out = []
    for href in hrefs:
        clean = href.split("?", 1)[0]
        if clean not in out:
            out.append(clean)
        if len(out) >= limit:
            break
    return out


def _caption_from_og(value: str) -> str:
    # Typical form: 123 likes, 5 comments - account on Date: "caption"
    match = re.search(r':\s*["“](.*)["”][.!]?\s*$', value or "", re.S)
    return match.group(1).strip() if match else (value or "").strip()


def _ocr_view(page) -> str:
    """Best-effort local OCR so CI never needs authenticated CDN images."""
    try:
        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(io.BytesIO(page.screenshot(full_page=False))))
        return re.sub(r"\n{3,}", "\n\n", text).strip()[:4000]
    except Exception:
        return ""


def _capture_post(page, url: str, lane: str, owner_hint: str = "") -> dict | None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(1200)
        if "challenge" in page.url or "login" in page.url:
            raise RuntimeError("instagram login/challenge required")
        og_desc = page.locator('meta[property="og:description"]').get_attribute("content") or ""
        og_image = page.locator('meta[property="og:image"]').get_attribute("content") or ""
        canonical = page.locator('link[rel="canonical"]').get_attribute("href") or url
        taken = ""
        times = page.locator("article time")
        if times.count():
            taken = times.first.get_attribute("datetime") or ""
        owner = owner_hint.lower()
        for href in page.locator('article header a[href^="/"]').evaluate_all("els => els.map(e => e.getAttribute('href'))"):
            m = re.fullmatch(r"/([A-Za-z0-9._]+)/", href or "")
            if m and m.group(1) not in {"explore", "accounts"}:
                owner = m.group(1).lower()
                break
        images = page.locator("article img").evaluate_all(
            "els => els.filter(e => e.naturalWidth >= 300).map(e => e.currentSrc || e.src)"
        )
        images = list(dict.fromkeys(x for x in images if isinstance(x, str) and x.startswith("http")))
        if not images and og_image:
            images = [og_image]
        if not owner:
            return None
        caption = _caption_from_og(og_desc)
        if len(caption) < 80:
            ocr = _ocr_view(page)
            if ocr:
                caption = f"{caption}\n{ocr}".strip()
        return {
            "url": canonical.split("?", 1)[0],
            "owner": owner,
            "lane": lane,
            "caption": caption,
            "takenAt": taken,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "image": images[0] if images else "",
            "images": images[:10],
            "isVideo": "/reel/" in canonical,
        }
    except Exception as exc:
        print(f"[instagram-browser] post failed {url}: {exc}")
        return None


def _capture_story(page, account: str) -> dict | None:
    url = f"https://www.instagram.com/stories/{account}/"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(1800)
        if "/stories/" not in page.url or "challenge" in page.url:
            return None
        images = page.locator('img[src*="instagram"], img[src*="fbcdn"]').evaluate_all(
            "els => els.filter(e => e.naturalWidth >= 300).map(e => e.currentSrc || e.src)"
        )
        images = list(dict.fromkeys(images))
        if not images:
            return None
        return {
            "url": url,
            "owner": account,
            "lane": "story",
            "caption": _ocr_view(page),
            "takenAt": datetime.now(timezone.utc).isoformat(),
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "image": images[-1],
            "images": [images[-1]],
        }
    except Exception as exc:
        print(f"[instagram-browser] story failed @{account}: {exc}")
        return None


def _dedupe(posts: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for post in posts:
        url = post.get("url", "")
        current = by_url.get(url)
        if current is None or LANE_PRIORITY.get(post.get("lane", "feed"), 0) > LANE_PRIORITY.get(current.get("lane", "feed"), 0):
            by_url[url] = post
    return list(by_url.values())


def _sanitize_posts(posts: list[dict]) -> list[dict]:
    """Keep event candidates only and whitelist snapshot fields.

    Saved collections can contain arbitrary personal content. Raw saved posts
    must never be committed merely because they appeared in the browser.
    """
    from .sources.instagram import _looks_like_event_post

    allowed = {
        "url", "owner", "lane", "caption", "takenAt", "capturedAt",
        "image", "images", "isVideo", "isPinned", "taggedUsers", "bioUrl",
        "likes", "comments",
    }
    out = []
    for post in _dedupe(posts):
        caption = str(post.get("caption") or "")[:6000]
        lower = caption.lower()
        if any(marker in lower for marker in (
            "no purchase required", "nation wide freebie", "giving away",
            "giveaway", "code will drop", "enter to win", "full year of perks",
            "annual membership", "full article",
        )):
            continue
        if not _looks_like_event_post(
            caption,
            has_image=bool(post.get("image")),
            is_curated_account=post.get("lane") == "feed",
        ):
            continue
        clean = {k: v for k, v in post.items() if k in allowed}
        clean["caption"] = caption
        clean["images"] = [
            u for u in (post.get("images") or [])[:10]
            if isinstance(u, str) and u.startswith("https://")
        ]
        out.append(clean)
    return out


def _merge_snapshot_posts(current: list[dict], previous: list[dict], limit: int = 1500) -> list[dict]:
    """Retain sanitized candidates while the long-tail account plan rotates."""
    merged = _dedupe([*current, *previous])
    merged.sort(key=lambda p: p.get("capturedAt") or p.get("takenAt") or "", reverse=True)
    return merged[:limit]


def _assert_logged_in(page) -> None:
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(1200)
    if "/accounts/login" in page.url or page.locator('input[name="username"]').count():
        raise RuntimeError(
            "Instagram browser session is not logged in; run "
            "`venv/bin/python -m scrapers.instagram_browser_worker --login`"
        )


def collect(headless: bool = True) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install local dependencies: pip install -r scrapers/requirements-local.txt") from exc

    PROFILE.mkdir(parents=True, exist_ok=True)
    protected, rotating, next_cursor = _account_plan()
    posts: list[dict] = []
    failures = 0
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE), headless=headless, viewport={"width": 1280, "height": 1000},
            **_browser_launch_options(),
        )
        page = context.pages[0] if context.pages else context.new_page()
        _assert_logged_in(page)
        # Explicit user signals first.
        for lane, url, limit in (
            ("saved", f"https://www.instagram.com/{IG_USERNAME}/saved/", 10),
            ("tagged", f"https://www.instagram.com/{IG_USERNAME}/tagged/", 5),
        ):
            try:
                for link in _post_links(page, url, limit):
                    post = _capture_post(page, link, lane)
                    if post:
                        posts.append(post)
            except Exception as exc:
                failures += 1
                print(f"[instagram-browser] {lane} failed: {exc}")
        # Hourly protected feeds, then the six-hour rotating long tail.
        for account in [*protected, *rotating]:
            if len(posts) >= MAX_CAPTURED_PER_RUN:
                break
            try:
                for link in _post_links(
                    page, f"https://www.instagram.com/{account}/", POSTS_PER_PROFILE
                ):
                    post = _capture_post(page, link, "feed", account)
                    if post:
                        posts.append(post)
                    time.sleep(random.uniform(1.5, 3.0))
                # Human-scale pacing avoids bursty profile traversal.
                time.sleep(random.uniform(4.0, 8.0))
            except Exception as exc:
                failures += 1
                print(f"[instagram-browser] feed failed @{account}: {exc}")
                if "challenge" in str(exc).lower():
                    break
        # Stories are intentionally excluded from unattended runs: each one
        # adds a profile navigation for ephemeral, low-parse-yield content.
        context.close()
    sanitized = _sanitize_posts(posts)
    previous = _json("instagram_browser_snapshot.json", {}).get("posts", [])
    retained = _merge_snapshot_posts(sanitized, previous)
    owner_counts = Counter(p.get("owner", "unknown") for p in retained)
    lane_counts = Counter(p.get("lane", "unknown") for p in retained)
    return {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "posts": retained,
        "diagnostics": {
            "protectedScheduled": len(protected),
            "rotatingScheduled": len(rotating),
            "rotationCursor": next_cursor,
            "failures": failures,
            "capturedThisRun": len(sanitized),
            "retainedPosts": len(retained),
            "uniqueOwners": len(owner_counts),
            "laneCounts": dict(lane_counts),
            "topOwners": dict(owner_counts.most_common(10)),
        },
    }


def login() -> None:
    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE), headless=False, **_browser_launch_options()
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.instagram.com/accounts/login/")
        print("Log in to Instagram in the browser, then press Enter here.")
        input()
        context.close()


def write_snapshot(snapshot: dict) -> None:
    if not snapshot.get("posts"):
        raise RuntimeError("Refusing to replace the Instagram snapshot with zero event candidates")
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshot, indent=2))
    tmp.replace(SNAPSHOT)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({
        "lastSuccess": snapshot["generatedAt"],
        "posts": len(snapshot["posts"]),
        "rotationCursor": snapshot.get("diagnostics", {}).get("rotationCursor", 0),
    }, indent=2))


def push_snapshot() -> None:
    subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", str(SNAPSHOT.relative_to(ROOT))], cwd=ROOT, check=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
    if changed:
        subprocess.run(["git", "commit", "-m", "Update local Instagram browser snapshot"], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    if args.login:
        login()
        return
    snapshot = collect(headless=not args.headed)
    write_snapshot(snapshot)
    print(f"[instagram-browser] wrote {len(snapshot['posts'])} posts to {SNAPSHOT}")
    if args.push:
        push_snapshot()


if __name__ == "__main__":
    main()
