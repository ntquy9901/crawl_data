"""Unit tests cho macro_crawler parse helpers (pure, no network)."""
from __future__ import annotations

from pathlib import Path

from macro_crawler import parse_fred_csv, parse_vcb_html, parse_vndirect_json

FIX = Path(__file__).resolve().parent / "fixtures" / "macro"


def test_parse_fred_csv():
    rows = parse_fred_csv((FIX / "fred_dxy.csv").read_text(encoding="utf-8"))
    assert rows[0] == {"date": "2006-01-03", "dxy": "112.5", "source": "fred"}
    # FRED "." sentinel → empty (NaN)
    assert next(r for r in rows if r["date"] == "2006-01-04")["dxy"] == ""


def test_parse_vndirect_json():
    rows = parse_vndirect_json((FIX / "vndirect_vnindex.json").read_text(encoding="utf-8"))
    assert len(rows) == 3
    first = rows[0]
    assert first["date"] == "2000-07-28"          # timezone/time bị cắt, giữ YYYY-MM-DD
    assert first["close"] == "100.5"
    assert first["volume"] == "1200000"
    assert first["source"] == "vndirect"


def test_parse_vcb_html():
    out = parse_vcb_html((FIX / "vcb_rates.html").read_text(encoding="utf-8"))
    assert out["usd_vnd_buy"] == "24180"          # bỏ phân cách hàng nghìn "24,180"
    assert out["usd_vnd_sell"] == "24340"


def test_parse_garbage_inputs():
    assert parse_fred_csv("not a csv at all\n") == []
    assert parse_vndirect_json("{bad json") == []
    assert parse_vcb_html("<html><body>no table</body></html>") == {}
