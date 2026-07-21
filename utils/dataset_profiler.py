"""
Dataset Profiler — compute persistent profiles/snapshots of data files.

CLI:
  snapshot  → compute + save profile for one or all sources
  diff      → compare two snapshots of a source
  list      → list available snapshots
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data"
PROFILES_DIR = PROJECT_ROOT / "data" / "dataset_profiles"
HN_TZ = timezone(timedelta(hours=7))

DATE_COLUMN_CANDIDATES = (
    "date", "pub_date", "publish_time", "effective_date", "collected_at"
)

EXPECTED_COLUMNS = {
    "vnstock": ["id", "title", "source", "date", "pdf_url"],
    "ssi": ["id", "source", "title", "pub_date", "url"],
    "hsc": ["id", "source", "title", "pub_date", "url"],
    "vndirect": ["id", "source", "title", "pub_date", "url"],
    "tuoitre": ["id", "source", "title", "pub_date", "url"],
    "thanhnien": ["id", "source", "title", "pub_date", "url"],
    "vietnamplus": ["id", "source", "title", "pub_date", "url"],
    "vnexpress": ["id", "source", "title", "pub_date", "url"],
    "cafef": ["id", "title", "pub_date", "article_url"],
    "forum_traderviet": ["id", "source", "title", "pub_date", "url"],
    "news_merged": ["source", "title", "pub_date", "url"],
}


def _file_to_key(path: Path) -> str:
    name = path.name
    mapping = {
        "vnstock_articles.csv": "vnstock",
        "vnstock_pdf_raw.csv": "vnstock_pdf_raw",
        "vnstock_pdfs_extracted.csv": "vnstock_pdf_raw",
        "data.csv": "vnstock",
        "data_archive.csv": "vnstock",
        "data_2021_2025.csv": "vnstock",
        "cafef_articles.csv": "cafef",
        "ssi_articles.csv": "ssi",
        "hsc_articles.csv": "hsc",
        "vndirect_articles.csv": "vndirect",
        "tuoitre_articles.csv": "tuoitre",
        "thanhnien_articles.csv": "thanhnien",
        "vietnamplus_articles.csv": "vietnamplus",
        "vnexpress_articles.csv": "vnexpress",
        "forum_articles.csv": "forum_traderviet",
        "news_articles.csv": "news_merged",
    }
    return mapping.get(name, "unknown")


def safe_read_csv(path: Path, **kwargs) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)
    except Exception:
        return pd.DataFrame()


def _detect_date_format(sample_series: pd.Series) -> str | None:
    sample = sample_series.dropna().head(50).astype(str)
    if sample.empty:
        return None
    dmy_count = sum(
        1 for s in sample if bool(re.match(r'\d{2}/\d{2}/\d{4}', s))
    )
    return "dmy" if dmy_count > len(sample) / 2 else "iso"


def _compute_temporal(df: pd.DataFrame, _key: str) -> dict:
    date_col = None
    for c in DATE_COLUMN_CANDIDATES:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        return {"date_column": None, "min": None, "max": None,
                "yearly_counts": {}, "gaps": [], "parse_error_pct": 0.0}

    fmt = _detect_date_format(df[date_col])
    parsed = pd.to_datetime(df[date_col], errors="coerce",
                            dayfirst=(fmt == "dmy"))
    valid = parsed.dropna()
    total = len(df[date_col].dropna())
    parse_error_pct = round(
        (total - len(valid)) / total * 100, 1
    ) if total > 0 else 0.0

    if valid.empty:
        return {"date_column": date_col, "min": None, "max": None,
                "yearly_counts": {}, "gaps": [], "parse_error_pct": parse_error_pct}

    years = valid.dt.year
    yearly_counts = years.value_counts().sort_index()
    yearly = {str(int(k)): int(v) for k, v in yearly_counts.items()}

    yr_min = int(yearly_counts.index.min())
    yr_max = int(yearly_counts.index.max())
    expected_years = set(range(yr_min, yr_max + 1))
    present_years = {int(k) for k in yearly}
    gaps = sorted(str(y) for y in expected_years - present_years)

    return {
        "date_column": date_col,
        "min": valid.min().strftime("%Y-%m-%d"),
        "max": valid.max().strftime("%Y-%m-%d"),
        "yearly_counts": yearly,
        "gaps": gaps,
        "parse_error_pct": parse_error_pct,
    }


def _compute_quality(df: pd.DataFrame, _key: str,
                     temporal: dict) -> dict:
    total = len(df)
    null_columns = {}
    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        if null_count > 0:
            null_columns[col] = round(null_count / total * 100, 1)

    dup_rate = 0.0
    for id_col in ("id", "document_id", "url"):
        if id_col in df.columns:
            dup_count = int(df[id_col].duplicated().sum())
            if dup_count > 0:
                dup_rate = round(dup_count / total * 100, 1)
            break

    expected = EXPECTED_COLUMNS.get(_key, [])
    present_cols = set(df.columns)
    missing_expected = [c for c in expected if c not in present_cols]

    non_null = sum(1 for v in null_columns.values() if v < 100)
    total_cols = len(df.columns)
    completeness = round(
        non_null / total_cols * 100, 1
    ) if total_cols else 100.0

    return {
        "null_columns": null_columns,
        "duplicate_rate_pct": dup_rate,
        "date_parse_error_pct": temporal.get("parse_error_pct", 0.0),
        "schema_valid": len(missing_expected) == 0,
        "missing_expected_columns": missing_expected,
        "completeness_pct": completeness,
    }


def compute_profile(path: Path, key: str) -> dict:
    df = safe_read_csv(path)
    if df.empty:
        return {"source_key": key, "file": path.name,
                "records": {"count": 0, "size_mb": 0.0},
                "temporal": {}, "quality": {}, "schema": {}}

    size_mb = round(path.stat().st_size / (1024 * 1024), 1)
    temporal = _compute_temporal(df, key)
    quality = _compute_quality(df, key, temporal)

    dtypes = {str(c): str(d) for c, d in df.dtypes.items()}
    expected = EXPECTED_COLUMNS.get(key, [])
    present_cols = list(df.columns)
    missing_expected = [c for c in expected if c not in present_cols]

    return {
        "source_key": key,
        "file": path.name,
        "records": {"count": len(df), "size_mb": size_mb},
        "temporal": temporal,
        "quality": quality,
        "schema": {
            "columns": present_cols,
            "dtypes": dtypes,
            "expected_columns": expected,
            "missing_expected": missing_expected,
        },
    }


def profile_path(source_key: str) -> Path:
    return PROFILES_DIR / source_key


def save_profile(profile: dict) -> Path:
    key = profile["source_key"]
    dir_path = profile_path(key)
    dir_path.mkdir(parents=True, exist_ok=True)

    now = datetime.now(HN_TZ)
    profile["snapshot_date"] = now.isoformat()
    filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}.json"
    out = dir_path / filename

    with open(out, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    return out


def load_snapshots(source_key: str) -> list[dict]:
    dir_path = profile_path(source_key)
    if not dir_path.exists():
        return []
    snapshots = []
    for f in sorted(dir_path.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            snapshots.append(json.load(fh))
    return snapshots


def diff_profiles(before: dict, after: dict) -> dict:
    changes = {}

    b_rec = before.get("records", {})
    a_rec = after.get("records", {})
    b_count = b_rec.get("count", 0)
    a_count = a_rec.get("count", 0)
    changes["row_count"] = {"before": b_count, "after": a_count,
                            "delta": a_count - b_count}

    b_t = before.get("temporal", {})
    a_t = after.get("temporal", {})
    changes["date_range"] = {
        "before": {"min": b_t.get("min"), "max": b_t.get("max")},
        "after": {"min": a_t.get("min"), "max": a_t.get("max")},
    }

    b_q = before.get("quality", {})
    a_q = after.get("quality", {})
    changes["quality"] = {
        "completeness": {"before": b_q.get("completeness_pct"),
                         "after": a_q.get("completeness_pct")},
        "duplicate_rate": {"before": b_q.get("duplicate_rate_pct"),
                           "after": a_q.get("duplicate_rate_pct")},
    }

    b_sz = b_rec.get("size_mb", 0)
    a_sz = a_rec.get("size_mb", 0)
    changes["size_mb"] = {"before": b_sz, "after": a_sz,
                          "delta": round(a_sz - b_sz, 1)}

    return changes


def _scan_data_files() -> list[tuple[Path, str]]:
    results = []
    for f in sorted(DATA_PATH.glob("*.csv")):
        if f.name.startswith((".", "data_catalog", "data_classification")):
            continue
        key = _file_to_key(f)
        if key != "unknown":
            results.append((f, key))
    for g in ("objective", "macro/raw"):
        for f in sorted(DATA_PATH.glob(f"{g}/*.csv")):
            if f.name.startswith("."):
                continue
            key = _file_to_key(f)
            if key == "unknown":
                continue
            results.append((f, key))
    return results


def _snapshot_all() -> list[Path]:
    written = []
    for path, key in _scan_data_files():
        profile = compute_profile(path, key)
        out = save_profile(profile)
        written.append(out)
    return written


def _snapshot_sources(keys: list[str]) -> list[Path]:
    written = []
    for path, key in _scan_data_files():
        if key in keys:
            profile = compute_profile(path, key)
            out = save_profile(profile)
            written.append(out)
    return written


def _list_snapshots():
    if not PROFILES_DIR.exists():
        return []
    entries = []
    for src_dir in sorted(PROFILES_DIR.iterdir()):
        if src_dir.is_dir():
            files = sorted(src_dir.glob("*.json"))
            if files:
                entries.append({
                    "source": src_dir.name,
                    "snapshots": len(files),
                    "latest": files[-1].stem,
                    "latest_path": str(files[-1]),
                })
    return entries


def cmd_snapshot(args):
    if args.sources:
        written = _snapshot_sources(args.sources)
    else:
        written = _snapshot_all()
    for w in written:
        print(f"  Snapshot: {w}")


def cmd_diff(args):
    snapshots = load_snapshots(args.source)
    if len(snapshots) < 2:
        print(f"  Need ≥2 snapshots for {args.source} (found {len(snapshots)})")
        return
    before = snapshots[-2]
    after = snapshots[-1]
    if args.from_tag:
        for s in snapshots:
            sd = s.get("snapshot_date", "")[:10]
            if sd == args.from_tag:
                before = s
                break
    if args.to_tag:
        for s in snapshots:
            sd = s.get("snapshot_date", "")[:10]
            if sd == args.to_tag:
                after = s
                break
    result = diff_profiles(before, after)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_list(_args):
    entries = _list_snapshots()
    if not entries:
        print("  No snapshots found.")
        return
    print(f"  {'Source':<25} {'Snapshots':>10}  {'Latest':<20}")
    print(f"  {'-'*25} {'-'*10}  {'-'*20}")
    for e in entries:
        print(f"  {e['source']:<25} {e['snapshots']:>10}  {e['latest']:<20}")


def main():
    ap = argparse.ArgumentParser(
        description="Dataset Profiler — snapshot, diff, list")
    sub = ap.add_subparsers(dest="command")

    snap = sub.add_parser("snapshot", help="Compute and save profile(s)")
    snap.add_argument("--sources", nargs="*", default=None,
                      help="Source keys (default: all)")

    diff = sub.add_parser("diff", help="Compare two snapshots")
    diff.add_argument("--source", required=True)
    diff.add_argument("--from-tag", help="YYYY-MM-DD of earlier snapshot")
    diff.add_argument("--to-tag", help="YYYY-MM-DD of later snapshot")

    sub.add_parser("list", help="List available snapshots")

    args = ap.parse_args()
    if args.command == "snapshot":
        cmd_snapshot(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
