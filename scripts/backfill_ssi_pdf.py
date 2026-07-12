"""Backfill SSI article bodies: download each report PDF, extract text, write back.

SSI is listing-complete (the URL IS the PDF download link), so the crawler never
visited article pages. This script downloads each PDF to data/pdf_ssi/{id}.pdf
(skip-if-exists → resumable), extracts body text via PyMuPDF, and writes the
`body` (+`pdf_filename`) column back into data/ssi_articles.csv in place.

Usage:
  uv run python scripts/backfill_ssi_pdf.py [--limit N] [--workers 4] [--test]
"""
from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.body_extractor import extract_pdf_body  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
SSI_CSV = DATA / "ssi_articles.csv"
PDF_DIR = DATA / "pdf_ssi"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")}


def download(url: str, dest: Path, timeout: int = 30) -> bool:
    """Stream-download url to dest via .part → atomic rename. Skip if dest exists."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        r = requests.get(url, headers=UA, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        with open(part, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        part.replace(dest)
        return True
    except Exception:  # noqa: BLE001
        part.unlink(missing_ok=True)
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="SSI PDF body backfill")
    ap.add_argument("--limit", type=int, default=0, help="cap rows (0=all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--csv", default=str(SSI_CSV))
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
    for col in ("body", "pdf_filename"):
        if col not in fieldnames:
            fieldnames.append(col)

    todo = rows if not args.limit else rows[: args.limit]
    print(f"SSI backfill: {len(todo)} rows, workers={args.workers}")

    def one(row: dict) -> bool:
        rid = row.get("id") or ""
        url = row.get("url") or row.get("pdf_url") or ""
        if not rid or not url:
            return False
        dest = PDF_DIR / f"{rid}.pdf"
        if not download(url, dest):
            return False
        row["pdf_filename"] = dest.name
        row["body"] = extract_pdf_body(dest)
        return bool(row["body"])

    done = fail = notext = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            ok = fut.result()
            if ok:
                done += 1
            elif (PDF_DIR / f"{r.get('id')}.pdf").exists():
                notext += 1  # downloaded but no text (scanned/image)
            else:
                fail += 1
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  body={done} fail={fail} notext={notext}")

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"-> {csv_path}: body filled {done}/{len(todo)} (fail={fail}, notext={notext})")


if __name__ == "__main__":
    main()
