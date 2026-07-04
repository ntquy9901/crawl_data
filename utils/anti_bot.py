"""
Anti-Bot module for Vietstock Crawler
Provides stealth features, random delays, and browser automation utilities
"""

import random
import time
import asyncio
from typing import Optional
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

from config import RANDOM_DELAY_MIN, RANDOM_DELAY_MAX, TIMEOUT, DEFAULT_USER_AGENTS


# Initialize user agent rotator
try:
    ua = UserAgent()
except Exception:
    # Fallback if fake-useragent fails
    ua = None


def random_delay(min_sec: Optional[float] = None, max_sec: Optional[float] = None) -> None:
    """
    Sleep for a random delay between min and max seconds

    Args:
        min_sec: Minimum delay in seconds (defaults to config value)
        max_sec: Maximum delay in seconds (defaults to config value)
    """
    min_val = min_sec if min_sec is not None else RANDOM_DELAY_MIN
    max_val = max_sec if max_sec is not None else RANDOM_DELAY_MAX
    delay = random.uniform(min_val, max_val)
    time.sleep(delay)


def get_random_user_agent() -> str:
    """
    Get a random user agent string

    Returns:
        Random user agent string
    """
    if ua:
        try:
            return ua.random
        except Exception:
            pass
    return random.choice(DEFAULT_USER_AGENTS)


async def human_like_scroll(page: Page, max_scrolls: int = 3) -> None:
    """
    Perform human-like scrolling on the page

    Args:
        page: Playwright page object
        max_scrolls: Maximum number of scroll actions
    """
    scroll_count = random.randint(1, max_scrolls)

    for _ in range(scroll_count):
        # Random scroll distance
        scroll_distance = random.randint(100, 500)
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")

        # Random delay between scrolls
        await asyncio.sleep(random.uniform(0.5, 2.0))


async def human_like_mouse_move(page: Page) -> None:
    """
    Perform human-like mouse movements on the page

    Args:
        page: Playwright page object
    """
    try:
        viewport = page.viewport_size
        if viewport:
            # Move mouse to random positions
            for _ in range(random.randint(2, 5)):
                x = random.randint(50, viewport['width'] - 50)
                y = random.randint(50, viewport['height'] - 50)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.5))
    except Exception:
        # Ignore errors from mouse movements
        pass


async def create_stealth_browser(headless: bool = True) -> tuple[Browser, BrowserContext, Page]:
    """
    Create a browser with stealth settings to avoid detection

    Args:
        headless: Whether to run browser in headless mode

    Returns:
        Tuple of (browser, context, page)
    """
    playwright = await async_playwright().start()

    # Initialize stealth
    stealth = Stealth()

    # Launch browser with anti-detection settings
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-features=VizDisplayCompositor',
        ],
    )

    # Create context with realistic settings
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent=get_random_user_agent(),
        locale='vi-VN',
        timezone_id='Asia/Ho_Chi_Minh',
        permissions=['geolocation'],
    )

    # Apply stealth to the context
    await stealth.apply_stealth_async(context)

    # Create page
    page = await context.new_page()

    # Set default timeout
    page.set_default_timeout(TIMEOUT)

    return browser, context, page


async def safe_goto(page: Page, url: str, max_retries: int = 3) -> bool:
    """
    Safely navigate to a URL with retry logic

    Args:
        page: Playwright page object
        url: URL to navigate to
        max_retries: Maximum number of retry attempts

    Returns:
        True if navigation succeeded, False otherwise
    """
    for attempt in range(max_retries):
        try:
            # Add random delay before navigation (except first attempt)
            if attempt > 0:
                random_delay()

            await page.goto(url, wait_until='domcontentloaded', timeout=TIMEOUT)
            return True

        except Exception as e:
            print(f"Navigation attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                return False

    return False


async def safe_click(page: Page, selector: str, timeout: int = 10000) -> bool:
    """
    Safely click an element with retry logic

    Args:
        page: Playwright page object
        selector: CSS selector of the element to click
        timeout: Timeout in milliseconds

    Returns:
        True if click succeeded, False otherwise
    """
    try:
        # Wait for element to be visible
        await page.wait_for_selector(selector, timeout=timeout, state='visible')

        # Add random human-like delay
        await asyncio.sleep(random.uniform(0.5, 1.5))

        # Click the element
        await page.click(selector)
        return True

    except Exception as e:
        print(f"Click failed for selector '{selector}': {e}")
        return False
