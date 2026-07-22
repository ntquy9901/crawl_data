"""
VietnamBiz crawler — tin tức tài chính/kinh doanh từ vietnambiz.vn.

Hai chế độ:
  --latest (RSS /tin-moi-nhat.rss) — 50 bài mới nhất, đầy đủ metadata.
  --range --category X (listing /category/trang-N.html) — backfill theo danh mục.

Cả hai đều listing-complete (không fetch từng bài). Plain HTTP (requests).
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from base_news_crawler import BaseNewsCrawler, now_iso, short_id, strip_html

HN_TZ = timezone(timedelta(hours=7))

CATEGORIES = [
    "thoi-su", "doanh-nghiep", "chung-khoan", "tai-chinh", "hang-hoa",
    "nha-dat", "kinh-doanh", "quoc-te", "du-bao",
]

CATEGORY_LABELS = {
    "thoi-su": "Thời sự", "doanh-nghiep": "Doanh nghiệp",
    "chung-khoan": "Chứng khoán", "tai-chinh": "Tài chính",
    "hang-hoa": "Hàng hóa", "nha-dat": "Nhà đất",
    "kinh-doanh": "Kinh doanh", "quoc-te": "Quốc tế",
    "du-bao": "Dự báo",
}


class VietnamBizCrawler(BaseNewsCrawler):
    source = "vietnambiz"
    base_url = "https://vietnambiz.vn"
    RSS_URL = f"{base_url}/tin-moi-nhat.rss"

    def __init__(self, category: str = "", **kw):
        kw.setdefault("workers", 6)
        super().__init__(**kw)
        self.category = category

    # ==================== RSS (daily) ====================

    def crawl_latest(self, max_pages: int = 1):
        self._audit(f"RUN latest RSS source={self.source}")
        t0 = time.time()
        xml = self.fetch(self.RSS_URL)
        if not xml:
            return self.counters
        items = self._parse_rss(xml)
        self._audit(f"RSS items={len(items)}")
        self._process_items(items)
        self._summarize(t0)
        return self.counters

    @staticmethod
    def _rss_field(item_block: str, tag: str) -> str:
        m = re.search(
            rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>",
            item_block, re.S,
        )
        return m.group(1).strip() if m else ""

    @staticmethod
    def _normalize_tz(s: str) -> str:
        s = re.sub(r"GMT\+(\d+)", lambda m: f"+{int(m.group(1)):02d}00", s)
        s = re.sub(r"GMT-(\d+)", lambda m: f"-{int(m.group(1)):02d}00", s)
        return s

    @staticmethod
    def _parse_pubdate(s: str) -> str:
        if not s:
            return ""
        s = VietnamBizCrawler._normalize_tz(s)
        try:
            dt = parsedate_to_datetime(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=HN_TZ)
            return dt.astimezone(HN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
        except Exception:
            return ""

    def _parse_rss(self, xml: str) -> list:
        items = []
        for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
            link = self._rss_field(block, "link")
            if not link or ".htm" not in link:
                continue
            title = self._rss_field(block, "title")
            if not title:
                continue
            pub_raw = self._rss_field(block, "pubDate")
            desc_raw = self._rss_field(block, "description")
            items.append({
                "url": link,
                "title": title,
                "pub_date": self._parse_pubdate(pub_raw),
                "lead": strip_html(desc_raw)[:500] if desc_raw else "",
                "category": "",
            })
        return items

    # ==================== Listing (backfill) ====================

    def listing_url(self, page: int) -> str:
        if not self.category:
            raise ValueError("category required for listing mode")
        if page <= 1:
            return f"{self.base_url}/{self.category}.htm"
        return f"{self.base_url}/{self.category}/trang-{page}.html"

    def parse_listing(self, html_text: str, page: int) -> list:
        items = []
        seen = set()
        for m in re.finditer(
            r'<a[^>]*href="(/([a-z0-9][a-z0-9-]*)-(\d{13,})\.htm)"',
            html_text,
        ):
            url = f"{self.base_url}{m.group(1)}"
            if url in seen:
                continue
            seen.add(url)

            window = html_text[m.start():m.start() + 2000]

            title_attr = re.search(r'title="([^"]+)"', m.group(0))
            if title_attr:
                title = html_mod.unescape(title_attr.group(1)).strip()
            else:
                a_end = html_text.find("</a>", m.end())
                if a_end != -1 and a_end - m.end() < 500:
                    title = strip_html(html_mod.unescape(
                        html_text[m.end():a_end]))
                else:
                    continue
            if not title or len(title) < 5:
                continue

            cat_m = re.search(
                r'<a[^>]*class="[^"]*category[^"]*"[^>]*>(.*?)</a>',
                window[:600], re.S,
            )
            category = strip_html(
                html_mod.unescape(cat_m.group(1))
            ) if cat_m else CATEGORY_LABELS.get(self.category, "")

            time_m = re.search(
                r'<span[^>]*class="[^"]*timeago[^>]*need-get-timeago[^"]*"'
                r'[^>]*title="(\d{4}-\d{2}-\d{2})',
                window[:800],
            )
            pub_date = time_m.group(1) if time_m else ""

            lead = ""
            sapo_m = re.search(
                r'<div[^>]*class="[^"]*sapo[^"]*"[^>]*>(.*?)</div>',
                window[:800], re.S,
            )
            if sapo_m:
                lead = strip_html(
                    html_mod.unescape(sapo_m.group(1))
                )[:300]
            if not lead:
                lead_m = re.search(
                    r'<p[^>]*>(.*?)</p>', window[:500], re.S,
                )
                if lead_m:
                    lead = strip_html(
                        html_mod.unescape(lead_m.group(1))
                    )[:300]

            items.append({
                "url": url,
                "title": title,
                "pub_date": pub_date,
                "category": category,
                "lead": lead,
            })

        return items

    def next_page(self, cur: int, html_text: str):
        if cur == 1:
            return 2
        return cur + 1 if f"/trang-{cur + 1}.html" in html_text else None

    # ==================== listing-complete ====================

    def _fetch_and_parse(self, item: dict):
        return {
            "id": short_id(item["url"]),
            "source": self.source,
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "pub_date": item.get("pub_date", ""),
            "url": item["url"],
            "author": "VietnamBiz",
            "lead": item.get("lead", ""),
            "pdf_url": "",
            "pdf_filename": "",
            "collected_at": now_iso(),
        }

    # ==================== CLI ====================

    @classmethod
    def cli(cls):
        ap = argparse.ArgumentParser(description="VietnamBiz crawler")
        mode = ap.add_mutually_exclusive_group()
        mode.add_argument("--latest", action="store_true", help="RSS daily")
        mode.add_argument("--range", action="store_true", help="backfill theo khoảng ngày")
        ap.add_argument("--category", default="", choices=CATEGORIES + [""],
                        help="danh mục (bắt buộc với --range/--from-date)")
        ap.add_argument("--from-date", type=str, default=None)
        ap.add_argument("--end-date", type=str, default=None)
        ap.add_argument("--max-pages", type=int, default=0)
        ap.add_argument("--max-articles", type=int, default=0)
        ap.add_argument("--csv", default=None)
        ap.add_argument("--test", action="store_true")
        ap.add_argument("--workers", type=int, default=6)
        args = ap.parse_args()

        def pd(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                print(f"! ngày không hợp lệ: {s} (YYYY-MM-DD)")
                sys.exit(2)

        start, end = pd(args.from_date), pd(args.end_date)
        is_range = bool(args.range or start or end)

        if is_range and not args.category:
            ap.error("--category required with --range/--from-date")

        c = cls(
            category=args.category, csv_file=args.csv, workers=args.workers,
            max_articles=5 if args.test else args.max_articles,
        )

        if is_range:
            c.crawl_range(start, end, max_pages=args.max_pages)
        else:
            c.crawl_latest(max_pages=args.max_pages or 1)


if __name__ == "__main__":
    VietnamBizCrawler.cli()
