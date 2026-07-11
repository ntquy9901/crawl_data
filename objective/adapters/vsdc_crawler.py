"""VSDC corporate-action adapter (FR-4, FR-5; AD-7; Tier-1).

VSDC (``vsd.vn``) serves notice-LISTING pages whose entries are
``<li><h3><a href="/vi/ad/{id}">{TICKER}{code}: {title}</a></h3></li>``. This
adapter extracts those notices, keeps only VN30 constituents (AD-4/5), and
classifies ``event_type`` from the title (AD-11).

STATUS: parse_listing is verified against a captured ``/vi/ad`` fixture
(``tests/fixtures/vsdc/sample_vsdc_ad.html``). The canonical listing endpoint +
notice-detail (full raw_text) structure need live verification during the first
real backfill — see PRD OQ-4 / addendum.
"""
from __future__ import annotations

import re

from lxml import html as L

from objective.base_objective_crawler import BaseObjectiveCrawler
from objective.classify import classify_event_type
from objective.vn30 import is_vn30, load_vn30

_NOTICE_RE = re.compile(r"^\s*([A-Z]{3,5})(\d{4,})\s*[:\-]\s*(.+)$")
_DATE_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")


class VsdcCrawler(BaseObjectiveCrawler):
    source = "vsdc"
    source_tier = "tier1"
    base_url = "https://vsd.vn"

    def listing_url(self, page: int) -> str:
        # VSDC notice listing. Pagination param + canonical endpoint verified live
        # at first backfill; default to the public news listing.
        return f"{self.base_url}/vi/tin-tuc?page={page}"

    def parse_listing(self, html_text: str, page: int) -> list[dict]:
        items: list[dict] = []
        try:
            tree = L.fromstring(html_text)
        except Exception:  # noqa: BLE001 — malformed HTML → empty page, no crash
            return items
        for a in tree.xpath("//a"):
            text = (a.text_content() or "").strip()
            m = _NOTICE_RE.match(text)
            if not m:
                continue
            ticker = m.group(1)
            title = f"{ticker}{m.group(2)}: {m.group(3).strip()}"
            href = a.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"
            items.append({
                "url": url,
                "title": title,
                "company_code": ticker,
                "pub_date": self._date_near(a),
                "category": "vsdc_notice",
            })
        return items

    @staticmethod
    def _date_near(node) -> str:
        cur = node.getparent()
        for _ in range(3):
            if cur is None:
                return ""
            m = _DATE_RE.search(cur.text_content() or "")
            if m:
                return m.group(1)
            cur = cur.getparent()
        return ""

    def parse_article(self, html_text: str, item: dict) -> dict:
        code = (item.get("company_code") or "").upper()
        return {
            "title": item.get("title", ""),
            "publish_time": item.get("pub_date", ""),
            "company_code": code,
            "company_name": load_vn30().get(code, ""),  # AD-12 canonical
            # raw_text best-effort = title; full notice-body extraction needs the
            # detail-page structure (live verification pending).
            "raw_text": item.get("title", ""),
            "language": "vi",
            "category": "vsdc_notice",
            "event_type": classify_event_type(item.get("title", "")),
            "attachment_urls": [],
        }

    def _keep_payload(self, payload: dict) -> bool:
        code = (payload.get("company_code") or "").upper()
        return bool(code) and is_vn30(code)
