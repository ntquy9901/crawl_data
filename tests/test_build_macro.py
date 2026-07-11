"""Unit tests cho build_macro_features.align_to_calendar (pure)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.build_macro_features import _engineer, align_to_calendar

# 5 VN business days: Tue, Wed, Thu, Fri, Mon (bỏ cuối tuần).
ANCHOR = pd.date_range("2024-01-02", periods=5, freq="B")


def test_align_no_shift_ffill():
    src = pd.DataFrame({"x": [1.0, None, 3.0]}, index=ANCHOR[:3])
    out = align_to_calendar(src, ANCHOR, shift_days=0, ffill=True)
    assert out.loc[ANCHOR[0], "x"] == 1.0
    assert out.loc[ANCHOR[3], "x"] == 3.0          # ffill từ day 3


def test_align_shift1_look_ahead_safe():
    # value dated D KHÔNG được xuất hiện tại anchor D (rò rỉ tương lai), chỉ từ D+1.
    src = pd.DataFrame({"x": [10.0]}, index=[ANCHOR[0]])
    out = align_to_calendar(src, ANCHOR, shift_days=1, ffill=True)
    assert pd.isna(out.loc[ANCHOR[0], "x"])        # cấm cùng ngày
    assert out.loc[ANCHOR[1], "x"] == 10.0         # có từ ngày tiếp theo


def test_align_nan_before_start_not_dropped():
    src = pd.DataFrame({"x": [5.0]}, index=[ANCHOR[2]])
    out = align_to_calendar(src, ANCHOR, shift_days=0, ffill=True)
    assert pd.isna(out.loc[ANCHOR[0], "x"])
    assert pd.isna(out.loc[ANCHOR[1], "x"])
    assert out.loc[ANCHOR[2], "x"] == 5.0


def test_align_cross_calendar_us_to_vn():
    # DXY US-time: value Thứ Sáu chỉ known từ anchor tiếp theo (Thứ Hai), không phải Thứ Sáu.
    src = pd.DataFrame({"x": [7.0]}, index=[pd.Timestamp("2024-01-05")])  # Friday
    out = align_to_calendar(src, ANCHOR, shift_days=1, ffill=True)
    assert pd.isna(out.loc[pd.Timestamp("2024-01-05"), "x"])   # Fri: chưa biết
    assert out.loc[pd.Timestamp("2024-01-08"), "x"] == 7.0     # Mon: đã biết


def test_engineer_replaces_inf_with_nan():
    # close=0 → log(0/prev) = -inf; phải được thay bằng NaN để không nhiễm CSV/model.
    df = pd.DataFrame({
        "vni_open": [1.0, 1.0], "vni_high": [1.0, 1.0], "vni_low": [1.0, 1.0],
        "vni_close": [100.0, 0.0], "vni_volume": [1000.0, 1000.0],
    }, index=pd.date_range("2024-01-02", periods=2))
    out = _engineer(df)
    assert not np.isinf(out["vni_return_1d"]).any()
    assert pd.isna(out["vni_return_1d"].iloc[1])   # -inf → NaN
