"""Unit tests for objective/adapters/vietstock_disclosure.py (FR-16)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from objective.adapters.vietstock_disclosure import (
    VietstockDisclosureCrawler,
    event_to_payload,
    parse_events,
    vsdate_to_utc,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vietstock" / "vnm_events.json"


# ---- vsdate_to_utc (AD-3) ----

def test_vsdate_to_utc_canonical():
    ms = 1784221200000
    expected = datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert vsdate_to_utc(f"/Date({ms})/") == expected
    assert vsdate_to_utc(f"/Date({ms})/").endswith("Z")


def test_vsdate_to_utc_garbage():
    assert vsdate_to_utc("") == ""
    assert vsdate_to_utc(None) == ""
    assert vsdate_to_utc("not a date") == ""


# ---- parse_events (BOM + nested [[...]]) ----

def test_parse_events_fixture():
    rows = parse_events(FIXTURE.read_text(encoding="utf-8-sig"))
    assert len(rows) >= 5
    assert rows[0]["Code"] == "VNM"
    assert "Title" in rows[0] and "Content" in rows[0]


def test_parse_events_handles_bom():
    payload = "﻿" + json.dumps([[{"Code": "VNM", "EventID": 1}]])
    assert parse_events(payload) == [{"Code": "VNM", "EventID": 1}]


def test_parse_events_flat_array():
    assert parse_events(json.dumps([{"Code": "X"}])) == [{"Code": "X"}]


# ---- event_to_payload ----

def test_event_to_payload_maps_fields():
    rows = parse_events(FIXTURE.read_text(encoding="utf-8-sig"))
    p = event_to_payload("VNM", rows[0])
    assert p["company_code"] == "VNM"
    assert p["company_name"] == "CTCP Sữa Việt Nam"
    assert p["publish_time"].endswith("Z")  # /Date()/ → UTC
    assert p["event_type"]  # classified (dividend / etc.)
    assert "<" not in p["raw_text"]  # Content HTML stripped


def test_event_to_payload_dividend_classification():
    rows = parse_events(FIXTURE.read_text(encoding="utf-8-sig"))
    # the fixture's first event is "Trả cổ tức bằng tiền mặt" → dividend
    p = event_to_payload("VNM", rows[0])
    assert p["event_type"] == "dividend"
    assert p["category"] == "Trả cổ tức bằng tiền mặt"


def test_crawler_is_vn30_iterated_by_default(tmp_path):
    # default tickers=None → crawl_latest uses load_vn30() (30 tickers)
    c = VietstockDisclosureCrawler(csv_file=tmp_path / "v.csv", raw_root=tmp_path / "raw")
    assert c.source_tier == "tier3"
    assert c.source == "vietstock"
