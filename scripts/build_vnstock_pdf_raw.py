"""Build data/vnstock_pdf_raw.csv — one row per local Vietstock PDF, with body.

Reads vnstock_articles.csv; for each row whose local PDF exists, extracts body
via PyMuPDF (cached in aggregated/pdf_bodies.jsonl — shared with aggregate_news).
Emits a raw CSV whose schema matches the other source CSVs (id, source, title,
body, lead, date, pdf_url, pdf_filename). Only rows with non-empty body are
included (= PDFs with extractable text).

Usage:
  uv run python scripts/build_vnstock_pdf_raw.py [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.body_extractor import extract_pdf_body, resolve_pdf_local_path  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
AGG = PROJECT_ROOT / "aggregated"
CSV_IN = DATA / "vnstock_articles.csv"
RAW_OUT = DATA / "vnstock_pdf_raw.csv"
PDF_CACHE = AGG / "pdf_bodies.jsonl"
COLS = ["id", "source", "title", "body", "lead", "date", "pdf_url", "pdf_filename"]


def _load_cache() -> dict:
    cache: dict[str, str] = {}
    if PDF_CACHE.exists():
        for line in PDF_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                cache[o["path"]] = o["body"]
            except Exception:  # noqa: BLE001
                continue
    return cache


def _save_cache(cache: dict) -> None:
    AGG.mkdir(parents=True, exist_ok=True)
    with open(PDF_CACHE, "w", encoding="utf-8") as f:
        for p, b in cache.items():
            f.write(json.dumps({"path": p, "body": b}, ensure_ascii=False) + "\n")


def _body(row: dict, cache: dict) -> str:
    p = resolve_pdf_local_path("vietstock", row, data_path=DATA)
    if not p or not p.exists():
        return ""
    key = str(p)
    if key in cache:
        return cache[key]
    b = extract_pdf_body(p)
    if b:  # cache only non-empty (empty = scanned → re-try next run)
        cache[key] = b
    return b


def main() -> None:
    ap = argparse.ArgumentParser(description="Build vnstock_pdf_raw.csv from local PDFs")
    ap.add_argument("--limit", type=int, default=0, help="cap input rows (0=all, debug)")
    args = ap.parse_args()
    with open(CSV_IN, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]

    cache = _load_cache()
    out: list[dict] = []
    skipped = 0
    for r in rows:
        fn = (r.get("pdf_filename") or "").strip()
        if not fn or not (DATA / "pdf" / fn).exists():
            skipped += 1
            continue
        body = _body(r, cache)
        if not body:
            continue
        out.append({
            "id": r.get("id", ""),
            "source": r.get("source", ""),
            "title": (r.get("title") or "").strip(),
            "body": body,
            "lead": body[:500],
            "date": (r.get("date") or "").strip(),
            "pdf_url": r.get("pdf_url", ""),
            "pdf_filename": fn,
        })
    _save_cache(cache)
    with open(RAW_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print(f"-> {RAW_OUT}: {len(out)} rows with body "
          f"(scanned {len(rows)}, no-pdf {skipped})")


if __name__ == "__main__":
    main()
