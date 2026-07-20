"""Unit tests for news_sitemap_crawler (tuoitre/thanhnien/vietnamplus sitemap backfill)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

import news_sitemap_crawler as nsc
from news_sitemap_crawler import (
    SOURCES,
    SitemapNewsCrawler,
    _parse_date,
    clean_title,
    parse_shard,
    shards_in_range,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "news_sitemap"


def test_clean_title_entity_escaped_cdata():
    # image:title style: HTML-entity-escaped CDATA
    raw = "&lt;![CDATA[Một bài viết ví dụ]]&gt;"
    assert clean_title(raw) == "Một bài viết ví dụ"


def test_clean_title_real_cdata():
    # news:title style: real CDATA (no entity escaping needed)
    raw = "<![CDATA[Một bài viết ví dụ]]>"
    assert clean_title(raw) == "Một bài viết ví dụ"


def test_clean_title_empty():
    assert clean_title("") == ""


def test_shards_in_range_filters_by_year_month():
    xml = FIXTURES.joinpath("tuoitre_index.xml").read_text(encoding="utf-8")
    shard_re = SOURCES["tuoitre"]["shard_re"]
    shards = shards_in_range(xml, shard_re, date(2026, 7, 1), date(2026, 7, 31))
    assert shards == ["https://tuoitre.vn/StaticSitemaps/sitemaps-2026-7-16-20.xml"]


def test_shards_in_range_no_match_outside_window():
    xml = FIXTURES.joinpath("tuoitre_index.xml").read_text(encoding="utf-8")
    shard_re = SOURCES["tuoitre"]["shard_re"]
    shards = shards_in_range(xml, shard_re, date(2020, 1, 1), date(2020, 12, 31))
    assert shards == []


def test_parse_shard_tuoitre_extracts_title_and_filters_suffix():
    xml = FIXTURES.joinpath("tuoitre_shard.xml").read_text(encoding="utf-8")
    items = parse_shard(xml, SOURCES["tuoitre"]["article_suffix"])
    assert len(items) == 1  # the .htm.rss url is filtered out
    it = items[0]
    assert it["url"] == "https://tuoitre.vn/mot-bai-viet-vi-du-100260715231418891.htm"
    assert it["title"] == "Một bài viết ví dụ"
    assert it["pub_date"] == "2026-07-15T23:23+07:00"


def test_parse_shard_vietnamplus_news_title():
    xml = FIXTURES.joinpath("vietnamplus_shard.xml").read_text(encoding="utf-8")
    items = parse_shard(xml, SOURCES["vietnamplus"]["article_suffix"])
    assert len(items) == 1
    assert items[0]["title"] == "Một bài viết ví dụ"
    assert items[0]["url"].endswith(".vnp")


def test_crawler_rejects_unknown_source():
    with pytest.raises(ValueError):
        SitemapNewsCrawler("unknown_source")


def test_crawler_dedup_against_existing_csv(tmp_path):
    csv_file = tmp_path / "tuoitre_articles.csv"
    csv_file.write_text(
        "id,source,title,category,pub_date,url,author,lead,pdf_url,pdf_filename,collected_at,body\n"
        "abc,tuoitre,old,,2020-01-01,https://tuoitre.vn/mot-bai-viet-vi-du-100260715231418891.htm,,,,,,\n",
        encoding="utf-8-sig",
    )
    crawler = SitemapNewsCrawler("tuoitre", csv_file=csv_file)
    assert "https://tuoitre.vn/mot-bai-viet-vi-du-100260715231418891.htm" in crawler.seen


def test_parse_date_valid():
    assert _parse_date("2020-01-01", None) == date(2020, 1, 1)


def test_parse_date_none_uses_default():
    default = date(2011, 1, 1)
    assert _parse_date(None, default) is default


def test_parse_date_invalid_exits(monkeypatch):
    with pytest.raises(SystemExit):
        _parse_date("not-a-date", None)


def test_crawl_backfill_index_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", lambda self, url: None)
    crawler = SitemapNewsCrawler("tuoitre", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill()
    assert counters["kept"] == 0
    assert not (tmp_path / "t.csv").exists()


def test_crawl_backfill_stops_at_max_articles(tmp_path, monkeypatch):
    index_xml = FIXTURES.joinpath("tuoitre_index.xml").read_text(encoding="utf-8")
    shard_xml = FIXTURES.joinpath("tuoitre_shard.xml").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url == nsc.SOURCES["tuoitre"]["index_url"]:
            return index_xml
        return shard_xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)
    crawler = SitemapNewsCrawler("tuoitre", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill(max_articles=1)
    assert counters["kept"] == 1


def test_main_cli_runs_backfill(tmp_path, monkeypatch):
    index_xml = FIXTURES.joinpath("tuoitre_index.xml").read_text(encoding="utf-8")
    shard_xml = FIXTURES.joinpath("tuoitre_shard.xml").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url == nsc.SOURCES["tuoitre"]["index_url"]:
            return index_xml
        return shard_xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)
    out_csv = tmp_path / "t.csv"
    monkeypatch.setattr(
        sys, "argv",
        ["news_sitemap_crawler.py", "--source", "tuoitre", "--csv", str(out_csv)],
    )
    nsc.main()
    assert out_csv.exists()


def test_main_cli_latest_narrows_window(tmp_path, monkeypatch):
    seen_from_dates = []
    orig_crawl_backfill = nsc.SitemapNewsCrawler.crawl_backfill

    def spy_crawl_backfill(self, from_date=None, end_date=None, **kw):
        seen_from_dates.append(from_date)
        return orig_crawl_backfill(self, from_date, end_date, **kw)

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", lambda self, url: None)
    monkeypatch.setattr(nsc.SitemapNewsCrawler, "crawl_backfill", spy_crawl_backfill)
    monkeypatch.setattr(
        sys, "argv",
        ["news_sitemap_crawler.py", "--source", "tuoitre", "--latest",
         "--csv", str(tmp_path / "t.csv")],
    )
    nsc.main()
    today = nsc.datetime.now(nsc.HN_TZ).date()
    assert seen_from_dates == [today - nsc.timedelta(days=nsc.LATEST_WINDOW_DAYS)]
