"""Unit tests for utils.pdf_helpers."""
from __future__ import annotations

from utils.pdf_helpers import generate_pdf_filename


def test_basic_vietnamese():
    assert generate_pdf_filename("MWG Khuyến nghị MUA", "01/02/2026") == \
        "01-02-2026_MWG_Khuyến_nghị_MUA.pdf"


def test_title_truncated_to_50():
    name = generate_pdf_filename("A" * 80, "2026-01-01")
    assert name == "2026-01-01_" + "A" * 50 + ".pdf"


def test_special_chars_stripped():
    # only alnum/space/-/_ kept; spaces→_
    assert generate_pdf_filename("Report: <BID> #1!", "2026-01-01") == \
        "2026-01-01_Report_BID_1.pdf"


def test_date_slash_normalized():
    assert generate_pdf_filename("Title", "31/12/2025") == "31-12-2025_Title.pdf"


def test_empty_inputs():
    assert generate_pdf_filename("", "2026-01-01") == "2026-01-01_.pdf"
    assert generate_pdf_filename("Title", "") == "_Title.pdf"


def test_hyphen_and_underscore_kept():
    assert generate_pdf_filename("Q1-2026 update_note", "2026-01-01") == \
        "2026-01-01_Q1-2026_update_note.pdf"
