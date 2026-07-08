"""
BaseNewsCrawler — khung chung cho crawler tin tức / báo cáo (plain HTTP).
Subclass chỉ override vài hook (xem dưới). Hỗ trợ:
  - khoảng ngày --from-date / --end-date (inclusive) và --latest (tin mới nhất)
  - --workers (fetch song song) + --batch (append theo lô)
  - audit log -> logs/<source>_audit.log (tiến độ + lỗi)
  - resume: dedup theo `url` → KHÔNG lấy lại từ đầu; re-run tiếp tục tự nhiên
"""

import argparse
import csv
import hashlib
import html
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.absolute()
DATA_PATH = PROJECT_ROOT / "data"
LOG_PATH = PROJECT_ROOT / "logs"
HN_TZ = timezone(timedelta(hours=7))

CSV_HEADERS = [
    "id", "source", "title", "category", "pub_date", "url",
    "author", "lead", "pdf_url", "pdf_filename", "collected_at", "body",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
UA_HEADERS = {"User-Agent": UA, "Accept-Language": "vi,en;q=0.9"}

_WS = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def now_iso() -> str:
    return datetime.now(HN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def strip_html(s: str) -> str:
    return _WS.sub(" ", _TAG.sub(" ", s or "")).strip()


def short_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def parse_date(s) -> date:
    """Parse nhiều format ngày → date (hoặc None). Dùng cho range filter."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


class BaseNewsCrawler:
    """Khung chung. Subclass override các hook (xem dưới) + đặt `source`/`base_url`."""

    # ---- subclass override ----
    source = "base"
    base_url = ""

    def __init__(self, csv_file=None, workers=6, batch_size=100, max_articles=0,
                 timeout=20, retries=3, fetch_delay=0.4):
        self.csv_file = Path(csv_file) if csv_file else DATA_PATH / f"{self.source}_articles.csv"
        self.workers = workers
        self.batch_size = batch_size
        self.max_articles = max_articles
        self.timeout = timeout
        self.retries = retries
        self.fetch_delay = fetch_delay
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        LOG_PATH.mkdir(parents=True, exist_ok=True)
        self.seen = self._load_seen()
        self.counters = {"kept": 0, "dup": 0, "fail": 0, "out_of_range": 0}
        self._stop = False

    # ---------------- hooks (subclass override) ----------------
    def listing_url(self, page: int) -> str:
        raise NotImplementedError

    def parse_listing(self, html_text: str, page: int) -> list:
        """Trả list[dict], mỗi item có 'url' (+ tuỳ chọn title/pub_date/category)."""
        raise NotImplementedError

    def parse_article(self, html_text: str, item: dict) -> dict:
        """Sau khi fetch trang bài → trả field bổ sung (lead, author, category, pdf_url...).
        Default: lấy og:description / meta description làm lead."""
        lead = ""
        m = (re.search(r'<meta[^>]+property="og:description"[^>]*content="([^"]*)"', html_text)
             or re.search(r'<meta[^>]+name="description"[^>]*content="([^"]*)"', html_text))
        if m:
            lead = html.unescape(m.group(1))[:500]
        return {"lead": lead}

    def next_page(self, cur: int, html_text: str):
        """Trả page kế, hoặc None nếu hết trang. Default: cur+1 (override để detect last page)."""
        return cur + 1

    # ---------------- HTTP ----------------
    def fetch(self, url: str):
        last = None
        for i in range(self.retries):
            try:
                r = requests.get(url, headers=UA_HEADERS, timeout=self.timeout)
                if r.status_code == 200:
                    r.encoding = "utf-8"  # ép UTF-8 chống mojibake
                    return r.text
                last = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            time.sleep(self.fetch_delay * (i + 1))
        self._audit(f"FETCH FAIL {url} -> {last}")
        return None

    # ---------------- CSV / dedup (resume) ----------------
    def _load_seen(self) -> set:
        seen = set()
        if self.csv_file.exists():
            try:
                with open(self.csv_file, encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        u = row.get("url")
                        if u:
                            seen.add(u)
            except Exception as e:  # noqa: BLE001
                print(f"warn: load seen: {e}")
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
                w.writerow({k: r.get(k, "") for k in CSV_HEADERS})

    # ---------------- audit log ----------------
    def _audit(self, msg):
        line = f"[{datetime.now(HN_TZ).strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        try:
            with open(LOG_PATH / f"{self.source}_audit.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:  # noqa: BLE001
            pass
        print(f"  {msg}")

    # ---------------- flow ----------------
    def _fetch_and_parse(self, item: dict):
        url = item["url"]
        h = self.fetch(url)
        if not h:
            return None
        extra = self.parse_article(h, item) or {}
        return {
            "id": short_id(url),
            "source": self.source,
            "title": item.get("title") or extra.get("title", ""),
            "category": item.get("category") or extra.get("category", ""),
            "pub_date": item.get("pub_date") or extra.get("pub_date", ""),
            "url": url,
            "author": extra.get("author", ""),
            "lead": extra.get("lead", ""),
            "pdf_url": extra.get("pdf_url", ""),
            "pdf_filename": extra.get("pdf_filename", ""),
            "body": extra.get("body", ""),
            "collected_at": now_iso(),
        }

    def _process_items(self, items, start_date=None, end_date=None):
        """Lọc range + dedup → fetch song song theo batch → save. Trả số kept."""
        todo = []
        for it in items:
            u = it.get("url")
            if not u:
                continue
            d = parse_date(it.get("pub_date"))
            if start_date and d and d < start_date:
                self.counters["out_of_range"] += 1
                continue
            if end_date and d and d > end_date:
                self.counters["out_of_range"] += 1
                continue
            if u in self.seen:
                self.counters["dup"] += 1
                continue
            todo.append(it)

        kept_batch = []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            for i in range(0, len(todo), self.batch_size):
                if self._stop:
                    break
                chunk = todo[i:i + self.batch_size]
                futs = {ex.submit(self._fetch_and_parse, it): it for it in chunk}
                for fut in as_completed(futs):
                    it = futs[fut]
                    try:
                        rec = fut.result()
                    except Exception as e:  # noqa: BLE001
                        self.counters["fail"] += 1
                        self._audit(f"ERROR {it.get('url')} -> {e}")
                        continue
                    if not rec:
                        self.counters["fail"] += 1
                        continue
                    self.seen.add(rec["url"])
                    kept_batch.append(rec)
                    self.counters["kept"] += 1
                    if self.max_articles and self.counters["kept"] >= self.max_articles:
                        self._stop = True
                        break
                if kept_batch:
                    self._append(kept_batch)
                    kept_batch = []
                    self._audit(f"batch kept={self.counters['kept']} dup={self.counters['dup']} "
                                f"fail={self.counters['fail']} oor={self.counters['out_of_range']}")
                if self._stop:
                    break
        if kept_batch:
            self._append(kept_batch)
        return self.counters["kept"]

    def crawl_latest(self, max_pages=1):
        """Lấy tin mới nhất (chạy daily)."""
        self._audit(f"RUN latest source={self.source} "
                    f"workers={self.workers} batch={self.batch_size}")
        t0 = time.time()
        page = 1
        while page <= max_pages and not self._stop:
            url = self.listing_url(page)
            self._audit(f"page {page}: {url}")
            h = self.fetch(url)
            if not h:
                break
            items = self.parse_listing(h, page)
            self._audit(f"page {page}: items={len(items)}")
            if not items:
                break
            self._process_items(items)
            if self._stop:
                break
            nxt = self.next_page(page, h)
            if nxt is None or nxt <= page:
                break
            page = nxt
        self._summarize(t0)
        return self.counters

    def crawl_range(self, start_date=None, end_date=None, max_pages=0):
        """Paginate listing (newest→oldest), lọc theo [start,end].
        Dừng khi qua start hoặc hết trang."""
        self._audit(f"RUN range source={self.source} {start_date}..{end_date} "
                    f"workers={self.workers} batch={self.batch_size} max_pages={max_pages}")
        t0 = time.time()
        page = 1
        while not self._stop:
            if max_pages and page > max_pages:
                self._audit(f"reached max_pages={max_pages}")
                break
            url = self.listing_url(page)
            self._audit(f"page {page}: {url}")
            h = self.fetch(url)
            if not h:
                break
            items = self.parse_listing(h, page)
            self._audit(f"page {page}: items={len(items)} kept_so_far={self.counters['kept']} "
                        f"dup={self.counters['dup']} oor={self.counters['out_of_range']}")
            if not items:
                break
            self._process_items(items, start_date, end_date)
            # dừng nếu cả page đều cũ hơn start_date (đã qua khoảng cần lấy)
            if start_date:
                dates = [parse_date(it.get("pub_date")) for it in items]
                parsed = [d for d in dates if d]
                if parsed and len(parsed) == len(items) and all(d < start_date for d in parsed):
                    self._audit(f"page {page} all before start {start_date} -> stop")
                    break
            nxt = self.next_page(page, h)
            if nxt is None or nxt <= page:
                self._audit(f"last page reached at {page}")
                break
            page = nxt
        self._summarize(t0)
        return self.counters

    def _summarize(self, t0):
        c = self.counters
        self._audit(f"RUN END kept={c['kept']} dup={c['dup']} oor={c['out_of_range']} "
                    f"fail={c['fail']} elapsed={time.time()-t0:.0f}s -> {self.csv_file}")

    # ---------------- CLI (subclass gọi) ----------------
    @classmethod
    def cli(cls):
        ap = argparse.ArgumentParser(description=f"{cls.source} crawler")
        mode = ap.add_mutually_exclusive_group()
        mode.add_argument("--latest", action="store_true", help="lấy tin mới nhất (vd daily)")
        mode.add_argument("--range", action="store_true",
                          help="lấy theo khoảng --from-date..--end-date")
        ap.add_argument("--from-date", type=str, default=None, help="YYYY-MM-DD (inclusive)")
        ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD (inclusive)")
        ap.add_argument("--max-pages", type=int, default=0, help="0=∞ (latest default 1)")
        ap.add_argument("--workers", type=int, default=6)
        ap.add_argument("--batch", type=int, default=100)
        ap.add_argument("--max-articles", type=int, default=0, help="cap (0=∞)")
        ap.add_argument("--csv", default=None)
        ap.add_argument("--test", action="store_true", help="giới hạn 5 bài")
        args = ap.parse_args()

        def pd(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                print(f"! ngày không hợp lệ: {s} (YYYY-MM-DD)")
                sys.exit(2)

        start, end = pd(args.from_date), pd(args.end_date)
        crawler = cls(csv_file=args.csv, workers=args.workers, batch_size=args.batch,
                      max_articles=5 if args.test else args.max_articles)
        if args.range or start or end:
            crawler.crawl_range(start, end, max_pages=args.max_pages)
        else:
            crawler.crawl_latest(max_pages=args.max_pages or 1)
