#!/usr/bin/env python3
"""
Vietstock Crawler - Main Script
Crawls analysis reports from finance.vietstock.vn

Usage:
    python crawler.py                    # Crawl all available reports
    python crawler.py --date 2025-01-01   # Crawl from specific date
    python crawler.py --headless false   # Run with visible browser
    python crawler.py --test             # Test mode (crawl first page only)
"""

import argparse
import asyncio
import calendar
import logging
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path

import aiofiles
import pandas as pd

# Import modules
from config import (
    BASE_URL,
    CAPTCHA_MAX_RETRIES,
    CAPTCHA_PAUSE_MINUTES,
    CSV_FILE,
    CSV_HEADERS,
    DOWNLOAD_PDF,
    LOG_PATH,
    PDF_PATH,
    RANDOM_DELAY_MAX,
    RANDOM_DELAY_MIN,
    TARGET_URL,
    ensure_paths_exist,
)
from utils.alert import get_alert, get_detector
from utils.anti_bot import (
    create_stealth_browser,
    get_random_user_agent,
    human_like_scroll,
    safe_goto,
)
from utils.dedup import get_dedup_manager
from utils.pdf_helpers import generate_pdf_filename
from utils.proxy_manager import get_proxy_manager

_DATE_FMT_DMY = "%d/%m/%Y"
_XPATH_SELF = "xpath=.."


# Setup logging
def setup_logging():
    """Setup logging configuration"""
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOG_PATH / f"vietstock_crawler_{datetime.now().strftime('%Y%m%d')}.log"

    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # File handler with UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Console handler - handle Unicode properly
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Configure logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


class VietstockCrawler:
    """Main crawler class for Vietstock analysis reports"""

    def __init__(self, headless: bool = True, test_mode: bool = False, max_pages: int = 0,
                 start_date: date | None = None, end_date: date | None = None,
                 start_page: int = 1, window_ranges: list | None = None):
        self.headless = headless
        self.test_mode = test_mode
        self.max_pages = max_pages  # 0 = unlimited
        self.start_date = start_date  # lower bound (inclusive); None = no lower bound
        self.end_date = end_date      # upper bound (inclusive); None = no upper bound
        self.start_page = max(1, start_page)  # fast-forward past earlier pages
        self.window_ranges = window_ranges or []  # date windows (DD/MM/YYYY) for old-data back-fill
        self.browser = None
        self.context = None
        self.page = None
        self.browser_ua = None  # real browser UA, captured at init, used for downloads
        self.dedup = get_dedup_manager()
        self.detector = get_detector()
        self.alert = get_alert()
        self.proxy_manager = get_proxy_manager()
        self.crawled_count = 0
        self.skipped_count = 0
        self.downloaded_count = 0

    @staticmethod
    def parse_report_date(date_str: str) -> date | None:
        """
        Parse a report date string into a date object.

        Vietstock cards expose dates as DD/MM/YYYY (year may be 2 or 4 digits).
        Returns None if the string cannot be parsed.
        """
        if not date_str:
            return None
        for fmt in (_DATE_FMT_DMY, '%d/%m/%y'):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    async def init_browser(self):
        """Initialize browser with stealth settings"""
        logger.info("Initializing browser with stealth mode...")
        self.browser, self.context, self.page = await create_stealth_browser(
            headless=self.headless
        )
        # Capture the browser's real User-Agent for consistent, non-blocked downloads.
        # Vietstock rejects empty/bot-like UAs with HTTP 4xx; the browser UA always passes.
        self.browser_ua = await self.page.evaluate('navigator.userAgent')
        logger.info("Browser initialized successfully")

    async def close_browser(self):
        """Close browser and cleanup"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")

    def generate_pdf_filename(self, title: str, date_str: str) -> str:
        """Generate filename for PDF download (delegates to utils.pdf_helpers)."""
        return generate_pdf_filename(title, date_str)

    async def check_for_captcha(self) -> bool:
        """
        Check if current page has captcha/bot detection

        Returns:
            True if captcha detected
        """
        try:
            content = await self.page.content()
            title = await self.page.title()
            is_detected, reason = self.detector.detect_captcha(content, title)

            if is_detected:
                logger.warning(f"CAPTCHA/Bot detection detected: {reason}")

                # Take screenshot
                screenshot_path = (
                    LOG_PATH / f"captcha_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                await self.page.screenshot(path=str(screenshot_path))

                # Send alert
                await self.alert.log_captcha_alert(
                    url=self.page.url,
                    reason=reason,
                    screenshot_path=screenshot_path
                )

                return True
        except Exception as e:
            logger.error(f"Error checking for captcha: {e}")

        return False

    async def pause_on_captcha(self) -> None:
        """
        Pause the crawler for CAPTCHA_PAUSE_MINUTES after a captcha/bot-detection
        event (skill BUOC 5: "tam nghi 5 phut"). Emits a per-minute countdown so
        the cooldown is visible in monitoring, then the caller retries.
        """
        total_seconds = CAPTCHA_PAUSE_MINUTES * 60
        logger.warning(
            f"CAPTCHA detected - pausing {CAPTCHA_PAUSE_MINUTES} minutes "
            f"(anti-bot cooldown) before retrying..."
        )
        for remaining in range(total_seconds, 0, -60):
            logger.info(f"Captcha cooldown: ~{remaining // 60} min remaining")
            await asyncio.sleep(min(60, remaining))
        logger.info("Captcha cooldown finished - resuming crawl")

    async def navigate_to_target(self) -> bool:
        """
        Navigate to target URL and check for captcha/bot detection.

        If a captcha is detected, the crawler pauses CAPTCHA_PAUSE_MINUTES and
        retries, up to CAPTCHA_MAX_RETRIES attempts (skill BUOC 5).

        Returns:
            True if navigation succeeded without captcha, False otherwise
        """
        for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
            logger.info(f"Navigating to: {TARGET_URL} (attempt {attempt}/{CAPTCHA_MAX_RETRIES})")

            if not await safe_goto(self.page, TARGET_URL):
                logger.error("Failed to navigate to target URL")
                await asyncio.sleep(10)  # brief wait before retrying a failed load
                continue

            # Add human-like behavior
            await asyncio.sleep(2)
            await human_like_scroll(self.page, max_scrolls=2)

            # Check for captcha -> pause and retry
            if await self.check_for_captcha():
                await self.pause_on_captcha()
                continue

            logger.info("Navigation successful")
            return True

        logger.error(
            f"Navigation failed: captcha/bot-detection persisted after "
            f"{CAPTCHA_MAX_RETRIES} attempts"
        )
        return False

    async def _find_report_cards(self) -> list:
        """Find report card elements using multiple strategies. Returns list of elements."""
        all_found_items = []
        try:
            images = await self.page.query_selector_all('img[src*="edocs"]')
            logger.info(f"Found {len(images)} report thumbnail images")
            for img in images:
                parent = await img.query_selector(_XPATH_SELF)
                if parent:
                    grandparent = await parent.query_selector(_XPATH_SELF)
                    if grandparent:
                        all_found_items.append(grandparent)
        except Exception as e:
            logger.debug(f"Strategy 1 (edoc images) failed: {e}")
        try:
            download_links = await self.page.query_selector_all(
                'a:has-text("Tải về"), a:has-text("Download")'
            )
            logger.info(f"Found {len(download_links)} download links")
            for link in download_links:
                parent = await link.query_selector(_XPATH_SELF)
                if parent:
                    all_found_items.append(parent)
        except Exception as e:
            logger.debug(f"Strategy 2 (download links) failed: {e}")
        return all_found_items

    async def _parse_report_item(self, item, seen_urls) -> dict | None:
        """Parse a single report card item. Returns report dict or None."""
        try:
            links = await item.query_selector_all('a')
            for link in links:
                href = await link.get_attribute('href')
                if not href or href in seen_urls:
                    continue
                if 'edoc' not in href.lower() and 'download' not in href.lower():
                    continue
                seen_urls.add(href)
                full_url = BASE_URL + href if href.startswith('/') else href
                text = await item.inner_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                title = lines[0][:100] if lines else "Unknown Report"
                source = "Vietstock"
                for line in lines:
                    if 'Nguồn:' in line or 'nguồn:' in line.lower():
                        source = line.split(':')[-1].strip()
                        break
                date_str = ""
                import re
                for line in lines:
                    match = re.search(r'_(\d{1,2}/\d{1,2}/\d{2,4})_', line)
                    if match:
                        date_str = match.group(1)
                        break
                    match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', line)
                    if match:
                        date_str = match.group(1)
                        break
                title_ascii = title.encode('ascii', 'replace').decode('ascii')
                logger.info(f"Added report: {title_ascii[:50]}... from {source}")
                return {'title': title, 'url': full_url, 'date': date_str, 'source': source}
        except Exception as e:
            logger.debug(f"Error processing item: {e}")
        return None

    async def extract_report_links(self) -> list[dict]:
        """
        Extract report links from current page

        Returns:
            List of report dictionaries with metadata
        """
        reports = []
        try:
            await asyncio.sleep(3)
            await human_like_scroll(self.page, max_scrolls=1)
            logger.info("Extracting report links from page...")
            all_found_items = await self._find_report_cards()
            logger.info(f"Total potential items found: {len(all_found_items)}")
            seen_urls = set()
            for item in all_found_items:
                report = await self._parse_report_item(item, seen_urls)
                if report:
                    reports.append(report)
                    break
            logger.info(f"Successfully extracted {len(reports)} unique reports")
        except Exception as e:
            logger.error(f"Error extracting report links: {e}")
        return reports

    async def _download_pdf_via_requests(
        self, pdf_url: str, pdf_path: Path, filename: str
    ) -> str | None:
        """Download PDF via requests with browser cookies. Returns filename or None."""
        import requests
        cookies = await self.context.cookies()
        ua = self.browser_ua or get_random_user_agent()
        last_err = "unknown"
        for attempt in range(1, 4):
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            session.headers.update({'User-Agent': ua, 'Referer': str(TARGET_URL)})
            try:
                response = await asyncio.to_thread(
                    lambda s=session: s.get(pdf_url, stream=True, timeout=60)
                )
                if response.status_code < 400:
                    content_type = response.headers.get('content-type', '')
                    if 'pdf' in content_type.lower():
                        async with aiofiles.open(pdf_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    await f.write(chunk)
                        logger.info(f"Downloaded PDF: {filename}")
                        return filename
                    last_err = f"non-PDF content-type: {content_type}"
                else:
                    last_err = f"HTTP {response.status_code}"
            except requests.RequestException as e:
                last_err = str(e)
            logger.warning(
                f"Download attempt {attempt}/3 failed ({last_err}); "
                f"backing off before retry"
            )
            if attempt < 3:
                await asyncio.sleep(8 * attempt)
        logger.warning(
            f"Requests download exhausted after retries ({last_err}); "
            f"trying Playwright fallback"
        )
        return await self._download_pdf_playwright(pdf_url, pdf_path, filename)

    async def _download_pdf_via_playwright_nav(
        self, pdf_url: str, pdf_path: Path, filename: str
    ) -> str | None:
        """Download PDF by navigating to page and clicking download button."""
        if not await safe_goto(self.page, pdf_url):
            return None
        await asyncio.sleep(2)
        if await self.check_for_captcha():
            await self.pause_on_captcha()
            return None
        pdf_selectors = [
            'a[href$=".pdf"]',
            'a:has-text("PDF")',
            'a:has-text("Tải về")',
            'a:has-text("Download")',
            '.btn-download',
            '[class*="download"]'
        ]
        found_pdf_url = None
        for selector in pdf_selectors:
            try:
                pdf_elem = await self.page.query_selector(selector)
                if pdf_elem:
                    found_pdf_url = await pdf_elem.get_attribute('href')
                    if found_pdf_url:
                        break
            except Exception:
                continue
        if not found_pdf_url:
            title_ascii = filename.encode('ascii', 'replace').decode('ascii')
            logger.warning(f"No PDF link found for: {title_ascii}")
            return None
        if found_pdf_url.startswith('/'):
            found_pdf_url = BASE_URL + found_pdf_url
        async with self.page.expect_download() as download_info:
            await self.page.click(f'a[href="{found_pdf_url}"]')
        download = await download_info.value
        await download.save_as(str(pdf_path))
        logger.info(f"Downloaded PDF: {filename}")
        return filename

    async def download_pdf(self, report: dict) -> str | None:
        """
        Download PDF from report URL

        Args:
            report: Report dictionary with metadata

        Returns:
            Path to downloaded PDF or None if failed
        """
        try:
            pdf_url = report['url']
            filename = self.generate_pdf_filename(report['title'], report['date'])
            pdf_path = PDF_PATH / filename
            if pdf_path.exists():
                logger.info(f"PDF already exists: {filename}")
                return filename
            if 'downloadedoc' in pdf_url.lower() or pdf_url.lower().endswith('.pdf'):
                logger.info(f"Direct download from: {pdf_url}")
                return await self._download_pdf_via_requests(pdf_url, pdf_path, filename)
            else:
                return await self._download_pdf_via_playwright_nav(pdf_url, pdf_path, filename)
        except Exception as e:
            title_ascii = report['title'].encode('ascii', 'replace').decode('ascii')
            logger.error(f"Error downloading PDF for {title_ascii}: {e}")
            return None

    async def _download_pdf_playwright(
        self, pdf_url: str, pdf_path: Path, filename: str
    ) -> str | None:
        """
        Fallback method to download PDF using Playwright

        Args:
            pdf_url: Direct PDF download URL
            pdf_path: Path to save PDF
            filename: PDF filename

        Returns:
            Filename if successful, None otherwise
        """
        try:
            # Use the browser's own network stack (APIRequestContext), which shares
            # the session cookies and User-Agent. This avoids the page.goto
            # "Download is starting" error that breaks the expect_download approach,
            # and fetches the bytes directly.
            headers = {'Referer': str(TARGET_URL)}
            if self.browser_ua:
                headers['User-Agent'] = self.browser_ua

            response = await self.context.request.get(pdf_url, headers=headers, timeout=60000)

            if response.status >= 400:
                logger.error(
                    f"Playwright fallback failed: HTTP {response.status} for {pdf_url}"
                )
                return None

            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type.lower():
                logger.error(f"Playwright fallback: response is not PDF ({content_type})")
                return None

            body = await response.body()
            async with aiofiles.open(pdf_path, 'wb') as f:
                await f.write(body)

            logger.info(f"Downloaded PDF via Playwright (APIRequest): {filename}")
            return filename

        except Exception as e:
            logger.error(f"Playwright download failed: {e}")
            return None

    async def handle_pagination(self) -> bool:
        """
        Advance to the next page of analysis reports.

        Vietstock paginates the report list with an in-page JavaScript control,
        not real links:

            <ul id="report-paging">
              <li class="next"><a href="javascript:void(0)" page="2" aria-label="next">
            </ul>

        There is no URL to navigate to, so we must CLICK the next button and
        wait for the report list (#report-content) to refresh via AJAX. The
        selector is deliberately scoped to #report-paging: generic selectors
        like [class*="next"] or a[href*="page"] match unrelated sidebar/menu
        links and send the crawler off-site (the original bug).

        Returns:
            True if a new page was loaded, False if there are no more pages.
        """
        PAGINATION_TIMEOUT = 20000  # ms to wait for the list to refresh after click

        try:
            # Pagination control sits at the bottom of the page
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)

            # Locate the report-list next button (scoped, never matches sidebar)
            next_btn = await self.page.query_selector('#report-paging li.next a')
            if not next_btn:
                logger.info("No next-page button (#report-paging) - last page reached")
                return False

            # Detect a disabled/hidden next button (another last-page indicator)
            li_info = await next_btn.evaluate(
                """el => {
                    const li = el.closest('li');
                    return {
                        className: (li && li.className) || '',
                        style: (li && li.getAttribute('style')) || ''
                    };
                }"""
            )
            li_class = (li_info.get('className') or '').lower()
            li_style = (li_info.get('style') or '').lower()
            if 'disabled' in li_class or 'display: none' in li_style or 'display:none' in li_style:
                logger.info("Next-page button is disabled - last page reached")
                return False

            target_page = await next_btn.get_attribute('page')

            # Capture a signature of the current first report so we can detect
            # when the AJAX call actually swaps the list. If the click does not
            # change anything, treat it as the last page.
            old_sig = await self.page.eval_on_selector(
                '#report-content a[href*="bao-cao-phan-tich"]',
                'el => el.getAttribute("href")',
            )
            if not old_sig:
                logger.warning("Could not capture report signature - cannot paginate safely")
                return False

            logger.info(f"Loading next page (page={target_page}) via JS pagination click")
            await next_btn.click()

            try:
                await self.page.wait_for_function(
                    """(old) => {
                        const sel = '#report-content a[href*="bao-cao-phan-tich"]';
                        const el = document.querySelector(sel);
                        return el && el.getAttribute('href') !== old;
                    }""",
                    arg=old_sig,
                    timeout=PAGINATION_TIMEOUT,
                )
            except Exception:
                logger.info("Report list did not change after click - last page reached")
                return False

            # Let the new page settle
            await asyncio.sleep(2)
            logger.info("Next page loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error handling pagination: {e}")
            return False

    def _load_pending_files(self) -> list[Path]:
        """Return sorted list of pending CSV files (data_pending_*.csv)."""
        return sorted(CSV_FILE.parent.glob('data_pending_*.csv'))

    def _merge_pending(self, df) -> tuple:
        """Append all pending-file rows onto df. Returns (merged_df, count, files)."""
        files = self._load_pending_files()
        if not files:
            return df, 0, []
        frames = [df]
        count = 0
        for f in files:
            try:
                pdf = pd.read_csv(f, encoding='utf-8-sig')
                frames.append(pdf)
                count += len(pdf)
            except Exception as e:
                logger.warning(f"Could not read pending file {f.name}: {e}")
        merged = pd.concat(frames, ignore_index=True) if count else df
        return merged, count, files

    def _write_pending(self, data: list[dict]) -> Path:
        """Append a batch to a pending file (used when the main CSV is locked)."""
        pending = CSV_FILE.parent / f"data_pending_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_new = pd.DataFrame(data)
        df_new.to_csv(pending, mode='a', index=False,
                      header=not pending.exists(), encoding='utf-8-sig')
        return pending

    def _recover_pending(self) -> None:
        """Merge leftover pending files into the main CSV. Called at startup so
        records from a previous run that ended while the CSV was locked are recovered."""
        files = self._load_pending_files()
        if not files:
            return
        try:
            df = pd.read_csv(CSV_FILE, encoding='utf-8-sig') if CSV_FILE.exists() \
                else pd.DataFrame(columns=CSV_HEADERS)
            df, count, files = self._merge_pending(df)
            if count:
                df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
                for f in files:
                    try:
                        f.unlink()
                    except Exception:
                        pass
                logger.info(f"Recovered {count} pending record(s) into {CSV_FILE.name}")
        except PermissionError:
            logger.warning(
                f"{CSV_FILE.name} locked at startup - {len(files)} pending file(s) merge deferred"
            )
        except Exception as e:
            logger.error(f"Could not recover pending files: {e}")

    def save_to_csv(self, data: list[dict]):
        """
        Save crawled data to CSV, robust against the CSV being open in another
        program (Windows exclusive lock -> PermissionError).

        Strategy: retry the write a few times; if still locked, write the batch
        to a pending file (data_pending_*.csv) so no records are lost. Pending
        files are merged back into the main CSV as soon as it becomes writable
        again (and at next startup via _recover_pending).

        Args:
            data: List of report dictionaries
        """
        if not data:
            return

        df_new = pd.DataFrame(data)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if CSV_FILE.exists():
                    df = pd.read_csv(CSV_FILE, encoding='utf-8-sig')
                else:
                    df = pd.DataFrame(columns=CSV_HEADERS)
                df, pending_count, pending_files = self._merge_pending(df)
                df = pd.concat([df, df_new], ignore_index=True)
                df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
                for f in pending_files:
                    try:
                        f.unlink()
                    except Exception:
                        pass
                msg = f"Saved {len(data)} records to {CSV_FILE}"
                if pending_count:
                    msg += f" (+ {pending_count} recovered from pending)"
                logger.info(msg)
                return
            except PermissionError:
                if attempt < max_attempts:
                    logger.warning(
                        f"{CSV_FILE.name} locked (attempt {attempt}/{max_attempts}), "
                        f"retrying in 5s..."
                    )
                    time.sleep(5)
                else:
                    pending = self._write_pending(data)
                    logger.error(
                        f"{CSV_FILE.name} still locked after {max_attempts} attempts - "
                        f"saved {len(data)} records to pending file {pending.name} "
                        f"(will auto-merge when writable)"
                    )
            except Exception as e:
                logger.error(f"Error saving to CSV: {e}")
                return

    async def _process_single_report(self, report: dict) -> tuple[dict | None, date | None]:
        """Process a single report: filter, dedup, download."""
        rdate = self.parse_report_date(report['date'])
        if self.start_date and rdate and rdate < self.start_date:
            title_ascii = report['title'].encode('ascii', 'replace').decode('ascii')
            logger.info(
                f"Skipping (before start-date {self.start_date.isoformat()}): "
                f"{title_ascii}"
            )
            self.skipped_count += 1
            return None, rdate
        if self.end_date and rdate and rdate > self.end_date:
            title_ascii = report['title'].encode('ascii', 'replace').decode('ascii')
            logger.info(f"Skipping (after end-date {self.end_date.isoformat()}): {title_ascii}")
            self.skipped_count += 1
            return None, rdate
        if self.dedup.is_duplicate(report['url']):
            title_ascii = report['title'].encode('ascii', 'replace').decode('ascii')
            logger.info(f"Skipping duplicate: {title_ascii}")
            self.skipped_count += 1
            return None, rdate
        pdf_filename = await self.download_pdf(report) if DOWNLOAD_PDF else None
        record = {
            'id': f"{report['date']}_{self.crawled_count}",
            'title': report['title'],
            'source': report['source'],
            'date': report['date'],
            'pdf_url': report['url'],
            'pdf_filename': pdf_filename,
            'downloaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.dedup.add_to_seen(report['url'], record['id'])
        self.crawled_count += 1
        if pdf_filename:
            self.downloaded_count += 1
        if DOWNLOAD_PDF:
            await asyncio.sleep(random.uniform(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX))
        return record, rdate

    async def _collect_reports(self, reports: list[dict]):
        """Process one page's reports: optional date-range filter, dedup,
        download (if DOWNLOAD_PDF), build records, mark seen.

        Returns (new_data, parsed_dates). Shared by crawl() and
        crawl_by_windows() so the collection logic stays in one place.
        """
        new_data = []
        parsed_dates = []
        for report in reports:
            record, rdate = await self._process_single_report(report)
            if rdate:
                parsed_dates.append(rdate)
            if record:
                new_data.append(record)
        return new_data, parsed_dates

    async def apply_date_window(self, from_ddmmyyyy: str, to_ddmmyyyy: str) -> bool:
        """Apply the listing's date-range filter and click the search button so
        #report-content reloads to that period.

        Vietstock's default listing window is ~1 year, so plain pagination can
        never reach older data. Setting #fromDate/#toDate (DD/MM/YYYY, the format
        the jQuery datepicker expects) and clicking #btnSearchEDoc reloads the
        list for the chosen window; pagination then walks within that window.
        """
        try:
            await self.page.evaluate(
                """([f, t]) => {
                    if (window.jQuery) {
                        jQuery('#fromDate').val(f).trigger('change');
                        jQuery('#toDate').val(t).trigger('change');
                    } else {
                        const a = document.getElementById('fromDate');
                        const b = document.getElementById('toDate');
                        if (a) a.value = f;
                        if (b) b.value = t;
                    }
                }""",
                [from_ddmmyyyy, to_ddmmyyyy],
            )
            await asyncio.sleep(0.5)
            await self.page.click('#btnSearchEDoc')
            await asyncio.sleep(3)  # let the filtered list reload via AJAX
            await human_like_scroll(self.page, max_scrolls=1)
            logger.info(f"Applied date window {from_ddmmyyyy} -> {to_ddmmyyyy}")
            return True
        except Exception as e:
            logger.error(f"apply_date_window failed for {from_ddmmyyyy}-{to_ddmmyyyy}: {e}")
            return False

    async def _process_window(self, wf: str, wt: str) -> int:
        """Process a single date window. Returns number of new reports."""
        window_new = 0
        page_num = 1
        while True:
            logger.info(f"Processing page {page_num} (window {wf}-{wt})...")
            reports = await self.extract_report_links()
            new_data, _ = await self._collect_reports(reports)
            if new_data:
                self.save_to_csv(new_data)
                window_new += len(new_data)
            if self.test_mode:
                logger.info("Test mode: stopping after first page of this window")
                break
            if self.max_pages and page_num >= self.max_pages:
                logger.info(f"Reached max_pages ({self.max_pages}) in window {wf}-{wt}")
                break
            if not await self.handle_pagination():
                logger.info(f"Window {wf}-{wt} exhausted (no more pages)")
                break
            page_num += 1
        return window_new

    async def crawl_by_windows(self):
        """Crawl old data by applying successive date windows to the listing
        filter. self.window_ranges is a list of (from_ddmmyyyy, to_ddmmyyyy)
        tuples. For each window: load the listing, apply the filter, then walk
        pages until the window is exhausted (next button gone)."""
        try:
            await self.init_browser()
            ensure_paths_exist()
            self.dedup.init_csv_file()
            self._recover_pending()
            self.dedup.load_existing_data()

            logger.info(f"Starting window crawl: {len(self.window_ranges)} window(s)")

            for wf, wt in self.window_ranges:
                logger.info(f"===== Window {wf} -> {wt} =====")
                window_ready = False
                for attempt in (1, 2):
                    if not await self.navigate_to_target():
                        logger.warning(
                            f"navigate_to_target failed (attempt {attempt}) "
                            f"for window {wf}-{wt}"
                        )
                        continue
                    if not await self.apply_date_window(wf, wt):
                        logger.warning(
                            f"apply_date_window failed (attempt {attempt}) "
                            f"for window {wf}-{wt}"
                        )
                        continue
                    window_ready = True
                    break
                if not window_ready:
                    logger.warning(f"Could not load+apply window {wf}-{wt} after retry; skipping")
                    continue

                window_new = await self._process_window(wf, wt)

                if window_new == 0:
                    logger.warning(
                        f"Window {wf}-{wt} yielded 0 new reports — possible transient miss "
                        f"(captcha/timeout) OR a genuine site gap. Re-run to verify."
                    )

                if self.test_mode:
                    break

        except Exception as e:
            logger.error(f"Window crawl error: {e}")
            await self.alert.log_error_alert(
                str(e), f"Page URL: {self.page.url if self.page else 'N/A'}"
            )

        finally:
            await self.close_browser()

    async def crawl(self):
        """Main crawl method"""
        try:
            await self.init_browser()
            ensure_paths_exist()
            self.dedup.init_csv_file()
            self._recover_pending()
            self.dedup.load_existing_data()

            logger.info("Starting crawl...")
            page_num = 1
            need_navigate = True

            if self.start_page > 1:
                logger.info(
                    f"Fast-forwarding to page {self.start_page} "
                    f"(skipping pages 1-{self.start_page - 1})..."
                )
                if not await self.navigate_to_target():
                    logger.error("Could not navigate to begin fast-forward")
                    return
                clicked = 1
                while clicked < self.start_page:
                    if not await self.handle_pagination():
                        logger.warning(
                            f"Site has only {clicked} page(s) - starting from page {clicked}"
                        )
                        self.start_page = clicked
                        break
                    clicked += 1
                page_num = self.start_page
                need_navigate = False

            while True:
                logger.info(f"Processing page {page_num}...")
                if need_navigate:
                    if page_num == 1:
                        if not await self.navigate_to_target():
                            break
                    else:
                        if not await self.handle_pagination():
                            logger.info("No more pages available")
                            break
                need_navigate = True

                reports = await self.extract_report_links()
                if not reports:
                    logger.warning(f"No reports found on page {page_num}")
                    page_num += 1
                    continue

                new_data, parsed_dates = await self._collect_reports(reports)
                if new_data:
                    self.save_to_csv(new_data)

                if (self.start_date and parsed_dates
                        and all(d < self.start_date for d in parsed_dates)):
                    logger.info(
                        f"Reached page fully before start-date "
                        f"{self.start_date.isoformat()} - stopping crawl"
                    )
                    break

                if self.test_mode:
                    logger.info("Test mode: stopping after first page")
                    break

                if self.max_pages and page_num >= self.max_pages:
                    logger.info(f"Reached max_pages limit ({self.max_pages}) - stopping")
                    break

                page_num += 1

        except Exception as e:
            logger.error(f"Crawl error: {e}")
            await self.alert.log_error_alert(
                str(e), f"Page URL: {self.page.url if self.page else 'N/A'}"
            )

        finally:
            await self.close_browser()

    def print_summary(self):
        """Print crawl summary"""
        logger.info("=" * 50)
        logger.info("CRAWL SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total reports processed: {self.crawled_count + self.skipped_count}")
        logger.info(f"New reports crawled: {self.crawled_count}")
        logger.info(f"Skipped (duplicates): {self.skipped_count}")
        logger.info(f"PDFs downloaded: {self.downloaded_count}")
        logger.info(f"Data saved to: {CSV_FILE}")
        logger.info("=" * 50)


def _month_add(d: date, months: int) -> date:
    """Return the first of the month that is `months` after d's month."""
    total = d.year * 12 + (d.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def _build_windows(from_date: date, to_date: date, months_step: int) -> list[tuple]:
    """Split [from_date, to_date] into consecutive (DD/MM/YYYY, DD/MM/YYYY)
    windows of `months_step` months each (aligned to month starts). Used by
    --from-date mode so the listing date filter can be applied period by period."""
    windows = []
    start = date(from_date.year, from_date.month, 1)
    while start <= to_date:
        end_month = _month_add(start, months_step - 1)
        last_day = calendar.monthrange(end_month.year, end_month.month)[1]
        w_end = min(date(end_month.year, end_month.month, last_day), to_date)
        windows.append((start.strftime(_DATE_FMT_DMY), w_end.strftime(_DATE_FMT_DMY)))
        start = _month_add(start, months_step)
    return windows


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Vietstock Crawler')
    parser.add_argument('--start-date', type=str, default=None,
                        help='Only crawl reports on/after this date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None,
                        help='Only crawl reports on/before this date (YYYY-MM-DD)')
    parser.add_argument('--headless', type=str, default='true', choices=['true', 'false'],
                        help='Run browser in headless mode (default: true)')
    parser.add_argument('--test', action='store_true',
                        help='Test mode - crawl first page only')
    parser.add_argument('--max-pages', type=int, default=0,
                        help='Max number of pages to crawl (0 = unlimited)')
    parser.add_argument('--start-page', type=int, default=1,
                        help='Page to start extracting from (skip earlier pages; '
                             'use to re-crawl a specific page, e.g. --start-page 12)')
    parser.add_argument('--from-date', type=str, default=None,
                        help='Window-crawl mode: backfill from this date (YYYY-MM-DD) to '
                             'today/end-date by driving the listing date filter. Required '
                             'to reach reports older than the default ~1-year window.')
    parser.add_argument('--window-months', type=int, default=6,
                        help='Window size in months for --from-date mode (default 6)')

    args = parser.parse_args()

    headless = args.headless.lower() == 'true'

    def _parse_cli_date(s):
        if not s:
            return None
        return datetime.strptime(s, '%Y-%m-%d').date()

    start_date = _parse_cli_date(args.start_date)
    end_date = _parse_cli_date(args.end_date)
    if start_date:
        logger.info(f"Date filter: start_date={start_date.isoformat()}")
    if end_date:
        logger.info(f"Date filter: end_date={end_date.isoformat()}")

    if args.from_date:
        from_d = _parse_cli_date(args.from_date)
        if not from_d:
            logger.error(f"Invalid --from-date: {args.from_date}")
            sys.exit(1)
        to_d = end_date or datetime.now().date()
        windows = _build_windows(from_d, to_d, args.window_months)
        logger.info(
            f"Window-crawl mode: {from_d.isoformat()} -> {to_d.isoformat()}, "
            f"{args.window_months}-month windows = {len(windows)} window(s)"
        )
        crawler = VietstockCrawler(headless=headless, test_mode=args.test,
                                   max_pages=args.max_pages, window_ranges=windows)
        await crawler.crawl_by_windows()
    else:
        crawler = VietstockCrawler(headless=headless, test_mode=args.test,
                                   max_pages=args.max_pages,
                                   start_date=start_date, end_date=end_date,
                                   start_page=args.start_page)
        await crawler.crawl()
    crawler.print_summary()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Crawler interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
