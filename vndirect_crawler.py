"""
VNDIRECT crawler — research notes (Company/Sector/Strategy/Economics Note) từ vndirect.com.vn.

Khác SSI/HSC: VNDIRECT nằm sau **Cloudflare** + listing **JS-render** → phải dùng
**Playwright stealth** để fetch listing page (đợi `networkidle` cho card render, đợi
Cloudflare challenge tự giải). Nhưng mỗi card `news-item` đã đủ metadata (title +
article url + date + category + lead) → listing-complete, **không fetch từng bài**
(chỉ fetch listing page).

Sequence (1 browser, dùng cho các trang listing). workers=1 (Playwright sync).

Dùng: python vndirect_crawler.py --latest --category company-note
       python vndirect_crawler.py --range --from-date 2026-01-01 --category company-note
       python vndirect_crawler.py --latest --test --category company-note   # 5 bài thử
Category: company-note (default) | sector-note | strategy-note | economics-note.
"""

import argparse
import re
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from base_news_crawler import BaseNewsCrawler, CSV_HEADERS, UA, strip_html, short_id, now_iso

CATEGORIES = ["company-note", "sector-note", "strategy-note", "economics-note"]
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox",
]


class VndirectCrawler(BaseNewsCrawler):
    source = "vndirect"
    base_url = "https://www.vndirect.com.vn"

    def __init__(self, category="company-note", **kw):
        super().__init__(workers=1, **kw)  # listing-complete + Playwright → sequence
        self.category = category
        self._pw = self._browser = self._ctx = self._page = None

    # ---------- Playwright (stealth) ----------
    def _ensure_browser(self):
        if self._page is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True, args=LAUNCH_ARGS)
            self._ctx = self._browser.new_context(
                user_agent=UA, locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh",
                viewport={"width": 1920, "height": 1080},
            )
            Stealth().apply_stealth_sync(self._ctx)
            self._page = self._ctx.new_page()

    def _close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass

    def fetch(self, url: str):
        """Fetch listing page qua Playwright (vượt Cloudflare + đợi JS render)."""
        self._ensure_browser()
        try:
            self._page.goto(url, timeout=60000, wait_until="domcontentloaded")
            try:
                self._page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:  # noqa: BLE001
                pass
            for _ in range(10):  # chờ Cloudflare "Just a moment" tự giải
                t = self._page.title()
                if "just a moment" not in t.lower() and "attention" not in t.lower():
                    break
                self._page.wait_for_timeout(3000)
            return self._page.content()
        except Exception as e:  # noqa: BLE001
            self._audit(f"FETCH FAIL {url} -> {e}")
            return None

    def crawl_latest(self, max_pages=1):
        try:
            return super().crawl_latest(max_pages)
        finally:
            self._close()

    def crawl_range(self, start_date=None, end_date=None, max_pages=0):
        try:
            return super().crawl_range(start_date, end_date, max_pages)
        finally:
            self._close()

    # ---------- hooks ----------
    def listing_url(self, page: int) -> str:
        base = f"{self.base_url}/en/category/{self.category}/"
        return base if page <= 1 else f"{base}page/{page}/"

    def parse_listing(self, html_text: str, page: int) -> list:
        """Mỗi card `news-item` → title + url + date + category + lead."""
        items = []
        for card in re.split(r"news-item flex-item", html_text)[1:]:
            card = card[:2500]
            m_href = re.search(r'<h3>\s*<a href="([^"]+)"', card)
            if not m_href:
                continue
            m_title = re.search(r"<h3>\s*<a[^>]*>(.*?)</a>", card, re.S)
            m_day = re.search(r'date-day">(\d+)</span>', card)
            m_mon = re.search(r"<sup>/(\d+)</sup>", card)
            m_yr = re.search(r"Year\s*(\d+)", card)
            m_lead = re.search(r"news-des[^>]*>(.*?)</div>", card, re.S)
            pub = f"{m_day.group(1)}/{m_mon.group(1)}/{m_yr.group(1)}" if (m_day and m_mon and m_yr) else ""
            items.append({
                "url": m_href.group(1),
                "title": strip_html(m_title.group(1)) if m_title else "",
                "pub_date": pub,  # DD/MM/YYYY
                "category": self.category,
                "lead": strip_html(m_lead.group(1))[:500] if m_lead else "",
            })
        return items

    def next_page(self, cur: int, html_text: str):
        return cur + 1 if f"/page/{cur + 1}/" in html_text else None

    def _fetch_and_parse(self, item: dict):
        """Listing-complete → không fetch trang bài."""
        return {
            "id": short_id(item["url"]), "source": self.source,
            "title": item.get("title", ""), "category": item.get("category", ""),
            "pub_date": item.get("pub_date", ""), "url": item["url"],
            "author": "VNDIRECT", "lead": item.get("lead", ""),
            "pdf_url": "", "pdf_filename": "", "collected_at": now_iso(),
        }

    # ---------- CLI (thêm --category) ----------
    @classmethod
    def cli(cls):
        ap = argparse.ArgumentParser(description="VNDIRECT crawler (Playwright)")
        mode = ap.add_mutually_exclusive_group()
        mode.add_argument("--latest", action="store_true")
        mode.add_argument("--range", action="store_true")
        ap.add_argument("--category", default="company-note", choices=CATEGORIES)
        ap.add_argument("--from-date", type=str, default=None)
        ap.add_argument("--end-date", type=str, default=None)
        ap.add_argument("--max-pages", type=int, default=0)
        ap.add_argument("--max-articles", type=int, default=0)
        ap.add_argument("--csv", default=None)
        ap.add_argument("--test", action="store_true")
        args = ap.parse_args()

        def pd(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                print(f"! ngày không hợp lệ: {s}"); sys.exit(2)

        start, end = pd(args.from_date), pd(args.end_date)
        c = cls(category=args.category, csv_file=args.csv,
                max_articles=5 if args.test else args.max_articles)
        if args.range or start or end:
            c.crawl_range(start, end, max_pages=args.max_pages)
        else:
            c.crawl_latest(max_pages=args.max_pages or 1)


if __name__ == "__main__":
    VndirectCrawler.cli()
