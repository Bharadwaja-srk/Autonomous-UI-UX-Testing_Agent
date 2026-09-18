"""
Playwright Browser Driver for Autonomous UI/UX & Accessibility Testing.
Executes actions against target web applications purely out-of-band as a black box.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("autonomous_tester.driver")


class BrowserDriver:
    def __init__(self, headless: bool = False, slow_mo: int = 200):
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def start(self) -> None:
        """Initialize the browser instance."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                ]
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                device_scale_factor=1,
            )
            self._page = await self._context.new_page()
            self._page.set_default_timeout(10000)
            logger.info("Browser driver started successfully.")

    async def navigate(self, url: str) -> Tuple[bool, Optional[str]]:
        """Navigate to a target URL."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("file://"):
                url = "https://" + url
            logger.info(f"Navigating to: {url}")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1.0)  # Short stabilization pause
            return True, None
        except Exception as e:
            logger.error(f"Navigation error for {url}: {str(e)}")
            return False, f"Navigation failed: {str(e)}"

    async def take_screenshot(self, output_path: Path) -> Tuple[bool, Optional[str]]:
        """Take screenshot and save to disk."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            await self._page.screenshot(path=str(output_path), full_page=False)
            return True, None
        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            return False, f"Screenshot failed: {str(e)}"

    async def click(self, selector: Optional[str] = None, coordinates: Optional[Dict[str, float]] = None, timeout: int = 5000) -> Tuple[bool, Optional[str]]:
        """Click an element by CSS/text selector or coordinates."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            if coordinates and ("x" in coordinates and "y" in coordinates):
                logger.info(f"Clicking at coordinates ({coordinates['x']}, {coordinates['y']})")
                await self._page.mouse.click(coordinates["x"], coordinates["y"])
                await asyncio.sleep(0.5)
                return True, None

            if selector:
                logger.info(f"Clicking element: {selector}")
                loc = self._page.locator(selector).first
                await loc.wait_for(state="visible", timeout=timeout)
                await loc.scroll_into_view_if_needed(timeout=2000)
                await loc.click(timeout=timeout)
                await asyncio.sleep(0.6)
                return True, None

            return False, "Neither selector nor coordinates provided for click"
        except PlaywrightTimeoutError:
            return False, f"Timeout waiting to click: {selector or coordinates}"
        except Exception as e:
            return False, f"Click failed on {selector or coordinates}: {str(e)}"

    async def type(self, selector: str, text: str, clear_first: bool = True, press_enter: bool = False, timeout: int = 5000) -> Tuple[bool, Optional[str]]:
        """Type text into an input element."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            logger.info(f"Typing into {selector}: '{text}' (press_enter={press_enter})")
            loc = self._page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout)
            await loc.scroll_into_view_if_needed(timeout=2000)
            if clear_first:
                await loc.fill("")
                await loc.type(text, delay=30)
            else:
                await loc.type(text, delay=30)
                
            if press_enter:
                await self._page.keyboard.press("Enter")
            await asyncio.sleep(0.6)
            return True, None
        except Exception as e:
            return False, f"Type failed on {selector}: {str(e)}"

    async def scroll(self, direction: str = "down", amount: int = 400) -> Tuple[bool, Optional[str]]:
        """Scroll the window up or down."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            delta = amount if direction == "down" else -amount
            logger.info(f"Scrolling {direction} by {amount}px")
            await self._page.mouse.wheel(0, delta)
            await asyncio.sleep(0.5)
            return True, None
        except Exception as e:
            return False, f"Scroll failed: {str(e)}"

    async def press_key(self, key: str) -> Tuple[bool, Optional[str]]:
        """Press a keyboard key."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            logger.info(f"Pressing keyboard key: {key}")
            await self._page.keyboard.press(key)
            await asyncio.sleep(0.5)
            return True, None
        except Exception as e:
            return False, f"Press key failed: {str(e)}"

    async def go_back(self) -> Tuple[bool, Optional[str]]:
        """Navigate back in browser history."""
        if not self._page:
            return False, "Browser page not initialized"
        try:
            logger.info("Navigating back")
            await self._page.go_back(wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(0.8)
            return True, None
        except Exception as e:
            return False, f"Go back failed: {str(e)}"

    async def wait(self, seconds: float = 1.0) -> Tuple[bool, Optional[str]]:
        """Wait for page activity to settle."""
        try:
            await asyncio.sleep(seconds)
            return True, None
        except Exception as e:
            return False, f"Wait interrupted: {str(e)}"

    async def evaluate(self, script: str, arg: Any = None) -> Any:
        """Evaluate JS in page context."""
        if not self._page:
            return None
        return await self._page.evaluate(script, arg)

    async def close(self) -> None:
        """Safely close page, context, and browser."""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error during browser close: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            logger.info("Browser driver closed.")
