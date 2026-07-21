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
       python vndirect_crawler.py --latest --category company-note --lang vi  # bản tiếng Việt
Category: company-note (default) | sector-note | strategy-note | economics-note.

--lang vi/en (mặc định en): mỗi category có bản tiếng Việt RIÊNG (slug + nội dung khác, không
phải bản dịch UI của trang en) — hreflang="vi" trên trang /en/category/<cat>/ trỏ tới
/category/<slug-vi>/ (khảo sát 2026-07-18). Ghi vào CÙNG CSV, phân biệt bằng cột `category`
hậu tố `-vi` (vd `company-note-vi`) — dedup theo url nên không đụng bản en.
"""

import argparse
import re
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from base_news_crawler import UA, BaseNewsCrawler, now_iso, short_id, strip_html
from utils.body_extractor import extract_html_body

CATEGORIES = ["company-note", "sector-note", "strategy-note", "economics-note"]
# slug tiếng Việt cho mỗi category (từ hreflang="vi" trên trang /en/category/<cat>/)
VI_SLUGS = {
    "company-note": "bao-cao-phan-tich-dn",
    "sector-note": "bao-cao-nganh",
    "strategy-note": "bao-cao-chien-luoc",
    "economics-note": "bao-cao-vi-mo-vi-chuyen-de-su-kien",
}
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox",
]


class VndirectCrawler(BaseNewsCrawler):
    source = "vndirect"
    base_url = "https://www.vndirect.com.vn"

    def __init__(self, category="company-note", lang="en", **kw):
        super().__init__(workers=1, **kw)  # listing-complete + Playwright → sequence
        self.category = category
        self.lang = lang
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

    def _fetch_single_body(self, row: dict) -> bool:
        """Fetch body for a single row via Playwright. Returns True if body obtained."""
        url = row.get("url") or ""
        if not url:
            return False
        try:
            self._page.goto(url, timeout=60000, wait_until="domcontentloaded")
            try:
                self._page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:  # noqa: BLE001
                pass
            for _ in range(10):
                t = self._page.title()
                if "just a moment" not in t.lower() and "attention" not in t.lower():
                    break
                self._page.wait_for_timeout(3000)
            row["body"] = extract_html_body(self._page.content(), "vndirect")
            return bool(row["body"])
        except Exception as e:  # noqa: BLE001
            self._audit(f"BODY FAIL {url} -> {e}")
            return False

    def fetch_bodies(self, test: bool = False, limit: int = 0) -> None:
        """Re-fetch body cho các row body rỗng qua Playwright (Cloudflare). Ghi in-place."""
        import csv as _csv
        with open(self.csv_file, encoding="utf-8-sig", newline="") as f:
            rows = list(_csv.DictReader(f))
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        if "body" not in fieldnames:
            fieldnames.append("body")
        todo = [r for r in rows if not (r.get("body") or "").strip()]
        if test:
            todo = todo[:5]
        elif limit:
            todo = todo[:limit]
        print(f"--fetch-body: {len(todo)}/{len(rows)} rows need body (Playwright sequential)")
        if not todo:
            return
        self._ensure_browser()
        done = fail = 0
        try:
            for i, row in enumerate(todo, 1):
                if self._fetch_single_body(row):
                    done += 1
                else:
                    fail += 1
                if i % 20 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)} body={done} fail={fail}")
        finally:
            with open(self.csv_file, "w", encoding="utf-8-sig", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
            self._close()
        print(f"-> {self.csv_file}: body filled {done}/{len(todo)} (fail={fail})")

    # ---------- hooks ----------
    def listing_url(self, page: int) -> str:
        if self.lang == "vi":
            base = f"{self.base_url}/category/{VI_SLUGS[self.category]}/"
        else:
            base = f"{self.base_url}/en/category/{self.category}/"
        return base if page <= 1 else f"{base}page/{page}/"

    def parse_listing(self, html_text: str, page: int) -> list:
        """Mỗi card `news-item` → title + url + date + category + lead.
        Trang vi ghi năm dạng "năm 2026" thay vì "Year 2026" (en)."""
        items = []
        for card in re.split(r"news-item flex-item", html_text)[1:]:
            card = card[:2500]
            m_href = re.search(r'<h3>\s*<a href="([^"]+)"', card)
            if not m_href:
                continue
            m_title = re.search(r"<h3>\s*<a[^>]*>(.*?)</a>", card, re.S)
            m_day = re.search(r'date-day">(\d+)</span>', card)
            m_mon = re.search(r"<sup>/(\d+)</sup>", card)
            # scope tới đúng markup date-year (không chỉ tìm "năm" bất kỳ đâu trong card -
            # "năm" là từ phổ biến, có thể xuất hiện trong news-des/lead, vd "năm 2025")
            m_yr = re.search(r'date-year[^"]*"[^>]*>\s*(?:Year|năm)\s*(\d+)', card)
            m_lead = re.search(r"news-des[^>]*>(.*?)</div>", card, re.S)
            pub = (
                f"{m_day.group(1)}/{m_mon.group(1)}/{m_yr.group(1)}"
                if (m_day and m_mon and m_yr) else ""
            )
            category = self.category if self.lang != "vi" else f"{self.category}-vi"
            items.append({
                "url": m_href.group(1),
                "title": strip_html(m_title.group(1)) if m_title else "",
                "pub_date": pub,  # DD/MM/YYYY
                "category": category,
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
        mode.add_argument("--fetch-body", action="store_true",
                          help="re-fetch body qua Playwright (Cloudflare) cho row body rỗng")
        ap.add_argument("--category", default="company-note", choices=CATEGORIES)
        ap.add_argument("--lang", default="en", choices=["en", "vi"],
                        help="en (mặc định) hoặc vi (bản tiếng Việt riêng, category hậu tố -vi)")
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
                print(f"! ngày không hợp lệ: {s}")
                sys.exit(2)

        start, end = pd(args.from_date), pd(args.end_date)
        c = cls(category=args.category, lang=args.lang, csv_file=args.csv,
                max_articles=5 if args.test else args.max_articles)
        if args.fetch_body:
            c.fetch_bodies(test=args.test)
        elif args.range or start or end:
            c.crawl_range(start, end, max_pages=args.max_pages)
        else:
            c.crawl_latest(max_pages=args.max_pages or 1)


if __name__ == "__main__":
    VndirectCrawler.cli()
