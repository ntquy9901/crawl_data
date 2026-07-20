"""Smoke (gate): vnexpress Wayback backfill runs end-to-end on saved fixtures. No network."""
from __future__ import annotations

from pathlib import Path

import pytest

import vnexpress_wayback_backfill as vw

pytestmark = pytest.mark.smoke
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "vnexpress_wayback"


def test_vnexpress_wayback_smoke(tmp_path, monkeypatch):
    cdx_json = FIXTURES.joinpath("cdx_sample.json").read_text(encoding="utf-8")
    snapshot_html = FIXTURES.joinpath("snapshot_sample.html").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url.startswith(vw.CDX_API):
            return cdx_json
        return snapshot_html

    monkeypatch.setattr(vw.VnexpressWaybackBackfill, "fetch", fake_fetch)
    csv_file = tmp_path / "vnexpress_articles.csv"
    crawler = vw.VnexpressWaybackBackfill("kinh-doanh", csv_file=csv_file, workers=2)
    counters = crawler.run()

    assert counters["kept"] == 2
    assert csv_file.exists()
    rows = csv_file.read_text(encoding="utf-8-sig").splitlines()
    assert "Một bài viết ví dụ" in rows[1] or "Một bài viết ví dụ" in rows[2]
