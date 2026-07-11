"""
Cấu hình cho macro features crawler — dữ liệu vĩ mô cho model dự đoán volatility VN30.

Nguồn (mỗi nguồn 1 raw CSV riêng trong data/macro/raw/):
  - VNINDEX OHLCV      : VNDIRECT finfo JSON API (full history từ 2000-07-28).
  - DXY (USD index)    : FRED CSV (DTWEXBGS, từ 2006-01-03).
  - USD/VND commercial : Vietcombank HTML table (~3-4 tháng gần).
  - USD/VND central    : SBV JSF (STUB v1 — JSF postback khó, method trả []).
  - SBV policy rates   : bảng tĩnh hand-curated (KHÔNG do crawler tạo).

Subfolder data/macro/ RIÊNG BIỆT, không đụng data/*.csv (news). data/macro/ được
commit (xem exception trong .gitignore) — nhỏ + khó fetch lại + cần reproduce.
Plain HTTP (requests) + stable UA (KHÔNG random — pitfall #1: nguồn trả 4xx với UA lạ).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.absolute()

# Paths — subfolder riêng, không đụng news CSV. data/macro/ được commit (.gitignore).
MACRO_PATH = PROJECT_ROOT / os.getenv("MACRO_PATH", "data/macro")
RAW_PATH = MACRO_PATH / os.getenv("MACRO_RAW_PATH", "raw")
PROCESSED_PATH = MACRO_PATH / os.getenv("MACRO_PROC_PATH", "processed")

# Per-source raw CSV (mỗi nguồn 1 file, append-resumable theo date).
RAW_VNINDEX = RAW_PATH / "vnindex_prices.csv"
RAW_DXY = RAW_PATH / "dxy.csv"
RAW_USD_VND_VCB = RAW_PATH / "usd_vnd_commercial_vcb.csv"
RAW_USD_VND_SBV = RAW_PATH / "usd_vnd_central_sbv.csv"
RAW_SBV_POLICY = RAW_PATH / "sbv_policy_rates.csv"  # hand-curated, không crawl

# Source endpoints.
VNDIRECT_FINFO_URL = "https://finfo-api.vndirect.com.vn/v4/stock_prices"
FRED_DXY_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS"
VCB_RATE_URL = "https://portal.vietcombank.com.vn/UserControls/TVPortal.TyGia/pListTyGia.aspx"

VNINDEX_SYMBOL = "VNINDEX"
VNDIRECT_PAGE_SIZE = 5000

# Polite HTTP — stable UA (KHÔNG random: pitfall #1, Vietstock/VCB trả 4xx với UA lạ).
REQUEST_TIMEOUT = int(os.getenv("MACRO_TIMEOUT", "25"))
REQUEST_DELAY = float(os.getenv("MACRO_DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("MACRO_MAX_RETRIES", "3"))
USER_AGENT = os.getenv(
    "MACRO_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)

# Per-source raw CSV schemas (header-once utf-8-sig, append utf-8).
HEADERS_VNINDEX = ["date", "open", "high", "low", "close", "volume", "source", "collected_at"]
HEADERS_DXY = ["date", "dxy", "source", "collected_at"]
HEADERS_USD_VND_VCB = ["date", "usd_vnd_buy", "usd_vnd_sell", "source", "collected_at"]
HEADERS_USD_VND_SBV = ["date", "usd_vnd_central", "source", "collected_at"]
HEADERS_SBV_POLICY = [
    "effective_date", "refinancing_rate", "discount_rate", "omo_rate", "source",
]

# Dynamic sources (crawler fetch). SBV policy rates = static (không trong list này).
SOURCES = ["vnindex", "dxy", "usd_vnd_vcb", "usd_vnd_sbv"]


def ensure_paths_exist():
    MACRO_PATH.mkdir(parents=True, exist_ok=True)
    RAW_PATH.mkdir(parents=True, exist_ok=True)
    PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
