import pytest

from scrapers.analog_directory import build_index, humanize_slug, parse_community_urls


SITEMAP = b'''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://analog.directory/communities/nyc-backgammon-club</loc></url>
  <url><loc>https://analog.directory/communities/reading-rhythms</loc></url>
  <url><loc>https://analog.directory/blog/posts/not-a-community</loc></url>
  <url><loc>https://evil.example/communities/not-allowed</loc></url>
</urlset>'''


def test_sitemap_import_is_links_only_and_exact_matches():
    communities = {"communities": [{"id": "com_1", "name": "NYC Backgammon Club"}]}
    result = build_index("Content-Signal: search=yes,ai-train=no,use=reference", SITEMAP, communities, generated_at="now")
    assert result["stats"] == {"communityLeads": 2, "matchedVerifiedCommunities": 1, "unverifiedLeads": 1}
    assert result["communities"][0]["matchedCommunityId"] == "com_1"
    assert result["policy"]["listingPagesFetched"] is False
    assert set(result["communities"][0]) <= {"analogSlug", "nameHint", "sourceUrl", "source", "status", "matchedCommunityId", "matchMethod"}


def test_refuses_update_without_explicit_search_permission():
    with pytest.raises(RuntimeError):
        build_index("User-agent: *\nAllow: /", SITEMAP, {})


def test_humanizes_only_the_url_slug():
    assert humanize_slug("nyc-b2b-startup-events") == "NYC B2B Startup Events"
