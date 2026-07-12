"""Build data/macro/processed/macro_features.csv từ raw macro CSV.

Pipeline (pure, không network):
  1. Anchor = trading calendar của VNINDEX (bộ ngày trade VN = T2–T6 trừ lễ).
  2. align_to_calendar: map mỗi nguồn lên anchor với quy tắc "giá trị đã biết as-of T":
     - shift_days=1 cho DXY (US-time): value dated D usable từ anchor day sau D.
     - shift_days=0 cho nguồn VN-local (VCB/SBV central): value dated T đã biết tại T.
     - SBV policy rates: step function (ffill giữa các effective_date).
  3. Engineer features (log return, z-score, % change).
  4. Ghi macro_features.csv (utf-8-sig) + macro_features_stats.txt (coverage từng feature).

NaN KHÔNG bị drop — nguồn có start-date muộn hơn (DXY 2006) sẽ NaN cho 2000–2005, báo trong stats.

Usage:
  uv run python scripts/build_macro_features.py [--limit N]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from macro_config import (  # noqa: E402
    PROCESSED_PATH,
    RAW_DXY,
    RAW_SBV_POLICY,
    RAW_USD_VND_SBV,
    RAW_USD_VND_VCB,
    RAW_VNINDEX,
)

HN_TZ = timezone(timedelta(hours=7))

# Final schema (KHÔNG có vndibor_* — descope v1; sẽ thêm khi có source VNDIBOR).
COLS = [
    "date",
    "vni_open", "vni_high", "vni_low", "vni_close", "vni_volume",
    "vni_return_1d", "vni_return_5d", "vni_volume_zscore",
    "dxy", "dxy_return_1d",
    "usd_vnd_sell", "usd_vnd_buy", "usd_vnd_central",
    "usd_vnd_change_1d", "usd_vnd_volatility_5d",
    "refinancing_rate", "discount_rate", "omo_rate",
]


def _load_raw(path: Path, value_cols: list[str], date_col: str = "date") -> pd.DataFrame:
    """Đọc raw CSV → DataFrame(index=date_col, columns=value_cols), numeric coerce + dedup."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).drop_duplicates(subset=[date_col]).sort_values(date_col)
    for c in value_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index(date_col)[value_cols]


def _load_optional(
    path: Path, value_cols: list[str], date_col: str = "date"
) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = _load_raw(path, value_cols, date_col)
    return df if not df.empty else None


def align_to_calendar(
    df_src: pd.DataFrame,
    anchor: pd.DatetimeIndex,
    shift_days: int = 0,
    ffill: bool = True,
) -> pd.DataFrame:
    """Map source series lên VN trading calendar (anchor).

    Với mỗi anchor day T, lấy source observation mới nhất có source-date thỏa quy tắc
    "đã biết as-of T":
      - shift_days=0: source-date <= T (nguồn VN-local, value dated T biết tại T).
      - shift_days=N: source-date <= T-N  → value dated D usable từ D+N (DXY US-time).
    Triển khai: offset source index +N ngày rồi merge_asof backward (đúng cho cross-calendar).
    """
    src = df_src.copy()
    src.index = pd.to_datetime(src.index)
    src = src.sort_index()
    if shift_days:
        src.index = src.index + pd.Timedelta(days=shift_days)
    right = src.reset_index(names="date")
    left = pd.DataFrame({"date": pd.to_datetime(anchor)})
    out = pd.merge_asof(left, right, on="date", direction="backward").set_index("date")
    if ffill:
        out = out.ffill()
    return out


def _engineer(df: pd.DataFrame) -> pd.DataFrame:
    """Feature engineering trên frame đã align (index = VNINDEX calendar)."""
    # VNINDEX returns + volume z-score
    df["vni_return_1d"] = np.log(df["vni_close"] / df["vni_close"].shift(1))
    df["vni_return_5d"] = np.log(df["vni_close"] / df["vni_close"].shift(5))
    m20 = df["vni_volume"].rolling(20).mean()
    s20 = df["vni_volume"].rolling(20).std()
    df["vni_volume_zscore"] = (df["vni_volume"] - m20) / s20
    # DXY 1d return
    if "dxy" in df.columns:
        df["dxy_return_1d"] = df["dxy"].pct_change()
    # USD/VND: ưu tiên central, fallback commercial sell
    fx = pd.Series(np.nan, index=df.index, dtype=float)
    if "usd_vnd_central" in df.columns:
        fx = df["usd_vnd_central"]
    if "usd_vnd_sell" in df.columns:
        fx = fx.fillna(df["usd_vnd_sell"])
    df["usd_vnd_change_1d"] = fx.pct_change()
    df["usd_vnd_volatility_5d"] = fx.pct_change().rolling(5).std()
    # log(0)/div-by-0 (close=0, std=0) sinh ±inf → thay NaN để không nhiễm CSV/model.
    df = df.replace([np.inf, -np.inf], np.nan)
    return df


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build macro_features.csv từ raw data")
    ap.add_argument("--limit", type=int, default=0, help="cap số dòng (0=all, debug)")
    args = ap.parse_args(argv)

    PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_PATH / "macro_features.csv"
    out_stats = PROCESSED_PATH / "macro_features_stats.txt"

    # 1. Anchor = VNINDEX trading calendar (VNINDEX BẮT BUỘC).
    if not RAW_VNINDEX.exists():
        raise SystemExit(
            f"Thiếu {RAW_VNINDEX} (anchor). Chạy: python macro_crawler.py --sources vnindex"
        )
    vni = _load_raw(RAW_VNINDEX, ["open", "high", "low", "close", "volume"])
    if vni.empty:
        raise SystemExit(f"{RAW_VNINDEX} không có dòng date hợp lệ (anchor rỗng) — kiểm tra raw.")
    vni = vni.rename(columns={"open": "vni_open", "high": "vni_high", "low": "vni_low",
                              "close": "vni_close", "volume": "vni_volume"})
    anchor = vni.index
    df = vni.copy()

    # 2. Align từng nguồn non-anchor (date_col explicit, không string-dispatch yếu).
    sources_used: list[tuple[str, str]] = [("vnindex_prices.csv", f"{len(vni)} rows (anchor)")]
    for name, path, cols, shift, date_col in [
        ("dxy.csv", RAW_DXY, ["dxy"], 1, "date"),
        ("usd_vnd_commercial_vcb.csv", RAW_USD_VND_VCB, ["usd_vnd_buy", "usd_vnd_sell"], 0, "date"),
        ("usd_vnd_central_sbv.csv", RAW_USD_VND_SBV, ["usd_vnd_central"], 0, "date"),
        ("sbv_policy_rates.csv", RAW_SBV_POLICY,
         ["refinancing_rate", "discount_rate", "omo_rate"], 0, "effective_date"),
    ]:
        src = _load_optional(path, cols, date_col=date_col)
        if src is None:
            sources_used.append((name, "MISSING"))
            continue
        df = df.join(align_to_calendar(src, anchor, shift_days=shift, ffill=True))
        sources_used.append((name, f"{len(src)} rows"))

    # 3. Feature engineering.
    df = _engineer(df)

    if args.limit:
        df = df.head(args.limit)

    # 4. Ghi output: đảm bảo đủ COLS (trừ "date" = index), date thành string YYYY-MM-DD.
    for c in COLS:
        if c != "date" and c not in df.columns:
            df[c] = np.nan
    out = df[[c for c in COLS if c != "date"]].copy()
    out.index = out.index.strftime("%Y-%m-%d")
    out.index.name = "date"
    out = out.reset_index()   # "date" từ index → column (không trùng vì đã loại khỏi df[...])
    out.to_csv(out_csv, index=False, encoding="utf-8-sig", na_rep="")

    _write_stats(df, sources_used, out_stats)
    print(f"-> {out_csv}: {len(df)} rows, {df.index.min().strftime('%Y-%m-%d')} .. "
          f"{df.index.max().strftime('%Y-%m-%d')}")
    print(f"-> {out_stats}")


def _write_stats(df: pd.DataFrame, sources_used: list[tuple[str, str]], out_stats: Path) -> None:
    n = len(df)
    with open(out_stats, "w", encoding="utf-8") as f:
        f.write("=== MACRO FEATURES STATS ===\n\n")
        f.write(f"Generated: {datetime.now(HN_TZ).strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        if n:
            f.write(f"Date range: {df.index.min().strftime('%Y-%m-%d')} .. "
                    f"{df.index.max().strftime('%Y-%m-%d')}  ({n} rows)\n")
        f.write("Anchor: VNINDEX trading calendar (vndirect)\n")
        f.write("Look-ahead: DXY shift=1 (US-time); VN-local & policy rates shift=0 (same-day)\n\n")
        f.write("Per-feature coverage (non-NaN % of N rows):\n")
        for c in COLS:
            if c == "date" or c not in df.columns:
                continue
            cov = int(df[c].notna().sum())
            pct = cov * 100 // n if n else 0
            f.write(f"  {c:<24} {pct:3d}%  ({cov}/{n})\n")
        f.write("\nSource files used:\n")
        for name, status in sources_used:
            f.write(f"  {name:<32} {status}\n")
        f.write("\nVNDIBOR: DESCOPE v1 (không có source sạch) — thêm columns khi có source.\n")


if __name__ == "__main__":
    main()
