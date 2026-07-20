"""
vnexpress backfill qua Wayback Machine (archive.org) — vì vnexpress.net chặn bot ở tầng
sitemap-shard (xem `news_sitemap_crawler.py` docstring: redirect 302 kể cả Googlebot UA
và Playwright headless trần). archive.org không bị chặn (không phải vnexpress.net) và có
snapshot trang chủ + trang "kinh-doanh" từ 2001 tới nay.

Cách làm: liệt kê snapshot (CDX API) của 1 URL mục tiêu → fetch từng snapshot (nội dung
lưu trữ, không phải trang live) → trích link bài viết (mọi URL vnexpress.net dạng
`...-<6-8 số>.html`, pattern ổn định qua mọi thời kỳ đã khảo sát 2010-2026) + text liên kết
làm title best-effort. Subclass `BaseNewsCrawler` để tái dùng fetch/_load_seen/_append
(cùng lý do đã áp dụng cho `news_sitemap_crawler.py` — tránh trùng lặp CSV/retry helper).

GIỚI HẠN (chấp nhận, ghi rõ để không hiểu lầm dữ liệu):
- `pub_date` = NGÀY PHÁT HIỆN snapshot (khi bài xuất hiện trên trang chủ/kinh-doanh),
  KHÔNG PHẢI ngày xuất bản thật của bài (muốn chính xác phải fetch từng bài — quá tốn,
  ngoài phạm vi "metadata nhẹ"). Coi là ngày gần đúng.
- Trước ~2010, vnexpress dùng URL scheme khác (không có `-<số>.html`) → snapshot cũ hơn
  gần như không trích được link (đã verify: snapshot 2006 cho URL "kinh-doanh" trả 404).
  Phạm vi thực tế hữu ích: ~2010-2026.
- 2 mục tiêu snapshot:
  - trang chủ `vnexpress.net/` — cadence THÁNG (đủ dày vì trang chủ đổi nội dung liên tục,
    lấy mẫu rải khắp 2001-2026, tin tức chung không riêng kinh doanh).
  - `vnexpress.net/kinh-doanh` — cadence NGÀY từ 2018-12 (khi URL scheme này xuất hiện)
    tới nay, dày hơn vì đây là trang mục tiêu (kinh doanh/CK).

Dùng: python vnexpress_wayback_backfill.py --target homepage
      python vnexpress_wayback_backfill.py --target kinh-doanh --test
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, timezone

from base_news_crawler import BaseNewsCrawler, now_iso, short_id, strip_html

HN_TZ = timezone(timedelta(hours=7))
CDX_API = "https://web.archive.org/cdx/search/cdx"

# title capped at 300 chars (non-greedy .{0,300}?) - Wayback snapshots are sometimes
# garbled/truncated HTML; without a cap a missing closing </a> could make this match
# consume a large chunk of subsequent markup as "title".
ARTICLE_RE = re.compile(
    r'<a\b[^>]*href="(https?://[a-z0-9.-]*vnexpress\.net/[^"]+-\d{6,8}\.html)"[^>]*>(.{0,300}?)</a>',
    re.S,
)

TARGETS = {
    "homepage": dict(
        original_url="http://vnexpress.net/",
        cadence=6,  # collapse=timestamp:6 -> 1 snapshot/tháng
    ),
    "kinh-doanh": dict(
        original_url="https://vnexpress.net/kinh-doanh",
        cadence=8,  # collapse=timestamp:8 -> 1 snapshot/ngày
    ),
}


def extract_articles(html_text: str) -> dict[str, str]:
    """Trả {url: title} — title ưu tiên bản dài nhất nếu 1 url xuất hiện nhiều lần
    (mỗi bài thường có 2 link: ảnh thumbnail rỗng text + tiêu đề có text)."""
    out: dict[str, str] = {}
    for url, text in ARTICLE_RE.findall(html_text):
        title = strip_html(text)
        if title and len(title) > len(out.get(url, "")):
            out[url] = title
    return out


class VnexpressWaybackBackfill(BaseNewsCrawler):
    source = "vnexpress"

    def __init__(self, target: str, csv_file=None, workers: int = 10, **kw):
        if target not in TARGETS:
            raise ValueError(f"unknown target: {target} (valid: {list(TARGETS)})")
        self.target = target
        self.cfg = TARGETS[target]
        # archive.org (CDX query + snapshot fetch) chậm hơn site thường -> timeout cao hơn
        # default (20s) của BaseNewsCrawler, đã quan sát CDX query rộng (25 năm) mất 30-60s.
        kw.setdefault("timeout", 60)
        super().__init__(csv_file=csv_file, workers=workers, **kw)
        self.counters = {"kept": 0, "dup": 0, "fail_snapshot": 0}

    def list_snapshots(self) -> list[tuple[str, str]]:
        """CDX API -> list (timestamp, original_url), collapse theo cadence (6=tháng, 8=ngày)."""
        cdx_url = (
            f"{CDX_API}?url={self.cfg['original_url']}&output=json&filter=statuscode:200"
            f"&collapse=timestamp:{self.cfg['cadence']}&limit=20000"
        )
        text = self.fetch(cdx_url)
        if not text:
            return []
        try:
            rows = json.loads(text)
        except json.JSONDecodeError:
            return []
        if len(rows) <= 1:
            return []
        return [(row[1], row[2]) for row in rows[1:] if len(row) >= 3]

    def _record(self, url: str, title: str, snapshot_date: str) -> dict:
        return {
            "id": short_id(url),
            "source": self.source,
            "title": title,
            "category": self.target,
            "pub_date": snapshot_date,  # xấp xỉ (ngày phát hiện snapshot, xem docstring)
            "url": url,
            "author": "",
            "lead": "",
            "pdf_url": "",
            "pdf_filename": "",
            "body": "",
            "collected_at": now_iso(),
        }

    def run(self, test: bool = False) -> dict:
        print(f"=== VNEXPRESS WAYBACK BACKFILL target={self.target} | workers={self.workers} ===")
        snapshots = self.list_snapshots()
        if test:
            snapshots = snapshots[-3:]
        print(f"  snapshots: {len(snapshots)}")
        if not snapshots:
            print("! không lấy được danh sách snapshot")
            return self.counters

        kept_batch = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {
                ex.submit(self.fetch, f"https://web.archive.org/web/{ts}id_/{orig}"): ts
                for ts, orig in snapshots
            }
            for i, fut in enumerate(as_completed(futs), 1):
                ts = futs[fut]
                html_text = fut.result()
                if not html_text:
                    self.counters["fail_snapshot"] += 1
                    continue
                snapshot_date = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
                for url, title in extract_articles(html_text).items():
                    if url in self.seen:
                        self.counters["dup"] += 1
                        continue
                    self.seen.add(url)
                    kept_batch.append(self._record(url, title, snapshot_date))
                    self.counters["kept"] += 1
                if len(kept_batch) >= 500:
                    self._append(kept_batch)
                    kept_batch = []
                if i % 50 == 0 or i == len(snapshots):
                    print(f"  [{i}/{len(snapshots)}] kept={self.counters['kept']} "
                          f"dup={self.counters['dup']} fail={self.counters['fail_snapshot']} "
                          f"[{time.time()-t0:.0f}s]")
        if kept_batch:
            self._append(kept_batch)
        print(f"\nDONE  kept={self.counters['kept']}  dup={self.counters['dup']}  "
              f"fail_snapshot={self.counters['fail_snapshot']}  "
              f"[{time.time()-t0:.0f}s] -> {self.csv_file}")
        return self.counters


def main():
    ap = argparse.ArgumentParser(description="vnexpress backfill qua Wayback Machine")
    ap.add_argument("--target", required=True, choices=list(TARGETS))
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--test", action="store_true", help="giới hạn 3 snapshot gần nhất")
    args = ap.parse_args()
    crawler = VnexpressWaybackBackfill(args.target, csv_file=args.csv, workers=args.workers)
    crawler.run(test=args.test)


if __name__ == "__main__":
    main()
