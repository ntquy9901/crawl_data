"""Smoke: dashboard generates from a synthetic CSV → valid HTML."""
from __future__ import annotations

import csv

import pytest

from objective.base_objective_crawler import OBJECTIVE_HEADERS
from objective.dashboard import generate_stats, render_html

pytestmark = pytest.mark.smoke


def test_dashboard_smoke(tmp_path):
    csv_path = tmp_path / "objective_v2026-07-12.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OBJECTIVE_HEADERS)
        w.writeheader()
        for i in range(5):
            r = {k: "" for k in OBJECTIVE_HEADERS}
            r.update(company_code="VNM", source="vietstock", event_type="dividend",
                     publish_time=f"2026-0{i+1}-10T00:00:00Z", title=f"event {i}")
            w.writerow(r)
    stats = generate_stats(csv_path)
    html = render_html(stats, generated_at="2026-07-12")
    out = tmp_path / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    assert out.exists()
    assert "<canvas" in html and "chart.js" in html
    assert "5" in html  # total records
