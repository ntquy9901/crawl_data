"""Schedule wiring test (FR-14): run_daily_all.ps1 invokes the objective
crawlers + build, and the adapters expose the inherited CLI."""
from __future__ import annotations

from pathlib import Path

from objective.adapters.tier2_rss.vnexpress import VnExpressRssCrawler
from objective.adapters.vsdc_crawler import VsdcCrawler

SCRIPT = Path(__file__).resolve().parent.parent / "run_daily_all.ps1"


def test_schedule_invokes_objective_crawlers_and_build():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "objective.adapters.vsdc_crawler --latest" in text       # VSDC (FR-4)
    assert "objective.adapters.tier2_rss.vnexpress --latest" in text  # VnExpress (FR-15)
    assert "objective.build_objective" in text                       # build (FR-12)


def test_objective_adapters_expose_cli():
    # inherited BaseNewsCrawler.cli() — required for `python -m ... --latest`
    assert callable(VsdcCrawler.cli)
    assert callable(VnExpressRssCrawler.cli)
