"""VnExpress (vnexpress.net) Tier-2 RSS adapter (FR-15)."""
from __future__ import annotations

from objective.adapters.tier2_rss.base import Tier2RssCrawler


class VnExpressRssCrawler(Tier2RssCrawler):
    source = "vnexpress"
    base_url = "https://vnexpress.net"
    # kinh-doanh (business) feed; chung-khoan (securities) is the sibling feed.
    feed_url = "https://vnexpress.net/rss/kinh-doanh.rss"


if __name__ == "__main__":  # CLI: python -m objective.adapters.tier2_rss.vnexpress --latest
    VnExpressRssCrawler.cli()
