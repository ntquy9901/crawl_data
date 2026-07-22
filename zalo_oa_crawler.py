"""
Zalo OA Article Crawler — metadata + body via Zalo Official Account OpenAPI.

###############################################################################
# IMPORTANT LIMITATION                                                    #
#                                                                         #
# Zalo OA API is an OWNER-ONLY API. There is NO public feed endpoint      #
# (no RSS, no Graph API equivalent). The article/getslice endpoint only   #
# returns articles published BY THE OA WHOSE ACCESS TOKEN you are using.  #
#                                                                         #
# Compare:                                                                #
#   - Facebook Graph API: /page/posts works for ANY public page           #
#   - Telegram: t.me/s/<channel> is a public web wrapper (no API key)     #
#   - Zalo OA API: only the OA owner can list their own articles          #
#                                                                         #
# => This crawler ONLY works for OAs you own/manage (have access token).  #
#    You CANNOT crawl posts from arbitrary Vietnamese finance OAs like    #
#    SSI, HSC, VNDIRECT, CafeF via this API unless they grant you access. #
#                                                                         #
# Alternative approach for third-party OA content:                        #
#   - Zalo's "OA Landing Page" (https://zalo.me/<oa_id>) is a public      #
#     profile page that shows recent posts in the web view. This page     #
#     is NOT documented for programmatic access and may require            #
#     Playwright/stealth to scrape (similar to cafef/vndirect crawlers).  #
###############################################################################

Required env vars (in .env or OS):
    ZALO_OA_ACCESS_TOKEN=<OA Access Token (long-lived)>
    ZALO_OA_APP_ID=<App ID from Zalo Developer>

How to obtain credentials:
    1. Go to https://developers.zalo.me
    2. Create an App → get App ID and Secret Key
    3. Go to https://developers.zalo.me/tools/explorer
    4. Select "OA Access Token" → "Get Access Token"
    5. Authorize the OA you own → copy the access token
       (Token expires ~10 days; needs periodic refresh via OA OAuth2 flow)
    6. Add to .env: ZALO_OA_ACCESS_TOKEN=...  ZALO_OA_APP_ID=...

API docs: https://developers.zalo.me/docs/api/official-account-api

Usage:
    PYTHONUTF8=1 python zalo_oa_crawler.py --channel ssi_research --latest
    PYTHONUTF8=1 python zalo_oa_crawler.py --channel ssi_research --backfill
    PYTHONUTF8=1 python zalo_oa_crawler.py --all --latest
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests  # noqa: F401  # used when API call stubs are implemented

from base_news_crawler import DATA_PATH, BaseNewsCrawler, now_iso, parse_date, short_id

HN_TZ = timezone(timedelta(hours=7))
API_BASE = "https://openapi.zalo.me/v2.0"
ARTICLE_GETSLICE = "/article/getslice"
MAX_LIMIT = 50
REQUEST_TIMEOUT = 30
DEFAULT_SLEEP = 1.0
BACKFILL_SLEEP = 0.6
PROGRESS_INTERVAL = 5
BATCH_SIZE = 200

# List of target Zalo OA accounts
# NOTE: You can ONLY crawl OAs for which you hold a valid access token.
# These entries document known Vietnamese finance OAs but are NOT crawlable
# unless you own/manage them.
ZALO_OAS: dict[str, dict] = {
    "ssi_research": {
        "oa_id": "1401539871632701643",  # placeholder — real OA ID on Zalo
        "display": "SSI Research",
        "description": "SSI Securities - Báo cáo phân tích",
    },
    "hsc_research": {
        "oa_id": "",
        "display": "HSC Research",
        "description": "HSC Securities - Tin tức thị trường",
    },
    "vndirect_research": {
        "oa_id": "",
        "display": "VNDIRECT Research",
        "description": "VNDIRECT Securities - Phân tích đầu tư",
    },
}


def _get_access_token() -> str:
    token = os.environ.get("ZALO_OA_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError(
            "ZALO_OA_ACCESS_TOKEN not set. "
            "Get it from https://developers.zalo.me/tools/explorer"
        )
    return token


def _get_headers() -> dict:
    return {
        "access_token": _get_access_token(),
        "Content-Type": "application/json",
    }


def fetch_article_list(
    offset: int = 0, limit: int = MAX_LIMIT, article_type: str = "normal"
) -> dict:
    """Call GET /article/getslice to list articles of the authorized OA.

    TODO: This is a stub. Actual API call logic:
        url = f"{API_BASE}{ARTICLE_GETSLICE}"
        params = {"offset": offset, "limit": min(limit, MAX_LIMIT), "type": article_type}
        resp = requests.get(url, headers=_get_headers(), params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Zalo API error: {data.get('message', 'unknown')}")
        return data

    Response shape (from docs):
        {
          "data": {
            "medias": [
              {
                "id": "...",
                "title": "...",
                "description": "...",
                "author": "...",
                "cover": { "url": "..." },
                "status": "show",
                "type": "normal",
                "created_at": 1234567890,
                "updated_at": 1234567890,
              }
            ]
          }
        }
    """
    raise NotImplementedError("TODO: implement fetch_article_list using requests.get")


def fetch_article_detail(token: str) -> dict:
    """Fetch full article body via GET /article/getnormal (v3.0).

    TODO: Implement with:
        url = f"{API_BASE}/article/getnormal?token={token}"
        resp = requests.get(url, headers=_get_headers(), timeout=REQUEST_TIMEOUT)
        ...
    """
    raise NotImplementedError("TODO: implement fetch_article_detail")


class ZaloOACrawler(BaseNewsCrawler):
    source = "zalo_oa"

    def __init__(self, channel_key: str, csv_file=None, workers: int = 6):
        if channel_key not in ZALO_OAS:
            raise ValueError(
                f"unknown OA channel: {channel_key} (known: {list(ZALO_OAS)})"
            )
        self.channel_key = channel_key
        self.cfg = ZALO_OAS[channel_key]
        csv_file = csv_file or DATA_PATH / f"zalo_oa_{channel_key}_articles.csv"
        super().__init__(csv_file=csv_file, workers=workers)
        self.counters: dict[str, int] = {
            "kept": 0, "dup": 0, "out_of_range": 0, "errors": 0,
        }

    def _record(self, article: dict) -> dict:
        return {
            "id": short_id(article["url"]),
            "source": f"zalo_oa_{self.channel_key}",
            "title": article.get("title", ""),
            "category": self.channel_key,
            "pub_date": article.get("pub_date", ""),
            "url": article["url"],
            "author": self.cfg["display"],
            "lead": article.get("lead", ""),
            "pdf_url": "",
            "pdf_filename": "",
            "body": article.get("body", ""),
            "collected_at": now_iso(),
        }

    def crawl_latest(self, max_pages: int = 1):
        """Fetch the most recent articles (daily)."""
        print(f"=== ZALO OA @{self.channel_key} ({self.cfg['display']}) latest ===")
        kept_batch: list[dict] = []
        t0 = time.time()

        for page in range(max_pages):
            offset = page * MAX_LIMIT
            try:
                data = fetch_article_list(offset=offset, limit=MAX_LIMIT)
            except NotImplementedError:
                print("  [STUB] fetch_article_list not implemented. Would fetch and process.")
                break
            articles = data.get("data", {}).get("medias", [])
            if not articles:
                break
            for art in articles:
                record = self._record(self._transform(art))
                if record["url"] in self.seen:
                    self.counters["dup"] += 1
                    continue
                self.seen.add(record["url"])
                kept_batch.append(record)
                self.counters["kept"] += 1
            if len(kept_batch) >= BATCH_SIZE:
                self._append(kept_batch)
                kept_batch = []
            time.sleep(DEFAULT_SLEEP)

        if kept_batch:
            self._append(kept_batch)

        elapsed = time.time() - t0
        print(f"  DONE: kept={self.counters['kept']} dup={self.counters['dup']} [{elapsed:.0f}s]")
        return self.counters

    def crawl_backfill(
        self,
        from_date: date | None = None,
        end_date: date | None = None,
        max_articles: int = 0,
    ):
        """Paginate through ALL articles (newest→oldest) using offset.

        TODO: The Zalo OA API returns max 50 per call (MAX_LIMIT). Iterate
        offset until:
          - data.medias is empty (no more articles)
          - all articles are older than from_date
          - max_articles reached
        """
        print(
            f"=== ZALO OA @{self.channel_key} ({self.cfg['display']}) "
            f"{from_date or 'floor'} -> {end_date or 'now'} ==="
        )
        kept_batch: list[dict] = []
        t0 = time.time()
        offset = 0

        while True:
            if max_articles and self.counters["kept"] >= max_articles:
                break

            try:
                data = fetch_article_list(offset=offset, limit=MAX_LIMIT)
            except NotImplementedError:
                print("  [STUB] fetch_article_list not implemented. Would paginate all articles.")
                # Stub: simulate 3 pages of dummy data for testing
                if offset >= MAX_LIMIT * 2:
                    break
                data = {
                    "data": {
                        "medias": [
                            {
                                "id": f"stub_{offset + i}",
                                "title": f"Test Article {offset + i}",
                                "description": "Stub article for testing",
                                "author": self.cfg["display"],
                                "created_at": int(time.time()) - offset * 1000,
                            }
                            for i in range(3)
                        ]
                    }
                }

            articles = data.get("data", {}).get("medias", [])
            if not articles:
                print("  No more articles.")
                break

            for art in articles:
                record = self._record(self._transform(art))
                d = parse_date(record["pub_date"])
                if end_date and d and d > end_date:
                    continue
                if from_date and d and d < from_date:
                    print(f"  Reached articles before {from_date}, stopping.")
                    break
                if record["url"] in self.seen:
                    self.counters["dup"] += 1
                    continue
                self.seen.add(record["url"])
                kept_batch.append(record)
                self.counters["kept"] += 1

            # flush
            if len(kept_batch) >= BATCH_SIZE:
                self._append(kept_batch)
                kept_batch = []

            if self.counters["kept"] % PROGRESS_INTERVAL == 0:
                print(
                    f"  offset={offset} kept={self.counters['kept']} "
                    f"dup={self.counters['dup']} [{time.time() - t0:.0f}s]"
                )

            offset += MAX_LIMIT
            time.sleep(BACKFILL_SLEEP)

        if kept_batch:
            self._append(kept_batch)

        elapsed = time.time() - t0
        print(
            f"  DONE: kept={self.counters['kept']} dup={self.counters['dup']} "
            f"errors={self.counters['errors']} [{elapsed:.0f}s] -> {self.csv_file}"
        )
        return self.counters

    @staticmethod
    def _transform(art: dict) -> dict:
        """Convert a Zalo OA API article dict to the standard schema fields."""

        # TODO: fetch_article_detail(art["id"]) to get full body if needed
        created_at = art.get("created_at", 0)
        pub_date = (
            datetime.fromtimestamp(created_at, tz=HN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
            if created_at
            else ""
        )

        title = art.get("title", "")
        description = art.get("description", "")

        return {
            "url": f"https://zalo.me/{art.get('id', '')}",
            "title": title,
            "pub_date": pub_date,
            "lead": description[:500] if description else "",
            "author": art.get("author", ""),
            "body": "",  # TODO: populate from fetch_article_detail body field
            "category": art.get("type", "normal"),
        }


def _parse_date_or_none(s: str | None) -> date | None:
    return parse_date(s) if s else None


def main():
    ap = argparse.ArgumentParser(
        description="Zalo OA Article Crawler (OWN OA ONLY — see docstring)"
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--channel", choices=list(ZALO_OAS), help="OA key to crawl")
    group.add_argument("--all", action="store_true", help="crawl all configured OAs")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--latest", action="store_true", help="fetch recent articles")
    mode.add_argument("--backfill", action="store_true", help="fetch all articles with pagination")
    ap.add_argument("--from-date", type=str, default=None, help="YYYY-MM-DD (backfill)")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD (backfill)")
    ap.add_argument("--max-articles", type=int, default=0, help="cap (0=∞)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    channels = list(ZALO_OAS) if args.all else [args.channel]
    for ch in channels:
        crawler = ZaloOACrawler(ch, workers=args.workers)
        if args.latest:
            crawler.crawl_latest()
        else:
            crawler.crawl_backfill(
                from_date=_parse_date_or_none(args.from_date),
                end_date=_parse_date_or_none(args.end_date),
                max_articles=args.max_articles,
            )


if __name__ == "__main__":
    main()
