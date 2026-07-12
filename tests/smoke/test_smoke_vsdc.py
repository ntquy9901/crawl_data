"""Smoke (gate): VSDC parse_listing runs end-to-end on a saved fixture and
yields VN30 corporate-action notices. No network."""
from __future__ import annotations

from pathlib import Path

import pytest

from objective.adapters.vsdc_crawler import VsdcCrawler

pytestmark = pytest.mark.smoke
FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "vsdc" / "sample_vsdc_ad.html"


def test_vsdc_parse_listing_smoke():
    items = VsdcCrawler().parse_listing(FIXTURE.read_text(encoding="utf-8"), page=1)
    assert items, "fixture yielded no notices"
    vn30 = [it for it in items if VsdcCrawler()._keep_payload({"company_code": it["company_code"]})]
    assert vn30, "no VN30 notices extracted from fixture"
    tickers = {it["company_code"] for it in vn30}
    assert tickers & {"ACB", "TPB", "VHM", "MBB"}  # VN30 bond-notice issuers in fixture
