"""Unit tests for objective/build_objective.py (FR-10,12,13; AD-8,9,13,14)."""
from __future__ import annotations

import csv
from datetime import date

from objective.base_objective_crawler import OBJECTIVE_HEADERS
from objective.build_objective import build_objective, discover_source_csvs
from objective.schema import compute_checksum


def _row(doc_id, source, tier, url, pub, code, raw, checksum, event="dividend"):
    return {
        "document_id": doc_id, "source": source, "source_tier": tier, "url": url,
        "publish_time": pub, "crawl_time": "2026-07-10T00:00:00Z",
        "company_code": code, "company_name": code, "title": "t", "raw_text": raw,
        "language": "vi", "category": "", "event_type": event,
        "attachment_urls": "[]", "checksum": checksum, "raw_path": "",
    }


def _write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OBJECTIVE_HEADERS)
        w.writeheader()
        w.writerows(rows)


def _make_sources(tmp_path):
    obj = tmp_path / "objective"
    obj.mkdir()
    shared = compute_checksum("cổ tức VNM đợt 1")  # same disclosure in two sources
    # read order is alphabetical: 'vietstock' < 'vsdc', so vietstock's shared row wins
    _write(obj / "vietstock_records.csv", [
        _row("a" * 16, "vietstock", "tier3", "https://vs/1",
             "2026-07-08T00:00:00Z", "VNM", "vnm unique A", "cA"),
        _row("b" * 16, "vietstock", "tier3", "https://vs/2",
             "2026-07-09T00:00:00Z", "VNM", "cổ tức VNM đợt 1", shared),
    ])
    _write(obj / "vsdc_records.csv", [
        _row("c" * 16, "vsdc", "tier1", "https://vsd/1",
             "2026-07-10T00:00:00Z", "ACB", "acb event", "cB"),
        # cross-source dup (same checksum as vietstock's shared row) → deduped
        _row("d" * 16, "vsdc", "tier1", "https://vsd/2",
             "2026-07-09T00:00:00Z", "VNM", "cổ tức VNM đợt 1", shared),
        _row("e" * 16, "vsdc", "tier1", "https://vsd/3",
             "2026-07-10T00:00:00Z", "GPH", "gph", "cG", "other"),  # non-VN30
        _row("f" * 16, "vsdc", "tier1", "https://vsd/4",
             "NOT-UTC", "VNM", "bad", "cX"),  # bad UTC
    ])
    # AD-14: Tier-2 unenriched MUST be excluded from the unified dataset
    _write(obj / "news_unenriched_vnexpress_records.csv", [
        _row("g" * 16, "vnexpress", "tier2", "https://vne/1",
             "2026-07-07T00:00:00Z", "", "news", "cN", "other"),
    ])
    return obj


def test_discover_excludes_news_unenriched(tmp_path):
    obj = _make_sources(tmp_path)
    names = [p.name for p in discover_source_csvs(obj)]
    assert "vsdc_records.csv" in names
    assert "vietstock_records.csv" in names
    assert all(not n.startswith("news_unenriched_") for n in names)  # AD-14


def test_build_merges_dedups_filters_versions(tmp_path):
    obj = _make_sources(tmp_path)
    out, stats = build_objective(obj_dir=obj, on_date=date(2026, 7, 12))
    assert out.name == "objective_v2026-07-12.csv"           # versioned (FR-12)
    assert stats["sources"] == 2                              # excluded news_unenriched (AD-14)
    assert stats["read"] == 6                                 # 4 vsdc + 2 vietstock
    assert stats["utc_rejected"] == 1                        # AD-3
    assert stats["vn30_rejected"] == 1                       # GPH (AD-4/5)
    assert stats["deduped"] == 1                             # cross-source checksum dup (AD-6/13)
    assert stats["kept"] == 3                                # vnmA, vnm-shared, acbB


def test_build_output_sorted_and_canonical(tmp_path):
    obj = _make_sources(tmp_path)
    out, _ = build_objective(obj_dir=obj, on_date=date(2026, 7, 12))
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    # sorted by publish_time asc: 07-08 (vnmA), 07-09 (vnm shared), 07-10 (acbB)
    assert [r["company_code"] for r in rows] == ["VNM", "VNM", "ACB"]
    # every kept row is VN30 + canonical UTC (AD-9 separation by directory)
    for r in rows:
        assert r["company_code"] in {"ACB", "VNM"}
        assert r["publish_time"].endswith("Z")


def test_build_empty_obj_dir(tmp_path):
    obj = tmp_path / "objective"
    obj.mkdir()
    out, stats = build_objective(obj_dir=obj, on_date=date(2026, 7, 12))
    assert stats["read"] == 0 and stats["kept"] == 0
    assert out.exists()  # header-only file written
