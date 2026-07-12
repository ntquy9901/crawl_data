"""
Macro economic time-series crawler — dữ liệu vĩ mô cho model dự đoán volatility VN30.

Raw → data/macro/raw/<source>.csv (mỗi nguồn 1 file, append-resumable theo date).
Self-contained (KHÔNG dùng base_news_crawler — template đó cho listing→article, sai shape
cho time-series bulk-fetch). Class-based, mirror cafef_crawler.py.

Nguồn (fetch BULK per source, song song theo nguồn qua ThreadPoolExecutor):
  - vnindex      : VNDIRECT finfo JSON, paginate (full history từ 2000-07-28).
  - dxy          : FRED CSV (DTWEXBGS, từ 2006-01-03) — 1 GET trả cả lịch sử.
  - usd_vnd_vcb  : Vietcombank HTML table, lặp theo ngày (chỉ ~3-4 tháng gần).
  - usd_vnd_sbv  : SBV JSF — STUB v1 (JSF postback khó), trả [] + cảnh báo.
  VNDIBOR descope v1 (không có source sạch) → KHÔNG crawl, columns NaN ở build.

Resume theo date: đọc max(date) trong raw CSV, chỉ fetch ngày mới hơn (lệch có chủ đích
so với cafef URL-dedup, vì time-series tự unique theo date). Stable UA (pitfall #1).

Usage:
  PYTHONUTF8=1 python macro_crawler.py                      # toàn bộ nguồn, resume
  PYTHONUTF8=1 python macro_crawler.py --sources dxy        # chỉ DXY
  PYTHONUTF8=1 python macro_crawler.py --from-date 2024-01-01 --end-date 2024-06-30
  PYTHONUTF8=1 python macro_crawler.py --test               # cap ~5 dòng/nguồn
"""

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import lxml.html
import requests

from macro_config import (
    FRED_DXY_URL,
    HEADERS_DXY,
    HEADERS_USD_VND_SBV,
    HEADERS_USD_VND_VCB,
    HEADERS_VNINDEX,
    MAX_RETRIES,
    RAW_DXY,
    RAW_USD_VND_SBV,
    RAW_USD_VND_VCB,
    RAW_VNINDEX,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    SOURCES,
    USER_AGENT,
    VCB_RATE_URL,
    VNDIRECT_FINFO_URL,
    VNDIRECT_PAGE_SIZE,
    VNINDEX_SYMBOL,
    ensure_paths_exist,
)

UA_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.9"}
HN_TZ = timezone(timedelta(hours=7))


# ---------- helpers ----------
def now_iso() -> str:
    return datetime.now(HN_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def fetch(url: str, params: dict | None = None):
    """GET với retry. Trả text hoặc None (fail-graceful)."""
    last = None
    for i in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, headers=UA_HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                r.encoding = r.encoding or "utf-8"
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(REQUEST_DELAY * (i + 1))
    print(f"  ! fetch fail {url} -> {last}")
    return None


def _num(x) -> str:
    """Chuỗi hoá số an toàn: None/NaN/empty → ''."""
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("", "nan", "null", "none") else s


def _clean_num(s: str) -> str:
    """VCB dùng ',' làm phân cách hàng nghìn ('24,340') → '24340'."""
    return (s or "").replace(",", "").replace(" ", "").strip()


def parse_fred_csv(text: str) -> list[dict]:
    """FRED CSV (header: observation_date,DTWEXBGS). '.' sentinel = NaN → ''."""
    rows: list[dict] = []
    for r in csv.DictReader(text.splitlines()):
        d = (r.get("observation_date") or "")[:10]
        if not d:
            continue
        val = (r.get("DTWEXBGS") or "").strip()
        dxy = "" if val in (".", "") else val
        rows.append({"date": d, "dxy": dxy, "source": "fred"})
    return rows


def parse_vndirect_json(text: str) -> list[dict]:
    """VNDIRECT finfo: resp['data'] = [{date, open, high, low, close, volume, ...}]."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return []
    rows: list[dict] = []
    for d in obj.get("data") or []:
        day = (d.get("date") or "")[:10]
        if not day:
            continue
        rows.append({
            "date": day,
            "open": _num(d.get("open")),
            "high": _num(d.get("high")),
            "low": _num(d.get("low")),
            "close": _num(d.get("close")),
            "volume": _num(d.get("volume")),
            "source": "vndirect",
        })
    return rows


def parse_vcb_html(text: str) -> dict:
    """Trích usd_vnd_buy/usd_vnd_sell từ bảng tỷ giá VCB. Trả {} nếu không có USD.

    Bảng VCB có cột tên tiền tệ cạnh mã → không cố định vị trí cột. Tìm row USD, lấy các
    cell numeric (digit sau khi bỏ phân cách hàng nghìn), buy=đầu, sell=cuối.
    Cần verify trên máy user (HTML có thể đổi).
    """
    try:
        doc = lxml.html.fromstring(text)
    except Exception:  # noqa: BLE001
        return {}
    for tr in doc.xpath("//tr"):
        cells = [td.text_content().strip() for td in tr.xpath(".//td")]
        if len(cells) < 3 or not any(c.upper() == "USD" for c in cells[:2]):
            continue
        nums = [n for n in (_clean_num(c) for c in cells) if n and n.lstrip("-").isdigit()]
        if len(nums) >= 2:
            return {"usd_vnd_buy": nums[0], "usd_vnd_sell": nums[-1]}
        if len(nums) == 1:
            return {"usd_vnd_buy": nums[0], "usd_vnd_sell": nums[0]}
    return {}


class MacroCrawler:
    def __init__(self, from_date=None, end_date=None, workers=4, test=False, sources=None):
        self.from_date = from_date                  # date|None (None = resume)
        self.end_date = end_date or datetime.now(HN_TZ).date()
        self.workers = workers
        self.test = test
        self.sources = sources or list(SOURCES)
        ensure_paths_exist()

    # ---------- CSV resume (theo date) ----------
    def _max_date(self, csv_path: Path):
        if not csv_path.exists():
            return None
        days = []
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                d = (r.get("date") or "")[:10]
                try:
                    days.append(date.fromisoformat(d))
                except ValueError:
                    continue  # bỏ row date hỏng thay vì crash toàn bộ resume
        return max(days, default=None)

    def _window(self, csv_path: Path) -> tuple[str, str]:
        """Khoảng (from, to) ISO để query nguồn có date-range param. Resume từ max date."""
        if self.from_date is not None:
            from_d = self.from_date
        else:
            mx = self._max_date(csv_path)
            from_d = (mx + timedelta(days=1)) if mx else date(2000, 1, 1)
        return from_d.isoformat(), self.end_date.isoformat()

    def _init_csv(self, csv_path: Path, headers: list[str]) -> None:
        if not csv_path.exists():
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow(headers)

    def _append(self, csv_path: Path, headers: list[str], rows: list[dict]) -> None:
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=headers, extrasaction="ignore").writerows(rows)

    def _save(self, csv_path: Path, headers: list[str], rows: list[dict]) -> int:
        """Lọc row mới (date > max hiện có, ≤ end_date), dedup batch, append. Trả số row ghi."""
        max_existing = self._max_date(csv_path)
        kept: dict[str, dict] = {}
        for r in rows:
            d = (r.get("date") or "")[:10]
            if not d:
                continue
            if max_existing and d <= max_existing.isoformat():
                continue
            if d > self.end_date.isoformat():
                continue
            kept[d] = r
        if not kept:
            return 0
        new_rows = list(kept.values())
        self._init_csv(csv_path, headers)
        self._append(csv_path, headers, new_rows)
        return len(new_rows)

    # ---------- fetch per source (mỗi cái trả list[dict] raw, chưa có collected_at) ----------
    def fetch_dxy(self) -> list[dict]:
        # FRED trả cả lịch sử trong 1 GET; lọc theo date ở _save.
        text = fetch(FRED_DXY_URL)
        rows = parse_fred_csv(text) if text else []
        return rows[:5] if self.test else rows

    def fetch_vnindex(self) -> list[dict]:
        from_iso, to_iso = self._window(RAW_VNINDEX)
        rows: list[dict] = []
        page = 1
        while True:
            text = fetch(VNDIRECT_FINFO_URL, params={
                "symbol": VNINDEX_SYMBOL, "sort": "date",
                "size": VNDIRECT_PAGE_SIZE, "page": page,
                "from": from_iso, "to": to_iso,
            })
            page_rows = parse_vndirect_json(text) if text else []
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(page_rows) < VNDIRECT_PAGE_SIZE:
                break
            page += 1
        return rows[:5] if self.test else rows

    def fetch_usd_vnd_vcb(self) -> list[dict]:
        # VCB chỉ trả 1 ngày/call (param Textdate DD/MM/YYYY) → lặp từ max+1 tới end.
        # VCB chỉ giữ ~3-4 tháng; gặp dải trống dài (15 ngày liên tục) thì dừng sớm
        # tránh hàng nghìn requests vô ích khi backfill rộng (VCB không có data cũ).
        from_iso, to_iso = self._window(RAW_USD_VND_VCB)
        cur = date.fromisoformat(to_iso)
        end = date.fromisoformat(from_iso)
        rows: list[dict] = []
        empty_streak = 0
        while cur >= end:
            text = fetch(VCB_RATE_URL, params={"Textdate": cur.strftime("%d/%m/%Y")})
            parsed = parse_vcb_html(text) if text else {}
            if parsed:
                rows.append({"date": cur.isoformat(), **parsed, "source": "vcb"})
                empty_streak = 0
            else:
                empty_streak += 1
                if empty_streak >= 15:
                    break
            if self.test and len(rows) >= 5:
                break
            cur -= timedelta(days=1)
            time.sleep(REQUEST_DELAY)
        return rows

    def fetch_usd_vnd_sbv(self) -> list[dict]:
        # STUB v1: SBV tygia.jspx là JSF (postback ViewState) — disproportionate cho v1.
        print("  ! usd_vnd_sbv: SBV JSF (tygia.jspx) — STUB v1, raw file để trống.")
        return []

    # ---------- orchestration ----------
    def run(self) -> None:
        jobs = {
            "vnindex": (RAW_VNINDEX, HEADERS_VNINDEX, self.fetch_vnindex),
            "dxy": (RAW_DXY, HEADERS_DXY, self.fetch_dxy),
            "usd_vnd_vcb": (RAW_USD_VND_VCB, HEADERS_USD_VND_VCB, self.fetch_usd_vnd_vcb),
            "usd_vnd_sbv": (RAW_USD_VND_SBV, HEADERS_USD_VND_SBV, self.fetch_usd_vnd_sbv),
        }
        print(f"=== MACRO CRAWLER | sources={self.sources} | from={self.from_date} | "
              f"to={self.end_date} | test={self.test} ===")
        t0 = time.time()

        def one(name: str) -> int:
            csv_path, headers, fn = jobs[name]
            rows = fn()
            stamp = now_iso()
            for r in rows:
                r["collected_at"] = stamp
            return self._save(csv_path, headers, rows)

        results: dict[str, int] = {}
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(one, name): name for name in self.sources}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    results[name] = fut.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  [{name}] FAIL {type(e).__name__}: {e}")
                    results[name] = -1

        for name in self.sources:
            n = results.get(name, -1)
            print(f"  [{name}] {'FAIL' if n < 0 else f'{n} new rows'}")
        print(f"DONE in {time.time() - t0:.0f}s")


def main():
    ap = argparse.ArgumentParser(description="Macro economic time-series crawler")
    ap.add_argument("--from-date", help="YYYY-MM-DD (mặc định: resume từ max date trong raw CSV)")
    ap.add_argument("--end-date", help="YYYY-MM-DD (mặc định: hôm nay)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sources", default=",".join(SOURCES),
                    help=f"comma-list (mặc định tất cả: {','.join(SOURCES)})")
    ap.add_argument("--test", action="store_true", help="cap ~5 dòng mỗi nguồn (debug)")
    args = ap.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    bad = [s for s in sources if s not in SOURCES]
    if bad:
        ap.error(f"--sources không hợp lệ {bad}; cho phép: {SOURCES}")
    fd = date.fromisoformat(args.from_date) if args.from_date else None
    ed = date.fromisoformat(args.end_date) if args.end_date else None

    MacroCrawler(from_date=fd, end_date=ed, workers=args.workers,
                 test=args.test, sources=sources).run()


if __name__ == "__main__":
    main()
