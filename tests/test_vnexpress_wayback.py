"""Unit tests for vnexpress_wayback_backfill (Wayback Machine harvester for vnexpress,
since the live sitemap-shard endpoint is bot-blocked — see news_sitemap_crawler.py docstring)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import vnexpress_wayback_backfill as vw
from vnexpress_wayback_backfill import TARGETS, VnexpressWaybackBackfill, extract_articles

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "vnexpress_wayback"


def test_extract_articles_prefers_longer_title_for_duplicate_url():
    html = FIXTURES.joinpath("snapshot_sample.html").read_text(encoding="utf-8")
    out = extract_articles(html)
    assert out["https://vnexpress.net/mot-bai-viet-vi-du-5098041.html"] == "Một bài viết ví dụ"


def test_extract_articles_matches_subdomain_urls():
    html = FIXTURES.joinpath("snapshot_sample.html").read_text(encoding="utf-8")
    out = extract_articles(html)
    url = "http://kinhdoanh.vnexpress.net/tin-tuc/hang-hoa/chong-do-voi-thit-ngoai-nhap-3336505.html"
    assert url in out


def test_extract_articles_rejects_url_without_numeric_id():
    html = FIXTURES.joinpath("snapshot_sample.html").read_text(encoding="utf-8")
    out = extract_articles(html)
    assert "https://vnexpress.net/khong-phai-bai-viet.html" not in out


def test_extract_articles_empty_html():
    assert extract_articles("") == {}


def test_crawler_rejects_unknown_target():
    with pytest.raises(ValueError):
        VnexpressWaybackBackfill("unknown_target")


def test_list_snapshots_parses_cdx_json(tmp_path, monkeypatch):
    cdx_json = FIXTURES.joinpath("cdx_sample.json").read_text(encoding="utf-8")
    monkeypatch.setattr(VnexpressWaybackBackfill, "fetch", lambda self, url: cdx_json)
    c = VnexpressWaybackBackfill("kinh-doanh", csv_file=tmp_path / "v.csv")
    snapshots = c.list_snapshots()
    assert snapshots == [
        ("20181213021559", "https://vnexpress.net/kinh-doanh"),
        ("20190101154125", "https://vnexpress.net/kinh-doanh"),
    ]


def test_list_snapshots_handles_fetch_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(VnexpressWaybackBackfill, "fetch", lambda self, url: None)
    c = VnexpressWaybackBackfill("homepage", csv_file=tmp_path / "v.csv")
    assert c.list_snapshots() == []


def test_list_snapshots_handles_malformed_json(tmp_path, monkeypatch):
    monkeypatch.setattr(VnexpressWaybackBackfill, "fetch", lambda self, url: "not json")
    c = VnexpressWaybackBackfill("homepage", csv_file=tmp_path / "v.csv")
    assert c.list_snapshots() == []


def test_run_dedups_and_writes_csv(tmp_path, monkeypatch):
    cdx_json = FIXTURES.joinpath("cdx_sample.json").read_text(encoding="utf-8")
    snapshot_html = FIXTURES.joinpath("snapshot_sample.html").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url.startswith(vw.CDX_API):
            return cdx_json
        return snapshot_html

    monkeypatch.setattr(VnexpressWaybackBackfill, "fetch", fake_fetch)
    csv_file = tmp_path / "vnexpress_articles.csv"
    c = VnexpressWaybackBackfill("kinh-doanh", csv_file=csv_file, workers=2)
    counters = c.run()

    # 2 snapshots, each yields the same 2 articles -> 2 kept + 2 dup (second snapshot)
    assert counters["kept"] == 2
    assert counters["dup"] == 2
    rows = csv_file.read_text(encoding="utf-8-sig").splitlines()
    assert len(rows) == 3  # header + 2 articles


def test_run_no_snapshots_returns_early(tmp_path, monkeypatch):
    monkeypatch.setattr(VnexpressWaybackBackfill, "fetch", lambda self, url: None)
    c = VnexpressWaybackBackfill("homepage", csv_file=tmp_path / "v.csv")
    counters = c.run()
    assert counters["kept"] == 0
    assert not (tmp_path / "v.csv").exists()


def test_main_cli_runs(tmp_path, monkeypatch):
    cdx_json = FIXTURES.joinpath("cdx_sample.json").read_text(encoding="utf-8")
    snapshot_html = FIXTURES.joinpath("snapshot_sample.html").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url.startswith(vw.CDX_API):
            return cdx_json
        return snapshot_html

    monkeypatch.setattr(VnexpressWaybackBackfill, "fetch", fake_fetch)
    out_csv = tmp_path / "v.csv"
    monkeypatch.setattr(
        sys, "argv",
        ["vnexpress_wayback_backfill.py", "--target", "kinh-doanh", "--csv", str(out_csv)],
    )
    vw.main()
    assert out_csv.exists()


def test_targets_have_original_url_and_cadence():
    for cfg in TARGETS.values():
        assert cfg["original_url"].startswith("http")
        assert cfg["cadence"] in (6, 8)
