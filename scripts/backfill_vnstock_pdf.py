"""Backfill missing Vietstock report PDFs (download-theo-thiếu).

Reads vnstock_articles.csv; for rows with pdf_url but no local PDF, downloads
via Playwright page.goto + download-event-listener (the `downloadedoc/{id}`
endpoint auto-triggers PDF download for available docs; old/removed ones
redirect to Error page quickly). Sequential browser session — the endpoint
requires full browser session cookies. RULE: skip-if-exists (idempotent re-run).
Writes `pdf_filename` + `downloaded_at` back in-place.

Usage:
  uv run python scripts/backfill_vnstock_pdf.py [--limit N] [--test]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time as _time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.pdf_helpers import generate_pdf_filename  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
CSV_FILE = DATA / "vnstock_articles.csv"
PDF_DIR = DATA / "pdf"
FAIL_LOG = DATA / "vnstock_pdf_download_failures.txt"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
REFERER = "https://finance.vietstock.vn/"

_DOC_ID_RE = re.compile(r"downloadedoc/(\d+)", re.IGNORECASE)


def dest_for(row: dict) -> Path:
    """Unique dest per row: {date}_{title}__{doc_id}.pdf."""
    base = generate_pdf_filename(row.get("title", ""), row.get("date", ""))
    m = _DOC_ID_RE.search(row.get("pdf_url") or "")
    if m:
        return PDF_DIR / f"{base[:-4]}__{m.group(1)}.pdf"
    return PDF_DIR / base


def has_local(row: dict) -> bool:
    fn = (row.get("pdf_filename") or "").strip()
    return bool(fn) and (PDF_DIR / fn).exists()


def _reconcile_existing_pdfs(rows: list[dict]) -> int:
    """Match rows without pdf_filename to existing on-disk PDFs from prior runs."""
    reconciled = 0
    for r in rows:
        if (r.get("pdf_filename") or "").strip() or not (r.get("pdf_url") or "").strip():
            continue
        old = PDF_DIR / generate_pdf_filename(r.get("title", ""), r.get("date", ""))
        if old.exists() and old.stat().st_size > 1000:
            r["pdf_filename"] = old.name
            reconciled += 1
    return reconciled


def _download_one(pg, url: str, dest: Path) -> bool:
    """Download one PDF via page.goto + download-event-listener.

    For auto-download URLs, goto raises "Download is starting" — the event
    listener captures the download regardless. For Error/HTML pages, goto
    completes quickly with no download. Poll briefly to distinguish.
    """
    captured = []
    def _on_download(dl):
        captured.append(dl)
    pg.on("download", _on_download)
    try:
        pg.goto(url, timeout=10000, wait_until="domcontentloaded")
    except Exception:
        pass
    for _ in range(15):
        if captured:
            break
        _time.sleep(0.1)
    pg.remove_listener("download", _on_download)
    pg.goto("about:blank")
    if not captured:
        return False
    captured[0].save_as(str(dest))
    return dest.exists() and dest.stat().st_size > 1000


def main() -> None:
    ap = argparse.ArgumentParser(description="Vietstock PDF backfill (download-missing)")
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0=all)")
    ap.add_argument("--csv", default=str(CSV_FILE))
    ap.add_argument("--test", action="store_true", help="limit 5 rows")
    args = ap.parse_args()
    if args.test:
        args.limit = 5

    csv_path = Path(args.csv)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"! empty {csv_path}")
        sys.exit(1)
    fieldnames = list(rows[0].keys())
    for col in ("pdf_filename", "downloaded_at"):
        if col not in fieldnames:
            fieldnames.append(col)

    reconciled = _reconcile_existing_pdfs(rows)
    if reconciled:
        print(f"reconciled {reconciled} rows to existing on-disk PDFs (prior run)")

    todo = [r for r in rows if (r.get("pdf_url") or "").strip() and not has_local(r)]
    if args.limit:
        todo = todo[: args.limit]
    print(f"Vietstock PDF backfill: {len(todo)} to download (of {len(rows)} rows)")
    if not todo:
        print("nothing to do — all rows with pdf_url already have a local PDF")
        return

    recovered = 0

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  playwright unavailable — cannot download")
        sys.exit(1)

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA)
        pg = ctx.new_page()
        pg.goto(REFERER, timeout=30000, wait_until="domcontentloaded")
        t0 = _time.time()

        for idx, r in enumerate(todo, 1):
            dest = dest_for(r)
            if dest.exists() and dest.stat().st_size > 1000:
                r["pdf_filename"] = dest.name
                recovered += 1
                continue
            url = (r.get("pdf_url") or "").strip()
            if _download_one(pg, url, dest):
                r["pdf_filename"] = dest.name
                r["downloaded_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                recovered += 1
            if idx % 50 == 0 or idx == len(todo):
                print(f"  {idx}/{len(todo)} recovered={recovered} "
                      f"[{_time.time()-t0:.0f}s]")

        br.close()

    still_fail = [r for r in todo if not has_local(r)]

    if still_fail:
        with open(FAIL_LOG, "w", encoding="utf-8") as f:
            for r in still_fail:
                f.write(f"{(r.get('pdf_url') or '').strip()}\t{(r.get('title') or '')[:60]}\n")

    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)
    print(f"-> {csv_path}: downloaded {recovered}/{len(todo)} "
          f"(fail={len(still_fail)}"
          f"{f', logged -> {FAIL_LOG.name}' if still_fail else ''})")


if __name__ == "__main__":
    main()
