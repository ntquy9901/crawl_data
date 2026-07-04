"""
Cafef news crawler — thu thập metadata + lead bài viết thị trường hằng ngày.

Nguồn & chiến lược theo skill `.claude/skills/source-news-download/SKILL.md`:
  - Hằng ngày (daily): RSS mỗi section (cafef.vn/<slug>.rss, ~50 item / ~3 ngày).
  - Backfill: sitemap shards theo tháng (2016–2026) — shard không gắn tag section,
    nên phải fetch từng bài để đọc JSON-LD articleSection (bounded).

Plain HTTP (requests) — cafef không cần Playwright/stealth.
Self-contained: không đụng utils/dedup.py (hardcode pdf_url) hay config Vietstock.
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from cafef_config import (
    BASE_URL, RSS_URL_FMT, SITEMAP_INDEX, SITEMAP_SHARD_RE,
    CAFEF_SECTIONS, DEFAULT_SECTIONS, CSV_HEADERS, CSV_FILE,
    REQUEST_TIMEOUT, REQUEST_DELAY, MAX_RETRIES, USER_AGENT,
    ensure_paths_exist,
)

UA_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.9"}
ID_RE = re.compile(r"-(\d{17,20})\.chn(?:[?#]|$)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
HN_TZ = timezone(timedelta(hours=7))


# ---------- helpers ----------
def now_iso() -> str:
    return datetime.now(HN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def fetch(url: str):
    """GET với retry. Trả về text hoặc None."""
    last = None
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=UA_HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(REQUEST_DELAY * (i + 1))
    print(f"  ! fetch fail {url} -> {last}")
    return None


def extract_id(url: str) -> str:
    m = ID_RE.search(url)
    return m.group(1) if m else ""


def strip_html(html: str) -> str:
    return WS_RE.sub(" ", HTML_TAG_RE.sub(" ", html or "")).strip()


def parse_pubdate(rfc822: str) -> str:
    if not rfc822:
        return ""
    try:
        dt = parsedate_to_datetime(rfc822)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=HN_TZ)
        return dt.astimezone(HN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")
    except Exception:  # noqa: BLE001
        return ""


# ---------- RSS ----------
ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)


def _field(item: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", item, re.S)
    return m.group(1).strip() if m else ""


def parse_rss(xml: str, section: str) -> list:
    out = []
    for item in ITEM_RE.findall(xml):
        link = _field(item, "link")
        if not link or ".chn" not in link:
            continue
        out.append({
            "id": extract_id(link),
            "title": strip_html(_field(item, "title")),
            "section": section,
            "pub_date": parse_pubdate(_field(item, "pubDate")),
            "article_url": link,
            "author": "",
            "lead": strip_html(_field(item, "description"))[:500],
            "collected_at": now_iso(),
        })
    return out


# ---------- crawler ----------
class CafefNewsCrawler:
    def __init__(self, sections=None, csv_file=CSV_FILE):
        self.sections = sections or DEFAULT_SECTIONS
        self.csv_file = Path(csv_file)
        ensure_paths_exist()
        self.seen = self._load_seen()
        self.counters = {"new": 0, "dup": 0, "fail": 0}

    def _load_seen(self) -> set:
        seen = set()
        if self.csv_file.exists():
            with open(self.csv_file, "r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    u = row.get("article_url")
                    if u:
                        seen.add(u)
        return seen

    def _init_csv(self):
        if not self.csv_file.exists():
            with open(self.csv_file, "w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow(CSV_HEADERS)

    def _append(self, records):
        self._init_csv()
        with open(self.csv_file, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            for r in records:
                w.writerow(r)

    def _collect(self, records) -> int:
        """Dedup + append. Trả về số record mới."""
        new = []
        for r in records:
            if not r["id"] or not r["article_url"]:
                self.counters["fail"] += 1
                continue
            if r["article_url"] in self.seen:
                self.counters["dup"] += 1
                continue
            self.seen.add(r["article_url"])
            new.append(r)
            self.counters["new"] += 1
        if new:
            self._append(new)
        return len(new)

    # --- daily mode (RSS) ---
    def crawl_daily(self, test=False):
        print(f"=== CAFEF DAILY | sections={self.sections} | test={test} ===")
        for slug in self.sections:
            label = CAFEF_SECTIONS.get(slug, slug)
            url = RSS_URL_FMT.format(slug=slug)
            print(f"[RSS] {label} ({slug})")
            xml = fetch(url)
            if not xml:
                self.counters["fail"] += 1
                continue
            recs = parse_rss(xml, slug)
            if test:
                recs = recs[:5]
            n = self._collect(recs)
            print(f"      parsed={len(recs)}  new={n}  dup={self.counters['dup']}")
            time.sleep(REQUEST_DELAY)
        self._summary()
        return self.counters

    def _summary(self):
        c = self.counters
        print(
            f"\nTOTAL  new={c['new']}  dedup-skip={c['dup']}  fail={c['fail']}"
            f"  -> {self.csv_file}"
        )


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Cafef news crawler (RSS daily)")
    ap.add_argument("--daily", action="store_true", help="chạy thu thập hằng ngày qua RSS")
    ap.add_argument("--sections", nargs="*", default=None,
                    help=f"slug section (default: {' '.join(DEFAULT_SECTIONS)})")
    ap.add_argument("--test", action="store_true", help="giới hạn 5 item/section")
    ap.add_argument("--csv", default=str(CSV_FILE), help="file CSV output")
    args = ap.parse_args()

    sections = args.sections or DEFAULT_SECTIONS
    invalid = [s for s in sections if s not in CAFEF_SECTIONS]
    if invalid:
        print(f"! section không hợp lệ: {invalid}")
        print(f"  hợp lệ: {list(CAFEF_SECTIONS)}")
        sys.exit(2)

    crawler = CafefNewsCrawler(sections=sections, csv_file=args.csv)
    crawler.crawl_daily(test=args.test)


if __name__ == "__main__":
    main()
