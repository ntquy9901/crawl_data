"""Unit tests cho MacroCrawler logic — network stubbed qua monkeypatch `fetch`.

Mục tiêu: cover fetch_*, resume (_max_date/_window/_save), orchestration (run), CLI —
không đụng network thật.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

import macro_crawler as mc
from macro_config import HEADERS_DXY, VNDIRECT_PAGE_SIZE

FIX = Path(__file__).resolve().parent / "fixtures" / "macro"


def _stub_fetch_from(monkeypatch, fname: str) -> None:
    """Monkeypatch mc.fetch để trả nội dung fixture (no network)."""
    monkeypatch.setattr(
        mc, "fetch", lambda url, params=None: (FIX / fname).read_text(encoding="utf-8")
    )


def test_num_and_clean_num():
    assert mc._num(None) == "" and mc._num("nan") == "" and mc._num(1.5) == "1.5"
    assert mc._clean_num("24,340") == "24340" and mc._clean_num(None) == ""


# ---------- fetch methods (network stubbed) ----------
def test_fetch_dxy_stubbed(monkeypatch):
    _stub_fetch_from(monkeypatch, "fred_dxy.csv")
    rows = mc.MacroCrawler().fetch_dxy()
    assert rows[0]["date"] == "2006-01-03" and rows[0]["dxy"] == "112.5"
    assert rows[1]["dxy"] == ""                       # "." sentinel → empty


def test_fetch_vnindex_stubbed(monkeypatch):
    _stub_fetch_from(monkeypatch, "vndirect_vnindex.json")
    rows = mc.MacroCrawler().fetch_vnindex()
    assert len(rows) == 3 and rows[0]["close"] == "100.5" and rows[0]["source"] == "vndirect"


def test_fetch_vnindex_paginates_until_short_page(monkeypatch):
    big = {"data": [{"date": f"2000-02-{i:02d}", "open": 1, "high": 1, "low": 1,
                     "close": 1, "volume": 1} for i in range(1, VNDIRECT_PAGE_SIZE + 1)]}
    small = '{"data":[{"date":"2000-03-01","open":2,"high":2,"low":2,"close":2,"volume":2}]}'
    calls = {"n": 0}

    def fake(url, params=None):
        calls["n"] += 1
        return json.dumps(big) if params and params.get("page") == 1 else small

    monkeypatch.setattr(mc, "fetch", fake)
    rows = mc.MacroCrawler().fetch_vnindex()
    assert len(rows) == VNDIRECT_PAGE_SIZE + 1        # full page + short page
    assert calls["n"] == 2                            # dừng sau page ngắn


def test_fetch_usd_vnd_vcb_stubbed(monkeypatch):
    _stub_fetch_from(monkeypatch, "vcb_rates.html")
    c = mc.MacroCrawler(from_date=date(2024, 1, 2), end_date=date(2024, 1, 3))
    rows = c.fetch_usd_vnd_vcb()
    assert rows and rows[0]["usd_vnd_sell"] == "24340" and rows[0]["source"] == "vcb"


def test_fetch_usd_vnd_sbv_stub_returns_empty():
    assert mc.MacroCrawler().fetch_usd_vnd_sbv() == []


# ---------- resume / save logic ----------
def test_max_date_and_missing(tmp_path):
    csv_path = tmp_path / "dxy.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS_DXY)
        w.writerow(["2024-01-02", "1", "fred", "t"])
        w.writerow(["not-a-date", "9", "fred", "t"])   # malformed → phải bỏ qua
        w.writerow(["2024-03-01", "2", "fred", "t"])
    c = mc.MacroCrawler()
    assert c._max_date(csv_path) == date(2024, 3, 1)    # không crash, max đúng
    assert c._max_date(tmp_path / "nope.csv") is None


def test_window_resumes_from_max_plus_one(tmp_path):
    csv_path = tmp_path / "dxy.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS_DXY)
        w.writerow(["2024-01-05", "1", "fred", "t"])
    c = mc.MacroCrawler(end_date=date(2024, 1, 10))
    fr, to = c._window(csv_path)
    assert fr == "2024-01-06" and to == "2024-01-10"


def test_save_skips_existing_future_and_dedups(tmp_path):
    csv_path = tmp_path / "dxy.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS_DXY)
        w.writerow(["2024-01-02", "101.0", "fred", "t"])
        w.writerow(["2024-01-03", "102.0", "fred", "t"])
    c = mc.MacroCrawler(end_date=date(2024, 1, 5))
    n = c._save(csv_path, HEADERS_DXY, [
        {"date": "2024-01-03", "dxy": "102.0"},      # đã có → skip
        {"date": "2024-01-04", "dxy": "103.0"},      # mới → keep
        {"date": "2024-01-06", "dxy": "999.0"},      # future (>end) → skip
        {"date": "2024-01-04", "dxy": "103.1"},      # trùng date → keep cuối
    ])
    assert n == 1
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3                             # 2 gốc + 1 mới
    assert rows[-1]["dxy"] == "103.1"                 # dedup giữ value cuối


# ---------- run() orchestration ----------
def test_run_writes_dxy_via_threadpool(monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "RAW_DXY", tmp_path / "dxy.csv")
    _stub_fetch_from(monkeypatch, "fred_dxy.csv")
    mc.MacroCrawler(sources=["dxy"]).run()
    with open(tmp_path / "dxy.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 5


def test_run_isolates_failing_source(monkeypatch, tmp_path):
    # fetch raise → run() phải bắt, đánh dấu -1, KHÔNG crash; không ghi file.
    monkeypatch.setattr(mc, "RAW_DXY", tmp_path / "dxy.csv")

    def boom(url, params=None):
        raise RuntimeError("net down")

    monkeypatch.setattr(mc, "fetch", boom)
    mc.MacroCrawler(sources=["dxy"]).run()      # không raise
    assert not (tmp_path / "dxy.csv").exists()  # không ghi gì


# ---------- CLI ----------
def test_main_rejects_bad_source(monkeypatch):
    monkeypatch.setattr("sys.argv", ["macro_crawler.py", "--sources", "bogus"])
    with pytest.raises(SystemExit):
        mc.main()
