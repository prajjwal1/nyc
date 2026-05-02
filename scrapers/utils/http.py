import httpx
import asyncio
import random

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

_semaphore = asyncio.Semaphore(5)


async def fetch(url: str, *, headers: dict | None = None, timeout: float = 30) -> httpx.Response:
    async with _semaphore:
        h = {"User-Agent": random.choice(USER_AGENTS)}
        if headers:
            h.update(headers)
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.get(url, headers=h)
            resp.raise_for_status()
            return resp


async def fetch_text(url: str, **kwargs) -> str:
    resp = await fetch(url, **kwargs)
    return resp.text


async def fetch_json(url: str, **kwargs) -> dict:
    resp = await fetch(url, **kwargs)
    return resp.json()
