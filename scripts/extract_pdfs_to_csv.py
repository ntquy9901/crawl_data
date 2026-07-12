"""Extract ALL local Vietstock PDFs → CSV (parallel, for export / other projects).

Scans data/pdf/*.pdf directly (no dependency on vnstock_articles.csv mapping —
safe to run mid-download, since the download writes .part→*.pdf atomically and
this reads only complete *.pdf). Extracts body via PyMuPDF in PARALLEL
(ProcessPool — CPU-bound). Cached via aggregated/pdf_bodies.jsonl (shared with
aggregate_news / build_vnstock_pdf_raw). Does NOT touch vnstock_articles.csv.

Output: data/vnstock_pdfs_extracted.csv {pdf_filename, body}.

Usage:
  uv run python scripts/extract_pdfs_to_csv.py [--workers 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from utils.body_extractor import extract_pdf_body  # noqa: E402

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF_DIR = PROJECT_ROOT / "data" / "pdf"
AGG = PROJECT_ROOT / "aggregated"
OUT = PROJECT_ROOT / "data" / "vnstock_pdfs_extracted.csv"
CACHE = AGG / "pdf_bodies.jsonl"


def _load_cache() -> dict:
    cache: dict[str, str] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                cache[o["path"]] = o["body"]
            except Exception:  # noqa: BLE001
                continue
    return cache


def _save_cache(cache: dict) -> None:
    AGG.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        for p, b in cache.items():
            f.write(json.dumps({"path": p, "body": b}, ensure_ascii=False) + "\n")


def _extract(task: tuple[str, str]) -> tuple[str, str]:
    """Worker (top-level → picklable for ProcessPool). Returns (path_str, body)."""
    path_str, cached = task
    if cached:
        return path_str, cached
    try:
        body = extract_pdf_body(pathlib.Path(path_str))
    except Exception:  # noqa: BLE001 — defensive: never let one PDF kill the pool
        body = ""
    return path_str, body


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract all local Vietstock PDFs → CSV (parallel)")
    ap.add_argument("--workers", type=int, default=4, help="process pool size (CPU-bound)")
    args = ap.parse_args()

    cache = _load_cache()
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    cached_n = sum(1 for p in pdfs if str(p) in cache)
    print(f"PDFs on disk: {len(pdfs)} | already cached: {cached_n} | "
          f"to parse: {len(pdfs) - cached_n} | workers={args.workers}")
    if not pdfs:
        return

    tasks = [(str(p), cache.get(str(p), "")) for p in pdfs]
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, (path_str, body) in enumerate(ex.map(_extract, tasks), 1):
            if body:
                cache[path_str] = body
                rows.append({"pdf_filename": pathlib.Path(path_str).name, "body": body})
            if i % 500 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} extracted={len(rows)}")

    _save_cache(cache)
    tmp = OUT.with_suffix(OUT.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pdf_filename", "body"])
        w.writeheader()
        w.writerows(rows)
    tmp.replace(OUT)  # atomic
    print(f"-> {OUT}: {len(rows)} rows with body")


if __name__ == "__main__":
    main()
