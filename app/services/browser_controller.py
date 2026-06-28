"""
BrowserController — smart Playwright wrapper for AI-driven browser automation.

Supports:
  - Headed (visible) or headless mode
  - Smart element finding by text/label/placeholder (not just CSS selectors)
  - DOM state extraction — feeds LLM with interactive elements list
  - Screenshot → base64 for vision models
  - Multi-tab support
  - Login credential injection via env vars
"""

import asyncio
import base64
import os
import re
from dataclasses import dataclass, field
from typing import Any

from app.utils import logger

HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() != "false"


@dataclass
class PageElement:
    idx: int
    tag: str
    type: str = ""
    text: str = ""
    id: str = ""
    name: str = ""
    placeholder: str = ""
    href: str = ""
    value: str = ""
    role: str = ""
    aria_label: str = ""

    def label(self) -> str:
        return (
            self.aria_label or self.placeholder or self.text or
            self.name or self.id or self.href or f"[{self.tag}#{self.idx}]"
        )[:80]

    def to_str(self) -> str:
        t = f"[{self.idx}] {self.tag}"
        if self.type:
            t += f"({self.type})"
        t += f" — {self.label()}"
        return t


@dataclass
class PageState:
    url: str = ""
    title: str = ""
    elements: list[PageElement] = field(default_factory=list)
    text_excerpt: str = ""
    screenshot_b64: str = ""     # empty unless capture_screenshot=True

    def elements_text(self) -> str:
        return "\n".join(e.to_str() for e in self.elements[:60])

    def to_context(self, include_screenshot: bool = False) -> str:
        lines = [
            f"URL: {self.url}",
            f"Title: {self.title}",
            "",
            "Interactive elements:",
            self.elements_text() or "(none detected)",
            "",
            "Page text (excerpt):",
            self.text_excerpt[:1500],
        ]
        return "\n".join(lines)


class BrowserController:
    """
    AI-friendly Playwright controller.
    One instance per browser session.
    """

    def __init__(self, headless: bool = HEADLESS, slow_mo: int = 0):
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._started = False

    async def start(self) -> None:
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            slow_mo=self._slow_mo,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()
        self._started = True
        logger.info(f"BrowserController started (headless={self._headless})")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._started = False

    # ── Navigation ─────────────────────────────────────────────────────────

    async def navigate(self, url: str, wait: str = "domcontentloaded") -> str:
        if not url.startswith("http"):
            url = "https://" + url
        await self._page.goto(url, timeout=30000, wait_until=wait)
        await asyncio.sleep(1)
        return self._page.url

    async def go_back(self) -> None:
        await self._page.go_back()

    async def reload(self) -> None:
        await self._page.reload()

    # ── Actions ────────────────────────────────────────────────────────────

    async def click(self, target: str) -> bool:
        """Click by CSS selector, text, aria-label, or element index [N]."""
        try:
            # Index reference like "[3]"
            m = re.match(r"^\[?(\d+)\]?$", target.strip())
            if m:
                idx = int(m.group(1))
                el = await self._element_by_idx(idx)
                if el:
                    await el.click(timeout=5000)
                    await asyncio.sleep(0.5)
                    return True

            # Try CSS selector first
            try:
                await self._page.click(target, timeout=3000)
                await asyncio.sleep(0.5)
                return True
            except Exception:
                pass

            # Try by text (button, link, label)
            for method in [
                self._page.get_by_role("button", name=target),
                self._page.get_by_role("link", name=target),
                self._page.get_by_text(target),
                self._page.get_by_label(target),
                self._page.get_by_placeholder(target),
            ]:
                try:
                    await method.first.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    return True
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Click failed for '{target}': {e}")
        return False

    async def type_text(self, target: str, text: str, clear_first: bool = True) -> bool:
        """Type into field identified by selector, label, placeholder, or index."""
        try:
            m = re.match(r"^\[?(\d+)\]?$", target.strip())
            if m:
                idx = int(m.group(1))
                el = await self._element_by_idx(idx)
                if el:
                    if clear_first:
                        await el.triple_click()
                    await el.type(text)
                    return True

            for method in [
                lambda: self._page.fill(target, text),
                lambda: self._page.get_by_label(target).fill(text),
                lambda: self._page.get_by_placeholder(target).fill(text),
            ]:
                try:
                    await method()
                    return True
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Type failed for '{target}': {e}")
        return False

    async def select_option(self, target: str, value: str) -> bool:
        try:
            await self._page.select_option(target, value, timeout=5000)
            return True
        except Exception as e:
            logger.warning(f"Select failed: {e}")
            return False

    async def press_key(self, key: str) -> None:
        await self._page.keyboard.press(key)

    async def scroll(self, direction: str = "down", amount: int = 3) -> None:
        delta = amount * 300
        if direction == "up":
            delta = -delta
        await self._page.mouse.wheel(0, delta)
        await asyncio.sleep(0.3)

    async def wait_for_selector(self, selector: str, timeout: int = 10000) -> bool:
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def wait_seconds(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def switch_to_frame(self, frame_selector: str) -> bool:
        try:
            frame = self._page.frame_locator(frame_selector)
            self._active_frame = frame
            return True
        except Exception:
            return False

    # ── State & Screenshot ─────────────────────────────────────────────────

    async def get_state(self, capture_screenshot: bool = False) -> PageState:
        url = self._page.url
        title = await self._page.title()
        elements = await self._extract_elements()
        text = await self._extract_visible_text()
        screenshot_b64 = ""
        if capture_screenshot:
            screenshot_b64 = await self.screenshot_b64()
        return PageState(
            url=url, title=title, elements=elements,
            text_excerpt=text, screenshot_b64=screenshot_b64,
        )

    async def screenshot_b64(self) -> str:
        data = await self._page.screenshot(type="jpeg", quality=60)
        return base64.b64encode(data).decode()

    async def extract_text(self, selector: str = "body") -> str:
        try:
            el = self._page.locator(selector).first
            return await el.inner_text(timeout=5000)
        except Exception:
            return ""

    async def current_url(self) -> str:
        return self._page.url

    # ── Private helpers ────────────────────────────────────────────────────

    async def _extract_elements(self) -> list[PageElement]:
        js = """
        () => {
            const tags = ['a','button','input','select','textarea','[role="button"]',
                          '[role="link"]','[role="tab"]','[role="menuitem"]','[role="checkbox"]',
                          '[role="radio"]','label'];
            const els = document.querySelectorAll(tags.join(','));
            const results = [];
            let idx = 0;
            for (const el of els) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                if (el.offsetParent === null && el.tagName !== 'INPUT') continue;
                results.push({
                    idx: idx++,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    text: (el.innerText || el.textContent || '').trim().slice(0, 80),
                    id: el.id || '',
                    name: el.name || '',
                    placeholder: el.placeholder || '',
                    href: el.href || '',
                    value: el.value || '',
                    role: el.getAttribute('role') || '',
                    aria_label: el.getAttribute('aria-label') || '',
                });
                if (idx >= 80) break;
            }
            return results;
        }
        """
        try:
            raw = await self._page.evaluate(js)
            return [PageElement(**r) for r in raw]
        except Exception:
            return []

    async def _extract_visible_text(self) -> str:
        try:
            text = await self._page.evaluate(
                "() => document.body.innerText"
            )
            # Collapse whitespace
            return re.sub(r"\n{3,}", "\n\n", text or "").strip()[:3000]
        except Exception:
            return ""

    async def _element_by_idx(self, idx: int):
        elements = await self._extract_elements()
        for e in elements:
            if e.idx == idx:
                js = f"""
                () => {{
                    const tags = ['a','button','input','select','textarea',
                                  '[role="button"]','[role="link"]','[role="tab"]',
                                  '[role="menuitem"]','[role="checkbox"]','[role="radio"]','label'];
                    const els = [...document.querySelectorAll(tags.join(','))].filter(el => {{
                        const r = el.getBoundingClientRect();
                        return r.width > 0 || r.height > 0;
                    }});
                    return els[{idx}] ? true : false;
                }}
                """
                # Return locator by nth matching element
                tags = "a,button,input,select,textarea,[role='button'],[role='link'],[role='tab'],[role='menuitem'],[role='checkbox'],[role='radio'],label"
                return self._page.locator(tags).nth(idx)
        return None
