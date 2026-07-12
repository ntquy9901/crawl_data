"""Unit tests for objective/adapters/vsdc_crawler.py (FR-4, AD-7, VN30 filter)."""
from __future__ import annotations

from pathlib import Path

from objective.adapters.vsdc_crawler import VsdcCrawler

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vsdc" / "sample_vsdc_ad.html"


def _listing():
    return VsdcCrawler().parse_listing(FIXTURE.read_text(encoding="utf-8"), page=1)


def test_parse_listing_extracts_notice_items():
    items = _listing()
    assert len(items) >= 5
    sample = items[0]
    assert set(["url", "title", "company_code", "pub_date", "category"]).issubset(sample)
    assert sample["url"].startswith("https://vsd.vn/vi/ad/")
    assert sample["company_code"].isupper() and sample["company_code"].isalpha()


def test_parse_listing_finds_vn30_tickers():
    codes = {it["company_code"] for it in _listing()}
    # ACB / TPB / VHM / MBB are VN30 and present in the captured bond notices
    assert "ACB" in codes
    assert codes & {"ACB", "TPB", "VHM", "MBB"}


def test_keep_payload_filters_non_vn30():
    c = VsdcCrawler()
    assert c._keep_payload({"company_code": "ACB"}) is True   # VN30
    assert c._keep_payload({"company_code": "GPH"}) is False  # not VN30
    assert c._keep_payload({"company_code": ""}) is False      # empty dropped


def test_parse_article_builds_payload_with_canonical_name():
    c = VsdcCrawler()
    item = {"title": "ACB12602: Đăng ký, lưu ký trái phiếu", "company_code": "ACB",
            "pub_date": "10/07/2026", "url": "https://vsd.vn/vi/ad/197664"}
    p = c.parse_article("<html></html>", item)
    assert p["company_code"] == "ACB"
    assert p["company_name"] == "Ngân hàng TMCP Á Châu"  # AD-12 canonical from vn30
    assert p["event_type"] == "bond_issuance"            # classified (AD-11)
    assert p["publish_time"] == "10/07/2026"             # passed through (to_utc at build)


def test_parse_listing_malformed_html_returns_empty():
    assert VsdcCrawler().parse_listing("not html at all", 1) == []
