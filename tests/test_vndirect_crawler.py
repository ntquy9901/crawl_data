"""Unit tests for vndirect_crawler --lang support (en/vi listing pages, FR: bilingual notes)."""
from __future__ import annotations

import sys

import vndirect_crawler as vc
from vndirect_crawler import CATEGORIES, VI_SLUGS, VndirectCrawler

EN_CARD = """news-item flex-item">
    <div class="news-left">
        <div class="news-date">
            <p><span class="date-day">29</span><sup>/04</sup></p>
            <p class="date-year font16 font300 text-center">Year 2026</p>
        </div>
    </div>
    <div class="news-infor">
        <h3><a href="https://www.vndirect.com.vn/en/kdh-earnings-flash/" class="font24 font700">\
KDH – An Lap bargain purchase gain</a></h3>
        <div class="news-des font16">KDH reported 1Q26 revenue growth.</div>
    </div>
</div>"""

VI_CARD = """news-item flex-item">
    <div class="news-left">
        <div class="news-date">
            <p><span class="date-day">13</span><sup>/02</sup></p>
            <p class="date-year font16 font300 text-center">năm 2026</p>
        </div>
    </div>
    <div class="news-infor">
        <h3><a href="https://www.vndirect.com.vn/pnj-cap-nhat/" class="font24 font700">\
PNJ – Sẵn s\xe0ng cho tăng trưởng</a></h3>
        <div class="news-des font16">Nội dung tiếng Việt.</div>
    </div>
</div>"""

# regression: lead text contains "năm 2099" outside the date-year markup - must not be
# picked up as the pub_date year (only the date-year <p> should match)
VI_CARD_NAM_IN_LEAD = """news-item flex-item">
    <div class="news-left">
        <div class="news-date">
            <p><span class="date-day">13</span><sup>/02</sup></p>
            <p class="date-year font16 font300 text-center">năm 2026</p>
        </div>
    </div>
    <div class="news-infor">
        <h3><a href="https://www.vndirect.com.vn/pnj-cap-nhat/" class="font24 font700">\
PNJ – Sẵn s\xe0ng cho tăng trưởng</a></h3>
        <div class="news-des font16">Kết quả kinh doanh năm 2099 vượt kỳ vọng.</div>
    </div>
</div>"""


def _crawler(category="company-note", lang="en"):
    c = VndirectCrawler.__new__(VndirectCrawler)
    c.category = category
    c.lang = lang
    c.base_url = "https://www.vndirect.com.vn"
    return c


def test_vi_slugs_cover_all_categories():
    assert set(VI_SLUGS) == set(CATEGORIES)


def test_listing_url_en_default():
    c = _crawler(lang="en")
    assert c.listing_url(1) == "https://www.vndirect.com.vn/en/category/company-note/"


def test_listing_url_vi_uses_slug():
    c = _crawler(category="sector-note", lang="vi")
    assert c.listing_url(1) == "https://www.vndirect.com.vn/category/bao-cao-nganh/"


def test_listing_url_pagination():
    c = _crawler(lang="vi")
    assert c.listing_url(3) == "https://www.vndirect.com.vn/category/bao-cao-phan-tich-dn/page/3/"


def test_parse_listing_en_extracts_year_and_category():
    c = _crawler(lang="en")
    items = c.parse_listing(EN_CARD, 1)
    assert len(items) == 1
    it = items[0]
    assert it["pub_date"] == "29/04/2026"
    assert it["category"] == "company-note"
    assert "KDH" in it["title"]


def test_parse_listing_vi_extracts_nam_year_and_tags_category():
    c = _crawler(lang="vi")
    items = c.parse_listing(VI_CARD, 1)
    assert len(items) == 1
    it = items[0]
    assert it["pub_date"] == "13/02/2026"  # "năm 2026" parsed, not just "Year"
    assert it["category"] == "company-note-vi"
    assert "PNJ" in it["title"]


def test_parse_listing_ignores_nam_outside_date_year_markup():
    c = _crawler(lang="vi")
    items = c.parse_listing(VI_CARD_NAM_IN_LEAD, 1)
    assert len(items) == 1
    # must pick the date-year "năm 2026", not the "năm 2099" in the lead text
    assert items[0]["pub_date"] == "13/02/2026"


def test_init_defaults_to_lang_en(tmp_path):
    c = VndirectCrawler(csv_file=tmp_path / "v.csv")
    assert c.lang == "en"
    assert c.category == "company-note"


def test_init_accepts_lang_vi(tmp_path):
    c = VndirectCrawler(category="sector-note", lang="vi", csv_file=tmp_path / "v.csv")
    assert c.lang == "vi"
    assert c.listing_url(1) == "https://www.vndirect.com.vn/category/bao-cao-nganh/"


def test_cli_wires_lang_flag(tmp_path, monkeypatch):
    seen = {}

    def fake_crawl_latest(self, max_pages=1):
        seen["lang"] = self.lang
        seen["category"] = self.category
        return {}

    monkeypatch.setattr(VndirectCrawler, "crawl_latest", fake_crawl_latest)
    monkeypatch.setattr(
        sys, "argv",
        ["vndirect_crawler.py", "--latest", "--category", "sector-note", "--lang", "vi",
         "--csv", str(tmp_path / "v.csv")],
    )
    vc.VndirectCrawler.cli()
    assert seen == {"lang": "vi", "category": "sector-note"}
