"""Smoke gate (phase -1): project modules import under the uv 3.13 env and the
core news-crawler schema is present. No network.

Phase 1 will add a functional smoke test for body_extractor on a saved HTML fixture
under tests/fixtures/.
"""
import pytest

pytestmark = pytest.mark.smoke


def test_core_modules_import():
    import base_news_crawler
    import cafef_config
    from utils import dedup

    assert "url" in base_news_crawler.CSV_HEADERS
    assert cafef_config.CSV_HEADERS
    assert hasattr(dedup, "DedupManager")
