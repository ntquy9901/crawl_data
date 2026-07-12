"""Tier-2 RSS adapter framework (FR-15, AD-14).

News has no native ``company_code`` (it needs NLP/NER to extract a ticker from
the text), so Tier-2 records carry ``company_code=""`` and are written to the
COMPANION file ``news_unenriched_<source>_records.csv`` — never the unified VN30
dataset (``build_objective`` excludes ``news_unenriched_*``, AD-14). The RSS
item data (title / link / pubDate / description) is captured inline; no per-
article fetch (efficient — the feed IS the data for the raw corpus).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from objective.base_objective_crawler import DATA_PATH, BaseObjectiveCrawler
from objective.schema import EventType


def _pubdate_to_iso(pubdate: str) -> str:
    """RFC-822 pubDate (``Sun, 12 Jul 2026 07:14:25 +0700``) → ISO-8601."""
    if not pubdate:
        return ""
    try:
        return parsedate_to_datetime(pubdate).isoformat()
    except (TypeError, ValueError):
        return pubdate  # let to_utc try, or reject


class Tier2RssCrawler(BaseObjectiveCrawler):
    source_tier = "tier2"
    feed_url = ""       # subclass sets the RSS endpoint
    base_url = ""

    def __init__(self, csv_file=None, **kwargs):
        # companion file (AD-14): unenriched news, kept out of the unified dataset
        if csv_file is None:
            csv_file = DATA_PATH / "objective" / f"news_unenriched_{self.source}_records.csv"
        super().__init__(csv_file=csv_file, **kwargs)

    def listing_url(self, page: int) -> str:
        return self.feed_url

    def next_page(self, cur: int, html_text: str):  # RSS = single-page feed
        return None

    def parse_listing(self, xml_text: str, page: int) -> list[dict]:
        items: list[dict] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items
        for it in root.iter("item"):
            link = (it.findtext("link") or "").strip()
            if not link:
                continue
            items.append({
                "url": link,
                "title": (it.findtext("title") or "").strip(),
                "pub_date": _pubdate_to_iso((it.findtext("pubDate") or "").strip()),
                "description": (it.findtext("description") or "").strip(),
                "category": self.source,
            })
        return items

    def _fetch_and_parse(self, item: dict) -> dict | None:
        # RSS data is inline in the item — no per-article fetch. company_code is
        # null (unenriched, AD-14); event_type needs NLP (default OTHER).
        raw = item.get("description", "") or item.get("title", "")
        payload = {
            "title": item.get("title", ""),
            "publish_time": item.get("pub_date", ""),
            "company_code": "",          # unenriched — NLP fills later
            "company_name": "",
            "raw_text": raw,
            "language": "vi",
            "category": item.get("category", "news"),
            "event_type": EventType.OTHER,
            "attachment_urls": [],
        }
        return self._build_row(item["url"], raw, payload, item)

    def parse_article(self, html_text: str, item: dict) -> dict:  # not used (RSS inline)
        return {}
