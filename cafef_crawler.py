"""
Cafef news crawler — thu thập metadata + lead bài viết thị trường hằng ngày.

Nguồn & chiến lược theo skill `.claude/skills/source-news-download/SKILL.md`:
  - Hằng ngày (daily): RSS mỗi section (cafef.vn/<slug>.rss, ~50 item / ~3 ngày).
  - Backfill: sitemap shards theo tháng (2016–2026, sitemap KHÔNG cover 2001–2015),
    mỗi shard không tag section → phải fetch từng bài đọc breadcrumb JSON-LD
    (item.@id của position-2 = URL section) để classify; cùng fetch đó lấy luôn lead.

Plain HTTP (requests) — cafef không cần Playwright/stealth. Self-contained.
"""

import argparse
import csv
import html
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from cafef_config import (
    CAFEF_SECTIONS,
    CANDIDATES_CACHE,
    CSV_FILE,
    CSV_HEADERS,
    DEFAULT_SECTIONS,
    MAX_RETRIES,
    PROXY_FILE,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    RSS_URL_FMT,
    SITEMAP_INDEX,
    USE_PROXY,
    USER_AGENT,
    ensure_paths_exist,
)
from utils.body_extractor import extract_html_body

UA_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.9"}
ID_RE = re.compile(r"-(\d{17,20})\.chn(?:[?#]|$)")
HTML_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
HN_TZ = timezone(timedelta(hours=7))
SHARD_RE = re.compile(r"<loc>(https://cafef\.vn/sitemaps/sitemaps-(\d{4})-(\d{1,2})-\d+-\d+\.xml)</loc>")


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
                r.encoding = "utf-8"  # cafef/sitemap không luôn khai báo charset → ép UTF-8
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(REQUEST_DELAY * (i + 1))
    print(f"  ! fetch fail {url} -> {last}")
    return None


def _load_proxy_pool():
    """Đọc proxies.txt → list proxy string (IP:PORT hoặc IP:PORT:USER:PASS)."""
    if not USE_PROXY or not PROXY_FILE.exists():
        return []
    out = []
    with open(PROXY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                out.append(line)
    return out


_PROXY_POOL = _load_proxy_pool()


def _proxy_kwargs():
    """Trả {'proxies': {...}} random từ pool (cho requests), hoặc {} nếu không dùng proxy."""
    if not _PROXY_POOL:
        return {}
    p = random.choice(_PROXY_POOL)  # noqa: S2245
    parts = p.split(":")
    if len(parts) == 2:
        url = f"http://{parts[0]}:{parts[1]}"  # noqa: S5332
    elif len(parts) >= 4:
        url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"  # noqa: S5332
    else:
        return {}
    return {"proxies": {"http": url, "https": url}}


def _fetch_once(url: str, timeout: int = 15):
    """GET 1 lần, ngắn — cho backfill (rất nhiều request).
    Dùng proxy xoay vòng nếu CAFEF_USE_PROXY."""
    try:
        r = requests.get(url, headers=UA_HEADERS, timeout=timeout, **_proxy_kwargs())
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text
    except Exception:  # noqa: BLE001
        pass
    return None


def extract_id(url: str) -> str:
    m = ID_RE.search(url)
    return m.group(1) if m else ""


def strip_html(s: str) -> str:
    return WS_RE.sub(" ", HTML_TAG_RE.sub(" ", s or "")).strip()


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


# ---------- RSS (daily) ----------
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


# ---------- sitemap (backfill) ----------
def shards_in_range(from_d, to_d) -> list:
    """Trả list shard URL (oldest→newest) có tháng trong [from_d, to_d]."""
    idx = fetch(SITEMAP_INDEX)
    if not idx:
        return []
    lo, hi = (from_d.year, from_d.month), (to_d.year, to_d.month)
    found = []
    for m in SHARD_RE.finditer(idx):
        ym = (int(m.group(2)), int(m.group(3)))
        if lo <= ym <= hi:
            found.append((ym, m.group(1)))
    found.sort()
    return [u for _, u in found]


def parse_shard(xml: str) -> list:
    """Trích (url, lastmod, title) từ mỗi <url> trong shard."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not loc:
            continue
        lastmod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        tm = re.search(r"<image:title>([^<]*)</image:title>", block)
        title = ""
        if tm:
            title = html.unescape(tm.group(1)).replace("<![CDATA[", "").replace("]]>", "").strip()
        out.append({
            "url": loc.group(1),
            "lastmod": lastmod.group(1) if lastmod else "",
            "title": title,
        })
    return out


def save_candidates(path: Path, candidates: list) -> None:
    """Ghi danh sách candidate ra JSONL (snapshot của lần gather, dedup theo url)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with open(path, "w", encoding="utf-8") as f:
        for c in candidates:
            u = c.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def load_candidates(path: Path) -> list:
    """Đọc candidate cache (JSONL), dedup theo url."""
    out, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            u = c.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(c)
    return out


def _extract_section_from_jsonld(html_text: str, sections_set: set) -> str:
    """Extract section from JSON-LD BreadcrumbList. Returns section slug or ''."""
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_text, re.S):
        try:
            obj = json.loads(block)
        except Exception:  # noqa: BLE001
            continue
        if obj.get("@type") != "BreadcrumbList":
            continue
        for el in obj.get("itemListElement", []) or []:
            iid = ((el.get("item") or {}).get("@id") or "")
            mm = re.search(r"cafef\.vn/([a-z0-9-]+)\.chn", iid)
            if mm and mm.group(1) in sections_set:
                return mm.group(1)
    return ""


def classify_one(cand: dict, sections_set: set) -> dict:
    """Fetch 1 bài → trả {section, title, lead, body}. section='' nếu không thuộc sections."""
    h = _fetch_once(cand["url"])
    if not h:
        return {"section": "", "title": cand.get("title", ""), "lead": ""}
    section = _extract_section_from_jsonld(h, sections_set)
    title = cand.get("title", "")
    if not title:
        m = re.search(r'<meta[^>]+property="og:title"[^>]*content="([^"]*)"', h)  # noqa: S8786
        if m:
            title = html.unescape(m.group(1))
    lead = ""
    m = (re.search(r'<meta[^>]+property="og:description"[^>]*content="([^"]*)"', h)  # noqa: S8786
         or re.search(r'<meta[^>]+name="description"[^>]*content="([^"]*)"', h))  # noqa: S8786
    if m:
        lead = html.unescape(m.group(1))[:500]
    body = extract_html_body(h, "cafef")
    return {"section": section, "title": title, "lead": lead, "body": body}


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
            with open(self.csv_file, encoding="utf-8-sig", newline="") as f:
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
        """Dedup + append (daily). Trả về số record mới."""
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

    # --- backfill mode (sitemap shards) ---
    def _gather_candidates(self, from_date, end_date, shards, cache_file, refresh):
        """Gather candidates from shards or cache. Returns list of candidate dicts."""
        if cache_file.exists() and not refresh:
            candidates = load_candidates(cache_file)
            print(f"  candidates from cache: {len(candidates)}  ({cache_file})")
        else:
            print(f"  shards in range: {len(shards)}; gathering (mất ~15-20 phút)...")
            candidates = []
            for i, s in enumerate(shards, 1):
                xml = fetch(s)
                if not xml:
                    print(f"  [shard {i}/{len(shards)}] fetch fail: {s}")
                    continue
                for art in parse_shard(xml):
                    if ".chn" not in art["url"]:
                        continue
                    try:
                        d = datetime.fromisoformat(art["lastmod"]).date()
                    except Exception:  # noqa: BLE001
                        d = None
                    if d and (d < from_date or d > end_date):
                        continue
                    candidates.append(art)
                if i % 20 == 0:
                    print(f"  [shard {i}/{len(shards)}] candidates so far: {len(candidates)}")
            print(f"  total candidates gathered: {len(candidates)}")
            save_candidates(cache_file, candidates)
            print(f"  cached -> {cache_file}  (lần sau dùng cache, bỏ qua quét shard)")
        return candidates

    def _classify_and_collect(self, todo, sections_set, max_articles):
        """Classify candidates in parallel. Returns (kept, out_section, fail)."""
        kept = out_section = fail = 0
        processed = 0
        batch = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            fut_to_cand = {ex.submit(classify_one, c, sections_set): c for c in todo}
            for fut in as_completed(fut_to_cand):
                c = fut_to_cand[fut]
                processed += 1
                try:
                    res = fut.result()
                except Exception:  # noqa: BLE001
                    res = None
                if not res:
                    fail += 1
                elif res["section"] and c["url"] not in self.seen:
                    self.seen.add(c["url"])
                    batch.append({
                        "id": extract_id(c["url"]),
                        "title": res.get("title") or c.get("title", ""),
                        "section": res["section"],
                        "pub_date": (c.get("lastmod", "")[:19] or ""),
                        "article_url": c["url"],
                        "author": "",
                        "lead": res.get("lead", ""),
                        "body": res.get("body", ""),
                        "collected_at": now_iso(),
                    })
                    kept += 1
                    if len(batch) >= 200:
                        self._append(batch)
                        print(
                            f"  saved kept={kept} (processed {processed}/{len(todo)}) "
                            f"[{time.time()-t0:.0f}s]"
                        )
                        batch = []
                elif not res["section"]:
                    out_section += 1
                if max_articles and kept >= max_articles:
                    for f in fut_to_cand:
                        f.cancel()
                    break
                if processed % 1000 == 0:
                    print(
                        f"  progress processed={processed}/{len(todo)} kept={kept} "
                        f"out_section={out_section} fail={fail} [{time.time()-t0:.0f}s]"
                    )
        if batch:
            self._append(batch)
        return kept, out_section, fail

    def crawl_backfill(self, from_date, end_date=None, max_articles=0, workers=6,
                       refresh=False, cache_file=CANDIDATES_CACHE):
        end_date = end_date or datetime.now(HN_TZ).date()
        sections_set = set(self.sections)
        print(f"=== CAFEF BACKFILL {from_date} -> {end_date} | sections={self.sections} | "
              f"workers={workers} | refresh={refresh} ===")

        shards = shards_in_range(from_date, end_date)
        candidates = self._gather_candidates(from_date, end_date, shards, cache_file, refresh)
        todo = [c for c in candidates if c["url"] not in self.seen]
        print(
            f"  unseen candidates: {len(todo)}  "
            f"(already collected: {len(candidates) - len(todo)})"
        )

        kept, out_section, fail = self._classify_and_collect(todo, sections_set, max_articles)

        self.counters["new"] = kept
        self.counters["dup"] = out_section
        self.counters["fail"] = fail
        print(
            f"\nBACKFILL DONE  kept(in-section)={kept}  out_section={out_section}  "
            f"fail={fail}  processed={len(todo)}  "
            f"  -> {self.csv_file} (total rows now ~{len(self.seen)})"
        )
        return self.counters

    def _summary(self):
        c = self.counters
        print(
            f"\nTOTAL  new={c['new']}  dedup-skip={c['dup']}  fail={c['fail']}"
            f"  -> {self.csv_file}"
        )


# ---------- CLI ----------
def _parse_date(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        print(f"! ngày không hợp lệ: {s} (YYYY-MM-DD)")
        sys.exit(2)


def fetch_bodies(csv_file: Path, workers: int = 3, test: bool = False, limit: int = 0) -> None:
    """Re-fetch body cho các row body rỗng trong cafef CSV (bypass seen). Ghi in-place.

    Cafef throttle IP → dùng proxy (CAFEF_USE_PROXY) + workers thấp (3)."""
    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    if "body" not in fieldnames:
        fieldnames.append("body")
    todo = [r for r in rows if not (r.get("body") or "").strip()]
    if test:
        todo = todo[:5]
    elif limit:
        todo = todo[:limit]
    print(f"--fetch-body: {len(todo)}/{len(rows)} rows need body, workers={workers}")
    if not todo:
        return

    def one(row: dict) -> bool:
        url = row.get("article_url") or row.get("url") or ""
        if not url:
            return False
        h = _fetch_once(url)
        if not h:
            return False
        row["body"] = extract_html_body(h, "cafef")
        return bool(row["body"])

    done = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            if fut.result():
                done += 1
            else:
                fail += 1
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} body={done} fail={fail} [{time.time()-t0:.0f}s]")
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"-> {csv_file}: body filled {done}/{len(todo)} (fail={fail})")


def main():
    ap = argparse.ArgumentParser(description="Cafef news crawler (RSS daily + sitemap backfill)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--daily", action="store_true", help="chế độ daily (RSS)")
    mode.add_argument("--backfill", action="store_true", help="chế độ backfill (sitemap shards)")
    mode.add_argument("--fetch-body", action="store_true",
                      help="re-fetch body cho các row body rỗng (dùng proxy + --workers 3)")
    ap.add_argument("--sections", nargs="*", default=None,
                    help=f"slug section (default: {' '.join(DEFAULT_SECTIONS)})")
    ap.add_argument("--test", action="store_true", help="daily: giới hạn 5 item/section")
    ap.add_argument("--csv", default=str(CSV_FILE), help="file CSV output")
    # backfill
    ap.add_argument("--from-date", type=str, default=None,
                    help="backfill từ YYYY-MM-DD (default 2016-01-01 = sitemap floor)")
    ap.add_argument("--end-date", type=str, default=None,
                    help="backfill đến YYYY-MM-DD (default: hôm nay)")
    ap.add_argument("--max-articles", type=int, default=0, help="cap số bài thu thập (0=∞)")
    ap.add_argument("--workers", type=int, default=6, help="số luồng fetch song song (backfill)")
    ap.add_argument("--refresh-shards", action="store_true",
                    help="bỏ cache candidate, quét lại sitemap shards "
                         "(lấy bài mới publish sau lần cache)")
    args = ap.parse_args()

    sections = args.sections or DEFAULT_SECTIONS
    invalid = [s for s in sections if s not in CAFEF_SECTIONS]
    if invalid:
        print(f"! section không hợp lệ: {invalid}\n  hợp lệ: {list(CAFEF_SECTIONS)}")
        sys.exit(2)

    crawler = CafefNewsCrawler(sections=sections, csv_file=args.csv)

    if args.fetch_body:
        fetch_bodies(Path(args.csv), workers=args.workers, test=args.test)
    elif args.backfill:
        from_d = _parse_date(args.from_date, datetime.strptime("2016-01-01", "%Y-%m-%d").date())
        end_d = _parse_date(args.end_date, datetime.now(HN_TZ).date())
        crawler.crawl_backfill(from_d, end_d, max_articles=args.max_articles,
                               workers=args.workers, refresh=args.refresh_shards)
    else:
        crawler.crawl_daily(test=args.test)


if __name__ == "__main__":
    main()
