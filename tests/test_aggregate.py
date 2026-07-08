"""Unit tests for scripts.aggregate_news pure helpers."""
from __future__ import annotations

from scripts.aggregate_news import _norm_date


def test_norm_date_iso():
    assert _norm_date("2026-07-08") == "2026-07-08"


def test_norm_date_dmy():
    assert _norm_date("08/07/2026") == "2026-07-08"
    assert _norm_date("08-07-2026") == "2026-07-08"


def test_norm_date_iso_datetime():
    assert _norm_date("2026-07-08T05:00:00+0700") == "2026-07-08"
    assert _norm_date("2026-07-08T05:00:00") == "2026-07-08"


def test_norm_date_empty():
    assert _norm_date("") == ""
    assert _norm_date(None) == ""  # type: ignore[arg-type]


def test_norm_date_garbage():
    assert _norm_date("not a date") == ""
