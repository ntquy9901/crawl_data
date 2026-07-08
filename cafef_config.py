"""
Cấu hình cho Cafef news crawler (sibling của Vietstock crawler).
Nguồn: skill `source-news-download` — Cafef = cổng tin tức thị trường hằng ngày.
Metadata + lead qua RSS; backfill qua sitemap shards (2016–2026).
Plain HTTP (requests) — cafef không cần Playwright/stealth.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.absolute()
BASE_URL = "https://cafef.vn"

# Paths (riêng biệt với Vietstock để không đụng data.csv)
DATA_PATH = PROJECT_ROOT / os.getenv("CAFEF_DATA_PATH", "data")
LOG_PATH = PROJECT_ROOT / os.getenv("LOG_PATH", "logs")
CSV_FILE = PROJECT_ROOT / os.getenv("CAFEF_CSV_FILE", "data/cafef_articles.csv")
# Cache danh sách <url,lastmod,title> lấy từ sitemap shards, để resume backfill không
# phải quét lại 757 shard (~15-20 phút) mỗi lần. Xoá file hoặc --refresh-shards để build lại.
CANDIDATES_CACHE = DATA_PATH / "cafef_candidates.jsonl"

# Proxy xoay vòng cho backfill sâu (chống IP throttle của cafef). Mặc định TẮT.
# Bật: set CAFEF_USE_PROXY=true + nạp residential proxy (IP:PORT hoặc IP:PORT:USER:PASS)
# vào CAFEF_PROXY_FILE (mặc định proxies.txt). Mỗi article fetch dùng 1 proxy random.
USE_PROXY = os.getenv("CAFEF_USE_PROXY", "false").lower() == "true"
PROXY_FILE = PROJECT_ROOT / os.getenv("CAFEF_PROXY_FILE", "proxies.txt")

# Section slug -> nhãn (theo skill: CK + Tài chính + Nhận định).
# Cafef không có section "tai-chinh" hay "nhan-dinh" (404); map sang slug thật
# lấy từ cafef.vn/sitemaps/category.rss.
CAFEF_SECTIONS = {
    "thi-truong-chung-khoan": "Chứng khoán",
    "tai-chinh-ngan-hang": "Tài chính",
    "vi-mo-dau-tu": "Nhận định",
}
DEFAULT_SECTIONS = list(CAFEF_SECTIONS.keys())

RSS_URL_FMT = BASE_URL + "/{slug}.rss"
SECTION_URL_FMT = BASE_URL + "/{slug}.chn"
SITEMAP_INDEX = BASE_URL + "/sitemap.xml"
SITEMAP_SHARD_RE = r"sitemaps-(\d{4})-(\d{1,2})-\d+-\d+\.xml"

# Polite HTTP settings
REQUEST_TIMEOUT = int(os.getenv("CAFEF_TIMEOUT", "25"))
REQUEST_DELAY = float(os.getenv("CAFEF_DELAY", "1.0"))  # giây giữa các request
MAX_RETRIES = int(os.getenv("CAFEF_MAX_RETRIES", "3"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Schema CSV (đặt article_url làm khóa dedup — không phải pdf_url như Vietstock)
CSV_HEADERS = [
    "id",            # numeric ID lấy từ URL bài viết
    "title",
    "section",       # slug của section
    "pub_date",      # ISO 8601 (YYYY-MM-DDTHH:MM:SS+07:00)
    "article_url",
    "author",        # có thể rỗng với RSS
    "lead",          # sapo/đoạn đầu (strip HTML từ RSS description)
    "collected_at",  # ISO timestamp lúc cào
]


def ensure_paths_exist():
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    LOG_PATH.mkdir(parents=True, exist_ok=True)
