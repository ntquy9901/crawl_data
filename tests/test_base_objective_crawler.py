"""Unit tests for objective/base_objective_crawler.py (AD-7, AD-2, AD-3, AD-6, AD-13)."""
from __future__ import annotations

import csv
from pathlib import Path

from objective import base_objective_crawler as boc
from objective.base_objective_crawler import (
    OBJECTIVE_HEADERS,
    BaseObjectiveCrawler,
    now_utc,
    to_utc,
)

# ---- to_utc (AD-3) ----

def test_to_utc_empty():
    assert to_utc("") == ""
    assert to_utc(None) == ""


def test_to_utc_offset_converted_to_utc():
    # 2026-07-10 10:00:00 +07:00 → 03:00:00 UTC
    assert to_utc("2026-07-10T10:00:00+07:00") == "2026-07-10T03:00:00Z"


def test_to_utc_z_kept():
    assert to_utc("2026-07-10T10:00:00Z") == "2026-07-10T10:00:00Z"


def test_to_utc_naive_assumes_vn_tz():
    # naive 10:00 assumed +07 → 03:00 UTC
    assert to_utc("2026-07-10T10:00:00") == "2026-07-10T03:00:00Z"
    assert to_utc("2026-07-10 10:00:00") == "2026-07-10T03:00:00Z"


def test_to_utc_date_only_midnight_utc():
    assert to_utc("2026-07-10") == "2026-07-10T00:00:00Z"
    assert to_utc("10/07/2026") == "2026-07-10T00:00:00Z"


def test_to_utc_unparseable_returns_empty():
    assert to_utc("not a date") == ""
    assert to_utc("hôm nay") == ""


def test_now_utc_is_canonical():
    t = now_utc()
    assert t.endswith("Z") and len(t) == 20  # YYYY-MM-DDTHH:MM:SSZ


# ---- OBJECTIVE_HEADERS ----

def test_objective_headers_are_16_record_fields():
    from dataclasses import fields
    assert OBJECTIVE_HEADERS == [f.name for f in fields(boc.ObjectiveRecord)]
    assert len(OBJECTIVE_HEADERS) == 16


# ---- a fake adapter to exercise the flow without network ----

class _FakeCrawler(BaseObjectiveCrawler):
    source = "fake"
    source_tier = "tier1"

    def fetch(self, url):  # noqa: D401 — bypass network
        return "<html><body>raw disclosure page</body></html>"

    def parse_article(self, html, item):
        return {
            "title": "Thông báo cổ tức VNM",
            "publish_time": "2026-07-10",
            "company_code": "vnm",          # lowercase → must be uppercased
            "company_name": "Công ty CP Sữa Việt Nam",
            "raw_text": "<p>Cổ tức bằng tiền mặt 10%</p>",
            "language": "vi",
            "category": "cbtt",
            "event_type": "dividend",
            "attachment_urls": ["https://x.vn/a.pdf", "https://x.vn/b.pdf"],
        }


def _make(tmp_path: Path) -> _FakeCrawler:
    return _FakeCrawler(csv_file=tmp_path / "rec.csv", raw_root=tmp_path / "raw")


# ---- _fetch_and_parse ----

def test_fetch_and_parse_builds_full_row(tmp_path):
    c = _make(tmp_path)
    row = c._fetch_and_parse({"url": "https://x.vn/ad/1?utm_src=z"})
    assert row is not None
    assert set(row.keys()) == set(OBJECTIVE_HEADERS)
    assert row["document_id"] and len(row["document_id"]) == 16      # AD-13
    assert len(row["checksum"]) == 64                                # AD-6
    assert row["crawl_time"].endswith("Z")                          # AD-3
    assert row["publish_time"] == "2026-07-10T00:00:00Z"            # AD-3 date-only
    assert row["company_code"] == "VNM"                             # uppercased (AD-4)
    assert row["event_type"] == "dividend"
    assert "utm_src" not in row["url"]                              # canonicalized (AD-13)
    assert row["attachment_urls"] == ["https://x.vn/a.pdf", "https://x.vn/b.pdf"]


def test_fetch_and_parse_saves_raw(tmp_path):
    c = _make(tmp_path)
    row = c._fetch_and_parse({"url": "https://x.vn/ad/1"})
    raw = Path(row["raw_path"])
    assert raw.exists()
    assert "raw disclosure page" in raw.read_text(encoding="utf-8")  # AD-2
    assert raw.name.startswith(row["document_id"]) and raw.name.endswith(".html")


def test_fetch_and_parse_returns_none_on_fetch_fail(tmp_path):
    class _Fail(_FakeCrawler):
        def fetch(self, url):
            return None
    c = _Fail(csv_file=tmp_path / "rec.csv", raw_root=tmp_path / "raw")
    assert c._fetch_and_parse({"url": "https://x.vn/ad/1"}) is None


# ---- _append / _init_csv / _load_seen ----

def test_append_writes_objective_csv(tmp_path):
    c = _make(tmp_path)
    row = c._fetch_and_parse({"url": "https://x.vn/ad/1"})
    c._append([row])
    text = (tmp_path / "rec.csv").read_text(encoding="utf-8-sig")
    header = text.splitlines()[0]
    assert header.split(",") == OBJECTIVE_HEADERS
    # attachment_urls serialized as pipe-separated
    data = list(csv.DictReader((tmp_path / "rec.csv").open(encoding="utf-8-sig")))
    assert data[0]["document_id"] == row["document_id"]
    assert data[0]["attachment_urls"] == "https://x.vn/a.pdf|https://x.vn/b.pdf"


def test_load_seen_reads_url_column(tmp_path):
    c = _make(tmp_path)
    c._append([c._fetch_and_parse({"url": "https://x.vn/ad/1?b=2&a=1"})])
    c2 = _make(tmp_path)  # fresh instance reads existing CSV
    seen = c2._load_seen()
    assert any("x.vn/ad/1" in u for u in seen)  # resume works (AD-6 url-dedup)


# ---- default paths ----

def test_default_csv_and_raw_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(boc, "DATA_PATH", tmp_path)
    c = _FakeCrawler()  # no explicit csv_file/raw_root
    assert c.csv_file == tmp_path / "objective" / "fake_records.csv"
    assert c.raw_dir == tmp_path / "raw" / "fake"
    assert c.raw_dir.exists()
