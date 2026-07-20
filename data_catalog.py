"""
data_catalog — Data Source Registry + Benchmark Report Generator.

Two modes:
  report  → quét data/*.csv, tính thống kê, sinh report markdown
  summary → in tóm tắt nhanh ra terminal

Usage:
  python data_catalog.py report              # sinh docs/reports/dataset_benchmark.md
  python data_catalog.py report --force      # ghi đè nếu đã tồn tại
  python data_catalog.py summary             # in tóm tắt ra terminal
  python data_catalog.py catalog             # xuất catalog CSV ra data/data_catalog.csv
"""

import argparse
import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.absolute()
DATA_PATH = PROJECT_ROOT / "data"
REPORT_PATH = PROJECT_ROOT / "docs" / "reports"
HN_TZ = timezone(timedelta(hours=7))

# ── Data Source Registry ────────────────────────────────────────────────
# Each source: { key, name, type, url, description, crawl_method,
#               schema_family, columns, file_pattern, owner, notes }
DATA_SOURCES = [
    {
        "key": "vnstock",
        "name": "Vietstock Analysis Reports",
        "type": "analysis_report",
        "url": "https://finance.vietstock.vn/bao-cao-phan-tich",
        "description": "Báo cáo phân tích thị trường chứng khoán từ các CTCK (VNDS, MBS, KBSV, VDS, BSC...)",
        "crawl_method": "Playwright browser (stealth) + pagination + PDF download",
        "schema_family": "vietstock",
        "columns": "id, title, source, date, pdf_url, pdf_filename, downloaded_at",
        "file_pattern": "vnstock_articles.csv",
        "owner": "Vietstock",
        "notes": "Canonical dataset (14.8k reports). PDF download for recent years only."
    },
    {
        "key": "vnstock_pdf_raw",
        "name": "Vietstock PDF Raw Text",
        "type": "analysis_report_text",
        "url": "https://finance.vietstock.vn/bao-cao-phan-tich",
        "description": "Nội dung text trích xuất từ PDF báo cáo Vietstock",
        "crawl_method": "PyMuPDF extract from downloaded PDFs",
        "schema_family": "vietstock_text",
        "columns": "id, source, title, body, lead, date, pdf_url, pdf_filename",
        "file_pattern": "vnstock_pdf_raw.csv",
        "owner": "Vietstock",
        "notes": "~2.5k records với body text, file ~248MB do newlines trong body."
    },
    {
        "key": "cafef",
        "name": "Cafef News",
        "type": "news",
        "url": "https://cafef.vn",
        "description": "Tin tức thị trường chứng khoán, tài chính doanh nghiệp từ cafef.vn (RSS + sitemap)",
        "crawl_method": "HTTP requests (RSS daily + sitemap backfill)",
        "schema_family": "cafef",
        "columns": "id, title, section, pub_date, article_url, author, lead, collected_at, body",
        "file_pattern": "cafef_articles.csv",
        "owner": "Cafef (FPT Online)",
        "notes": "~39k rows nhưng chỉ ~4k có date. Deep backfill bị throttle. Schema khác biệt."
    },
    {
        "key": "ssi",
        "name": "SSI Research Bulletins",
        "type": "broker_report",
        "url": "https://www.ssi.com.vn/khach-hang-ca-nhan/bao-cao-ve-bctc",
        "description": "Báo cáo phân tích từ SSI Securities (PDF bulletins, listing-complete)",
        "crawl_method": "HTTP requests + pagination",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "ssi_articles.csv",
        "owner": "SSI Securities",
        "notes": "1.9k reports, 2019-2025, listing complete (~217 trang)."
    },
    {
        "key": "hsc",
        "name": "HSC Research Insights",
        "type": "broker_report",
        "url": "https://www.hsc.com.vn/research-insights",
        "description": "Research insights từ HSC Securities (daily-only, không pub_date)",
        "crawl_method": "HTTP requests (daily-only listing, không backfill)",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "hsc_articles.csv",
        "owner": "HSC Securities",
        "notes": "~40 records. pub_date toàn NaN (HSC không expose). Daily-only."
    },
    {
        "key": "vndirect",
        "name": "VNDIRECT Research Notes",
        "type": "broker_report",
        "url": "https://www.vndirect.com.vn/research-notes",
        "description": "Research notes từ VNDIRECT Securities (4 category, bilingual en/vi)",
        "crawl_method": "Playwright stealth (vượt Cloudflare) + category pagination",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "vndirect_articles.csv",
        "owner": "VNDIRECT Securities",
        "notes": "2k records (EN + VI), 2016-2022, 4 categories."
    },
    {
        "key": "tuoitre",
        "name": "Tuổi Trẻ News",
        "type": "mass_media",
        "url": "https://tuoitre.vn",
        "description": "Tin tức phổ thông từ tuoitre.vn (metadata-only, sitemap crawl)",
        "crawl_method": "Sitemap shard crawl (metadata-only, title embedded in sitemap)",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "tuoitre_articles.csv",
        "owner": "Tuổi Trẻ Newspaper",
        "notes": "283k records, 2011-2016. Date range dừng 2016 (backfill 1 lần)."
    },
    {
        "key": "thanhnien",
        "name": "Thanh Niên News",
        "type": "mass_media",
        "url": "https://thanhnien.vn",
        "description": "Tin tức phổ thông từ thanhnien.vn (metadata-only, sitemap crawl)",
        "crawl_method": "Sitemap shard crawl (metadata-only, title embedded in sitemap)",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "thanhnien_articles.csv",
        "owner": "Thanh Niên Newspaper",
        "notes": "387k records, 2011-2025. Metadata-only."
    },
    {
        "key": "vietnamplus",
        "name": "VietnamPlus News",
        "type": "mass_media",
        "url": "https://www.vietnamplus.vn",
        "description": "Tin tức phổ thông từ VietnamPlus.vn (metadata-only, sitemap crawl)",
        "crawl_method": "Sitemap shard crawl (metadata-only, title embedded in sitemap)",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "vietnamplus_articles.csv",
        "owner": "VietnamPlus (TTXVN)",
        "notes": "773k records, 2010-2026. Lớn nhất. Up-to-date."
    },
    {
        "key": "vnexpress",
        "name": "VnExpress News",
        "type": "mass_media",
        "url": "https://vnexpress.net",
        "description": "Tin tức từ VnExpress (Wayback Machine backfill do chặn bot sitemap)",
        "crawl_method": "Wayback Machine CDX API + snapshot fetch (archive.org)",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "vnexpress_articles.csv",
        "owner": "VnExpress (FPT Online)",
        "notes": "14k records, 2012-2026. pub_date ≈ snapshot date. Category có sẵn."
    },
    {
        "key": "news_merged",
        "name": "News Articles (Merged)",
        "type": "merged_dataset",
        "url": "",
        "description": "Hợp nhất từ cafef + ssi + hsc + vndirect + tuoitre + thanhnien + vietnamplus + vnexpress",
        "crawl_method": "merge_news.py (union + dedup theo url + cột source)",
        "schema_family": "news_merged",
        "columns": "source, data_type, title, category, pub_date, url, author, lead, body, pdf_url, collected_at",
        "file_pattern": "news_articles.csv",
        "owner": "N/A (merged)",
        "notes": "1.76M records. data_type phân loại nguồn. Dedup theo url."
    },
    {
        "key": "objective_vn30",
        "name": "VN30 Objective Records",
        "type": "structured_financial",
        "url": "",
        "description": "VN30 corporate action events, disclosures (Vietstock API + VSDC)",
        "crawl_method": "objective/adapters (Vietstock POST /data/EventsTypeData + VSDC crawl)",
        "schema_family": "objective",
        "columns": "document_id, source, source_tier, url, publish_time, crawl_time, company_code, company_name, title, raw_text, language, category, event_type, attachment_urls, checksum, raw_path",
        "file_pattern": "objective/objective_v*.csv",
        "owner": "Vietstock + VSDC",
        "notes": "435 records, 29/30 tickers. Tier-1 (VSDC) + Tier-3 (Vietstock)."
    },
    {
        "key": "macro_dxy",
        "name": "DXY US Dollar Index",
        "type": "macro_time_series",
        "url": "https://fred.stlouisfed.org",
        "description": "US Dollar Index daily data từ FRED (St. Louis Fed)",
        "crawl_method": "macro_crawler.py (FRED API)",
        "schema_family": "macro",
        "columns": "date, dxy, source, collected_at",
        "file_pattern": "macro/raw/dxy.csv",
        "owner": "FRED (Federal Reserve)",
        "notes": "5.3k records, 2006-2026. Daily, clean continuous."
    },
    {
        "key": "macro_sbv_rates",
        "name": "SBV Policy Rates",
        "type": "macro_policy",
        "url": "https://www.sbv.gov.vn",
        "description": "Lãi suất điều hành NHNN (refinancing, discount, OMO)",
        "crawl_method": "macro_crawler.py (manual collection)",
        "schema_family": "macro",
        "columns": "effective_date, refinancing_rate, discount_rate, omo_rate, source",
        "file_pattern": "macro/raw/sbv_policy_rates.csv",
        "owner": "State Bank of Vietnam",
        "notes": "11 records, 2011-2023. Chỉ 11 lần thay đổi."
    },
    {
        "key": "forum_traderviet",
        "name": "TraderViet Forum Threads",
        "type": "forum_discussion",
        "url": "https://traderviet.io/forums/",
        "description": "Threads từ diễn đàn TraderViet — phân tích CKVN, kiến thức trading",
        "crawl_method": "HTTP requests (XenForo listing pages + thread bodies)",
        "schema_family": "news",
        "columns": "id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body",
        "file_pattern": "forum_articles.csv",
        "owner": "TraderViet Community",
        "notes": "~800 threads từ stock analysis + trading knowledge sections."
    },
]


def safe_read_csv(path: Path, **kwargs) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)
        return df
    except Exception as e:
        print(f"  WARN: {path.name}: {e}")
        return pd.DataFrame()


def compute_stats(path: Path, source_key: str) -> dict:
    """Compute comprehensive statistics for a single data file."""
    df = safe_read_csv(path)
    if df.empty:
        return {"file": path.name, "rows": 0, "size_mb": 0, "columns": 0,
                "column_list": [], "null_columns": {}, "date_range": {},
                "unique_values": {}}

    size_mb = path.stat().st_size / (1024 * 1024)

    cols = list(df.columns)
    null_counts = df.isnull().sum().to_dict()
    null_pct = {k: round(v / len(df) * 100, 1) for k, v in null_counts.items() if v > 0}

    date_cols = [c for c in cols if c in ("date", "pub_date", "publish_time", "effective_date")]
    date_range = {}
    for dc in date_cols:
        if dc in df.columns:
            sample = df[dc].dropna().head(20).astype(str).tolist()
            has_dmy = any(bool(re.match(r'\d{2}/\d{2}/\d{4}', s)) for s in sample if s)
            parsed = pd.to_datetime(df[dc], errors="coerce", dayfirst=has_dmy)
            valid = parsed.dropna()
            if not valid.empty:
                date_range[dc] = {"min": valid.min().isoformat(), "max": valid.max().isoformat()}

    unique_counts = {}
    for c in ("source", "category", "section", "company_code", "company_name"):
        if c in df.columns:
            unique_counts[c] = int(df[c].nunique())

    return {
        "file": path.name,
        "rows": len(df),
        "size_mb": round(size_mb, 1),
        "columns": len(cols),
        "column_list": cols,
        "null_columns": null_pct,
        "date_range": date_range,
        "unique_values": unique_counts,
    }


def scan_data_dir() -> list[dict]:
    """Scan data/*.csv + data/objective/*.csv + data/macro/raw/*.csv."""
    results = []
    patterns = [
        list(DATA_PATH.glob("*.csv")),
        list(DATA_PATH.glob("objective/*.csv")),
        list(DATA_PATH.glob("macro/raw/*.csv")),
    ]
    for files in patterns:
        for f in sorted(files):
            if f.name.startswith("."):
                continue
            # map file to source key
            key = _file_to_key(f)
            src = next((s for s in DATA_SOURCES if s["key"] == key), None)
            stats = compute_stats(f, key)
            stats["source_key"] = key
            stats["source_info"] = src or {}
            results.append(stats)
    return results


def _file_to_key(path: Path) -> str:
    name = path.name
    mapping = {
        "vnstock_articles.csv": "vnstock",
        "vnstock_pdf_raw.csv": "vnstock_pdf_raw",
        "vnstock_pdfs_extracted.csv": "vnstock_pdf_raw",  # companion
        "data.csv": "vnstock",  # legacy
        "data_archive.csv": "vnstock",
        "data_2021_2025.csv": "vnstock",
        "cafef_articles.csv": "cafef",
        "ssi_articles.csv": "ssi",
        "hsc_articles.csv": "hsc",
        "vndirect_articles.csv": "vndirect",
        "tuoitre_articles.csv": "tuoitre",
        "thanhnien_articles.csv": "thanhnien",
        "vietnamplus_articles.csv": "vietnamplus",
    "vnexpress_articles.csv": "vnexpress",
    "forum_articles.csv": "forum_traderviet",
    "news_articles.csv": "news_merged",
        "dxy.csv": "macro_dxy",
        "sbv_policy_rates.csv": "macro_sbv_rates",
    }
    if "objective" in str(path):
        if "news_unenriched" in name:
            for src in ("nld", "thanhnien", "tuoitre", "vietnamplus", "vnexpress"):
                if src in name:
                    return f"objective_{src}"
            return "objective_news_unenriched"
        if "vietstock_records" in name:
            return "objective_vn30"
        if "vsdc_records" in name:
            return "objective_vsdc"
        if name.startswith("objective_v"):
            return "objective_vn30"
        return "objective"
    return mapping.get(name, "unknown")


def generate_report(force: bool = False) -> str:
    """Generate comprehensive dataset benchmark markdown report."""
    REPORT_PATH.mkdir(parents=True, exist_ok=True)
    today = datetime.now(HN_TZ).strftime("%Y-%m-%d %H:%M")
    filename = REPORT_PATH / f"dataset_benchmark_{datetime.now(HN_TZ).strftime('%Y-%m-%d')}.md"

    if filename.exists() and not force:
        print(f"  Report exists: {filename} (use --force to overwrite)")
        return str(filename)

    scans = scan_data_dir()

    # Group by source key
    groups = {}
    for s in scans:
        key = s["source_key"]
        if key not in groups:
            groups[key] = []
        groups[key].append(s)

    lines = []
    _w = lines.append

    _w("# Dataset Benchmark Report — crawl_data")
    _w("")
    _w(f"> **Generated:** {today} ICT")
    _w("> **Project:** Vietstock Analysis Reports Crawler — Multi-source Vietnamese stock market data")
    _w("> **Purpose:** Dataset documentation for academic paper / professor report")
    _w("")
    _w("---")
    _w("")

    # ── 1. Executive Summary ──
    total_rows = sum(s["rows"] for s in scans)
    total_mb = sum(s["size_mb"] for s in scans)
    src_count = len(groups)

    _w("## 1. Executive Summary")
    _w("")
    _w("| Metric | Value |")
    _w("|---|---|")
    _w(f"| **Data sources** | {src_count} unique sources |")
    _w(f"| **Total records** | {total_rows:,} |")
    _w(f"| **Total size** | {total_mb:,.0f} MB ({total_mb/1024:.1f} GB) |")
    _w("| **Date coverage** | 2005 — 2026 |")
    _w("| **Collection period** | 2021-07 — 2026-07 (5+ years) |")
    _w("| **Crawl methods** | HTTP requests, Playwright browser, Sitemap, Wayback Machine |")
    _w("| **Data types** | Analysis reports, news, broker research, corporate actions, macroeconomics |")
    _w("")

    # ── 2. Data Source Overview ──
    _w("## 2. Data Source Overview")
    _w("")
    _w("| # | Source | Type | Records | Size | Date Range | Method |")
    _w("|---|---|---|---|---|---|---|")

    for idx, src in enumerate(DATA_SOURCES, 1):
        key = src["key"]
        stats_list = groups.get(key, [])
        if not stats_list:
            continue
        primary = stats_list[0]
        dr = _fmt_date_range(primary)
        _w(f"| {idx} | **{src['name']}** | {src['type']} | {primary['rows']:,} | {primary['size_mb']} MB | {dr} | {src['crawl_method']} |")

    _w("")

    # ── 3. Per-Source Detail ──
    _w("## 3. Per-Source Detail")
    _w("")

    for src in DATA_SOURCES:
        key = src["key"]
        stats_list = groups.get(key, [])
        if not stats_list:
            continue
        primary = stats_list[0]
        _w(f"### {src['name']}")
        _w("")
        _w(f"- **URL:** {src['url'] or 'N/A'}")
        _w(f"- **Description:** {src['description']}")
        _w(f"- **Owner:** {src['owner']}")
        _w(f"- **Records:** {primary['rows']:,}")
        _w(f"- **Size:** {primary['size_mb']} MB")
        _w(f"- **Columns ({primary['columns']}):** `{src['columns']}`")
        _w(f"- **Crawl method:** {src['crawl_method']}")
        _w("")

        # Date range
        if primary["date_range"]:
            for dc, rng in primary["date_range"].items():
                _w(f"- **Date range ({dc}):** {rng['min']} → {rng['max']}")

        # Unique values
        if primary["unique_values"]:
            uv = "; ".join(f"{k}={v}" for k, v in primary["unique_values"].items())
            _w(f"- **Unique values:** {uv}")

        # Null columns
        if primary["null_columns"]:
            nulls = {k: v for k, v in sorted(primary["null_columns"].items(), key=lambda x: -x[1])}
            null_str = "; ".join(f"{k}: {v}%" for k, v in list(nulls.items())[:5])
            _w(f"- **Missing data (top 5):** {null_str}")

        _w(f"- **Notes:** {src['notes']}")
        _w("")

    # ── 4. Schema Reference ──
    _w("## 4. Schema Reference")
    _w("")

    schemas = {
        "news": {
            "description": "Unified schema for news articles and broker reports",
            "sources": "ssi, hsc, vndirect, tuoitre, thanhnien, vietnamplus, vnexpress",
            "fields": [
                ("id", "str", "MD5 hash (12 chars) of URL"),
                ("source", "str", "Source name identifier"),
                ("title", "str", "Article/report title"),
                ("category", "str", "Section/category"),
                ("pub_date", "str", "Publication date (DD/MM/YYYY or ISO)"),
                ("url", "str", "Canonical URL"),
                ("author", "str", "Author or institution"),
                ("lead", "str", "Description/abstract (~500 chars)"),
                ("pdf_url", "str", "URL to PDF (if applicable)"),
                ("pdf_filename", "str", "Local PDF filename (if downloaded)"),
                ("collected_at", "str", "ISO timestamp of crawl"),
                ("body", "str", "Full article body text"),
            ],
        },
        "vietstock": {
            "description": "Vietstock analysis reports metadata",
            "sources": "vnstock_articles.csv",
            "fields": [
                ("id", "str", "Composite id (date_index)"),
                ("title", "str", "Report title"),
                ("source", "str", "Broker/issuer"),
                ("date", "str", "Report date (DD/MM/YYYY)"),
                ("pdf_url", "str", "PDF download URL"),
                ("pdf_filename", "str", "Local PDF file"),
                ("downloaded_at", "str", "ISO timestamp of download"),
            ],
        },
        "objective": {
            "description": "VN30 objective corporate action records",
            "sources": "objective/*.csv",
            "fields": [
                ("document_id", "str", "Unique document ID"),
                ("source", "str", "Source identifier"),
                ("source_tier", "str", "Data reliability tier (1-3)"),
                ("url", "str", "Source URL"),
                ("publish_time", "str", "Publication timestamp"),
                ("crawl_time", "str", "Crawl timestamp (UTC)"),
                ("company_code", "str", "VN30 ticker code"),
                ("company_name", "str", "Company name"),
                ("title", "str", "Event/document title"),
                ("raw_text", "str", "Full raw text"),
                ("language", "str", "Language code"),
                ("category", "str", "News category"),
                ("event_type", "str", "Classified event type"),
                ("attachment_urls", "str", "URLs to attachments"),
                ("checksum", "str", "Content checksum (dedup)"),
                ("raw_path", "str", "Path to raw HTML/JSON"),
            ],
        },
        "cafef": {
            "description": "Cafef news (independent schema)",
            "sources": "cafef_articles.csv",
            "fields": [
                ("id", "str", "MD5 hash of URL"),
                ("title", "str", "Article title"),
                ("section", "str", "Cafef section"),
                ("pub_date", "str", "Publication date (ISO)"),
                ("article_url", "str", "Article URL"),
                ("author", "str", "Author name"),
                ("lead", "str", "Sapo/abstract"),
                ("collected_at", "str", "Crawl timestamp"),
                ("body", "str", "Full body text"),
            ],
        },
        "macro": {
            "description": "Macroeconomic time-series data",
            "sources": "macro/raw/*.csv",
            "fields": [
                ("date / effective_date", "str/date", "Date (ISO)"),
                ("dxy", "float", "US Dollar Index"),
                ("refinancing_rate", "float", "SBV refinancing rate (%)"),
                ("discount_rate", "float", "SBV discount rate (%)"),
                ("omo_rate", "float", "OMO rate (%)"),
                ("source", "str", "Data source"),
                ("collected_at", "str", "Crawl timestamp"),
            ],
        },
    }

    for schema_name, schema in schemas.items():
        _w(f"### {schema_name.title()} Schema")
        _w("")
        _w(f"- **Description:** {schema['description']}")
        _w(f"- **Sources:** {schema['sources']}")
        _w("")
        _w("| Field | Type | Description |")
        _w("|---|---|---|")
        for field, ftype, desc in schema["fields"]:
            _w(f"| `{field}` | {ftype} | {desc} |")
        _w("")

    # ── 5. Data Quality Assessment ──
    _w("## 5. Data Quality Assessment")
    _w("")

    quality_issues = []
    for s in scans:
        key = s["source_key"]
        src = next((x for x in DATA_SOURCES if x["key"] == key), None)
        name = src["name"] if src else key
        if s["null_columns"]:
            for col, pct in sorted(s["null_columns"].items(), key=lambda x: -x[1]):
                if pct >= 50:
                    quality_issues.append(f"- **{name}** — `{col}` missing {pct}%")
                elif pct >= 20:
                    quality_issues.append(f"- **{name}** — `{col}` missing {pct}% (moderate)")
        if s["rows"] == 0:
            quality_issues.append(f"- **{name}** — empty file ({s['file']})")

    if quality_issues:
        _w("### Known Issues")
        _w("")
        for issue in quality_issues:
            _w(f"{issue}")
        _w("")

    _w("### Completeness Summary")
    _w("")
    _w("| Source | Completeness | Notes |")
    _w("|---|---|---|")
    for s in scans:
        key = s["source_key"]
        src = next((x for x in DATA_SOURCES if x["key"] == key), None)
        name = src["name"] if src else s["file"]
        null_cols = len(s["null_columns"])
        total_cols = s["columns"]
        completeness = round((1 - null_cols / total_cols) * 100, 1) if total_cols else 100
        notes = ""
        if s["rows"] == 0:
            notes = "Empty"
        elif null_cols >= total_cols / 2:
            notes = "Many missing columns"
        elif null_cols == 0:
            notes = "Complete"
        else:
            notes = f"{null_cols}/{total_cols} columns partial"
        _w(f"| {name} | {completeness}% | {notes} |")
    _w("")

    # ── 6. Collection Methodology ──
    _w("## 6. Collection Methodology")
    _w("")
    _w("The dataset is collected using a multi-strategy crawling architecture:")
    _w("")
    _w("1. **Playwright browser (stealth):** Used for sites with JavaScript-rendered content or Cloudflare protection. "
        "Applies stealth patches (`playwright-stealth`), random User-Agent, human-like delays. "
        "Used by: Vietstock (analysis reports), VNDIRECT (research notes).")
    _w("2. **HTTP requests:** Direct HTTP GET with retry logic, randomized User-Agent. "
        "Used by: Cafef (RSS + sitemap), SSI (research), HSC, news sitemap crawler.")
    _w("3. **Sitemap shard crawl:** Parses XML sitemap shards (which already embed article title in `<image:title>` / `<news:title>`). "
        "No per-article fetch needed. Used by: Tuổi Trẻ, Thanh Niên, VietnamPlus.")
    _w("4. **Wayback Machine backfill:** For sites that block bots at the sitemap level (VnExpress). "
        "Uses archive.org CDX API to list snapshots, fetches saved pages, extracts article links.")
    _w("5. **API integration:** Direct API calls for structured data. "
        "Used by: Vietstock disclosure API (`/data/EventsTypeData`), VSDC corporate actions.")
    _w("")

    # ── 7. Limitations ──
    _w("## 7. Known Limitations")
    _w("")
    _w("| Issue | Impact | Status |")
    _w("|---|---|---|")
    _w("| HSC lacks pub_date | 39 records undateable | Site limitation |")
    _w("| Cafef deep backfill throttle | Only ~4k dated records | IP throttling by Cafef |")
    _w("| Tuoi Tre data ends 2016 | Missing 2016-2026 | Backfill not re-run |")
    _w("| VnExpress dates approximate | ~14k records, date ≈ snapshot date | Wayback limitation |")
    _w("| Vietstock gap 2006-2007 | Zero records | Real gap on site |")
    _w("| Cafef schema mismatch | Different columns from other news | Independent design |")
    _w("| PDF text extraction incomplete | ~2.5k of 14.8k PDFs extracted | CPU-bound, partial |")
    _w("| VN30: 1/30 ticker missing | Chưa có dữ liệu disclosure cho 1 mã | Đang chờ adapter |")
    _w("| Date format inconsistency | DD/MM/YYYY vs ISO mixed in datasets | Normalization needed |")
    _w("")

    # ── 8. Sample Records ──
    _w("## 8. Sample Records")
    _w("")

    for src in DATA_SOURCES[:5]:  # top 5 sources
        key = src["key"]
        stats_list = groups.get(key, [])
        if not stats_list:
            continue
        primary = stats_list[0]
        path = DATA_PATH / primary["file"]
        if not path.exists():
            continue
        df = safe_read_csv(path, nrows=3)
        if df.empty:
            continue
        _w(f"### {src['name']}")
        _w("")
        _w("```")
        _w(df.to_string(max_colwidth=60))
        _w("```")
        _w("")

    # ── 9. Citation ──
    _w("## 9. Citation")
    _w("")
    _w("If using this dataset in academic work, please cite as:")
    _w("")
    _w("> ```bibtex")
    _w("> @misc{crawl_data_2026,")
    _w(">   author = {Quy, Nguyen T.},")
    _w(">   title = {crawl\\_data: Multi-Source Vietnamese Stock Market Dataset},")
    _w(">   year = {2026},")
    _w(">   howpublished = {\\url{https://github.com/ntquy9901/crawl\\_data}},")
    _w(f">   note = {{Accessed: {datetime.now(HN_TZ).strftime('%Y-%m-%d')}}}")
    _w("> }")
    _w("> ```")
    _w("")
    _w("---")
    _w("")
    _w("*Report generated by `data_catalog.py`*")

    report_text = "\n".join(lines)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"  Report written: {filename} ({len(report_text):,} chars)")
    return str(filename)


def print_summary():
    """Print quick terminal summary."""
    scans = scan_data_dir()
    groups = {}
    for s in scans:
        key = s["source_key"]
        if key not in groups:
            groups[key] = []
        groups[key].append(s)

    print(f"\n{'='*80}")
    print(f"  Data Catalog Summary — {datetime.now(HN_TZ).strftime('%Y-%m-%d %H:%M')} ICT")
    print(f"{'='*80}")
    print(f"  {'Source':<35} {'Rows':>10} {'Size':>10} {'Date Range':<30}")
    print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*30}")

    total_rows = 0
    total_mb = 0
    for src in DATA_SOURCES:
        key = src["key"]
        stats_list = groups.get(key, [])
        if not stats_list:
            continue
        primary = stats_list[0]
        dr = _fmt_date_range(primary)
        print(f"  {src['name']:<35} {primary['rows']:>10,} {primary['size_mb']:>8.1f} MB  {dr:<30}")
        total_rows += primary["rows"]
        total_mb += primary["size_mb"]

    print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*30}")
    print(f"  {'TOTAL':<35} {total_rows:>10,} {total_mb:>8.0f} MB")
    print(f"{'='*80}\n")


def _fmt_date_range(stats: dict) -> str:
    dr = stats.get("date_range", {})
    if not dr:
        return "N/A"
    for dc, rng in dr.items():
        return f"{rng['min'][:10]} → {rng['max'][:10]}"
    return "N/A"


def export_catalog_csv():
    """Export data source catalog to CSV."""
    out = DATA_PATH / "data_catalog.csv"
    fields = ["key", "name", "type", "url", "description", "crawl_method",
              "schema_family", "columns", "file_pattern", "owner", "notes"]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in DATA_SOURCES:
            w.writerow({k: s.get(k, "") for k in fields})
    print(f"  Catalog written: {out} ({len(DATA_SOURCES)} sources)")


def main():
    ap = argparse.ArgumentParser(description="Data Catalog — source tracking + benchmark report")
    ap.add_argument("mode", choices=["report", "summary", "catalog"],
                    help="report: sinh benchmark markdown | summary: terminal | catalog: CSV")
    ap.add_argument("--force", action="store_true", help="force overwrite report")
    args = ap.parse_args()

    if args.mode == "report":
        generate_report(force=args.force)
    elif args.mode == "summary":
        print_summary()
    elif args.mode == "catalog":
        export_catalog_csv()


if __name__ == "__main__":
    main()
