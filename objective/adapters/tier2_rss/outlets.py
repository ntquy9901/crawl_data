"""Additional Tier-2 RSS outlets (FR-15). Each verified live (2026-07-12) to
return items; the framework (Tier2RssCrawler) does the parsing.

Run one: ``python -m objective.adapters.tier2_rss.outlets <name> --latest``

NOT YET ADDED (RSS not found at common paths — needs per-site discovery or a
sitemap fallback): vneconomy, vietnamplus, baodautu, baochinhphu, TTXVN
(vietnam.vn), Kinh tế Sài Gòn.
"""
from __future__ import annotations

import sys

from objective.adapters.tier2_rss.base import Tier2RssCrawler


class TuoitreRssCrawler(Tier2RssCrawler):
    source = "tuoitre"
    base_url = "https://tuoitre.vn"
    feed_url = "https://tuoitre.vn/rss/tai-chinh.rss"  # tài chính


class NldRssCrawler(Tier2RssCrawler):
    source = "nld"  # Người Lao Động
    base_url = "https://nld.com.vn"
    feed_url = "https://nld.com.vn/rss/kinh-te.rss"


class ThanhnienRssCrawler(Tier2RssCrawler):
    source = "thanhnien"
    base_url = "https://thanhnien.vn"
    # thoi-su (general) — a finance-section RSS path wasn't found; still a news
    # corpus source (VN30 relevance is filtered at NLP enrichment).
    feed_url = "https://thanhnien.vn/rss/thoi-su.rss"


OUTLETS = {
    "tuoitre": TuoitreRssCrawler,
    "nld": NldRssCrawler,
    "thanhnien": ThanhnienRssCrawler,
}


if __name__ == "__main__":
    # python -m objective.adapters.tier2_rss.outlets <tuoitre|nld|thanhnien> --latest
    name = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    cls = OUTLETS.get(name) if name else None
    if cls is None:
        print(f"usage: python -m objective.adapters.tier2_rss.outlets "
              f"{{{','.join(OUTLETS)}}} --latest")
        sys.exit(2)
    sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != name]  # strip name
    cls.cli()
