"""Outlet subclasses + the outlets runner dispatch (FR-15, story 3.2)."""
from __future__ import annotations

from objective.adapters.tier2_rss.outlets import (
    OUTLETS,
    TuoitreRssCrawler,
)

SAMPLE = """<?xml version="1.0"?><rss><channel>
<item><title>VNM cổ tức</title><link>https://tuoitre.vn/a-1.htm</link>
<pubDate>Sun, 12 Jul 2026 07:00:00 +0700</pubDate><description>d</description></item>
</channel></rss>"""


def test_outlets_registry_has_verified():
    assert set(OUTLETS) == {"tuoitre", "nld", "thanhnien", "vietnamplus"}


def test_each_outlet_has_source_and_feed_url():
    for cls in OUTLETS.values():
        c = cls.__new__(cls)
        assert c.source and c.feed_url.startswith("http") and c.source_tier == "tier2"


def test_outlet_parses_rss_via_framework():
    c = TuoitreRssCrawler.__new__(TuoitreRssCrawler)
    items = c.parse_listing(SAMPLE, 1)
    assert len(items) == 1
    assert items[0]["url"] == "https://tuoitre.vn/a-1.htm"


def test_outlet_dispatch_missing_name_exits():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "objective.adapters.tier2_rss.outlets"],
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 2 and "usage" in r.stdout.lower()
