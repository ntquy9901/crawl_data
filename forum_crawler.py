"""
forum_crawler — Crawl Vietnamese stock forums (traderviet.io, voz.vn, danketoan.com).

Kế thừa BaseNewsCrawler template method pattern.

Usage:
  python forum_crawler.py --source traderviet --latest --max-pages 5
  python forum_crawler.py --source traderviet --range --from-date 2026-01-01 --max-pages 50 --workers 4
  python forum_crawler.py --source voz --range --from-date 2026-06-01 --max-pages 20 --workers 2
  python forum_crawler.py --source danketoan --latest --max-pages 3
  python forum_crawler.py --list-sources
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests

from base_news_crawler import (
    BaseNewsCrawler,
    strip_html,
)

HN_TZ = timezone(timedelta(hours=7))

# ── Source definitions ───────────────────────────────────────────────────
FORUM_SOURCES = {
    "traderviet": {
        "name": "Traderviet.io Trading Forum",
        "base_url": "https://traderviet.io",
        "type": "forum",
        "description": "Diễn đàn trading Việt Nam — phân tích CK, Forex, Crypto",
        "sections": [
            {"id": 71, "slug": "phan-tich-chung-khoan-viet-nam", "name": "Phân tích Chứng khoán Việt Nam"},
            {"id": 77, "slug": "kien-thuc-trading-kinh-nghiem-trading", "name": "Kiến thức Trading"},
        ],
        "platform": "XenForo 2.x",
        "bot_protection": "none",
        "crawl_method": "HTTP requests",
    },
    "voz": {
        "name": "VOZ Financial Forum",
        "base_url": "https://voz.vn",
        "type": "forum",
        "description": "Diễn đàn VOZ — Kinh tế/Luật, Điểm báo, CLB Chứng khoán",
        "sections": [
            {"id": 92, "slug": "kinh-te-luat", "name": "Kinh tế / Luật (stock club)"},
        ],
        "platform": "XenForo 2.x (custom theme)",
        "bot_protection": "cloudflare (light)",
        "crawl_method": "HTTP requests + fallback retry",
    },
    "danketoan": {
        "name": "Dân Kế Toán — Stock Section",
        "base_url": "https://danketoan.com",
        "type": "forum",
        "description": "Diễn đàn Kế toán — chuyên mục Chứng khoán",
        "sections": [
            {"id": 242, "slug": "chung-khoan", "name": "Chứng khoán"},
        ],
        "platform": "XenForo 2.x",
        "bot_protection": "none",
        "crawl_method": "HTTP requests",
    },
}


class ForumCrawler(BaseNewsCrawler):
    """Crawl Vietnamese stock forums.

    Hook usage:
      - `source` set at runtime from --source
      - `listing_url(page)` → forum listing page
      - `parse_listing(html, page)` → list of thread dicts
      - `parse_article(html, item)` → full thread content
      - `next_page(cur, html)` → next page number or None
    """

    source = "forum"
    base_url = ""
    section_id = 0
    section_slug = ""
    bot_protection = "none"

    def __init__(self, forum_source, section_id, section_slug, **kwargs):
        self.forum_source = forum_source
        self.base_url = forum_source["base_url"]
        self.section_id = section_id
        self.section_slug = section_slug
        self.bot_protection = forum_source.get("bot_protection", "none")
        super().__init__(**kwargs)

    def listing_url(self, page: int) -> str:
        if page <= 1:
            return f"{self.base_url}/forums/{self.section_slug}.{self.section_id}/"
        return f"{self.base_url}/forums/{self.section_slug}.{self.section_id}/page-{page}"

    def parse_listing(self, html_text: str, page: int) -> list:
        """Parse XenForo 2.x forum listing → list[dict] with url, title, pub_date."""
        items = []
        if not html_text:
            self._audit("parse_listing: empty html_text")
            return items

        # Split by structItem--thread markers
        count = html_text.count('structItem structItem--thread')
        self._audit(f"parse_listing page {page}: structItem markers={count}")
        parts = html_text.split('structItem structItem--thread')

        for idx, part in enumerate(parts[1:], 1):
            try:
                item = self._parse_thread_block(part)
                if item and item.get("url"):
                    items.append(item)
                else:
                    self._audit(f"  part {idx}: no url found (title={item.get('title','?')[:30] if item else 'None'})")
            except Exception as e:
                self._audit(f"  part {idx}: error {e}")

        return items

    def _parse_thread_block(self, block: str) -> dict:
        title = ""
        url = ""
        pub_date = ""
        author = ""
        reply_count = 0
        view_count = 0

        # Thread URL: XenForo 2 uses /t/<slug>.<id>/ pattern
        m = re.search(r'href="(/t/[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if m:
            url = m.group(1)
            title = strip_html(m.group(2))

        # Fallback: look for any <a> with thread-like href
        if not url:
            m = re.search(r'href="(/[^"]*(?:thread|posts)/[^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if m:
                url = m.group(1)
                title = strip_html(m.group(2))

        if url:
            url = urljoin(self.base_url, url)

        # Author from data-author attribute (most reliable)
        m = re.search(r'data-author="([^"]+)"', block)
        if m:
            author = m.group(1)
        else:
            m = re.search(r'<a[^>]*class="username[^"]*"[^>]*>((?:(?!</a>).)*)</a>', block, re.DOTALL)
            if m:
                author = strip_html(m.group(1))

        # Date from <time datetime="..."> attribute (ISO format)
        m = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if m:
            pub_date = m.group(1)[:19]  # ISO format (strip timezone)

        # Reply count from pairs--justified
        m = re.search(r'<dt>\s*Trả lời\s*</dt>\s*<dd[^>]*>\s*([\d,]+)\s*</dd>', block)
        if m:
            try:
                reply_count = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        # View count
        m = re.search(r'<dt>\s*Xem\s*</dt>\s*<dd[^>]*>\s*([\d,]+)\s*</dd>', block)
        if m:
            try:
                view_count = int(m.group(1).replace(",", ""))
            except ValueError:
                pass

        if url:
            return {
                "url": url,
                "title": title,
                "pub_date": pub_date,
                "author": author,
                "reply_count": reply_count,
                "view_count": view_count,
            }
        return None

    def parse_article(self, html_text: str, item: dict) -> dict:
        """Parse full thread page → lead, body, author, date."""
        lead = ""
        body = ""
        author = item.get("author", "")
        pub_date = item.get("pub_date", "")

        # JSON-LD (voz.vn has rich schema.org/DiscussionForumPosting)
        jsonld_blocks = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html_text, re.DOTALL | re.IGNORECASE
        )
        for block in jsonld_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    if data.get("@type") in ("DiscussionForumPosting", "Article"):
                        if data.get("headline"):
                            lead = strip_html(data["headline"])[:500]
                        if data.get("description"):
                            if not lead:
                                lead = strip_html(data["description"])[:500]
                        if data.get("datePublished") and not pub_date:
                            pub_date = data["datePublished"][:19]
                        if data.get("author"):
                            author = strip_html(str(data.get("author", "")))
                elif isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict) and entry.get("@type") in (
                            "DiscussionForumPosting", "Article"
                        ):
                            if entry.get("headline") and not lead:
                                lead = strip_html(entry["headline"])[:500]
                            if entry.get("datePublished") and not pub_date:
                                pub_date = entry["datePublished"][:19]
            except json.JSONDecodeError:
                continue

        # Try to get body from first post
        body_parts = []

        # XenForo 2: <article class="message-body"> or <div class="message-content">
        m = re.search(
            r'<article[^>]*class="message[^"]*"[^>]*>(.*?)</article>',
            html_text, re.DOTALL
        )
        if not m:
            m = re.search(
                r'<div[^>]*class="message-content[^"]*"[^>]*>(.*?)</div>',
                html_text, re.DOTALL
            )
        if not m:
            m = re.search(
                r'<div[^>]*class="bbWrapper[^"]*"[^>]*>(.*?)</div>',
                html_text, re.DOTALL
            )

        if m:
            body = strip_html(m.group(1))[:10000]
        else:
            # Fallback: get meta description
            lead_m = re.search(
                r'<meta[^>]+name="description"[^>]*content="([^"]*)"',
                html_text
            )
            if lead_m:
                lead = lead_m.group(1)[:500]

        # Extract author from message if not already got
        if not author:
            m = re.search(
                r'<a[^>]*class="username[^"]*"[^>]*>((?:(?!</a>).)*)</a>',
                html_text, re.DOTALL
            )
            if m:
                author = strip_html(m.group(1))

        # Get thread title from <h1>
        if not item.get("title"):
            m = re.search(r'<h1[^>]*>((?:(?!</h1>).)*)</h1>', html_text, re.DOTALL)
            if m:
                item["title"] = strip_html(m.group(1))

        return {
            "title": item.get("title", ""),
            "lead": body[:500] if body else lead,
            "body": body,
            "author": author,
            "pub_date": pub_date,
        }

    def next_page(self, cur: int, html_text: str):
        """Detect next page link."""
        m = re.search(
            r'<a[^>]*class="pageNav-jump--next[^"]*"[^>]*href="([^"]*page-(\d+))"',
            html_text
        )
        if m:
            return int(m.group(2))
        # Try generic next link
        m = re.search(
            r'<a[^>]*class="[^"]*next[^"]*"[^>]*href="[^"]*page-(\d+)"',
            html_text
        )
        if m:
            return int(m.group(1))
        # Check if current page < total pages
        m = re.search(r'<a[^>]*class="pageNav-page[^"]*"[^>]*href="[^"]*page-(\d+)"', html_text)
        max_page = 0
        for m in re.finditer(r'<a[^>]*class="pageNav-page[^"]*"[^>]*href="[^"]*page-(\d+)"', html_text):
            p = int(m.group(1))
            if p > max_page:
                max_page = p
        if max_page > cur:
            return cur + 1
        # Check for "next" in pagination
        if 'pageNav-jump--next' in html_text or 'data-page-nav="next"' in html_text:
            return cur + 1
        return None

    def fetch(self, url: str):
        """Override fetch with forum-appropriate headers and retry."""
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        }
        last = None
        for i in range(self.retries):
            try:
                r = requests.get(url, headers=headers, timeout=self.timeout)
                if r.status_code == 200:
                    if "just a moment" in r.text[:500].lower() or "__cf_chl_tk" in r.text:
                        self._audit(f"CLOUDFLARE {url} (attempt {i+1})")
                        delay = self.fetch_delay * (i + 1) * 5
                        time.sleep(delay)
                        continue
                    r.encoding = "utf-8"
                    return r.text
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
            delay = self.fetch_delay * (i + 1) * 2
            time.sleep(delay)
        self._audit(f"FETCH FAIL {url} -> {last}")
        return None


class VozForumCrawler(ForumCrawler):
    """VOZ-specific forum crawler with different URL structure."""

    def listing_url(self, page: int) -> str:
        if page <= 1:
            return f"{self.base_url}/f/{self.section_slug}.{self.section_id}/"
        return f"{self.base_url}/f/{self.section_slug}.{self.section_id}/page-{page}"

    def parse_listing(self, html_text: str, page: int) -> list:
        items = []
        parts = html_text.split('structItem structItem--thread')
        seen_urls = set()
        for part in parts[1:]:
            try:
                item = self._parse_thread_block(part)
                if item and item.get("url") and item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    items.append(item)
            except Exception:
                continue
        return items


def main():
    ap = argparse.ArgumentParser(description="Forum Crawler — Vietnamese stock forums")
    ap.add_argument("--source", choices=list(FORUM_SOURCES.keys()), default="traderviet",
                    help="Forum source to crawl")
    ap.add_argument("--list-sources", action="store_true", help="List available sources")
    ap.add_argument("--section", type=int, default=None,
                    help="Section ID (default: first section)")

    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--latest", action="store_true", help="Latest threads")
    mode.add_argument("--range", action="store_true", help="Date range backfill")

    ap.add_argument("--from-date", type=str, default=None, help="YYYY-MM-DD")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD")
    ap.add_argument("--max-pages", type=int, default=0, help="0=∞")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--max-articles", type=int, default=0)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--test", action="store_true", help="Limit to 5 articles")

    args = ap.parse_args()

    if args.list_sources:
        print("\nAvailable forum sources:")
        for key, src in FORUM_SOURCES.items():
            print(f"  {key:<15} {src['name']}")
            print(f"  {'':15} Sections: {', '.join(s['name'] for s in src['sections'])}")
        print()
        return

    forum = FORUM_SOURCES[args.source]

    sections = forum["sections"]
    if args.section:
        sections = [s for s in sections if s["id"] == args.section]
    if not sections:
        print(f"Section {args.section} not found in {args.source}")
        sys.exit(1)

    def pd(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date: {s} (use YYYY-MM-DD)")
            sys.exit(2)

    start, end = pd(args.from_date), pd(args.end_date)

    for section in sections:
        print(f"\nCrawling {forum['name']} → section: {section['name']} (id={section['id']})")

        crawler_cls = VozForumCrawler if args.source == "voz" else ForumCrawler
        crawler = crawler_cls(
            forum_source=forum,
            section_id=section["id"],
            section_slug=section["slug"],
            csv_file=args.csv or None,
            workers=args.workers,
            batch_size=args.batch,
            max_articles=5 if args.test else args.max_articles,
            timeout=30,
            retries=5,
            fetch_delay=2.0,
        )

        if args.range or start or end:
            crawler.crawl_range(start, end, max_pages=args.max_pages)
        else:
            crawler.crawl_latest(max_pages=args.max_pages or 5)

        print(f"  Done: {crawler.counters['kept']} new threads | "
              f"dup={crawler.counters['dup']} fail={crawler.counters['fail']}")


if __name__ == "__main__":
    main()
