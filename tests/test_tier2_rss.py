"""Unit tests for objective Tier-2 RSS framework (FR-15, AD-14)."""
from __future__ import annotations

from pathlib import Path

from objective.adapters.tier2_rss.base import Tier2RssCrawler, _pubdate_to_iso
from objective.adapters.tier2_rss.vnexpress import VnExpressRssCrawler

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vnexpress" / "sample_feed.xml"
SAMPLE_RSS = """<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>CEO PNJ muốn mua 1 triệu cổ phiếu</title>
    <link>https://vnexpress.net/x-5096383.html</link>
    <pubDate>Sun, 12 Jul 2026 07:14:25 +0700</pubDate>
    <description>PNJ công bố giao dịch cổ đông nội bộ.</description>
  </item>
  <item><title>no link</title></item>
</channel></rss>"""


def test_pubdate_rfc822_to_iso():
    iso = _pubdate_to_iso("Sun, 12 Jul 2026 07:14:25 +0700")
    assert iso.startswith("2026-07-12T07:14:25") and "+07:00" in iso


def test_pubdate_empty():
    assert _pubdate_to_iso("") == ""


def test_parse_listing_extracts_items():
    class _C(Tier2RssCrawler):
        source = "t"
    items = _C.__new__(_C)  # bypass __init__
    out = items.parse_listing(SAMPLE_RSS, 1)
    assert len(out) == 1  # the no-link item is skipped
    it = out[0]
    assert it["url"] == "https://vnexpress.net/x-5096383.html"
    assert it["title"] == "CEO PNJ muốn mua 1 triệu cổ phiếu"
    assert it["pub_date"].startswith("2026-07-12T07:14:25")


def test_parse_listing_malformed_xml():
    class _C(Tier2RssCrawler):
        source = "t"
    c = _C.__new__(_C)
    assert c.parse_listing("not xml", 1) == []


def test_fetch_and_parse_inline_null_company_code(tmp_path):
    c = VnExpressRssCrawler(csv_file=tmp_path / "n.csv", raw_root=tmp_path / "raw")
    row = c._fetch_and_parse({
        "url": "https://vnexpress.net/x-1.html",
        "title": "Tin tức VNM",
        "pub_date": "2026-07-12T07:14:25+07:00",
        "description": "Nội dung tin about VNM.",
    })
    assert row["company_code"] == ""              # unenriched (AD-14)
    assert row["source_tier"] == "tier2"
    assert row["event_type"] == "other"           # news event_type needs NLP
    assert row["publish_time"].endswith("Z")      # to_utc'd (AD-3)
    assert len(row["checksum"]) == 64


def test_companion_file_path(tmp_path, monkeypatch):
    from objective.adapters.tier2_rss import base as b
    monkeypatch.setattr(b, "DATA_PATH", tmp_path)
    c = VnExpressRssCrawler()
    assert c.csv_file == tmp_path / "objective" / "news_unenriched_vnexpress_records.csv"
