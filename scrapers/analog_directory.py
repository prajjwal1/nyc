"""Build an attributed discovery index from Analog Directory's sitemap.

Analog explicitly permits search indexing but prohibits scraping at scale and
copying/mirroring its database. This importer therefore makes exactly two
requests (robots.txt and sitemap.xml), stores canonical community hyperlinks
and name hints derived from URL slugs, and never fetches listing pages,
descriptions, images, editorial text, or proprietary fields.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ROBOTS_URL = "https://analog.directory/robots.txt"
SITEMAP_URL = "https://analog.directory/sitemap.xml"
OUTPUT_PATH = ROOT / "data" / "analog_directory_index.json"


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "City-Kin-search-index/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def search_indexing_allowed(robots: str) -> bool:
    """Require the site's explicit search=yes signal before indexing."""
    return bool(re.search(r"(?im)^\s*Content-Signal:\s*[^\n]*\bsearch\s*=\s*yes\b", robots))


def humanize_slug(slug: str) -> str:
    words = unquote(slug).replace("_", "-").split("-")
    keep_upper = {"nyc", "ny", "bk", "ai", "b2b", "lgbtq", "usa", "us"}
    return " ".join(word.upper() if word.lower() in keep_upper else word.capitalize() for word in words if word)


def parse_community_urls(xml: bytes) -> list[dict]:
    root = ElementTree.fromstring(xml)
    found = {}
    for node in root.iter():
        if not node.tag.endswith("loc") or not node.text:
            continue
        url = node.text.strip()
        parsed = urlparse(url)
        match = re.fullmatch(r"/communities/([^/]+)/?", parsed.path)
        if parsed.netloc.lower() != "analog.directory" or not match:
            continue
        slug = unquote(match.group(1)).lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._~-]*", slug):
            continue
        found[slug] = {
            "analogSlug": slug,
            "nameHint": humanize_slug(slug),
            "sourceUrl": f"https://analog.directory/communities/{slug}",
            "source": "analog-directory",
            "status": "discovery_only",
        }
    return [found[key] for key in sorted(found)]


def _fold(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def match_verified_communities(entries: list[dict], communities_doc: dict) -> int:
    """Attach only exact normalized-name matches; never fuzzy-merge entities."""
    by_name = {}
    for community in communities_doc.get("communities") or []:
        key = _fold(community.get("name") or "")
        if key:
            by_name.setdefault(key, []).append(community)
    matched = 0
    for entry in entries:
        # A one-word name is too ambiguous for a name-only cross-directory
        # join (e.g. "Elsewhere"). Keep it as a lead until an official URL or
        # platform ID independently bridges the identities.
        if len(re.findall(r"[A-Za-z0-9]+", entry["nameHint"])) < 2:
            continue
        candidates = by_name.get(_fold(entry["nameHint"]), [])
        if len(candidates) == 1:
            entry["matchedCommunityId"] = candidates[0].get("id")
            entry["matchMethod"] = "exact_normalized_multiword_name"
            entry["status"] = "matched_to_independently_verified_community"
            matched += 1
    return matched


def build_index(robots: str, sitemap: bytes, communities_doc: dict, *, generated_at: str | None = None) -> dict:
    if not search_indexing_allowed(robots):
        raise RuntimeError("Analog no longer explicitly permits search indexing; refusing to update")
    entries = parse_community_urls(sitemap)
    matched = match_verified_communities(entries, communities_doc)
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "Analog Directory",
            "url": "https://analog.directory/",
            "sitemapUrl": SITEMAP_URL,
            "usage": "attributed search/discovery reference only",
        },
        "policy": {
            "listingPagesFetched": False,
            "descriptionsCopied": False,
            "imagesCopied": False,
            "requiresIndependentVerificationBeforePublication": True,
        },
        "stats": {"communityLeads": len(entries), "matchedVerifiedCommunities": matched, "unverifiedLeads": len(entries) - matched},
        "communities": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--robots-file", type=Path)
    parser.add_argument("--sitemap-file", type=Path)
    args = parser.parse_args()
    robots = (args.robots_file.read_text() if args.robots_file else _fetch(ROBOTS_URL).decode("utf-8", errors="replace"))
    sitemap = args.sitemap_file.read_bytes() if args.sitemap_file else _fetch(SITEMAP_URL)
    try:
        communities_doc = json.loads((ROOT / "data" / "communities.json").read_text())
    except (OSError, ValueError):
        communities_doc = {"communities": []}
    payload = build_index(robots, sitemap, communities_doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n")
    temp.replace(args.output)
    print(f"Indexed {payload['stats']['communityLeads']} attributed leads; matched {payload['stats']['matchedVerifiedCommunities']}")


if __name__ == "__main__":
    main()
