"""Vietstock per-company disclosure adapter (FR-16) — Tier-3 republish.

Calls Vietstock's ``/data/EventsTypeData`` POST endpoint directly (EXCEPTION to
the no-Vietstock-JSON-API rule — authorized 2026-07-12, see CLAUDE.md; scoped to
VN30 corporate-action events). The analysis-reports crawler (``crawler.py``)
remains browser-only.

Flow (HTTP, no browser in steady state):
  1. GET ``finance.vietstock.vn/<TICKER>/cong-bo-thong-tin.htm`` → extract the
     anti-forgery ``__RequestVerificationToken`` from the hidden input (session
     cookie auto-pairs).
  2. POST ``/data/EventsTypeData`` (code=<ticker>, pageSize, token) → JSON event
     rows (Title / Content / Time=/Date(ms)// / Code / CompanyName / Name).
  3. Each event → ObjectiveRecord (event_type via classify_event_type, UTC time).

Iterates the VN30 universe (AD-5). Resumable via the canonical url seen-set.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import requests

from base_news_crawler import UA_HEADERS, strip_html
from objective.base_objective_crawler import BaseObjectiveCrawler
from objective.classify import classify_event_type
from objective.vn30 import load_vn30

_TOKEN_RE = re.compile(r"name=__RequestVerificationToken type=hidden value=([A-Za-z0-9_\-]+)")
_VSDATE_RE = re.compile(r"/Date\((-?\d+)\)/")


def vsdate_to_utc(value) -> str:
    """``/Date(1784221200000)/`` → canonical UTC ``YYYY-MM-DDTHH:MM:SSZ`` (AD-3)."""
    m = _VSDATE_RE.search(str(value or ""))
    if not m:
        return ""
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def parse_events(json_text: str) -> list[dict]:
    """Parse the EventsTypeData response (handles BOM + nested ``[[...]]``)."""
    try:
        j = json.loads(json_text)
    except json.JSONDecodeError:
        j = json.loads(json_text.encode().decode("utf-8-sig"))  # strip UTF-8 BOM
    rows = j[0] if isinstance(j, list) and j and isinstance(j[0], list) else j
    return rows if isinstance(rows, list) else []


def event_to_payload(ticker: str, event: dict) -> dict:
    """Map one EventsTypeData row → an objective payload (for _build_row)."""
    content = event.get("Content", "") or ""
    name = event.get("Name", "") or ""
    title = event.get("Title", "") or name
    return {
        "title": title,
        "publish_time": vsdate_to_utc(event.get("Time")),
        "company_code": ticker,
        "company_name": event.get("CompanyName", ""),
        "raw_text": strip_html(content) or title,
        "language": "vi",
        "category": name,
        "event_type": classify_event_type(f"{name} {title}"),
        "attachment_urls": [],
    }


class VietstockDisclosureCrawler(BaseObjectiveCrawler):
    source = "vietstock"
    source_tier = "tier3"
    base_url = "https://finance.vietstock.vn"
    _api = "https://finance.vietstock.vn/data/EventsTypeData"

    def __init__(self, csv_file=None, tickers: list[str] | None = None,
                 page_size: int = 50, **kwargs):
        super().__init__(csv_file=csv_file, **kwargs)
        self.tickers = tickers
        self.page_size = page_size
        self._sess = requests.Session()
        self._sess.headers.update(UA_HEADERS)

    # ---- live helpers (not unit-tested; exercised by crawl) ----
    def _token(self, ticker: str) -> str | None:
        try:
            r = self._sess.get(f"{self.base_url}/{ticker}/cong-bo-thong-tin.htm", timeout=15)
        except requests.RequestException:
            return None
        m = _TOKEN_RE.search(r.text or "")
        return m.group(1) if m else None

    def _fetch_events(self, ticker: str, token: str, page: int = 1) -> list[dict]:
        data = {
            "eventTypeID": -1, "channelID": 0, "code": ticker, "catID": -1,
            "page": page, "pageSize": self.page_size,
            "orderBy": "Date1", "orderDir": "DESC",
            "__RequestVerificationToken": token,
        }
        hdrs = {"X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.base_url}/{ticker}/cong-bo-thong-tin.htm"}
        try:
            r = self._sess.post(self._api, data=data, headers=hdrs, timeout=15)
        except requests.RequestException:
            return []
        return parse_events(r.text)

    # ---- the crawl: iterate VN30, POST per ticker, build rows ----
    def crawl_latest(self, max_pages: int = 1):
        tickers = self.tickers if self.tickers is not None else list(load_vn30())
        self._audit(f"RUN vietstock-disclosure tickers={len(tickers)} page_size={self.page_size}")
        for ticker in tickers:
            token = self._token(ticker)
            if not token:
                self._audit(f"no token {ticker} — skip")
                continue
            events = self._fetch_events(ticker, token, page=1)
            rows = []
            for e in events:
                # synthetic per-event URL (canonicalize keeps the path) → unique document_id
                url = f"{self.base_url}/{ticker}/events/{e.get('EventID')}"
                key = self._dedup_key(url)
                if key in self.seen:
                    self.counters["dup"] += 1
                    continue
                payload = event_to_payload(ticker, e)
                if not self._keep_payload(payload):  # VN30 safety (ticker is VN30 by iteration)
                    continue
                row = self._build_row(url, e.get("Content", "") or "", payload, {"url": url})
                rows.append(row)
                self.seen.add(key)
                self.counters["kept"] += 1
            if rows:
                self._append(rows)
                self._audit(f"{ticker}: kept={len(rows)} dup={self.counters['dup']}")
        self._audit(f"RUN END kept={self.counters['kept']} dup={self.counters['dup']} "
                    f"-> {self.csv_file}")
        return self.counters


if __name__ == "__main__":  # CLI: python -m objective.adapters.vietstock_disclosure --latest
    VietstockDisclosureCrawler.cli()
