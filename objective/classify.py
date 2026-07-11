"""event_type classification (AD-11). Shared heuristic used by Tier-1 adapters
(VSDC/Vietstock/Cafef) to map a Vietnamese disclosure title → EventType.

Keyword-based, first-match-wins. Conservative: unknown → ``other``. Extend the
``_RULES`` list as new title patterns appear during backfill.
"""
from __future__ import annotations

from objective.schema import EventType

# (substring-lower, event_type) — first match wins, so order specific→general.
_RULES: list[tuple[str, str]] = [
    ("báo cáo tài chính", EventType.FINANCIAL_STATEMENT),
    ("tái lập báo cáo tài chính", EventType.FINANCIAL_STATEMENT),
    ("đại hội đồng cổ đông", EventType.AGM),
    ("nghị quyết hội đồng quản trị", EventType.BOARD_RESOLUTION),
    ("nghị quyết hđqt", EventType.BOARD_RESOLUTION),
    ("phát hành thêm cổ phiếu", EventType.STOCK_ISSUANCE),
    ("phát hành cổ phiếu", EventType.STOCK_ISSUANCE),
    ("chia cổ phiếu", EventType.STOCK_SPLIT),
    ("stock split", EventType.STOCK_SPLIT),
    ("phát hành quyền mua", EventType.RIGHTS_ISSUE),
    ("quyền mua cổ phiếu", EventType.RIGHTS_ISSUE),
    ("chốt danh sách cổ đông", EventType.SHAREHOLDER_CHANGE),
    ("lập danh sách cổ đông", EventType.SHAREHOLDER_CHANGE),
    ("thay đổi cổ đông lớn", EventType.SHAREHOLDER_CHANGE),
    ("giao dịch cổ đông", EventType.INSIDER_TRADING),
    ("công bố thông tin giao dịch", EventType.INSIDER_TRADING),
    ("sáp nhập", EventType.MA),
    ("hợp nhất", EventType.MA),
    ("mua lại", EventType.MA),
    ("bổ nhiệm", EventType.EXEC_CHANGE),
    ("bãi nhiệm", EventType.EXEC_CHANGE),
    ("thay đổi nhân sự", EventType.EXEC_CHANGE),
    ("esop", EventType.ESOP),
    ("sở hữu nước ngoài", EventType.FOREIGN_OWNERSHIP),
    ("room nước ngoài", EventType.FOREIGN_OWNERSHIP),
    ("trái phiếu", EventType.BOND_ISSUANCE),
    ("coupon", EventType.BOND_ISSUANCE),
    ("cổ tức", EventType.DIVIDEND),
    ("chia tiền mặt", EventType.DIVIDEND),
]


def classify_event_type(text: str) -> str:
    """Map a Vietnamese disclosure title → an EventType value (AD-11)."""
    if not text:
        return EventType.OTHER
    t = str(text).lower()
    for needle, event in _RULES:
        if needle in t:
            return event
    return EventType.OTHER
