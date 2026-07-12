"""Unit tests for objective/dashboard.py."""
from __future__ import annotations

import csv

from objective.base_objective_crawler import OBJECTIVE_HEADERS
from objective.dashboard import find_latest_dataset, generate_stats, render_html


def _row(code, src, evt, pub):
    r = {k: "" for k in OBJECTIVE_HEADERS}
    r.update(company_code=code, source=src, event_type=evt, publish_time=pub, title="t")
    return r


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OBJECTIVE_HEADERS)
        w.writeheader()
        w.writerows(rows)


def test_generate_stats(tmp_path):
    csv_path = tmp_path / "objective_v2026-07-12.csv"
    _write_csv(csv_path, [
        _row("VNM", "vietstock", "dividend", "2026-07-10T00:00:00Z"),
        _row("VNM", "vietstock", "agm", "2026-06-01T00:00:00Z"),
        _row("ACB", "vsdc", "bond_issuance", "2025-01-15T00:00:00Z"),
    ])
    s = generate_stats(csv_path)
    assert s["total_records"] == 3
    assert s["tickers_covered"] == 2
    assert s["by_source"] == {"vietstock": 2, "vsdc": 1}
    assert s["by_event_type"]["dividend"] == 1
    assert s["top_tickers"][0] == ("VNM", 2)
    assert s["date_range"]["oldest"] == "2025-01-15"
    assert s["date_range"]["newest"] == "2026-07-10"
    assert len(s["monthly_counts"]) >= 2
    assert s["per_ticker"][0]["ticker"] == "VNM"


def test_generate_stats_news_corpus(tmp_path):
    csv_path = tmp_path / "objective_v2026-07-12.csv"
    _write_csv(csv_path, [_row("VNM", "vietstock", "dividend", "2026-07-10T00:00:00Z")])
    # companion news file
    news = tmp_path / "news_unenriched_vnexpress_records.csv"
    _write_csv(news, [_row("", "vnexpress", "other", "2026-07-12T00:00:00Z")] * 5)
    s = generate_stats(csv_path, news_dir=tmp_path)
    assert s["news_corpus"] == 5


def test_generate_stats_empty(tmp_path):
    csv_path = tmp_path / "objective_v2026-07-12.csv"
    _write_csv(csv_path, [])
    s = generate_stats(csv_path)
    assert s["total_records"] == 0
    assert s["date_range"]["oldest"] == ""


def test_render_html_contains_charts_and_data():
    s = {
        "total_records": 42, "tickers_covered": 10, "vn30_total": 30,
        "date_range": {"oldest": "2020-01-01", "newest": "2026-07-12"},
        "by_source": {"vietstock": 40, "vsdc": 2},
        "by_event_type": {"dividend": 30, "agm": 12},
        "top_tickers": [("VNM", 10), ("ACB", 5)],
        "monthly_counts": [["2026-01", 5], ["2026-07", 10]],
        "news_corpus": 50,
        "per_ticker": [{"ticker": "VNM", "count": 10, "latest": "2026-07-10", "types": "dividend"}],
    }
    html = render_html(s, generated_at="2026-07-12")
    assert "chart.js@4" in html
    assert "canvas" in html
    assert "42" in html  # total records card
    assert "VNM" in html  # table row
    assert '"dividend"' in html  # event type in embedded JSON


def test_find_latest_dataset(tmp_path):
    for d in ["2026-07-10", "2026-07-12", "2026-07-11"]:
        _write_csv(tmp_path / f"objective_v{d}.csv", [])
    latest = find_latest_dataset(tmp_path)
    assert latest is not None
    assert "2026-07-12" in latest.name
