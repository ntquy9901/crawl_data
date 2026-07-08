"""
Configuration module for Vietstock Crawler
Loads settings from .env file and provides constants
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

# Crawler URLs
TARGET_URL = os.getenv("TARGET_URL", "https://finance.vietstock.vn/bao-cao-phan-tich")
BASE_URL = os.getenv("BASE_URL", "https://finance.vietstock.vn")

# Paths
DATA_PATH = PROJECT_ROOT / os.getenv("DATA_PATH", "data")
PDF_PATH = PROJECT_ROOT / os.getenv("PDF_PATH", "data/pdf")
LOG_PATH = PROJECT_ROOT / os.getenv("LOG_PATH", "logs")
CSV_FILE = PROJECT_ROOT / os.getenv("CSV_FILE", "data/data.csv")

# Crawler Settings
RANDOM_DELAY_MIN = int(os.getenv("RANDOM_DELAY_MIN", "3"))
RANDOM_DELAY_MAX = int(os.getenv("RANDOM_DELAY_MAX", "8"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
TIMEOUT = int(os.getenv("TIMEOUT", "30000"))

# PDF download toggle. false (default) = metadata-only: skip download + the
# per-report random delay so the crawl runs as fast as possible. pdf_url is
# always recorded, so PDFs can be fetched in a later pass.
DOWNLOAD_PDF = os.getenv("DOWNLOAD_PDF", "false").lower() == "true"

# Proxy Settings
USE_PROXY = os.getenv("USE_PROXY", "false").lower() == "true"
PROXY_FILE = PROJECT_ROOT / os.getenv("PROXY_FILE", "proxies.txt")

# Captcha pause settings (skill BƯỚC 5: pause 5 minutes on detection, then retry)
CAPTCHA_PAUSE_MINUTES = int(os.getenv("CAPTCHA_PAUSE_MINUTES", "5"))
CAPTCHA_MAX_RETRIES = int(os.getenv("CAPTCHA_MAX_RETRIES", "3"))

# Captcha detection keywords (more specific to avoid false positives)
CAPTCHA_KEYWORDS = [
    "verify you are human",
    "human verification",
    "are you a robot",
    "security check",
    "please verify",
    "unusual traffic",
    "access denied",
    "cloudflare",
    "challenge platform",
    "ray id",  # Cloudflare specific
]

# CSV Headers
CSV_HEADERS = [
    "id",
    "title",
    "source",
    "date",
    "pdf_url",
    "pdf_filename",
    "downloaded_at",
]

# User Agents (will be enhanced with fake-useragent)
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",  # noqa: E501
]


def ensure_paths_exist():
    """Ensure all required directories exist"""
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    PDF_PATH.mkdir(parents=True, exist_ok=True)
    LOG_PATH.mkdir(parents=True, exist_ok=True)
