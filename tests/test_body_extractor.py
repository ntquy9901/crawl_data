"""Unit tests for utils.body_extractor (phase 1)."""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from utils.body_extractor import (
    extract_html_body,
    extract_pdf_body,
    normalize_body,
    resolve_pdf_local_path,
)

FIX = Path(__file__).resolve().parent / "fixtures"


# ---------- normalize_body ----------
def test_normalize_strips_boilerplate_and_collapses_whitespace():
    raw = "TIN MỚI\n\n\n   Ông Đỗ Quý Hải   đăng ký   \n\nXEM THÊM\n"
    out = normalize_body(raw)
    assert "TIN MỚI" not in out
    assert "XEM THÊM" not in out
    assert "Ông Đỗ Quý Hải đăng ký" in out  # whitespace collapsed


def test_normalize_truncates_head_tail():
    out = normalize_body("alpha " * 5000, max_chars=1000)
    assert "[…truncated…]" in out
    assert len(out) < 30000


@pytest.mark.parametrize("val", ["", None])
def test_normalize_empty(val):
    assert normalize_body(val) == ""  # type: ignore[arg-type]


# ---------- extract_html_body ----------
def test_extract_html_cafef_fixture():
    html = (FIX / "sample_cafef.html").read_text(encoding="utf-8")
    body = extract_html_body(html, "cafef")
    assert len(body) > 200
    assert "HPX" in body or "Đỗ Quý Hải" in body


def test_extract_html_hsc_fixture():
    html = (FIX / "sample_hsc.html").read_text(encoding="utf-8")
    body = extract_html_body(html, "hsc")
    assert len(body) > 100
    assert any(k in body for k in ("Vietnam", "tariff", "Bamboo", "Strategy"))


def test_extract_html_empty():
    assert extract_html_body("", "cafef") == ""


def test_extract_html_fallback_article_tag():
    # unknown source → falls through to //article in the fallback chain
    html = "<html><body><article>" + ("alpha " * 150) + "</article></body></html>"
    assert len(extract_html_body(html, "unknown_source")) > 100


# ---------- extract_pdf_body ----------
def test_extract_pdf_body_generated(tmp_path):
    p = tmp_path / "t.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Recommendation BUY MWG target price 121438 VND")
    doc.save(p)
    doc.close()
    body = extract_pdf_body(p)
    assert "MWG" in body
    assert "121438" in body


def test_extract_pdf_body_missing(tmp_path):
    assert extract_pdf_body(tmp_path / "nope.pdf") == ""


def test_extract_pdf_body_malformed(tmp_path):
    """A corrupt PDF must not crash — returns ''."""
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"%PDF-1.4\nbroken garbage not a real pdf object tree\n")
    assert extract_pdf_body(p) == ""


# ---------- resolve_pdf_local_path ----------
def test_resolve_vietstock(tmp_path):
    p = resolve_pdf_local_path("vietstock", {"pdf_filename": "x.pdf"}, data_path=tmp_path)
    assert p == tmp_path / "pdf" / "x.pdf"


def test_resolve_vietstock_no_filename(tmp_path):
    assert resolve_pdf_local_path("vietstock", {}, data_path=tmp_path) is None


def test_resolve_ssi(tmp_path):
    p = resolve_pdf_local_path("ssi", {"id": "abc123"}, data_path=tmp_path)
    assert p == tmp_path / "pdf_ssi" / "abc123.pdf"


def test_resolve_unknown_source(tmp_path):
    assert resolve_pdf_local_path("cafef", {"id": "1"}, data_path=tmp_path) is None
