from bs4 import BeautifulSoup
from ..utils.http import fetch_text
from ..utils.event_parser import build_event, parse_date, parse_time

URL = "https://www.nycforfree.co"


async def scrape() -> list[dict]:
    events = []
    try:
        html = await fetch_text(URL)
        soup = BeautifulSoup(html, "lxml")

        for article in soup.select("article, .post, .entry, [class*='blog-item'], [class*='post-card']"):
            title_el = article.select_one("h2 a, h3 a, .entry-title a, [class*='title'] a, h2, h3")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = f"{URL}{link}"

            date_el = article.select_one("time, [class*='date'], .post-date")
            date_text = ""
            if date_el:
                date_text = date_el.get("datetime", date_el.get_text(strip=True))

            desc_el = article.select_one("p, .excerpt, .summary, [class*='excerpt']")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            event_date = parse_date(date_text) if date_text else None
            start_time = parse_time(desc or title)

            if event_date:
                events.append(build_event(
                    title=title,
                    description=desc,
                    event_date=event_date,
                    start_time=start_time,
                    source="nycforfree",
                    source_url=link or URL,
                    price="free",
                ))
    except Exception as e:
        print(f"[nycforfree] Failed: {e}")
    return events
