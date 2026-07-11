"""Tests for the E1 code-review fixes (regression guards on the contract bugs
the adversarial review caught)."""
from __future__ import annotations

import csv

from objective import base_objective_crawler as boc
from objective.base_objective_crawler import BaseObjectiveCrawler, row_to_objective_record, to_utc
from objective.classify import classify_event_type
from objective.schema import (
    EventType,
    canonicalize_url,
    deserialize_attachment_urls,
    serialize_attachment_urls,
)

# ---- canonicalize_url: exact-match tracking + query-key case (review #3,#5,#8) ----

def test_canonicalize_retains_ref_prefixed_params():
    # exact "ref"/"ref_src" stripped, but "reference"/"ref_id"/"refresh" KEPT
    for kept in ("reference", "ref_id", "refresh", "referral"):
        out = canonicalize_url(f"https://x.vn/p?{kept}=v&id=1")
        assert f"{kept}=v" in out, f"{kept} was wrongly stripped"


def test_canonicalize_strips_exact_ref():
    assert "ref=" not in canonicalize_url("https://x.vn/p?ref=home&id=1")
    assert "ref_src=" not in canonicalize_url("https://x.vn/p?ref_src=x&id=1")


def test_canonicalize_lowercases_query_keys():
    assert canonicalize_url("https://x.vn/p?Page=1&Lang=en") == \
        canonicalize_url("https://x.vn/p?page=1&lang=en")


# ---- to_utc: fractional + midnight consistency (review #3,#6) ----

def test_to_utc_fractional_z():
    assert to_utc("2026-07-10T10:00:00.123Z") == "2026-07-10T10:00:00Z"
    assert to_utc("2026-07-10T10:00:00.500+07:00") == "2026-07-10T03:00:00Z"


def test_to_utc_date_only_equals_naive_midnight():
    # AD-3 consistency: the same instant must not land on different days
    a = to_utc("2026-07-10")
    assert a == to_utc("2026-07-10 00:00:00") == to_utc("2026-07-10T00:00:00")
    assert a == "2026-07-10T00:00:00Z"


# ---- attachment_urls JSON round-trip (review #4) ----

def test_serialize_deserialize_attachment_urls_with_pipe():
    urls = ["https://x.vn/dl?f=a|b", "https://y.vn/c.pdf"]
    s = serialize_attachment_urls(urls)
    assert deserialize_attachment_urls(s) == urls  # pipe in URL survives


def test_append_then_hydrate_roundtrip(tmp_path):
    class _C(BaseObjectiveCrawler):
        source = "rt"
        source_tier = "tier1"

        def fetch(self, url):
            return "<html>x</html>"

        def parse_article(self, html, item):
            return {"title": "t", "company_code": "ACB", "raw_text": "cổ tức",
                    "event_type": "dividend",
                    "attachment_urls": ["https://x.vn/dl?f=a|b"]}

    c = _C(csv_file=tmp_path / "r.csv", raw_root=tmp_path / "raw")
    row = c._fetch_and_parse({"url": "https://x.vn/ad/1"})
    c._append([row])
    data = list(csv.DictReader((tmp_path / "r.csv").open(encoding="utf-8-sig")))
    rec = row_to_objective_record(data[0])
    assert rec.attachment_urls == ["https://x.vn/dl?f=a|b"]  # round-trip intact
    assert rec.event_type == "dividend"


# ---- dedup: canonical resume (review #1 — the critical fix) ----

def test_dedup_key_canonicalizes():
    c = boc.BaseObjectiveCrawler.__new__(boc.BaseObjectiveCrawler)  # no __init__ side effects
    # raw with reordered params canonicalizes to one key
    assert c._dedup_key("https://x.vn/ad/1?b=2&a=1") == c._dedup_key("https://x.vn/ad/1?a=1&b=2")


def test_resume_treats_reordered_url_as_dup(tmp_path):
    class _C(BaseObjectiveCrawler):
        source = "dup"
        source_tier = "tier1"
        fetched = 0

        def fetch(self, url):
            type(self).fetched += 1
            return "<html>x</html>"

        def parse_article(self, html, item):
            return {"title": "t", "company_code": "ACB", "raw_text": "x", "event_type": "dividend"}

    f = tmp_path / "d.csv"
    f.write_text("document_id,source,source_tier,url,publish_time,crawl_time,company_code,"
                 "company_name,title,raw_text,language,category,event_type,attachment_urls,"
                 "checksum,raw_path\n"
                 "x,dup,tier1,https://x.vn/ad/1?a=1&b=2,,,,t,x,vi,,dividend,[],,\n",
                 encoding="utf-8-sig")
    c = _C(csv_file=f, raw_root=tmp_path / "raw")  # seen loaded with canonical url
    c._process_items([{"url": "https://x.vn/ad/1?b=2&a=1", "pub_date": "2026-07-10"}])
    assert c.counters["dup"] == 1   # recognized as seen despite reordered params
    assert type(c).fetched == 0     # NOT re-fetched (the bug's symptom)


# ---- classify: buyback vs MA + new terms (review #6) ----

def test_classify_buyback_is_not_ma():
    # "mua lại cổ phiếu" = share buyback, NOT merger (no SHARE_BUYBACK type → other)
    assert classify_event_type("Thông báo mua lại cổ phiếu") == EventType.OTHER
    assert classify_event_type("Mua lại doanh nghiệp XYZ") == EventType.MA


def test_classify_charter_capital_and_dividend_pay():
    assert classify_event_type("Nghị quyết tăng vốn điều lệ") == EventType.STOCK_ISSUANCE
    assert classify_event_type("Chi trả cổ tức đợt 2") == EventType.DIVIDEND
