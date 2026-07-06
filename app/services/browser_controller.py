"""
BrowserController — AI-driven Playwright wrapper.

Key upgrades over v1:
  - Shadow DOM piercing (Salesforce LWC, Cisco web UIs use shadow DOM)
  - networkidle wait after navigation (Salesforce needs 3-5s to hydrate)
  - Smart click: text → aria → idx → JS force-click fallback
  - Auto-scroll element into view before clicking
  - Visible-only element filter (skips hidden/offscreen elements)
"""

import asyncio
import base64
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.utils import logger

HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() != "false"

# One persistent browser identity (cookies/localStorage) — log in once with
# "Show browser" checked, session auto-saves, future runs (even headless) stay logged in.
DEFAULT_SESSION_PATH = Path("data") / "browser_sessions" / "session.json"

# Where Playwright stores downloaded browsers (Windows / Linux / Mac)
def _playwright_browsers_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache"))
    return base / "ms-playwright"


def _chromium_installed() -> bool:
    d = _playwright_browsers_dir()
    if not d.exists():
        return False
    return any(p.name.startswith("chromium") for p in d.iterdir() if p.is_dir())


async def ensure_browser_ready(progress_cb=None) -> bool:
    """
    Auto-install Playwright + Chromium on first use. No user action needed.
    progress_cb: optional async callable(str) for status messages.
    Returns True when ready.
    """
    async def _msg(text: str):
        logger.info(f"[BrowserSetup] {text}")
        if progress_cb:
            await progress_cb(text)

    # Step 1: ensure playwright Python package
    try:
        import playwright  # noqa
    except ImportError:
        await _msg("Installing Playwright package...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "playwright", "-q",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()

    # Step 2: ensure Chromium browser binary
    if not _chromium_installed():
        await _msg("Downloading Chromium browser (first time only, ~150MB)...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "playwright", "install", "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            await _msg(f"Chromium install failed: {stdout.decode()[:200]}")
            return False
        await _msg("Chromium ready.")

    return True

# JS that pierces shadow DOM — critical for Salesforce Lightning / Cisco labs
_SHADOW_DOM_JS = """
() => {
    const results = [];
    let idx = 0;
    const TAGS = new Set(['a','button','input','select','textarea']);
    const ROLES = new Set(['button','link','tab','menuitem','checkbox','radio',
                           'option','combobox','searchbox','textbox','spinbutton']);

    function isVisible(el) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        return true;
    }

    function collect(root) {
        // Collect matching elements in this root
        const selector = [
            'a[href]','button','input:not([type="hidden"])','select','textarea',
            '[role="button"]','[role="link"]','[role="tab"]','[role="menuitem"]',
            '[role="checkbox"]','[role="radio"]','[role="option"]',
            '[role="combobox"]','[role="searchbox"]','[role="textbox"]',
            '[tabindex]:not([tabindex="-1"])'
        ].join(',');

        let els;
        try { els = root.querySelectorAll(selector); } catch(e) { return; }

        for (const el of els) {
            if (!isVisible(el)) continue;
            results.push({
                idx: idx++,
                tag: el.tagName.toLowerCase(),
                type: el.type || '',
                text: (el.innerText || el.textContent || el.value || '').trim().slice(0, 100),
                id: el.id || '',
                name: el.name || '',
                placeholder: el.placeholder || '',
                href: el.href || '',
                value: el.value || '',
                role: el.getAttribute('role') || '',
                aria_label: el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || '',
                data_label: el.getAttribute('data-label') || el.getAttribute('data-value') || '',
            });
            if (idx >= 100) return;
        }

        // Recurse into shadow roots
        const allNodes = root.querySelectorAll('*');
        for (const node of allNodes) {
            if (node.shadowRoot) collect(node.shadowRoot);
            if (idx >= 100) break;
        }
    }

    collect(document);
    return results;
}
"""

# JS to click element by index, piercing shadow DOM
_CLICK_BY_IDX_JS = """
(targetIdx) => {
    let idx = 0;
    const selector = [
        'a[href]','button','input:not([type="hidden"])','select','textarea',
        '[role="button"]','[role="link"]','[role="tab"]','[role="menuitem"]',
        '[role="checkbox"]','[role="radio"]','[role="option"]',
        '[role="combobox"]','[role="searchbox"]','[role="textbox"]',
        '[tabindex]:not([tabindex="-1"])'
    ].join(',');

    function isVisible(el) {
        const r = el.getBoundingClientRect();
        return r.width > 0 || r.height > 0;
    }

    function find(root) {
        let els;
        try { els = root.querySelectorAll(selector); } catch(e) { return null; }
        for (const el of els) {
            if (!isVisible(el)) continue;
            if (idx === targetIdx) {
                el.scrollIntoView({block: 'center', behavior: 'instant'});
                el.focus();
                el.click();
                return 'clicked';
            }
            idx++;
        }
        const all = root.querySelectorAll('*');
        for (const node of all) {
            if (node.shadowRoot) {
                const r = find(node.shadowRoot);
                if (r) return r;
            }
        }
        return null;
    }
    return find(document);
}
"""

# JS to set value on input, piercing shadow DOM (handles React/LWC controlled inputs)
_SET_VALUE_JS = """
(targetIdx, value) => {
    let idx = 0;
    const selector = 'input:not([type="hidden"]),select,textarea,[role="textbox"],[role="searchbox"]';

    function isVisible(el) {
        const r = el.getBoundingClientRect();
        return r.width > 0 || r.height > 0;
    }

    function find(root) {
        let els;
        try { els = root.querySelectorAll(selector); } catch(e) { return null; }
        for (const el of els) {
            if (!isVisible(el)) continue;
            if (idx === targetIdx) {
                el.scrollIntoView({block: 'center', behavior: 'instant'});
                el.focus();
                // Native input value setter (works on React/LWC controlled inputs)
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                );
                if (nativeInputValueSetter && nativeInputValueSetter.set) {
                    nativeInputValueSetter.set.call(el, value);
                } else {
                    el.value = value;
                }
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return 'typed';
            }
            idx++;
        }
        const all = root.querySelectorAll('*');
        for (const node of all) {
            if (node.shadowRoot) {
                const r = find(node.shadowRoot);
                if (r) return r;
            }
        }
        return null;
    }
    return find(document);
}
"""


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
    data_label: str = ""

    def label(self) -> str:
        return (
            self.aria_label or self.data_label or self.placeholder or
            self.text or self.name or self.id or
            (self.href[:50] if self.href else "") or f"[{self.tag}#{self.idx}]"
        )[:80]

    def to_str(self) -> str:
        t = f"[{self.idx}] {self.tag}"
        if self.type and self.type not in ("submit", "button"):
            t += f"({self.type})"
        t += f" — {self.label()}"
        return t


@dataclass
class PageState:
    url: str = ""
    title: str = ""
    elements: list[PageElement] = field(default_factory=list)
    text_excerpt: str = ""
    screenshot_b64: str = ""

    def elements_text(self) -> str:
        return "\n".join(e.to_str() for e in self.elements[:80])

    def to_context(self) -> str:
        return "\n".join([
            f"URL: {self.url}",
            f"Title: {self.title}",
            "",
            "Interactive elements (shadow DOM included):",
            self.elements_text() or "(none detected — page may still be loading)",
            "",
            "Page text:",
            self.text_excerpt[:2000],
        ])


class BrowserController:

    def __init__(self, headless: bool = HEADLESS, slow_mo: int = 50, use_session: bool = True):
        self._headless = headless
        self._slow_mo = slow_mo
        self._use_session = use_session
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            slow_mo=self._slow_mo,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",        # allows cross-origin iframes (some labs)
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        context_kwargs = dict(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,   # lab environments often use self-signed certs
        )
        if self._use_session and DEFAULT_SESSION_PATH.exists():
            context_kwargs["storage_state"] = str(DEFAULT_SESSION_PATH)
            logger.info("BrowserController: restored saved session (cookies/localStorage)")
        self._context = await self._browser.new_context(**context_kwargs)
        # Mask automation detection
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        self._page = await self._context.new_page()
        logger.info(f"BrowserController started (headless={self._headless})")

    async def save_session(self) -> bool:
        """Persist cookies/localStorage so future runs (incl. headless) stay logged in."""
        if not self._context:
            return False
        try:
            DEFAULT_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
            await self._context.storage_state(path=str(DEFAULT_SESSION_PATH))
            return True
        except Exception as e:
            logger.warning(f"BrowserController: save_session failed: {e}")
            return False

    async def stop(self) -> None:
        if self._use_session:
            await self.save_session()
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

    # ── Navigation ─────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> str:
        if not url.startswith("http"):
            url = "https://" + url
        try:
            # networkidle is important for Salesforce, Cisco web UIs
            await self._page.goto(url, timeout=45000, wait_until="domcontentloaded")
            # Also wait for network to settle (max 5s extra)
            try:
                await self._page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Navigate warning: {e}")
        await asyncio.sleep(1.5)
        return self._page.url

    async def go_back(self) -> None:
        await self._page.go_back(wait_until="domcontentloaded")
        await asyncio.sleep(1)

    async def reload(self) -> None:
        await self._page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

    # ── Smart Click ────────────────────────────────────────────────────────

    async def click(self, target: str) -> bool:
        """
        Multi-strategy click — tries in order:
        1. Index [N] via shadow-DOM-piercing JS
        2. Playwright get_by_role / get_by_text / get_by_label
        3. CSS selector
        4. Force JS click as last resort
        """
        target = target.strip()
        await self._wait_stable()

        # ── Strategy 1: index reference ──
        m = re.match(r"^\[?(\d+)\]?$", target)
        if m:
            idx = int(m.group(1))
            result = await self._page.evaluate(_CLICK_BY_IDX_JS, idx)
            if result == "clicked":
                await self._post_action_wait()
                return True
            logger.warning(f"Click idx {idx} via JS failed")

        # ── Strategy 2: Playwright locators (work in shadow DOM via Playwright's engine) ──
        locators = [
            self._page.get_by_role("button", name=re.compile(target, re.I)),
            self._page.get_by_role("link", name=re.compile(target, re.I)),
            self._page.get_by_role("tab", name=re.compile(target, re.I)),
            self._page.get_by_role("menuitem", name=re.compile(target, re.I)),
            self._page.get_by_text(re.compile(target, re.I)),
            self._page.get_by_label(re.compile(target, re.I)),
            self._page.get_by_placeholder(re.compile(target, re.I)),
        ]
        for loc in locators:
            try:
                await loc.first.scroll_into_view_if_needed(timeout=2000)
                await loc.first.click(timeout=4000)
                await self._post_action_wait()
                return True
            except Exception:
                continue

        # ── Strategy 3: CSS selector ──
        try:
            await self._page.click(target, timeout=3000)
            await self._post_action_wait()
            return True
        except Exception:
            pass

        logger.warning(f"Click failed for all strategies: '{target}'")
        return False

    # ── Smart Type ─────────────────────────────────────────────────────────

    async def type_text(self, target: str, text: str) -> bool:
        """
        Multi-strategy type:
        1. Index [N] via shadow-DOM JS (handles React/LWC controlled inputs)
        2. Playwright fill by label/placeholder
        3. CSS selector fill
        """
        target = target.strip()
        await self._wait_stable()

        m = re.match(r"^\[?(\d+)\]?$", target)
        if m:
            idx = int(m.group(1))
            # Use JS value setter for React/LWC (they intercept native events)
            result = await self._page.evaluate(_SET_VALUE_JS, idx, text)
            if result == "typed":
                # Also use Playwright type for natural key events (autocomplete triggers)
                try:
                    input_els = self._page.locator(
                        "input:not([type=hidden]),textarea,[role='textbox'],[role='searchbox']"
                    )
                    el = input_els.nth(idx)
                    await el.click(timeout=2000)
                    await self._page.keyboard.press("Control+a")
                    await self._page.keyboard.type(text, delay=30)
                except Exception:
                    pass
                return True

        locators = [
            self._page.get_by_label(re.compile(target, re.I)),
            self._page.get_by_placeholder(re.compile(target, re.I)),
            self._page.get_by_role("textbox", name=re.compile(target, re.I)),
            self._page.get_by_role("searchbox", name=re.compile(target, re.I)),
        ]
        for loc in locators:
            try:
                await loc.first.fill(text, timeout=4000)
                return True
            except Exception:
                continue

        try:
            await self._page.fill(target, text, timeout=3000)
            return True
        except Exception:
            pass

        logger.warning(f"Type failed for all strategies: '{target}'")
        return False

    async def select_option(self, target: str, value: str) -> bool:
        try:
            await self._page.select_option(target, value=value, timeout=5000)
            return True
        except Exception:
            try:
                await self._page.select_option(target, label=value, timeout=3000)
                return True
            except Exception:
                return False

    async def press_key(self, key: str) -> None:
        await self._page.keyboard.press(key)
        await asyncio.sleep(0.5)

    async def scroll(self, direction: str = "down", amount: int = 3) -> None:
        delta = amount * 300 * (-1 if direction == "up" else 1)
        await self._page.mouse.wheel(0, delta)
        await asyncio.sleep(0.3)

    async def wait_seconds(self, seconds: float) -> None:
        await asyncio.sleep(min(seconds, 30))

    async def wait_for_text(self, text: str, timeout: int = 10000) -> bool:
        try:
            await self._page.wait_for_selector(f"text={text}", timeout=timeout)
            return True
        except Exception:
            return False

    # ── State & Screenshot ─────────────────────────────────────────────────

    async def get_state(self, capture_screenshot: bool = False) -> PageState:
        await self._wait_stable()
        url = self._page.url
        title = await self._page.title()
        elements = await self._extract_elements()
        text = await self._extract_visible_text()
        ss = await self.screenshot_b64() if capture_screenshot else ""
        return PageState(url=url, title=title, elements=elements, text_excerpt=text, screenshot_b64=ss)

    async def screenshot_b64(self) -> str:
        data = await self._page.screenshot(type="jpeg", quality=70, full_page=False)
        return base64.b64encode(data).decode()

    async def extract_text(self, selector: str = "body") -> str:
        try:
            return await self._page.locator(selector).first.inner_text(timeout=5000)
        except Exception:
            return await self._page.evaluate("() => document.body.innerText") or ""

    async def current_url(self) -> str:
        return self._page.url

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _wait_stable(self) -> None:
        """Wait for page to stop major JS activity."""
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass

    async def _post_action_wait(self) -> None:
        """After click: wait for any triggered navigation or DOM update."""
        await asyncio.sleep(0.8)
        try:
            await self._page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass

    async def _extract_elements(self) -> list[PageElement]:
        try:
            raw = await self._page.evaluate(_SHADOW_DOM_JS)
            return [PageElement(**r) for r in raw]
        except Exception as e:
            logger.warning(f"Element extraction error: {e}")
            return []

    async def _extract_visible_text(self) -> str:
        try:
            text = await self._page.evaluate("() => document.body.innerText || ''")
            return re.sub(r"\n{3,}", "\n\n", text).strip()[:3000]
        except Exception:
            return ""
