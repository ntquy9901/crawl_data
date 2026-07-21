"""
News sitemap-backfill crawler — metadata-only (title/url/pub_date) cho báo tin tức
phổ thông không có RSS lịch sử: tuoitre, thanhnien, vietnamplus, vneconomy,
baodautu, tinnhanhchungkhoan.

Sitemap của tuoitre/thanhnien/vietnamplus đã nhúng sẵn title (image:title hoặc
news:title trong mỗi <url> block) → KHÔNG cần fetch từng bài. vneconomy/baodautu/
tinnhanhchungkhoan chỉ có <loc> và <lastmod>, title được suy từ URL slug
(đủ dùng cho metadata-only; fetch body sau để lấy title thật).

Floor thực tế của sitemap mỗi nguồn (khảo sát 2026-07-22):
  - tuoitre            floor ~2011-01 (StaticSitemaps/sitemaps-YYYY-M-d1-d2.xml)
  - thanhnien          floor ~2011-06 (sitemaps/sitemaps-YYYY-M-d1-d2.xml)
  - vietnamplus        floor ~2010-01 (sitemaps/news-YYYY-M.xml)
  - vneconomy          floor ~2007-01 (sitemap/news-YYYY-MM.xml)
  - baodautu           floor ~2013-01 (sitemaps/news-YYYY-M.xml)
  - tinnhanhchungkhoan floor ~2010-01 (sitemaps/news-YYYY-M.xml)

nld.com.vn KHÔNG có: domain redirect toàn bộ (kể cả RSS) sang tuoitre.vn/nld/*.

vnexpress KHÔNG có: sitemap shard theo ngày bị chặn bot (redirect 302) — cần stealth.

Plain HTTP (requests) — tất cả nguồn không chặn bot ở tầng sitemap.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

from base_news_crawler import BaseNewsCrawler, now_iso, parse_date, short_id

HN_TZ = timezone(timedelta(hours=7))

CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)


def clean_title(raw: str) -> str:
    """image:title = HTML-entity-escaped CDATA (&lt;![CDATA[...]]&gt;); news:title =
    real CDATA. Xử lý cả hai: unescape entity trước, rồi bóc CDATA nếu có."""
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    m = CDATA_RE.search(unescaped)
    return (m.group(1) if m else unescaped).strip()


ID_SUFFIX_RE = re.compile(r"-(?:post|d)\d+$")

def slug_to_title(url: str) -> str:
    stem = url.rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0]
    stem = ID_SUFFIX_RE.sub("", stem)
    return " ".join(w.capitalize() for w in stem.replace("-", " ").split())


SOURCES = {
    "tuoitre": {
        "index_url": "https://tuoitre.vn/sitemaps/index.rss",
        "shard_re": re.compile(
            r"<loc>(https://tuoitre\.vn/StaticSitemaps/sitemaps-(\d{4})-(\d{1,2})-\d+-\d+\.xml)</loc>"),
        "article_suffix": ".htm",
        "floor": date(2011, 1, 1),
    },
    "thanhnien": {
        "index_url": "https://thanhnien.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://thanhnien\.vn/sitemaps/sitemaps-(\d{4})-(\d{1,2})-\d+-\d+\.xml)</loc>"),
        "article_suffix": ".htm",
        "floor": date(2011, 6, 1),
    },
    "vietnamplus": {
        "index_url": "https://www.vietnamplus.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://www\.vietnamplus\.vn/sitemaps/news-(\d{4})-(\d{1,2})\.xml)</loc>"),
        "article_suffix": ".vnp",
        "floor": date(2010, 1, 1),
    },
    "vneconomy": {
        "index_url": "https://vneconomy.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://vneconomy\.vn/sitemap/news-(\d{4})-(\d{2})\.xml)</loc>"),
        "article_suffix": ".htm",
        "floor": date(2007, 1, 1),
    },
    "baodautu": {
        "index_url": "https://baodautu.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://baodautu\.vn/sitemaps/news-(\d{4})-(\d{1,2})\.xml)</loc>"),
        "article_suffix": ".html",
        "floor": date(2013, 1, 1),
    },
    "tinnhanhchungkhoan": {
        "index_url": "https://www.tinnhanhchungkhoan.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://www\.tinnhanhchungkhoan\.vn/sitemaps/news-(\d{4})-(\d{1,2})\.xml)</loc>"),
        "article_suffix": ".html",
        "floor": date(2010, 1, 1),
    },
}

URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.S)
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
LASTMOD_RE = re.compile(r"<lastmod>([^<]+)</lastmod>")
IMAGE_TITLE_RE = re.compile(r"<image:title>(.*?)</image:title>", re.S)
NEWS_TITLE_RE = re.compile(r"<news:title>(.*?)</news:title>", re.S)


def shards_in_range(index_xml: str, shard_re: re.Pattern, from_d: date, to_d: date) -> list[str]:
    """Trả list shard URL (oldest->newest) có (năm, tháng) trong [from_d, to_d]."""
    lo, hi = (from_d.year, from_d.month), (to_d.year, to_d.month)
    found = []
    for m in shard_re.finditer(index_xml):
        ym = (int(m.group(2)), int(m.group(3)))
        if lo <= ym <= hi:
            found.append((ym, m.group(1)))
    found.sort()
    return [u for _, u in found]


def parse_shard(xml_text: str, article_suffix: str) -> list[dict]:
    """Trích {url, pub_date, title} từ mỗi <url> block.
    Title từ image:title/news:title nếu có; fallback slug-to-title."""
    out = []
    for block in URL_BLOCK_RE.findall(xml_text):
        loc_m = LOC_RE.search(block)
        if not loc_m:
            continue
        url = loc_m.group(1).strip()
        if not url.endswith(article_suffix):
            continue
        lastmod_m = LASTMOD_RE.search(block)
        title_m = NEWS_TITLE_RE.search(block) or IMAGE_TITLE_RE.search(block)
        title = clean_title(title_m.group(1)) if title_m else ""
        if not title:
            title = slug_to_title(url)
        out.append({
            "url": url,
            "pub_date": lastmod_m.group(1) if lastmod_m else "",
            "title": title,
        })
    return out


class SitemapNewsCrawler(BaseNewsCrawler):
    """Sitemap-shard backfill (khác topology paginated-listing của BaseNewsCrawler nên
    không dùng crawl_latest/crawl_range/parse_listing — chỉ tái dùng __init__/fetch/
    _load_seen/_append (CSV I/O + retry-fetch dùng chung, tránh trùng lặp cafef_crawler)."""

    def __init__(self, source: str, csv_file=None, workers: int = 8):
        if source not in SOURCES:
            raise ValueError(f"unknown source: {source} (valid: {list(SOURCES)})")
        self.source = source  # phải set trước super().__init__ (dùng làm default csv_file)
        self.cfg = SOURCES[source]
        super().__init__(csv_file=csv_file, workers=workers)
        self.counters = {"kept": 0, "dup": 0, "out_of_range": 0, "fail_shard": 0}

    def _record(self, item: dict) -> dict:
        return {
            "id": short_id(item["url"]),
            "source": self.source,
            "title": item.get("title", ""),
            "category": "",
            "pub_date": item.get("pub_date", ""),
            "url": item["url"],
            "author": "",
            "lead": "",
            "pdf_url": "",
            "pdf_filename": "",
            "body": "",
            "collected_at": now_iso(),
        }

    def _process_shard_items(
        self, items: list[dict], from_date, end_date, max_articles
    ) -> tuple[bool, list[dict]]:
        """Process items from a single shard. Returns (should_stop, records_to_keep)."""
        stop = False
        records = []
        for it in items:
            d = parse_date(it.get("pub_date"))
            if d and (d < from_date or d > end_date):
                self.counters["out_of_range"] += 1
                continue
            if it["url"] in self.seen:
                self.counters["dup"] += 1
                continue
            self.seen.add(it["url"])
            records.append(self._record(it))
            self.counters["kept"] += 1
            if max_articles and self.counters["kept"] >= max_articles:
                stop = True
                break
        return stop, records

    def crawl_backfill(self, from_date: date | None = None, end_date: date | None = None,
                        max_articles: int = 0, test: bool = False) -> dict:
        from_date = from_date or self.cfg["floor"]
        end_date = end_date or datetime.now(HN_TZ).date()
        if test:
            from_date = max(from_date, end_date - timedelta(days=30))
        print(f"=== {self.source.upper()} BACKFILL {from_date} -> {end_date} "
              f"| workers={self.workers} ===")

        index_xml = self.fetch(self.cfg["index_url"])
        if not index_xml:
            print("! không đọc được sitemap index")
            return self.counters
        shards = shards_in_range(index_xml, self.cfg["shard_re"], from_date, end_date)
        if test:
            shards = shards[-2:]
        print(f"  shards in range: {len(shards)}")

        kept_batch = []
        t0 = time.time()
        stop = False
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(self.fetch, s): s for s in shards}
            for i, fut in enumerate(as_completed(futs), 1):
                if stop:
                    break
                xml_text = fut.result()
                if not xml_text:
                    self.counters["fail_shard"] += 1
                    continue
                items = parse_shard(xml_text, self.cfg["article_suffix"])
                stop, new_records = self._process_shard_items(
                    items, from_date, end_date, max_articles
                )
                kept_batch.extend(new_records)
                if len(kept_batch) >= 500:
                    self._append(kept_batch)
                    kept_batch = []
                if i % 50 == 0 or i == len(shards):
                    print(f"  [{i}/{len(shards)}] kept={self.counters['kept']} "
                          f"dup={self.counters['dup']} fail_shard={self.counters['fail_shard']} "
                          f"[{time.time()-t0:.0f}s]")
        if kept_batch:
            self._append(kept_batch)
        print(f"\nDONE  kept={self.counters['kept']}  dup={self.counters['dup']}  "
              f"out_of_range={self.counters['out_of_range']}  "
              f"fail_shard={self.counters['fail_shard']}  "
              f"[{time.time()-t0:.0f}s] -> {self.csv_file}")
        return self.counters


def _parse_date(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        print(f"! ngày không hợp lệ: {s} (YYYY-MM-DD)")
        sys.exit(2)


LATEST_WINDOW_DAYS = 7  # đủ phủ chu kỳ shard 5 ngày (tuoitre/thanhnien) + biên tháng (vietnamplus)


def main():
    ap = argparse.ArgumentParser(
        description="News sitemap crawler (tuoitre/thanhnien/vietnamplus) — backfill hoặc daily")
    ap.add_argument("--source", required=True, choices=list(SOURCES), help="nguồn cần crawl")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--latest", action="store_true",
                      help=f"daily: chỉ quét {LATEST_WINDOW_DAYS} ngày gần nhất (dùng cho cron)")
    mode.add_argument("--from-date", type=str, default=None,
                      help="YYYY-MM-DD (backfill, default: floor sitemap)")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD (default: hôm nay)")
    ap.add_argument("--max-articles", type=int, default=0, help="cap số bài (0=∞)")
    ap.add_argument("--workers", type=int, default=8, help="số luồng fetch shard song song")
    ap.add_argument("--csv", default=None,
                    help="file CSV output (default: data/<source>_articles.csv)")
    ap.add_argument("--test", action="store_true", help="giới hạn 2 shard gần nhất")
    args = ap.parse_args()

    crawler = SitemapNewsCrawler(args.source, csv_file=args.csv, workers=args.workers)
    end_d = _parse_date(args.end_date, datetime.now(HN_TZ).date())
    if args.latest:
        from_d = end_d - timedelta(days=LATEST_WINDOW_DAYS)
    else:
        from_d = _parse_date(args.from_date, crawler.cfg["floor"])
    crawler.crawl_backfill(from_d, end_d, max_articles=args.max_articles, test=args.test)


if __name__ == "__main__":
    main()
