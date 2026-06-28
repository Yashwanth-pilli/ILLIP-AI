"""
Browser service — fetch pages and extract clean text.

Primary: httpx (fast, no overhead)
Fallback: Playwright (for JS-heavy pages, if installed)
Text extraction: trafilatura (best-in-class readability)
"""

import asyncio
import re
from dataclasses import dataclass

import httpx

from app.utils import logger

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = 15


@dataclass
class PageResult:
    url: str
    title: str = ""
    text: str = ""
    error: str = ""
    fetched_with: str = "httpx"

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error

    def truncated(self, chars: int = 3000) -> str:
        return self.text[:chars]


def _extract_text_trafilatura(html: str, url: str) -> tuple[str, str]:
    """Returns (title, clean_text)."""
    try:
        import trafilatura
        text = trafilatura.extract(html, include_links=False, include_tables=False, url=url) or ""
        # Extract title from HTML
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""
        return title, text
    except ImportError:
        return _extract_text_fallback(html)


def _extract_text_fallback(html: str) -> tuple[str, str]:
    """Regex fallback when trafilatura not installed."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""
    # Strip scripts/styles
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return title, text[:5000]


async def fetch_page(url: str) -> PageResult:
    """Fetch URL, extract clean text. Tries httpx first, Playwright on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers=_HEADERS,
        ) as c:
            r = await c.get(url)
            r.raise_for_status()
            html = r.text

        title, text = _extract_text_trafilatura(html, url)
        if len(text) < 100:
            title, text = _extract_text_fallback(html)

        return PageResult(url=url, title=title, text=text, fetched_with="httpx")

    except Exception as e:
        # Try Playwright for JS-heavy pages
        try:
            return await _fetch_playwright(url)
        except Exception:
            return PageResult(url=url, error=str(e))


async def _fetch_playwright(url: str) -> PageResult:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("playwright not installed")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"User-Agent": _HEADERS["User-Agent"]})
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        html = await page.content()
        title = await page.title()
        await browser.close()

    _, text = _extract_text_trafilatura(html, url)
    if len(text) < 100:
        _, text = _extract_text_fallback(html)

    return PageResult(url=url, title=title, text=text, fetched_with="playwright")


async def fetch_pages_parallel(urls: list[str], max_concurrent: int = 5) -> list[PageResult]:
    """Fetch multiple pages in parallel with concurrency limit."""
    sem = asyncio.Semaphore(max_concurrent)

    async def _limited(url):
        async with sem:
            return await fetch_page(url)

    return await asyncio.gather(*[_limited(u) for u in urls], return_exceptions=False)
