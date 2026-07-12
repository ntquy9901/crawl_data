"""Unit tests for objective/vn30.py — VN30 universe loader (AD-5)."""
from __future__ import annotations

import pytest

from objective.vn30 import _TICKER_RE, is_vn30, load_vn30


def test_load_vn30_returns_dict():
    out = load_vn30()
    assert isinstance(out, dict)
    assert len(out) == 30  # VN30 has exactly 30 constituents


def test_load_vn30_known_members():
    out = load_vn30()
    assert "VCB" in out
    assert "VNM" in out
    assert out["VNM"] == "Công ty CP Sữa Việt Nam"


def test_load_vn30_all_tickers_valid_format():
    out = load_vn30()
    for ticker in out:
        assert _TICKER_RE.match(ticker), f"bad ticker {ticker!r}"


def test_load_vn30_caches(tmp_path):
    load_vn30.cache_clear()
    a = load_vn30()
    b = load_vn30()
    assert a is b  # same object (lru_cache)


def test_is_vn30_case_insensitive():
    assert is_vn30("VCB")
    assert is_vn30("vcb")
    assert is_vn30("Vnm")
    assert not is_vn30("XYZZ")
    assert not is_vn30("")


def test_load_vn30_from_custom_path(tmp_path):
    f = tmp_path / "u.toml"
    f.write_text('[vn30]\nAAA = "Công ty AAA"\nBBB = "Công ty BBB"\n', encoding="utf-8")
    load_vn30.cache_clear()
    out = load_vn30(f)
    assert out == {"AAA": "Công ty AAA", "BBB": "Công ty BBB"}
    load_vn30.cache_clear()


def test_load_vn30_rejects_invalid_ticker(tmp_path):
    f = tmp_path / "bad.toml"
    f.write_text('[vn30]\nVCB = "ok"\nTOOLONG = "bad"\n', encoding="utf-8")
    load_vn30.cache_clear()
    with pytest.raises(ValueError, match="invalid VN30 ticker"):
        load_vn30(f)
    load_vn30.cache_clear()


def test_load_vn30_missing_table_raises(tmp_path):
    f = tmp_path / "empty.toml"
    f.write_text('[other]\nx = 1\n', encoding="utf-8")
    load_vn30.cache_clear()
    with pytest.raises(ValueError, match=r"\[vn30\]"):
        load_vn30(f)
    load_vn30.cache_clear()


def test_load_vn30_missing_file_raises():
    load_vn30.cache_clear()
    with pytest.raises(FileNotFoundError):
        load_vn30("/nonexistent/vn30.toml")
    load_vn30.cache_clear()
