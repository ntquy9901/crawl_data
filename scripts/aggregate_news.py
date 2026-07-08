"""Aggregate all news/report CSVs → aggregated/unified_articles.csv + stats.

Reproducible replacement for the ad-hoc unified dataset. Dedup by url, carry the
`body` column through, resolve Vietstock/SSI bodies from local PDFs (cached).

Inputs (data/): cafef, ssi, hsc, vndirect, vnstock articles CSV.
Outputs (aggregated/): unified_articles.csv, aggregation_stats.txt, pdf_bodies.jsonl.

Usage:
  uv run python scripts/aggregate_news.py [--no-pdf] [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.body_extractor import extract_pdf_body, resolve_pdf_local_path  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
AGG = PROJECT_ROOT / "aggregated"
UNIFIED_OUT = AGG / "unified_articles.csv"
STATS_OUT = AGG / "aggregation_stats.txt"
PDF_CACHE = AGG / "pdf_bodies.jsonl"

UNIFIED_COLS = [
    "unified_id", "source", "title", "body", "lead", "category", "author",
    "date", "pub_datetime", "url", "pdf_url", "pdf_filename",
    "collected_at", "origin_file",
]

# (origin_tag, filename, column_renames)
SOURCES = [
    ("cafef", "cafef_articles.csv", {"article_url": "url", "section": "category"}),
    ("ssi", "ssi_articles.csv", {}),
    ("hsc", "hsc_articles.csv", {}),
    ("vndirect", "vndirect_articles.csv", {}),
    ("vietstock", "vnstock_articles.csv", {}),
]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"  skip (missing): {path.name}")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _norm_date(s: str) -> str:
    """Best-effort → YYYY-MM-DD from various source formats."""
    from datetime import datetime

    if not s:
        return ""
    s = str(s).strip()
    for fmt, slen in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10), ("%d-%m-%Y", 10),
                      ("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%dT%H:%M:%S%z", 25)):
        try:
            return datetime.strptime(s[:slen], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _load_pdf_cache() -> dict:
    cache = {}
    if PDF_CACHE.exists():
        for line in PDF_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                cache[o["path"]] = o["body"]
            except Exception:  # noqa: BLE001
                continue
    return cache


def _save_pdf_cache(cache: dict) -> None:
    AGG.mkdir(parents=True, exist_ok=True)
    with open(PDF_CACHE, "w", encoding="utf-8") as f:
        for p, b in cache.items():
            f.write(json.dumps({"path": p, "body": b}, ensure_ascii=False) + "\n")


def _pdf_body(path: Path, cache: dict) -> str:
    key = str(path)
    if key in cache:
        return cache[key]
    b = extract_pdf_body(path) if path and path.exists() else ""
    if b:  # cache only non-empty (empty = scanned/missing → re-try next run)
        cache[key] = b
    return b


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate news CSVs → unified + stats")
    ap.add_argument("--no-pdf", action="store_true", help="skip PDF body parsing (fast)")
    ap.add_argument("--limit", type=int, default=0, help="cap rows per source (0=all, debug)")
    args = ap.parse_args()

    AGG.mkdir(parents=True, exist_ok=True)
    pdf_cache = {} if args.no_pdf else _load_pdf_cache()
    raw_counts: dict[str, int] = {}
    records: list[dict] = []

    for origin, fn, _renames in SOURCES:
        rows = _read_csv(DATA / fn)
        if args.limit:
            rows = rows[: args.limit]
        raw_counts[fn] = len(rows)
        for r in rows:
            url = r.get("url") or r.get("article_url") or r.get("pdf_url") or ""
            if not url:
                continue
            # body resolution
            body = (r.get("body") or "").strip()
            if not body and not args.no_pdf:
                if origin == "vietstock":
                    p = resolve_pdf_local_path("vietstock", r, data_path=DATA)
                    body = _pdf_body(p, pdf_cache) if p else ""
                elif origin == "ssi":
                    p = resolve_pdf_local_path("ssi", r, data_path=DATA)
                    body = _pdf_body(p, pdf_cache) if p else ""
            pub_raw = r.get("pub_date") or r.get("date") or ""
            records.append({
                "unified_id": "",
                "source": r.get("source") or origin,
                "title": (r.get("title") or "").strip(),
                "body": body,
                "lead": (r.get("lead") or "").strip(),
                "category": (r.get("category") or "").strip(),
                "author": (r.get("author") or "").strip(),
                "date": _norm_date(pub_raw),
                "pub_datetime": pub_raw,
                "url": url,
                "pdf_url": r.get("pdf_url") or "",
                "pdf_filename": r.get("pdf_filename") or "",
                "collected_at": r.get("collected_at") or r.get("downloaded_at") or "",
                "origin_file": fn,
            })

    # dedup by url (keep first), deterministic sort
    seen: set[str] = set()
    deduped: list[dict] = []
    for rec in records:
        u = rec["url"]
        if u in seen:
            continue
        seen.add(u)
        deduped.append(rec)
    deduped.sort(key=lambda r: (r["date"], r["source"], r["url"]))
    for i, rec in enumerate(deduped, 1):
        rec["unified_id"] = f"u{i:06d}"

    with open(UNIFIED_OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=UNIFIED_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(deduped)

    if not args.no_pdf:
        _save_pdf_cache(pdf_cache)
    _write_stats(deduped, raw_counts)
    print(f"-> {UNIFIED_OUT}: {len(deduped)} unique rows "
          f"(body filled: {sum(1 for r in deduped if r['body'])})")
    print(f"-> {STATS_OUT}")


def _write_stats(rows: list[dict], raw_counts: dict[str, int]) -> None:
    n = len(rows)
    with_lead = sum(1 for r in rows if r["lead"])
    with_body = sum(1 for r in rows if r["body"])
    with_date = sum(1 for r in rows if r["date"])
    years = Counter(r["date"][:4] for r in rows if r["date"])
    src_uniq = Counter(r["source"] for r in rows)
    origin_uniq = Counter(r["origin_file"] for r in rows)
    with open(STATS_OUT, "w", encoding="utf-8") as f:
        f.write("=== NEWS AGGREGATION STATS ===\n\n")
        f.write(f"Total unified rows (post-dedup by url): {n}\n")
        f.write(f"Rows WITH lead: {with_lead} ({with_lead * 100 // n if n else 0}%)\n")
        f.write(f"Rows WITH body: {with_body} ({with_body * 100 // n if n else 0}%)\n")
        f.write(f"Date parsed OK: {with_date}\n\n")
        f.write("Raw rows per input file:\n")
        for fn, c in raw_counts.items():
            f.write(f"  {fn:<30} {c}\n")
        f.write("\nUnique rows per origin file:\n")
        for fn, c in origin_uniq.most_common():
            f.write(f"  {fn:<30} {c}\n")
        f.write("\nTop sources:\n")
        for s, c in src_uniq.most_common(20):
            f.write(f"  {s:<22} {c}\n")
        f.write("\nPer-year coverage:\n")
        for y in sorted(years):
            f.write(f"  {y}    {years[y]}\n")


if __name__ == "__main__":
    main()
