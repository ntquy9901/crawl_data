"""Backfill missing Vietstock report PDFs (download-theo-thiếu).

Reads vnstock_articles.csv; for rows with pdf_url but no local PDF, downloads
via requests (stable browser UA + Referer — the `downloadedoc/{id}` endpoint
accepts this, no cookies needed per spike). Playwright fallback for failures
(captcha/non-PDF responses). RULE: skip-if-exists (idempotent re-run). Writes
`pdf_filename` + `downloaded_at` back in-place.

Usage:
  uv run python scripts/backfill_vnstock_pdf.py [--limit N] [--workers 3] [--no-playwright] [--test]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.pdf_helpers import generate_pdf_filename  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
CSV_FILE = DATA / "vnstock_articles.csv"
PDF_DIR = DATA / "pdf"
FAIL_LOG = DATA / "vnstock_pdf_download_failures.txt"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://finance.vietstock.vn/"}


_DOC_ID_RE = re.compile(r"downloadedoc/(\d+)", re.IGNORECASE)


def dest_for(row: dict) -> Path:
    """Unique dest per row: {date}_{title}__{doc_id}.pdf.

    doc_id (from pdf_url downloadedoc/{id}) makes the name unique — prevents
    filename collisions when two reports share the same date + truncated title
    (which crashed an earlier run via .part contention)."""
    base = generate_pdf_filename(row.get("title", ""), row.get("date", ""))
    m = _DOC_ID_RE.search(row.get("pdf_url") or "")
    if m:
        return PDF_DIR / f"{base[:-4]}__{m.group(1)}.pdf"
    return PDF_DIR / base


def has_local(row: dict) -> bool:
    fn = (row.get("pdf_filename") or "").strip()
    return bool(fn) and (PDF_DIR / fn).exists()


def download_requests(url: str, dest: Path, timeout: int = 60) -> bool:
    """requests download (UA + Referer). True if dest is a plausible PDF."""
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True)
        if r.status_code >= 400 or "pdf" not in r.headers.get("content-type", "").lower():
            return False  # captcha/HTML/redirect → leave for Playwright fallback
        with open(part, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        if part.stat().st_size < 1000:
            part.unlink(missing_ok=True)
            return False
        part.replace(dest)
        return True
    except Exception:  # noqa: BLE001
        part.unlink(missing_ok=True)
        return False


def run_playwright_fallback(fail_rows: list[dict]) -> list[dict]:
    """ONE browser session, recover failures via page.goto + expect_download."""
    recovered: list[dict] = []
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001
        print("  (playwright unavailable — skipping fallback)")
        return recovered
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA)
        pg = ctx.new_page()
        for r in fail_rows:
            dest = dest_for(r)
            if dest.exists() and dest.stat().st_size > 1000:
                r["pdf_filename"] = dest.name
                recovered.append(r)
                continue
            try:
                with pg.expect_download(timeout=60000) as di:
                    pg.goto((r.get("pdf_url") or "").strip(), timeout=60000)
                di.value.save_as(str(dest))
                if dest.stat().st_size > 1000:
                    r["pdf_filename"] = dest.name
                    recovered.append(r)
            except Exception:  # noqa: BLE001
                pass
        br.close()
    return recovered


def _reconcile_existing_pdfs(rows: list[dict]) -> int:
    """Reconcile rows with existing on-disk PDFs from prior runs. Returns count reconciled."""
    reconciled = 0
    for r in rows:
        if (r.get("pdf_filename") or "").strip() or not (r.get("pdf_url") or "").strip():
            continue
        old = PDF_DIR / generate_pdf_filename(r.get("title", ""), r.get("date", ""))
        if old.exists() and old.stat().st_size > 1000:
            r["pdf_filename"] = old.name
            reconciled += 1
    return reconciled


def _download_phase_a(todo: list[dict], workers: int) -> tuple[int, list[dict]]:
    """Phase A: parallel requests download. Returns (done_count, fail_rows)."""
    done = 0
    t0 = time.time()
    fail_rows: list[dict] = []

    def one(r: dict):
        return r, download_requests((r.get("pdf_url") or "").strip(), dest_for(r))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r, ok = fut.result()
            if ok:
                r["pdf_filename"] = dest_for(r).name
                r["downloaded_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                done += 1
            else:
                fail_rows.append(r)
            if i % 100 == 0 or i == len(todo):
                print(f"  phase A {i}/{len(todo)} done={done} fail={len(fail_rows)} "
                      f"[{time.time()-t0:.0f}s]")
    return done, fail_rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Vietstock PDF backfill (download-missing)")
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0=all)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--csv", default=str(CSV_FILE))
    ap.add_argument("--no-playwright", action="store_true", help="skip Playwright fallback phase")
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
    print(f"Vietstock PDF backfill: {len(todo)} to download (of {len(rows)} rows), "
          f"workers={args.workers}")
    if not todo:
        print("nothing to do — all rows with pdf_url already have a local PDF")
        return

    done, fail_rows = _download_phase_a(todo, args.workers)

    if fail_rows and not args.no_playwright:
        print(f"phase B: Playwright fallback for {len(fail_rows)} failures (sequential)")
        recovered = run_playwright_fallback(fail_rows)
        done += len(recovered)
        print(f"  phase B recovered {len(recovered)}/{len(fail_rows)}")
        still_fail = [r for r in fail_rows if not has_local(r)]
    else:
        still_fail = fail_rows

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
    print(f"-> {csv_path}: downloaded {done}/{len(todo)} "
          f"(fail={len(still_fail)}"
          f"{f', logged -> {FAIL_LOG.name}' if still_fail else ''})")


if __name__ == "__main__":
    main()
