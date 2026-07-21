"""
HSC crawler — Research Insights (article HTML) từ hsc.com.vn.

Site Next.js (SSR), không Cloudflare → plain HTTP. Article ở
`/en/research-insights-detail/<slug>`. Listing `/en/research-insights` không có
pagination rõ → daily-only (gói `--latest`). Cadence không đều (không daily).

Dùng: python hsc_crawler.py --latest             # toàn bộ research insights đang list
       python hsc_crawler.py --latest --test      # 5 bài thử
"""

import html
import re

from base_news_crawler import BaseNewsCrawler
from utils.body_extractor import extract_html_body


class HscCrawler(BaseNewsCrawler):
    source = "hsc"
    base_url = "https://www.hsc.com.vn"
    LISTING = f"{base_url}/en/research-insights"
    DETAIL_RE = re.compile(r"/en/research-insights-detail/([a-z0-9-]+)")

    def listing_url(self, page: int) -> str:
        return self.LISTING  # HSC chỉ có 1 trang listing

    def parse_listing(self, html_text: str, page: int) -> list:
        """Các link research-insights-detail (unique, bỏ echo __NEXT_DATA__)."""
        slugs = sorted(set(self.DETAIL_RE.findall(html_text)))
        return [
            {"url": f"{self.base_url}/en/research-insights-detail/{s}",
             "category": "Research Insight"}
            for s in slugs
        ]

    def parse_article(self, html_text: str, item: dict) -> dict:
        title = lead = pub = ""
        m = (re.search(r'<meta[^>]+property="og:title"[^>]*content="([^"]*)"', html_text)  # noqa: S8786
             or re.search(r"<title>(.*?)</title>", html_text, re.S))  # noqa: S8786
        if m:
            title = html.unescape(m.group(1)).strip()
        m = (re.search(r'<meta[^>]+property="og:description"[^>]*content="([^"]*)"', html_text)  # noqa: S8786
             or re.search(r'<meta[^>]+name="description"[^>]*content="([^"]*)"', html_text))  # noqa: S8786
        if m:
            lead = html.unescape(m.group(1))[:500]
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html_text)  # noqa: S8786
        if m:
            pub = m.group(1)[:19]  # ISO
        body = extract_html_body(html_text, self.source)
        return {"title": title, "lead": lead, "pub_date": pub,
                "author": "HSC", "body": body}

    def next_page(self, cur: int, html_text: str):
        return None  # HSC listing 1 trang → daily-only


if __name__ == "__main__":
    HscCrawler.cli()
