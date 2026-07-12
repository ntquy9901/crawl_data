"""build_objective — merge per-source cleaned CSVs into the versioned unified
VN30 objective dataset (FR-10, FR-12, FR-13; AD-8, AD-9, AD-13, AD-14).

Reads ``data/objective/*_records.csv`` (NOT ``news_unenriched_*`` — AD-14 Tier-2
raw stays in the companion file; NOT the opinion crawlers' ``data/*_articles.csv``
— AD-9 objective/opinion separation is enforced by directory), then:

  - AD-3 UTC-validate ``publish_time`` (reject non-canonical rows);
  - AD-4/5 keep only VN30 ``company_code``;
  - AD-6/13 cross-source dedup by ``checksum`` (sole cross-source identity);
  - write ``data/objective/objective_v<YYYYMM-DD>.csv`` (sorted, versioned).

CLI: ``python -m objective.build_objective [--date YYYY-MM-DD] [--out PATH]``
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

from objective.base_objective_crawler import OBJECTIVE_HEADERS, row_to_objective_record
from objective.schema import serialize_attachment_urls
from objective.vn30 import is_vn30

DATA_PATH = Path(__file__).resolve().parent.parent / "data"
OBJ_DIR = DATA_PATH / "objective"
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def discover_source_csvs(obj_dir: Path = OBJ_DIR) -> list[Path]:
    """Per-source cleaned CSVs. Excludes ``news_unenriched_*`` (AD-14)."""
    return sorted(
        p for p in obj_dir.glob("*_records.csv")
        if not p.name.startswith("news_unenriched_")
    )


def build_objective(
    obj_dir: Path = OBJ_DIR, out_path: Path | None = None, on_date: date | None = None
) -> tuple[Path, dict]:
    """Merge → unified versioned dataset. Returns (out_path, stats)."""
    on_date = on_date or date.today()
    out_path = Path(out_path) if out_path else OBJ_DIR / f"objective_v{on_date.isoformat()}.csv"
    stats = {"read": 0, "kept": 0, "deduped": 0, "utc_rejected": 0,
             "vn30_rejected": 0, "sources": 0}
    seen: set[str] = set()
    kept: list = []
    for src_csv in discover_source_csvs(obj_dir):
        stats["sources"] += 1
        with open(src_csv, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                stats["read"] += 1
                rec = row_to_objective_record(row)
                if not rec.publish_time or not _UTC_RE.match(rec.publish_time):
                    stats["utc_rejected"] += 1
                    continue
                if not (rec.company_code and is_vn30(rec.company_code)):
                    stats["vn30_rejected"] += 1
                    continue
                if rec.checksum in seen:
                    stats["deduped"] += 1
                    continue
                seen.add(rec.checksum)
                kept.append(rec)
                stats["kept"] += 1

    kept.sort(key=lambda r: (r.publish_time, r.source, r.company_code))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OBJECTIVE_HEADERS)
        w.writeheader()
        for rec in kept:
            row = {k: getattr(rec, k) for k in OBJECTIVE_HEADERS}
            row["attachment_urls"] = serialize_attachment_urls(rec.attachment_urls)
            w.writerow(row)
    return out_path, stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Build unified VN30 objective dataset")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD version (default: today)")
    ap.add_argument("--out", default=None, help="output CSV path")
    ap.add_argument("--obj-dir", default=None, help="per-source cleaned dir")
    args = ap.parse_args()
    on_date = date.fromisoformat(args.date) if args.date else None
    out, stats = build_objective(
        obj_dir=Path(args.obj_dir) if args.obj_dir else OBJ_DIR,
        out_path=Path(args.out) if args.out else None,
        on_date=on_date,
    )
    print(f"wrote {out}")
    print(f"  sources={stats['sources']} read={stats['read']} kept={stats['kept']} "
          f"deduped={stats['deduped']} utc_rejected={stats['utc_rejected']} "
          f"vn30_rejected={stats['vn30_rejected']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
