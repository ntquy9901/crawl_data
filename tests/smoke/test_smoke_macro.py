"""Smoke: build_macro_features chạy end-to-end trên fixtures (KHÔNG network)."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke

FIX_RAW = Path(__file__).resolve().parent.parent / "fixtures" / "macro" / "raw"


def test_build_macro_smoke(tmp_path, monkeypatch):
    import scripts.build_macro_features as bm

    # Trỏ raw + processed paths vào fixtures / tmp (VCB/SBV cố tình missing → skip).
    monkeypatch.setattr(bm, "RAW_VNINDEX", FIX_RAW / "vnindex_prices.csv")
    monkeypatch.setattr(bm, "RAW_DXY", FIX_RAW / "dxy.csv")
    monkeypatch.setattr(bm, "RAW_SBV_POLICY", FIX_RAW / "sbv_policy_rates.csv")
    monkeypatch.setattr(bm, "RAW_USD_VND_VCB", tmp_path / "_missing_vcb.csv")
    monkeypatch.setattr(bm, "RAW_USD_VND_SBV", tmp_path / "_missing_sbv.csv")
    monkeypatch.setattr(bm, "PROCESSED_PATH", tmp_path)

    bm.main([])

    out = tmp_path / "macro_features.csv"
    assert out.exists()
    with open(out, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)

    assert header == bm.COLS                         # đúng schema
    assert len(rows) == 7                            # 7 VN trading days trong fixture
    assert rows[0]["vni_close"] == "1172.3"          # anchor feature
    assert rows[0]["dxy"] == ""                      # shift=1: ngày đầu chưa biết
    assert rows[1]["dxy"] == "102.1"                 # từ ngày thứ 2 trở đi
    assert rows[0]["refinancing_rate"] == "4.5"      # policy rate ffill vào 2024
    assert (tmp_path / "macro_features_stats.txt").exists()
