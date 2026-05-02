from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time
import re

URL = "https://theskint.com/"


async def scrape() -> list[dict]:
    events = []
    try:
        html = await fetch_text(URL)
        soup = BeautifulSoup(html, "lxml")

        for article in soup.select("article, .post, .entry-content"):
            content = article.select_one(".entry-content, .post-content, .content")
            if not content:
                content = article

            title_el = article.select_one("h2, h1, .entry-title")
            post_date_el = article.select_one("time, [class*='date']")
            post_date = ""
            if post_date_el:
                post_date = post_date_el.get("datetime", post_date_el.get_text(strip=True))

            paragraphs = content.select("p")
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) < 10:
                    continue

                links = p.select("a[href]")
                link = links[0].get("href", "") if links else ""

                bold = p.select_one("strong, b")
                event_title = bold.get_text(strip=True) if bold else text[:80]

                event_date = parse_date(post_date) if post_date else None
                start_time = parse_time(text)

                if event_date and len(event_title) > 3:
                    events.append(build_event(
                        title=event_title,
                        description=text[:300],
                        event_date=event_date,
                        start_time=start_time,
                        source="theskint",
                        source_url=link or URL,
                        price="free",
                        categories=["free"],
                    ))
    except Exception as e:
        print(f"[theskint] Failed: {e}")
    return events
