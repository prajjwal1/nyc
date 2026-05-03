import asyncio
import random

import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Default browser-like headers — many sites 403 if these are missing
_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_semaphore = asyncio.Semaphore(5)


async def fetch(
    url: str, *, headers: dict | None = None, timeout: float = 30
) -> httpx.Response:
    async with _semaphore:
        h = {**_DEFAULT_HEADERS, "User-Agent": random.choice(USER_AGENTS)}
        if headers:
            h.update(headers)
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout, http2=False
        ) as client:
            resp = await client.get(url, headers=h)
            resp.raise_for_status()
            return resp


async def fetch_text(url: str, **kwargs) -> str:
    resp = await fetch(url, **kwargs)
    return resp.text


async def fetch_json(url: str, **kwargs) -> dict:
    resp = await fetch(url, **kwargs)
    return resp.json()
