"""Smoke (gate): VnExpress RSS parses end-to-end on a saved feed fixture. No network."""
from __future__ import annotations

from pathlib import Path

import pytest

from objective.adapters.tier2_rss.vnexpress import VnExpressRssCrawler

pytestmark = pytest.mark.smoke
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "vnexpress" / "sample_feed.xml"


def test_vnexpress_rss_smoke():
    items = VnExpressRssCrawler().parse_listing(FIXTURE.read_text(encoding="utf-8"), 1)
    assert items, "fixture yielded no RSS items"
    assert items[0]["url"].startswith("https://vnexpress.net/")
    assert items[0]["title"]
    assert items[0]["pub_date"].startswith("20")  # ISO-converted from RFC-822
