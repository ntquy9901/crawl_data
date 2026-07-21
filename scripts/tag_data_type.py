"""Gắn cột ``data_type`` vào dataset + xuất index phân loại toàn bộ dữ liệu.

Làm 2 việc:

1. Thêm cột ``data_type`` cho ``data/vnstock_articles.csv`` — toàn bộ là báo cáo
   phân tích CTCK (source = mã broker: VNDS/VPX/MBS/...) → ``subjective_expert``.
   Idempotent: nếu cột đã có, tính lại (re-run an toàn). Backup ``.bak`` lần đầu.

2. Xuất ``data/data_classification_index.csv`` — bảng tổng hợp các nhóm dữ liệu:
   ``dataset, source, data_type, rows, year_min, year_max`` cho mọi file hiện có
   (vnstock, news theo source, objective/*, macro, telegram). File thiếu → bỏ qua.

Chạy: PYTHONUTF8=1 python scripts/tag_data_type.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
from pathlib import Path

from data_classification import SUBJECTIVE_EXPERT

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
VNSTOCK = DATA / "vnstock_articles.csv"
INDEX_OUT = DATA / "data_classification_index.csv"

_YR = re.compile(r"(19|20)\d{2}")


def year_from_date(s: str) -> int | None:
    """Rút năm (int) từ nhiều format ngày (DD/MM/YYYY, ISO, ...). None nếu không có."""
    if not s:
        return None
    m = _YR.search(str(s))
    return int(m.group(0)) if m else None


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------- 1. tag vnstock_articles.csv ----------
def tag_vnstock(path: Path = VNSTOCK, dry_run: bool = False) -> int:
    if not path.exists():
        print(f"skip tag: {path} không có")
        return 0
    rows = _read_csv(path)
    if not rows:
        return 0
    fieldnames = list(rows[0].keys())
    if "data_type" not in fieldnames:
        fieldnames.append("data_type")
    changed = 0
    for r in rows:
        if r.get("data_type") != SUBJECTIVE_EXPERT:
            r["data_type"] = SUBJECTIVE_EXPERT
            changed += 1
    print(f"vnstock_articles: {len(rows)} rows → data_type={SUBJECTIVE_EXPERT} "
          f"(cột {'thêm mới' if changed else 'đã có'})")
    if dry_run:
        print("(dry-run: không ghi)")
    elif changed:
        bak = path.with_suffix(".csv.bak")
        if not bak.exists():
            shutil.copy2(path, bak)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"-> đã ghi {path}")
    return len(rows)


# ---------- 2. classification index ----------
def _row_stats(rows: list[dict], date_field: str) -> tuple[int, int | None, int | None]:
    yrs = [year_from_date(r.get(date_field, "")) for r in rows]
    yrs = [y for y in yrs if y]
    return len(rows), (min(yrs) if yrs else None), (max(yrs) if yrs else None)


def _index_vnstock(data_dir: Path) -> list[dict]:
    """Build index entry for vnstock analysis reports."""
    entries = []
    p = data_dir / "vnstock_articles.csv"
    if p.exists():
        rows = _read_csv(p)
        n, lo, hi = _row_stats(rows, "date")
        entries.append({"dataset": "vnstock_articles", "source": "(broker research PDFs)",
                        "data_type": SUBJECTIVE_EXPERT, "rows": n,
                        "year_min": lo or "", "year_max": hi or ""})
    return entries


def _index_news(data_dir: Path) -> list[dict]:
    """Build index entries for news articles by source."""
    entries = []
    p = data_dir / "news_articles.csv"
    if p.exists():
        rows = _read_csv(p)
        from collections import defaultdict
        by_src: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_src[r.get("source", "?")].append(r)
        from data_classification import classify
        for src in sorted(by_src):
            sub = by_src[src]
            n, lo, hi = _row_stats(sub, "pub_date")
            entries.append({"dataset": "news_articles", "source": src,
                            "data_type": classify(src), "rows": n,
                            "year_min": lo or "", "year_max": hi or ""})
    return entries


def _index_objective(obj_dir: Path) -> list[dict]:
    """Build index entries for objective layer CSVs."""
    entries = []
    for csv_p in sorted(obj_dir.rglob("*.csv")) if obj_dir.exists() else []:
        if csv_p.stat().st_size == 0:
            continue
        try:
            rows = _read_csv(csv_p)
        except Exception:  # noqa: BLE001
            continue
        if not rows:
            continue
        df = next((c for c in ("publish_time", "pub_date", "date") if c in rows[0]), None)
        n, lo, hi = _row_stats(rows, df or "")
        entries.append({"dataset": f"objective/{csv_p.parent.name}/{csv_p.name}",
                        "source": csv_p.stem, "data_type": "objective", "rows": n,
                        "year_min": lo or "", "year_max": hi or ""})
    return entries


def _index_macro(data_dir: Path) -> list[dict]:
    """Build index entries for macro data."""
    entries = []
    macro = data_dir / "macro"
    if macro.exists():
        for csv_p in sorted(macro.rglob("*.csv")):
            try:
                rows = _read_csv(csv_p)
            except Exception:  # noqa: BLE001
                continue
            if not rows:
                continue
            entries.append({"dataset": f"macro/{csv_p.name}", "source": csv_p.stem,
                            "data_type": "objective", "rows": len(rows),
                            "year_min": "", "year_max": ""})
    return entries


def build_index(data_dir: Path = DATA, out: Path = INDEX_OUT, dry_run: bool = False) -> list[dict]:
    entries: list[dict] = []
    entries.extend(_index_vnstock(data_dir))
    entries.extend(_index_news(data_dir))
    entries.extend(_index_objective(PROJECT_ROOT / "objective"))
    entries.extend(_index_macro(data_dir))

    p = data_dir / "telegram_articles.csv"
    if p.exists():
        rows = _read_csv(p)
        if rows:
            n, lo, hi = _row_stats(rows, "pub_date")
            entries.append({"dataset": "telegram_articles", "source": "telegram",
                            "data_type": "subjective_crowd", "rows": n,
                            "year_min": lo or "", "year_max": hi or ""})

    if dry_run:
        print("(dry-run: index không ghi)")
    else:
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["dataset", "source", "data_type",
                                               "rows", "year_min", "year_max"])
            w.writeheader()
            w.writerows(entries)
        print(f"-> index {out}: {len(entries)} nhóm dữ liệu")
    return entries


def main(dry_run: bool = False):
    tag_vnstock(dry_run=dry_run)
    print()
    entries = build_index(dry_run=dry_run)
    # in bảng tóm tắt
    print("\n=== PHÂN LOẠI DỮ LIỆU ===")
    print(f"{'dataset':38} {'source':22} {'data_type':18} {'rows':>7}  năm")
    for e in entries:
        yr = f"{e['year_min']}–{e['year_max']}" if e["year_min"] else "?"
        print(f"{e['dataset']:38} {e['source'][:22]:22} {e['data_type']:18} "
              f"{e['rows']:>7}  {yr}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Tag data_type + xuất index phân loại")
    ap.add_argument("--dry-run", action="store_true")
    main(dry_run=ap.parse_args().dry_run)
