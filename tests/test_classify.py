"""Unit tests for objective/classify.py (AD-11 classification)."""
from __future__ import annotations

from objective.classify import classify_event_type
from objective.schema import EventType


def test_classify_bond():
    assert classify_event_type("ACB12602: Đăng ký, lưu ký trái phiếu") == EventType.BOND_ISSUANCE


def test_classify_dividend():
    assert classify_event_type("Thông báo cổ tức bằng tiền mặt") == EventType.DIVIDEND


def test_classify_financial_statement():
    assert classify_event_type("Báo cáo tài chính kiểm toán năm 2025") == \
        EventType.FINANCIAL_STATEMENT


def test_classify_agm_and_board_resolution():
    assert classify_event_type("Thông báo đại hội đồng cổ đông thường niên") == EventType.AGM
    assert classify_event_type("Nghị quyết HĐQT về cổ tức") == EventType.BOARD_RESOLUTION


def test_classify_insider_and_shareholder():
    assert classify_event_type("Công bố thông tin giao dịch cổ đông") == EventType.INSIDER_TRADING
    assert classify_event_type("Chốt danh sách cổ đông thực hiện quyền") == \
        EventType.SHAREHOLDER_CHANGE


def test_classify_unknown_is_other():
    assert classify_event_type("Thông báo lý lịch chứng khoán") == EventType.OTHER
    assert classify_event_type("") == EventType.OTHER
    assert classify_event_type(None) == EventType.OTHER
