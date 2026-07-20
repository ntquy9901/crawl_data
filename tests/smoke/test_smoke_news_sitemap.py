"""Smoke (gate): tuoitre sitemap backfill runs end-to-end on saved fixtures. No network."""
from __future__ import annotations

from pathlib import Path

import pytest

import news_sitemap_crawler as nsc

pytestmark = pytest.mark.smoke
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "news_sitemap"


def test_tuoitre_backfill_smoke(tmp_path, monkeypatch):
    index_xml = FIXTURES.joinpath("tuoitre_index.xml").read_text(encoding="utf-8")
    shard_xml = FIXTURES.joinpath("tuoitre_shard.xml").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url == nsc.SOURCES["tuoitre"]["index_url"]:
            return index_xml
        return shard_xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)

    csv_file = tmp_path / "tuoitre_articles.csv"
    crawler = nsc.SitemapNewsCrawler("tuoitre", csv_file=csv_file, workers=2)
    counters = crawler.crawl_backfill()

    assert counters["kept"] == 1
    assert csv_file.exists()
    rows = csv_file.read_text(encoding="utf-8-sig").splitlines()
    assert len(rows) == 2  # header + 1 article
    assert "Một bài viết ví dụ" in rows[1]
