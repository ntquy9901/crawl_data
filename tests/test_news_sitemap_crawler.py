"""Unit tests for news_sitemap_crawler (tuoitre/thanhnien/vietnamplus sitemap backfill)."""
from __future__ import annotations

import re
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


# ────────── url_stub ──────────

def test_url_stub_typical():
    assert nsc.url_stub("https://example.com/bai-viet-1-12345.html") == "bai-viet-1-12345"


def test_url_stub_without_suffix():
    assert nsc.url_stub("https://example.com/bai-viet") == "bai-viet"


def test_url_stub_empty():
    assert nsc.url_stub("") == ""


# ────────── _assess_title_quality ──────────

def test_assess_title_quality_good():
    assert nsc.SitemapNewsCrawler._assess_title_quality("Báo Cáo Thường Niên 2026") == (True, "ok")


def test_assess_title_quality_too_short():
    assert nsc.SitemapNewsCrawler._assess_title_quality("AB") == (False, "too_short")
    assert nsc.SitemapNewsCrawler._assess_title_quality("") == (False, "too_short")


def test_assess_title_quality_single_short_word():
    assert nsc.SitemapNewsCrawler._assess_title_quality("Abc") == (False, "single_short_word:Abc")


def test_assess_title_quality_all_numeric():
    assert nsc.SitemapNewsCrawler._assess_title_quality("12345") == (False, "all_numeric")


def test_assess_title_quality_html_remnant():
    assert nsc.SitemapNewsCrawler._assess_title_quality("Tin Mới H1") == (False, "html_remnant")
    assert nsc.SitemapNewsCrawler._assess_title_quality("Bài Viết Div2") == (False, "html_remnant")


# ────────── SLUG_BASED_SOURCES ──────────

def test_slug_based_sources_contains_new_sources():
    assert "thoibaotaichinhvietnam" in nsc.SLUG_BASED_SOURCES
    assert "vietnamfinance" in nsc.SLUG_BASED_SOURCES


# ────────── new source configs ──────────

def test_cafebiz_config():
    cfg = nsc.SOURCES["cafebiz"]
    assert cfg["index_url"] == "https://cafebiz.vn/sitemap.xml"
    assert cfg["article_suffix"] == ".chn"
    assert cfg["floor"] == date(2019, 10, 1)


def test_thoibaotaichinhvietnam_config():
    cfg = nsc.SOURCES["thoibaotaichinhvietnam"]
    assert cfg["sitemap_url"] == "https://thoibaotaichinhvietnam.vn/sitemaparticles-site-1.xml"
    assert cfg["article_suffix"] == ".html"
    assert cfg["floor"] == date(2015, 1, 1)


def test_vietnamfinance_config():
    cfg = nsc.SOURCES["vietnamfinance"]
    assert cfg["sitemap_url"] == "https://vietnamfinance.vn/sitemap.xml"
    assert cfg["article_suffix"] == ".html"
    assert cfg["floor"] == date(2020, 1, 1)


# ────────── single-sitemap crawl_backfill path ──────────

def test_crawl_backfill_single_sitemap(tmp_path, monkeypatch):
    xml = FIXTURES.joinpath("vietnamfinance_sitemap.xml").read_text(encoding="utf-8")
    calls: list[str] = []

    def fake_fetch(self, url):
        calls.append(url)
        return xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)
    crawler = nsc.SitemapNewsCrawler("vietnamfinance", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill()
    assert counters["kept"] == 3
    assert counters["dup"] == 0
    assert len(calls) == 1
    assert calls[0] == nsc.SOURCES["vietnamfinance"]["sitemap_url"]
    rows = (tmp_path / "t.csv").read_text(encoding="utf-8-sig")
    assert "bai-viet-1" in rows
    assert "bai-viet-2" in rows
    assert "bai-viet-3" in rows


def test_crawl_backfill_single_sitemap_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", lambda self, url: None)
    crawler = nsc.SitemapNewsCrawler("vietnamfinance", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill()
    assert counters["kept"] == 0
    assert not (tmp_path / "t.csv").exists()


def test_crawl_backfill_single_sitemap_date_filter(tmp_path, monkeypatch):
    xml = FIXTURES.joinpath("vietnamfinance_sitemap.xml").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        return xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)
    crawler = nsc.SitemapNewsCrawler("vietnamfinance", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill(from_date=date(2026, 7, 19))
    assert counters["kept"] == 2
    assert counters["out_of_range"] == 1


def test_crawl_backfill_single_sitemap_test_mode_collects_title_samples(tmp_path, monkeypatch):
    xml = FIXTURES.joinpath("vietnamfinance_sitemap.xml").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        return xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)
    monkeypatch.setattr(nsc.SitemapNewsCrawler, "_print_title_quality_report",
                        lambda self, samples: None)
    crawler = nsc.SitemapNewsCrawler("vietnamfinance", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill(test=True)
    assert counters["kept"] == 3


def test_crawl_backfill_shard_path_via_fallback(tmp_path, monkeypatch):
    index_xml = FIXTURES.joinpath("tuoitre_index.xml").read_text(encoding="utf-8")
    shard_xml = FIXTURES.joinpath("tuoitre_shard.xml").read_text(encoding="utf-8")

    def fake_fetch(self, url):
        if url == nsc.SOURCES["tuoitre"]["index_url"]:
            return index_xml
        return shard_xml

    monkeypatch.setattr(nsc.SitemapNewsCrawler, "fetch", fake_fetch)
    crawler = nsc.SitemapNewsCrawler("tuoitre", csv_file=tmp_path / "t.csv")
    counters = crawler.crawl_backfill(max_articles=1, test=True)
    assert counters["kept"] == 1


# ────────── mutual-exclusion assertion ──────────

def test_init_rejects_both_sitemap_url_and_shard_re():
    nsc.SOURCES["_test_both"] = {
        "sitemap_url": "https://example.com/sitemap.xml",
        "shard_re": re.compile(r"foo"),
        "article_suffix": ".html",
        "floor": date(2020, 1, 1),
    }
    with pytest.raises(AssertionError, match="must have either"):
        SitemapNewsCrawler("_test_both")
    del nsc.SOURCES["_test_both"]
