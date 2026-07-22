"""
Telegram public channel crawler — metadata-only (text/date/views) via t.me/s/<channel>.

Scrapes public Telegram channel history through Telegram's web wrapper (t.me/s/).
No API key needed. Plain HTTP (requests) + regex (structure is stable).

Known Vietnamese stock channels configured in CHANNELS dict. To add more:
  telemetr.io/en/catalog/vietnam or tgramlink.com.

Usage:
  PYTHONUTF8=1 python telegram_crawler.py --channel kakatachannel --latest
  PYTHONUTF8=1 python telegram_crawler.py --channel kakatachannel --backfill
  PYTHONUTF8=1 python telegram_crawler.py --all --backfill
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date, datetime, timedelta, timezone

from base_news_crawler import DATA_PATH, BaseNewsCrawler, now_iso, parse_date, short_id

HN_TZ = timezone(timedelta(hours=7))
TG_BASE = "https://t.me/s"
BATCH_SIZE = 200
PROGRESS_INTERVAL = 20
DEFAULT_SLEEP = 1.5
LATEST_MAX = 50

CHANNELS: dict[str, dict] = {
    "chungkhoanF0": {
        "username": "ChungKhoanF0",
        "display": "Chứng khoán F0",
    },
    "kakatachannel": {
        "username": "kakatachannel",
        "display": "Kakata Chứng Khoán - Kiến thức là sức mạnh",
    },
    "chungkhoanvietnammoon": {
        "username": "chungkhoanvietnammoon",
        "display": "Chứng khoán Việt Nam",
    },
    "chungkhoanvietnam2026": {
        "username": "ChungKhoanVietNam2026",
        "display": "Chứng Khoán Việt Nam 2026",
    },
    "vnwallstreet": {
        "username": "vnwallstreet",
        "display": "VN Wall Street",
    },
    "FinancialStreetVN": {
        "username": "FinancialStreetVN",
        "display": "Channel Phố Tài Chính",
    },
    "chungkhoantangtruong": {
        "username": "chungkhoantangtruong",
        "display": "Chứng khoán tăng trưởng",
    },
    "longshortlientuc": {
        "username": "longshortlientuc",
        "display": "Long Short Liên Tục",
    },
}

MESSAGE_WRAP_RE = re.compile(
    r'<div[^>]*class="tgme_widget_message_wrap[^"]*"[^>]*>.*?</div>\s*'
    r'(?=<div[^>]*class="tgme_widget_message_wrap|$|</div>\s*</div>)',
    re.S,
)
DATE_ATTR_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
TEXT_BLOCK_RE = re.compile(
    r'<div\s+class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S
)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
BEFORE_RE = re.compile(r'<a[^>]*href="[^"]*\?before=(\d+)"')
NEXT_LINK_RE = re.compile(r'<link\s+rel="prev"\s+href="[^"]*\?before=(\d+)"')
MORE_BTN_RE = re.compile(r'class="tme_messages_more"[^>]*href="[^"]*\?before=(\d+)"')
DATA_POST_RE = re.compile(r'data-post="([^"]+)"')


def strip_tags(text: str) -> str:
    """Strip all HTML tags and collapse whitespace."""
    return WS_RE.sub(" ", TAG_RE.sub("", text or "")).strip()


def extract_messages(html_text: str, username: str) -> list[dict]:
    """Parse t.me/s/ HTML into list of {url, title, pub_date, body}."""
    raw_blocks = MESSAGE_WRAP_RE.findall(html_text)
    out = []
    for block in raw_blocks:
        dp = DATA_POST_RE.search(block)
        msg_id = dp.group(1).split("/")[-1] if dp else ""

        date_m = DATE_ATTR_RE.search(block)
        pub_date = date_m.group(1) if date_m else ""

        text_m = TEXT_BLOCK_RE.search(block)
        body = strip_tags(text_m.group(1) if text_m else "")
        if not body:
            continue

        url = f"https://t.me/{username}/{msg_id}" if msg_id else ""
        if not url or not pub_date:
            continue

        title = body[:200] if len(body) > 200 else body
        out.append({"url": url, "title": title, "pub_date": pub_date, "body": body})
    return out


def find_before(html_text: str) -> str | None:
    """Find the ?before= pagination token for older messages."""
    for pattern in (MORE_BTN_RE, NEXT_LINK_RE, BEFORE_RE):
        m = pattern.search(html_text)
        if m:
            return m.group(1)
    return None


class TelegramCrawler(BaseNewsCrawler):
    source = "telegram"

    def __init__(self, channel_key: str, csv_file=None, workers: int = 6):
        if channel_key not in CHANNELS:
            raise ValueError(
                f"unknown channel: {channel_key} (known: {list(CHANNELS)})"
            )
        self.channel_key = channel_key
        self.cfg = CHANNELS[channel_key]
        csv_file = csv_file or DATA_PATH / f"telegram_{channel_key}_articles.csv"
        super().__init__(csv_file=csv_file, workers=workers)
        self.counters: dict[str, int] = {
            "kept": 0, "dup": 0, "out_of_range": 0, "pages": 0, "empty_pages": 0,
        }

    def _record(self, msg: dict) -> dict:
        return {
            "id": short_id(msg["url"]),
            "source": f"telegram_{self.channel_key}",
            "title": msg.get("title", ""),
            "category": self.channel_key,
            "pub_date": msg.get("pub_date", ""),
            "url": msg["url"],
            "author": self.cfg["display"],
            "lead": "",
            "pdf_url": "",
            "pdf_filename": "",
            "body": msg.get("body", ""),
            "collected_at": now_iso(),
        }

    def _process_messages(self, messages, from_date, end_date, max_messages, kept_batch):
        """Filter, dedup, and append messages. Returns (stop, updated_batch)."""
        stop = False
        for msg in messages:
            d = parse_date(msg.get("pub_date"))
            if d and end_date and d > end_date:
                continue
            if from_date and d and d < from_date:
                return True, kept_batch
            if msg["url"] in self.seen:
                self.counters["dup"] += 1
                continue
            self.seen.add(msg["url"])
            kept_batch.append(self._record(msg))
            self.counters["kept"] += 1
            if max_messages and self.counters["kept"] >= max_messages:
                return True, kept_batch
        return stop, kept_batch

    def _flush_batch(self, kept_batch):
        """Write batch to CSV if threshold reached."""
        if len(kept_batch) >= BATCH_SIZE:
            self._append(kept_batch)
            return []
        return kept_batch

    def _log_progress(self, t0):
        """Print progress every PROGRESS_INTERVAL pages."""
        if self.counters["pages"] % PROGRESS_INTERVAL == 0:
            elapsed = time.time() - t0
            print(
                f"  pages={self.counters['pages']} kept={self.counters['kept']} "
                f"dup={self.counters['dup']} [{elapsed:.0f}s]"
            )

    def crawl_channel(
        self,
        from_date: date | None = None,
        end_date: date | None = None,
        max_messages: int = 0,
        sleep: float = DEFAULT_SLEEP,
    ) -> dict:
        username = self.cfg["username"]
        url = f"{TG_BASE}/{username}"
        end_date = end_date or datetime.now(HN_TZ).date()
        print(
            f"=== TELEGRAM @{username} ({self.cfg['display']}) "
            f"{from_date or 'floor'} -> {end_date} ==="
        )

        kept_batch: list[dict] = []
        t0 = time.time()

        while url:
            text = self.fetch(url)
            if not text:
                self.counters["empty_pages"] += 1
                break

            messages = extract_messages(text, username)
            prev = find_before(text)

            if not messages:
                self.counters["empty_pages"] += 1
                if not prev:
                    break
                url = f"{TG_BASE}/{username}?before={prev}"
                continue

            self.counters["pages"] += 1
            stop, kept_batch = self._process_messages(
                messages, from_date, end_date, max_messages, kept_batch
            )
            kept_batch = self._flush_batch(kept_batch)
            self._log_progress(t0)

            if not prev or stop:
                break
            time.sleep(sleep)
            url = f"{TG_BASE}/{username}?before={prev}"

        if kept_batch:
            self._append(kept_batch)

        elapsed = time.time() - t0
        print(
            f"\n  DONE @{username}: kept={self.counters['kept']} "
            f"dup={self.counters['dup']} pages={self.counters['pages']} "
            f"empty={self.counters['empty_pages']} [{elapsed:.0f}s] -> {self.csv_file}"
        )
        return self.counters


def _parse_date_or_none(s: str | None) -> date | None:
    return parse_date(s) if s else None


def main():
    ap = argparse.ArgumentParser(description="Telegram public channel crawler")
    channel_group = ap.add_mutually_exclusive_group(required=True)
    channel_group.add_argument(
        "--channel", choices=list(CHANNELS), help="channel key to crawl"
    )
    channel_group.add_argument(
        "--all", action="store_true", help="crawl all configured channels"
    )
    ap.add_argument("--from-date", type=str, default=None, help="YYYY-MM-DD")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD")
    ap.add_argument("--max-messages", type=int, default=0, help="cap (0=∞)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP)
    args = ap.parse_args()

    channels = list(CHANNELS) if args.all else [args.channel]
    common = {
        "end_date": _parse_date_or_none(args.end_date) or datetime.now(HN_TZ).date(),
        "max_messages": args.max_messages,
        "sleep": args.sleep,
    }

    for ch in channels:
        crawler = TelegramCrawler(ch, workers=args.workers)
        crawler.crawl_channel(
            from_date=_parse_date_or_none(args.from_date),
            **common,
        )


if __name__ == "__main__":
    main()
