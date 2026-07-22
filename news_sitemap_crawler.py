"""
News sitemap-backfill crawler — metadata-only (title/url/pub_date) cho báo tin tức
phổ thông không có RSS lịch sử: tuoitre, thanhnien, vietnamplus, vneconomy,
baodautu, tinnhanhchungkhoan, cafebiz.

Sitemap của tuoitre/thanhnien/vietnamplus/cafebiz/nhipsongkinhdoanh đã nhúng sẵn
title (image:title hoặc news:title trong mỗi <url> block) → KHÔNG cần fetch từng bài.
vneconomy/baodautu/tinnhanhchungkhoan/vietnamnet/fica/theinvestor chỉ có <loc> và
<lastmod>, title được suy từ URL slug (đủ dùng cho metadata-only; fetch body sau
để lấy title thật).

Floor thực tế của sitemap mỗi nguồn (khảo sát 2026-07-22):
  - tuoitre               floor ~2011-01 (StaticSitemaps/sitemaps-YYYY-M-d1-d2.xml)
  - thanhnien             floor ~2011-06 (sitemaps/sitemaps-YYYY-M-d1-d2.xml)
  - vietnamplus           floor ~2010-01 (sitemaps/news-YYYY-M.xml)
  - vneconomy             floor ~2007-01 (sitemap/news-YYYY-MM.xml)
  - baodautu              floor ~2013-01 (sitemaps/news-YYYY-M.xml)
  - tinnhanhchungkhoan    floor ~2010-01 (sitemaps/news-YYYY-M.xml)
  - cafebiz               floor ~2019-10 (StaticSitemaps/sitemaps-YYYY-M-d1-d2.xml)
  - thoibaotaichinhvietnam floor ~2015 (single sitemaparticles-site-1.xml)
  - vietnamfinance        floor ~2020 (single sitemap.xml)
  - vietnamnet            floor ~2003 (sitemap-article-MM-YYYY-NN.xml, month-TRƯỚC year)
  - fica                  floor ~2019 (article-1..21.xml, non-date shards — fetch ALL filter theo lastmod)
  - theinvestor           floor ~2026-07 (single sitemap.xml)
  - nhipsongkinhdoanh     floor ~2020-01 (cms-articles-YYYY-MM.xml, có news:title)

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
    stem = url.rstrip("/").rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0]
    stem = ID_SUFFIX_RE.sub("", stem)
    return " ".join(w.capitalize() for w in stem.replace("-", " ").split())


def url_stub(url: str) -> str:
    stem = url.rsplit("/", 1)[-1]
    return stem.rsplit(".", 1)[0]


SLUG_BASED_SOURCES = {"vneconomy", "baodautu", "tinnhanhchungkhoan",
                       "thoibaotaichinhvietnam", "vietnamfinance",
                       "vietnamnet", "fica", "theinvestor",
                       "coin68", "nhadautu", "vietbao"}

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
    "cafebiz": {
        "index_url": "https://cafebiz.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://cafebiz\.vn/StaticSitemaps/sitemaps-(\d{4})-(\d{1,2})-\d+-\d+\.xml)</loc>"),
        "article_suffix": ".chn",
        "floor": date(2019, 10, 1),
    },
    "thoibaotaichinhvietnam": {
        "sitemap_url": "https://thoibaotaichinhvietnam.vn/sitemaparticles-site-1.xml",
        "article_suffix": ".html",
        "floor": date(2015, 1, 1),
    },
    "vietnamfinance": {
        "sitemap_url": "https://vietnamfinance.vn/sitemap.xml",
        "article_suffix": ".html",
        "floor": date(2020, 1, 1),
    },
    "vietnamnet": {
        "index_url": "https://vietnamnet.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://vietnamnet\.vn/sitemap-article-(\d{2})-(\d{4})-\d{2}\.xml)</loc>"),
        "article_suffix": ".html",
        "floor": date(2003, 1, 1),
        "ym_swapped": True,
    },
    "fica": {
        "index_url": "https://fica.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://fica\.dantri\.com\.vn/sitemaps/article-\d+\.xml)</loc>"),
        "article_suffix": ".htm",
        "floor": date(2019, 1, 1),
        "fetch_all_shards": True,
    },
    "theinvestor": {
        "sitemap_url": "https://theinvestor.vn/sitemap.xml",
        "article_suffix": ".html",
        "floor": date(2026, 7, 1),
    },
    "nhipsongkinhdoanh": {
        "index_url": "https://nhipsongkinhdoanh.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://nhipsongkinhdoanh\.vn/sitemap/cms-articles-(\d{4})-(\d{2})\.xml)</loc>"),
        "article_suffix": ".htm",
        "floor": date(2020, 1, 1),
    },
    "coin68": {
        "index_url": "https://coin68.com/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://coin68\.com/post-sitemap\d+\.xml)</loc>"),
        "article_suffix": "/",
        "floor": date(2021, 1, 1),
        "fetch_all_shards": True,
    },
    "thuonghieucongluan": {
        "index_url": "https://thuonghieucongluan.com.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://thuonghieucongluan\.com\.vn/sitemap-article-(\d{4})-(\d{2})-(\d{2})\.xml)</loc>"),
        "article_suffix": ".html",
        "floor": date(2013, 10, 1),
    },
    "nhadautu": {
        "sitemap_url": "https://nhadautu.vn/sitemap.xml",
        "article_suffix": ".html",
        "floor": date(2026, 1, 1),
    },
    "vietbao": {
        "index_url": "https://vietbao.vn/sitemap.xml",
        "shard_re": re.compile(
            r"<loc>(https://vietbao\.vn/sitemap/sitemap-blog-(\d{4})-(\d{2})\.xml)</loc>"),
        "article_suffix": ".html",
        "floor": date(2024, 1, 1),
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


def shards_in_range_swapped(index_xml: str, shard_re: re.Pattern, from_d: date, to_d: date) -> list[str]:
    """Giống shards_in_range nhưng URL có tháng TRƯỚC năm: sitemap-article-MM-YYYY-NN.xml.
    group(2)=MM, group(3)=YYYY."""
    lo, hi = (from_d.year, from_d.month), (to_d.year, to_d.month)
    found = []
    for m in shard_re.finditer(index_xml):
        ym = (int(m.group(3)), int(m.group(2)))
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
        has_sitemap_url = "sitemap_url" in self.cfg
        has_shard_re = "shard_re" in self.cfg
        assert has_sitemap_url != has_shard_re, \
            f"{source}: must have either sitemap_url OR shard_re, not both/neither"
        super().__init__(csv_file=csv_file, workers=workers)
        self.counters = {"kept": 0, "dup": 0, "out_of_range": 0, "fail_shard": 0}

    @staticmethod
    def _assess_title_quality(title: str) -> tuple[bool, str]:
        t = title.strip()
        if not t or len(t) < 3:
            return False, "too_short"
        words = t.split()
        if len(words) == 1 and len(words[0]) <= 3:
            return False, f"single_short_word:{words[0]}"
        if len(words) == 1 and words[0].isdigit():
            return False, "all_numeric"
        if re.search(r'\b(?:h|div)\d{1,3}\b', t, re.I):
            return False, "html_remnant"
        return True, "ok"

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

    def _crawl_shards(self, shards: list[str], from_date, end_date,
                       max_articles, test, title_samples) -> None:
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
                if test and self.source in SLUG_BASED_SOURCES:
                    title_samples.extend(
                        (url_stub(it["url"]), it["title"])
                        for it in items if it.get("title")
                    )
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

    def crawl_backfill(self, from_date: date | None = None, end_date: date | None = None,
                        max_articles: int = 0, test: bool = False) -> dict:
        from_date = from_date or self.cfg["floor"]
        end_date = end_date or datetime.now(HN_TZ).date()
        if test:
            from_date = max(from_date, end_date - timedelta(days=30))
        print(f"=== {self.source.upper()} BACKFILL {from_date} -> {end_date} "
              f"| workers={self.workers} ===")

        title_samples: list[tuple[str, str]] = []
        t0 = time.time()

        sitemap_url = self.cfg.get("sitemap_url")
        if sitemap_url:
            xml_text = self.fetch(sitemap_url)
            if not xml_text:
                print("! không đọc được single sitemap")
                return self.counters
            items = parse_shard(xml_text, self.cfg["article_suffix"])
            print(f"  articles in single sitemap: {len(items)}")
            if test and self.source in SLUG_BASED_SOURCES:
                title_samples.extend(
                    (url_stub(it["url"]), it["title"])
                    for it in items if it.get("title")
                )
            _, new_records = self._process_shard_items(
                items, from_date, end_date, max_articles
            )
            if new_records:
                self._append(new_records)
        else:
            index_xml = self.fetch(self.cfg.get("index_url", ""))
            if not index_xml:
                print("! không đọc được sitemap index")
                return self.counters
            if self.cfg.get("fetch_all_shards"):
                all_shards = [m.group(1) for m in self.cfg["shard_re"].finditer(index_xml)]
                shards = all_shards
                print(f"  all shards (non-date): {len(shards)}")
            elif self.cfg.get("ym_swapped"):
                shards = shards_in_range_swapped(index_xml, self.cfg["shard_re"], from_date, end_date)
            else:
                shards = shards_in_range(index_xml, self.cfg["shard_re"], from_date, end_date)
            if test and not self.cfg.get("fetch_all_shards"):
                shards = shards[-2:]
            print(f"  shards in range: {len(shards)}")
            self._crawl_shards(shards, from_date, end_date, max_articles, test, title_samples)

        elapsed = time.time() - t0
        print(f"\nDONE  kept={self.counters['kept']}  dup={self.counters['dup']}  "
              f"out_of_range={self.counters['out_of_range']}  "
              f"fail_shard={self.counters['fail_shard']}  "
              f"[{elapsed:.0f}s] -> {self.csv_file}")
        if test and self.source in SLUG_BASED_SOURCES and title_samples:
            self._print_title_quality_report(title_samples)
        return self.counters

    def _print_title_quality_report(self, samples: list[tuple[str, str]]) -> None:
        results = [(stub, title, *self._assess_title_quality(title)) for stub, title in samples]
        good = sum(1 for _, _, ok, _ in results if ok)
        bad = [(stub, title, reason) for stub, title, ok, reason in results if not ok]
        pct = 100.0 * good / len(samples) if samples else 0
        print(f"\n{'='*60}")
        print(f"TITLE QUALITY ASSESSMENT (slug-based: {self.source})")
        print(f"{'='*60}")
        print(f"Sampled {len(samples)} titles from 2 shards")
        print(f"  Good: {good}/{len(samples)} ({pct:.1f}%)")
        print(f"  Bad:  {len(bad)}")
        if bad:
            print(f"\n{'URL stub':<55} {'Generated title':<50} {'Issue':<20}")
            print("-" * 125)
            for stub, title, reason in bad:
                print(f"{stub[:52]:<55} {title[:47]:<50} {reason:<20}")
        print("\nFirst 10 sample titles:")
        for _, (_, title) in enumerate(samples[:10], 1):
            flag = "⚠ " if not self._assess_title_quality(title)[0] else "  "
            print(f"  {flag}{title[:90]}")
        print()


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
        description="News sitemap crawler (multiple sources) — backfill hoặc daily")
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
    ap.add_argument("--test", action="store_true",
                    help="giới hạn 2 shard gần nhất + đánh giá chất lượng title (slug-based)")
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
