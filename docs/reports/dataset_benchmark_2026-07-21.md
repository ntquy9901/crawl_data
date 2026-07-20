# Dataset Benchmark Report — crawl_data

> **Generated:** 2026-07-21 01:04 ICT
> **Project:** Vietstock Analysis Reports Crawler — Multi-source Vietnamese stock market data
> **Purpose:** Dataset documentation for academic paper / professor report

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Data sources** | 22 unique sources |
| **Total records** | 3,009,859 |
| **Total size** | 1,218 MB (1.2 GB) |
| **Date coverage** | 2005 — 2026 |
| **Collection period** | 2021-07 — 2026-07 (5+ years) |
| **Crawl methods** | HTTP requests, Playwright browser, Sitemap, Wayback Machine |
| **Data types** | Analysis reports, news, broker research, corporate actions, macroeconomics |

## 2. Data Source Overview

| # | Source | Type | Records | Size | Date Range | Method |
|---|---|---|---|---|---|---|
| 1 | **Vietstock Analysis Reports** | analysis_report | 14,393 | 2.4 MB | 2001-06-30 → 2026-09-21 | Playwright browser (stealth) + pagination + PDF download |
| 2 | **Vietstock PDF Raw Text** | analysis_report_text | 11,778 | 247.6 MB | 2001-06-30 → 2026-09-21 | PyMuPDF extract from downloaded PDFs |
| 3 | **Cafef News** | news | 4,067 | 17.4 MB | 2026-07-01 → 2026-07-15 | HTTP requests (RSS daily + sitemap backfill) |
| 4 | **SSI Research Bulletins** | broker_report | 1,867 | 6.1 MB | 2019-01-16 → 2026-07-14 | HTTP requests + pagination |
| 5 | **HSC Research Insights** | broker_report | 6 | 0.0 MB | N/A | HTTP requests (daily-only listing, không backfill) |
| 6 | **VNDIRECT Research Notes** | broker_report | 2,043 | 3.8 MB | 2016-01-15 → 2026-07-13 | Playwright stealth (vượt Cloudflare) + category pagination |
| 7 | **Tuổi Trẻ News** | mass_media | 283,568 | 54.6 MB | 2011-01-06 → 2016-10-01 | Sitemap shard crawl (metadata-only, title embedded in sitemap) |
| 8 | **Thanh Niên News** | mass_media | 387,169 | 80.6 MB | 2011-06-01 → 2025-12-19 | Sitemap shard crawl (metadata-only, title embedded in sitemap) |
| 9 | **VietnamPlus News** | mass_media | 773,152 | 195.0 MB | 2010-01-01 → 2026-07-18 | Sitemap shard crawl (metadata-only, title embedded in sitemap) |
| 10 | **VnExpress News** | mass_media | 13,938 | 3.6 MB | 2012-09-04 → 2026-07-10 | Wayback Machine CDX API + snapshot fetch (archive.org) |
| 11 | **News Articles (Merged)** | merged_dataset | 1,465,810 | 355.6 MB | 2010-01-01 → 2026-07-18 | merge_news.py (union + dedup theo url + cột source) |
| 12 | **VN30 Objective Records** | structured_financial | 0 | 0 MB | N/A | objective/adapters (Vietstock POST /data/EventsTypeData + VSDC crawl) |
| 13 | **DXY US Dollar Index** | macro_time_series | 5,349 | 0.3 MB | 2006-01-02 → 2026-07-02 | macro_crawler.py (FRED API) |
| 14 | **SBV Policy Rates** | macro_policy | 11 | 0.0 MB | 2011-10-05 → 2023-06-19 | macro_crawler.py (manual collection) |
| 15 | **TraderViet Forum Threads** | forum_discussion | 1,104 | 4.4 MB | 2018-12-31 → 2026-07-20 | HTTP requests (XenForo listing pages + thread bodies) |

## 3. Per-Source Detail

### Vietstock Analysis Reports

- **URL:** https://finance.vietstock.vn/bao-cao-phan-tich
- **Description:** Báo cáo phân tích thị trường chứng khoán từ các CTCK (VNDS, MBS, KBSV, VDS, BSC...)
- **Owner:** Vietstock
- **Records:** 14,393
- **Size:** 2.4 MB
- **Columns (7):** `id, title, source, date, pdf_url, pdf_filename, downloaded_at`
- **Crawl method:** Playwright browser (stealth) + pagination + PDF download

- **Date range (date):** 2001-06-30T00:00:00 → 2026-09-21T00:00:00
- **Unique values:** source=108
- **Missing data (top 5):** pdf_filename: 83.8%
- **Notes:** Canonical dataset (14.8k reports). PDF download for recent years only.

### Vietstock PDF Raw Text

- **URL:** https://finance.vietstock.vn/bao-cao-phan-tich
- **Description:** Nội dung text trích xuất từ PDF báo cáo Vietstock
- **Owner:** Vietstock
- **Records:** 11,778
- **Size:** 247.6 MB
- **Columns (8):** `id, source, title, body, lead, date, pdf_url, pdf_filename`
- **Crawl method:** PyMuPDF extract from downloaded PDFs

- **Date range (date):** 2001-06-30T00:00:00 → 2026-09-21T00:00:00
- **Unique values:** source=74
- **Notes:** ~2.5k records với body text, file ~248MB do newlines trong body.

### Cafef News

- **URL:** https://cafef.vn
- **Description:** Tin tức thị trường chứng khoán, tài chính doanh nghiệp từ cafef.vn (RSS + sitemap)
- **Owner:** Cafef (FPT Online)
- **Records:** 4,067
- **Size:** 17.4 MB
- **Columns (9):** `id, title, section, pub_date, article_url, author, lead, collected_at, body`
- **Crawl method:** HTTP requests (RSS daily + sitemap backfill)

- **Date range (pub_date):** 2026-07-01T10:50:00+07:00 → 2026-07-15T08:30:00+07:00
- **Unique values:** section=3
- **Missing data (top 5):** author: 100.0%; collected_at: 10.4%; id: 8.4%; body: 0.1%; lead: 0.0%
- **Notes:** ~39k rows nhưng chỉ ~4k có date. Deep backfill bị throttle. Schema khác biệt.

### SSI Research Bulletins

- **URL:** https://www.ssi.com.vn/khach-hang-ca-nhan/bao-cao-ve-bctc
- **Description:** Báo cáo phân tích từ SSI Securities (PDF bulletins, listing-complete)
- **Owner:** SSI Securities
- **Records:** 1,867
- **Size:** 6.1 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** HTTP requests + pagination

- **Date range (pub_date):** 2019-01-16T00:00:00 → 2026-07-14T00:00:00
- **Unique values:** source=1; category=1
- **Missing data (top 5):** pdf_filename: 0.2%; body: 0.2%
- **Notes:** 1.9k reports, 2019-2025, listing complete (~217 trang).

### HSC Research Insights

- **URL:** https://www.hsc.com.vn/research-insights
- **Description:** Research insights từ HSC Securities (daily-only, không pub_date)
- **Owner:** HSC Securities
- **Records:** 6
- **Size:** 0.0 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** HTTP requests (daily-only listing, không backfill)

- **Unique values:** source=1; category=1
- **Missing data (top 5):** pub_date: 100.0%; pdf_url: 100.0%; pdf_filename: 100.0%
- **Notes:** ~40 records. pub_date toàn NaN (HSC không expose). Daily-only.

### VNDIRECT Research Notes

- **URL:** https://www.vndirect.com.vn/research-notes
- **Description:** Research notes từ VNDIRECT Securities (4 category, bilingual en/vi)
- **Owner:** VNDIRECT Securities
- **Records:** 2,043
- **Size:** 3.8 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** Playwright stealth (vượt Cloudflare) + category pagination

- **Date range (pub_date):** 2016-01-15T00:00:00 → 2026-07-13T00:00:00
- **Unique values:** source=1; category=8
- **Missing data (top 5):** pdf_url: 100.0%; pdf_filename: 100.0%; body: 52.7%
- **Notes:** 2k records (EN + VI), 2016-2022, 4 categories.

### Tuổi Trẻ News

- **URL:** https://tuoitre.vn
- **Description:** Tin tức phổ thông từ tuoitre.vn (metadata-only, sitemap crawl)
- **Owner:** Tuổi Trẻ Newspaper
- **Records:** 283,568
- **Size:** 54.6 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** Sitemap shard crawl (metadata-only, title embedded in sitemap)

- **Date range (pub_date):** 2011-01-06T07:01:00+07:00 → 2016-10-01T06:32:00+07:00
- **Unique values:** source=1; category=0
- **Missing data (top 5):** category: 100.0%; author: 100.0%; lead: 100.0%; pdf_url: 100.0%; pdf_filename: 100.0%
- **Notes:** 283k records, 2011-2016. Date range dừng 2016 (backfill 1 lần).

### Thanh Niên News

- **URL:** https://thanhnien.vn
- **Description:** Tin tức phổ thông từ thanhnien.vn (metadata-only, sitemap crawl)
- **Owner:** Thanh Niên Newspaper
- **Records:** 387,169
- **Size:** 80.6 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** Sitemap shard crawl (metadata-only, title embedded in sitemap)

- **Date range (pub_date):** 2011-06-01T00:33:44+07:00 → 2025-12-19T21:59:13+07:00
- **Unique values:** source=1; category=0
- **Missing data (top 5):** category: 100.0%; author: 100.0%; lead: 100.0%; pdf_url: 100.0%; pdf_filename: 100.0%
- **Notes:** 387k records, 2011-2025. Metadata-only.

### VietnamPlus News

- **URL:** https://www.vietnamplus.vn
- **Description:** Tin tức phổ thông từ VietnamPlus.vn (metadata-only, sitemap crawl)
- **Owner:** VietnamPlus (TTXVN)
- **Records:** 773,152
- **Size:** 195.0 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** Sitemap shard crawl (metadata-only, title embedded in sitemap)

- **Date range (pub_date):** 2010-01-01T07:20:00+07:00 → 2026-07-18T10:39:24+07:00
- **Unique values:** source=1; category=0
- **Missing data (top 5):** category: 100.0%; author: 100.0%; lead: 100.0%; pdf_url: 100.0%; pdf_filename: 100.0%
- **Notes:** 773k records, 2010-2026. Lớn nhất. Up-to-date.

### VnExpress News

- **URL:** https://vnexpress.net
- **Description:** Tin tức từ VnExpress (Wayback Machine backfill do chặn bot sitemap)
- **Owner:** VnExpress (FPT Online)
- **Records:** 13,938
- **Size:** 3.6 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** Wayback Machine CDX API + snapshot fetch (archive.org)

- **Date range (pub_date):** 2012-09-04T00:00:00 → 2026-07-10T00:00:00
- **Unique values:** source=1; category=2
- **Missing data (top 5):** author: 100.0%; lead: 100.0%; pdf_url: 100.0%; pdf_filename: 100.0%; body: 100.0%
- **Notes:** 14k records, 2012-2026. pub_date ≈ snapshot date. Category có sẵn.

### News Articles (Merged)

- **URL:** N/A
- **Description:** Hợp nhất từ cafef + ssi + hsc + vndirect + tuoitre + thanhnien + vietnamplus + vnexpress
- **Owner:** N/A (merged)
- **Records:** 1,465,810
- **Size:** 355.6 MB
- **Columns (11):** `source, data_type, title, category, pub_date, url, author, lead, body, pdf_url, collected_at`
- **Crawl method:** merge_news.py (union + dedup theo url + cột source)

- **Date range (pub_date):** 2010-01-01T07:20:00+07:00 → 2026-07-18T10:39:24+07:00
- **Unique values:** source=8; category=15
- **Missing data (top 5):** pdf_url: 99.9%; author: 99.7%; lead: 99.5%; body: 99.5%; category: 98.5%
- **Notes:** 1.76M records. data_type phân loại nguồn. Dedup theo url.

### VN30 Objective Records

- **URL:** N/A
- **Description:** VN30 corporate action events, disclosures (Vietstock API + VSDC)
- **Owner:** Vietstock + VSDC
- **Records:** 0
- **Size:** 0 MB
- **Columns (0):** `document_id, source, source_tier, url, publish_time, crawl_time, company_code, company_name, title, raw_text, language, category, event_type, attachment_urls, checksum, raw_path`
- **Crawl method:** objective/adapters (Vietstock POST /data/EventsTypeData + VSDC crawl)

- **Notes:** 435 records, 29/30 tickers. Tier-1 (VSDC) + Tier-3 (Vietstock).

### DXY US Dollar Index

- **URL:** https://fred.stlouisfed.org
- **Description:** US Dollar Index daily data từ FRED (St. Louis Fed)
- **Owner:** FRED (Federal Reserve)
- **Records:** 5,349
- **Size:** 0.3 MB
- **Columns (4):** `date, dxy, source, collected_at`
- **Crawl method:** macro_crawler.py (FRED API)

- **Date range (date):** 2006-01-02T00:00:00 → 2026-07-02T00:00:00
- **Unique values:** source=1
- **Missing data (top 5):** dxy: 3.9%
- **Notes:** 5.3k records, 2006-2026. Daily, clean continuous.

### SBV Policy Rates

- **URL:** https://www.sbv.gov.vn
- **Description:** Lãi suất điều hành NHNN (refinancing, discount, OMO)
- **Owner:** State Bank of Vietnam
- **Records:** 11
- **Size:** 0.0 MB
- **Columns (5):** `effective_date, refinancing_rate, discount_rate, omo_rate, source`
- **Crawl method:** macro_crawler.py (manual collection)

- **Date range (effective_date):** 2011-10-05T00:00:00 → 2023-06-19T00:00:00
- **Unique values:** source=1
- **Notes:** 11 records, 2011-2023. Chỉ 11 lần thay đổi.

### TraderViet Forum Threads

- **URL:** https://traderviet.io/forums/
- **Description:** Threads từ diễn đàn TraderViet — phân tích CKVN, kiến thức trading
- **Owner:** TraderViet Community
- **Records:** 1,104
- **Size:** 4.4 MB
- **Columns (12):** `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`
- **Crawl method:** HTTP requests (XenForo listing pages + thread bodies)

- **Date range (pub_date):** 2018-12-31T12:40:01 → 2026-07-20T16:01:05
- **Unique values:** source=1; category=0
- **Missing data (top 5):** category: 100.0%; pdf_url: 100.0%; pdf_filename: 100.0%
- **Notes:** ~800 threads từ stock analysis + trading knowledge sections.

## 4. Schema Reference

### News Schema

- **Description:** Unified schema for news articles and broker reports
- **Sources:** ssi, hsc, vndirect, tuoitre, thanhnien, vietnamplus, vnexpress

| Field | Type | Description |
|---|---|---|
| `id` | str | MD5 hash (12 chars) of URL |
| `source` | str | Source name identifier |
| `title` | str | Article/report title |
| `category` | str | Section/category |
| `pub_date` | str | Publication date (DD/MM/YYYY or ISO) |
| `url` | str | Canonical URL |
| `author` | str | Author or institution |
| `lead` | str | Description/abstract (~500 chars) |
| `pdf_url` | str | URL to PDF (if applicable) |
| `pdf_filename` | str | Local PDF filename (if downloaded) |
| `collected_at` | str | ISO timestamp of crawl |
| `body` | str | Full article body text |

### Vietstock Schema

- **Description:** Vietstock analysis reports metadata
- **Sources:** vnstock_articles.csv

| Field | Type | Description |
|---|---|---|
| `id` | str | Composite id (date_index) |
| `title` | str | Report title |
| `source` | str | Broker/issuer |
| `date` | str | Report date (DD/MM/YYYY) |
| `pdf_url` | str | PDF download URL |
| `pdf_filename` | str | Local PDF file |
| `downloaded_at` | str | ISO timestamp of download |

### Objective Schema

- **Description:** VN30 objective corporate action records
- **Sources:** objective/*.csv

| Field | Type | Description |
|---|---|---|
| `document_id` | str | Unique document ID |
| `source` | str | Source identifier |
| `source_tier` | str | Data reliability tier (1-3) |
| `url` | str | Source URL |
| `publish_time` | str | Publication timestamp |
| `crawl_time` | str | Crawl timestamp (UTC) |
| `company_code` | str | VN30 ticker code |
| `company_name` | str | Company name |
| `title` | str | Event/document title |
| `raw_text` | str | Full raw text |
| `language` | str | Language code |
| `category` | str | News category |
| `event_type` | str | Classified event type |
| `attachment_urls` | str | URLs to attachments |
| `checksum` | str | Content checksum (dedup) |
| `raw_path` | str | Path to raw HTML/JSON |

### Cafef Schema

- **Description:** Cafef news (independent schema)
- **Sources:** cafef_articles.csv

| Field | Type | Description |
|---|---|---|
| `id` | str | MD5 hash of URL |
| `title` | str | Article title |
| `section` | str | Cafef section |
| `pub_date` | str | Publication date (ISO) |
| `article_url` | str | Article URL |
| `author` | str | Author name |
| `lead` | str | Sapo/abstract |
| `collected_at` | str | Crawl timestamp |
| `body` | str | Full body text |

### Macro Schema

- **Description:** Macroeconomic time-series data
- **Sources:** macro/raw/*.csv

| Field | Type | Description |
|---|---|---|
| `date / effective_date` | str/date | Date (ISO) |
| `dxy` | float | US Dollar Index |
| `refinancing_rate` | float | SBV refinancing rate (%) |
| `discount_rate` | float | SBV discount rate (%) |
| `omo_rate` | float | OMO rate (%) |
| `source` | str | Data source |
| `collected_at` | str | Crawl timestamp |

## 5. Data Quality Assessment

### Known Issues

- **Cafef News** — `author` missing 100.0%
- **Vietstock Analysis Reports** — `pdf_filename` missing 83.8%
- **Vietstock Analysis Reports** — `pdf_filename` missing 100.0%
- **Vietstock Analysis Reports** — `pdf_filename` missing 100.0%
- **TraderViet Forum Threads** — `category` missing 100.0%
- **TraderViet Forum Threads** — `pdf_url` missing 100.0%
- **TraderViet Forum Threads** — `pdf_filename` missing 100.0%
- **HSC Research Insights** — `pub_date` missing 100.0%
- **HSC Research Insights** — `pdf_url` missing 100.0%
- **HSC Research Insights** — `pdf_filename` missing 100.0%
- **News Articles (Merged)** — `pdf_url` missing 99.9%
- **News Articles (Merged)** — `author` missing 99.7%
- **News Articles (Merged)** — `lead` missing 99.5%
- **News Articles (Merged)** — `body` missing 99.5%
- **News Articles (Merged)** — `category` missing 98.5%
- **Thanh Niên News** — `category` missing 100.0%
- **Thanh Niên News** — `author` missing 100.0%
- **Thanh Niên News** — `lead` missing 100.0%
- **Thanh Niên News** — `pdf_url` missing 100.0%
- **Thanh Niên News** — `pdf_filename` missing 100.0%
- **Thanh Niên News** — `body` missing 100.0%
- **Tuổi Trẻ News** — `category` missing 100.0%
- **Tuổi Trẻ News** — `author` missing 100.0%
- **Tuổi Trẻ News** — `lead` missing 100.0%
- **Tuổi Trẻ News** — `pdf_url` missing 100.0%
- **Tuổi Trẻ News** — `pdf_filename` missing 100.0%
- **Tuổi Trẻ News** — `body` missing 100.0%
- **VietnamPlus News** — `category` missing 100.0%
- **VietnamPlus News** — `author` missing 100.0%
- **VietnamPlus News** — `lead` missing 100.0%
- **VietnamPlus News** — `pdf_url` missing 100.0%
- **VietnamPlus News** — `pdf_filename` missing 100.0%
- **VietnamPlus News** — `body` missing 100.0%
- **VNDIRECT Research Notes** — `pdf_url` missing 100.0%
- **VNDIRECT Research Notes** — `pdf_filename` missing 100.0%
- **VNDIRECT Research Notes** — `body` missing 52.7%
- **VnExpress News** — `author` missing 100.0%
- **VnExpress News** — `lead` missing 100.0%
- **VnExpress News** — `pdf_url` missing 100.0%
- **VnExpress News** — `pdf_filename` missing 100.0%
- **VnExpress News** — `body` missing 100.0%
- **objective_nld** — `company_code` missing 100.0%
- **objective_nld** — `company_name` missing 100.0%
- **objective_thanhnien** — `company_code` missing 100.0%
- **objective_thanhnien** — `company_name` missing 100.0%
- **objective_tuoitre** — `publish_time` missing 100.0%
- **objective_tuoitre** — `company_code` missing 100.0%
- **objective_tuoitre** — `company_name` missing 100.0%
- **objective_vietnamplus** — `company_code` missing 100.0%
- **objective_vietnamplus** — `company_name` missing 100.0%
- **objective_vnexpress** — `company_code` missing 100.0%
- **objective_vnexpress** — `company_name` missing 100.0%
- **VN30 Objective Records** — empty file (objective_v2026-07-12.csv)
- **VN30 Objective Records** — `publish_time` missing 30.8% (moderate)

### Completeness Summary

| Source | Completeness | Notes |
|---|---|---|
| Cafef News | 44.4% | Many missing columns |
| Vietstock Analysis Reports | 85.7% | 1/7 columns partial |
| Vietstock Analysis Reports | 85.7% | 1/7 columns partial |
| Vietstock Analysis Reports | 85.7% | 1/7 columns partial |
| data_catalog.csv | 90.9% | 1/11 columns partial |
| TraderViet Forum Threads | 75.0% | 3/12 columns partial |
| HSC Research Insights | 75.0% | 3/12 columns partial |
| News Articles (Merged) | 27.3% | Many missing columns |
| SSI Research Bulletins | 83.3% | 2/12 columns partial |
| Thanh Niên News | 41.7% | Many missing columns |
| Tuổi Trẻ News | 50.0% | Many missing columns |
| VietnamPlus News | 50.0% | Many missing columns |
| VNDIRECT Research Notes | 75.0% | 3/12 columns partial |
| VnExpress News | 58.3% | 5/12 columns partial |
| Vietstock Analysis Reports | 71.4% | 2/7 columns partial |
| Vietstock PDF Raw Text | 100.0% | Complete |
| Vietstock PDF Raw Text | 100.0% | Complete |
| news_unenriched_nld_records.csv | 87.5% | 2/16 columns partial |
| news_unenriched_thanhnien_records.csv | 87.5% | 2/16 columns partial |
| news_unenriched_tuoitre_records.csv | 81.2% | 3/16 columns partial |
| news_unenriched_vietnamplus_records.csv | 87.5% | 2/16 columns partial |
| news_unenriched_vnexpress_records.csv | 87.5% | 2/16 columns partial |
| VN30 Objective Records | 100% | Empty |
| VN30 Objective Records | 100.0% | Complete |
| VN30 Objective Records | 100.0% | Complete |
| VN30 Objective Records | 93.8% | 1/16 columns partial |
| vsdc_records.csv | 100.0% | Complete |
| DXY US Dollar Index | 75.0% | 1/4 columns partial |
| SBV Policy Rates | 100.0% | Complete |

## 6. Collection Methodology

The dataset is collected using a multi-strategy crawling architecture:

1. **Playwright browser (stealth):** Used for sites with JavaScript-rendered content or Cloudflare protection. Applies stealth patches (`playwright-stealth`), random User-Agent, human-like delays. Used by: Vietstock (analysis reports), VNDIRECT (research notes).
2. **HTTP requests:** Direct HTTP GET with retry logic, randomized User-Agent. Used by: Cafef (RSS + sitemap), SSI (research), HSC, news sitemap crawler.
3. **Sitemap shard crawl:** Parses XML sitemap shards (which already embed article title in `<image:title>` / `<news:title>`). No per-article fetch needed. Used by: Tuổi Trẻ, Thanh Niên, VietnamPlus.
4. **Wayback Machine backfill:** For sites that block bots at the sitemap level (VnExpress). Uses archive.org CDX API to list snapshots, fetches saved pages, extracts article links.
5. **API integration:** Direct API calls for structured data. Used by: Vietstock disclosure API (`/data/EventsTypeData`), VSDC corporate actions.

## 7. Known Limitations

| Issue | Impact | Status |
|---|---|---|
| HSC lacks pub_date | 39 records undateable | Site limitation |
| Cafef deep backfill throttle | Only ~4k dated records | IP throttling by Cafef |
| Tuoi Tre data ends 2016 | Missing 2016-2026 | Backfill not re-run |
| VnExpress dates approximate | ~14k records, date ≈ snapshot date | Wayback limitation |
| Vietstock gap 2006-2007 | Zero records | Real gap on site |
| Cafef schema mismatch | Different columns from other news | Independent design |
| PDF text extraction incomplete | ~2.5k of 14.8k PDFs extracted | CPU-bound, partial |
| VN30: 1/30 ticker missing | Chưa có dữ liệu disclosure cho 1 mã | Đang chờ adapter |
| Date format inconsistency | DD/MM/YYYY vs ISO mixed in datasets | Normalization needed |

## 8. Sample Records

### Vietstock Analysis Reports

```
             id                                                        title source        date                                          pdf_url                                                 pdf_filename        downloaded_at
0  30/06/2026_0  POW: Khuyến nghị KHẢ QUAN với giá mục tiêu 17,300 đồng/c...   VNDS  30/06/2026  https://finance.vietstock.vn/downloadedoc/20993  30-06-2026_POW_Khuyến_nghị_KHẢ_QUAN_với_giá_mục_tiêu_173...  2026-07-01 01:31:59
1  30/06/2026_1  Báo cáo Vĩ mô: Đông lực chính sách - Cho mục tiêu tăng t...    MAS  30/06/2026  https://finance.vietstock.vn/downloadedoc/20979  30-06-2026_Báo_cáo_Vĩ_mô_Đông_lực_chính_sách_-_Cho_mục_t...  2026-07-01 01:32:02
2  30/06/2026_2  Báo cáo ngành Xây dựng - Vật liệu: KQKD phân hóa do giá ...    MBS  30/06/2026  https://finance.vietstock.vn/downloadedoc/20978  30-06-2026_Báo_cáo_ngành_Xây_dựng_-_Vật_liệu_KQKD_phân_h...  2026-07-01 01:32:05
```

### Vietstock PDF Raw Text

```
             id source                                                        title                                                         body                                                         lead        date                                          pdf_url                                                 pdf_filename
0  30/06/2026_0   VNDS  POW: Khuyến nghị KHẢ QUAN với giá mục tiêu 17,300 đồng/c...  30/06/2026\nBáo cáo cập nhật\nwww.vndirect.com.vn\n1\nKy...  30/06/2026\nBáo cáo cập nhật\nwww.vndirect.com.vn\n1\nKy...  30/06/2026  https://finance.vietstock.vn/downloadedoc/20993  30-06-2026_POW_Khuyến_nghị_KHẢ_QUAN_với_giá_mục_tiêu_173...
1  26/06/2026_7    VPX  Báo cáo ngành Ngân hàng: Thông tư 25/2026/TT-NHNN nới lỏ...  26/06/2026\nSector report\n1\nBáo cáo ngành Ngân hàng\nT...  26/06/2026\nSector report\n1\nBáo cáo ngành Ngân hàng\nT...  26/06/2026  https://finance.vietstock.vn/downloadedoc/20940  26-06-2026_Báo_cáo_ngành_Ngân_hàng_Thông_tư_252026TT-NHN...
2  29/06/2026_7    MBS  Báo cáo ngành Dầu khí: Dự báo KQKD Q2/2026 khả quan nhờ...  MBS Research | BÁO CÁO NGÀNH\n29 Tháng 6, 2026\n1 | MBS ...  MBS Research | BÁO CÁO NGÀNH\n29 Tháng 6, 2026\n1 | MBS ...  29/06/2026  https://finance.vietstock.vn/downloadedoc/20973  29-06-2026_Báo_cáo_ngành_Dầu_khí_Dư_báo_KQKD_Q22026_khả_...
```

### Cafef News

```
                   id                                                        title                 section                  pub_date                                                  article_url  author                                                         lead              collected_at                                                         body
0  188260704171525847        Chủ tịch Đỗ Quý Hải đăng ký mua 10 triệu cổ phiếu HPX  thi-truong-chung-khoan  2026-07-04T18:07:00+0700  https://cafef.vn/chu-tich-do-quy-hai-dang-ky-mua-10-trie...     NaN  Ông Đỗ Quý Hải - Chủ tịch HĐQT Hải Phát Invest đăng ký m...  2026-07-04T22:34:38+0700  Ông Đỗ Quý Hải - Chủ tịch HĐQT CTCP Đầu tư Hải Phát (Hải...
1  188260704171408624  Chứng khoán tuần qua: Cổ phiếu PNJ có “biến”, hơn 1,2 tỷ...  thi-truong-chung-khoan  2026-07-04T17:15:00+0700  https://cafef.vn/chung-khoan-tuan-qua-co-phieu-pnj-co-bi...     NaN  Cổ phiếu PNJ có “biến”; Hơn 1,2 tỷ cổ phiếu có thể phải ...  2026-07-04T22:34:38+0700  Cổ phiếu PNJ có “biến” Tâm điểm chú ý của thị trường tro...
2  188260704171236574  Cổ phiếu rơi về “đáy” 3 năm, con trai Chủ tịch Nam Long ...  thi-truong-chung-khoan  2026-07-04T17:13:00+0700  https://cafef.vn/co-phieu-roi-ve-day-3-nam-con-trai-chu-...     NaN  Ông Nguyễn Nam, con trai ông Nguyễn Xuân Quang – Chủ tịc...  2026-07-04T22:34:38+0700  Theo thông tin vừa được công bố, ông Nguyễn Nam, người c...
```

### SSI Research Bulletins

```
             id source                                                   title            category    pub_date                                                          url author                                                         lead                                                      pdf_url      pdf_filename              collected_at                                                         body
0  70a511a4aa64    ssi   Bản Tin Thị Trường 29/06/2026: Đối diện áp lực cục bộ  Bản Tin Thị Trường  29/06/2026  https://www.ssi.com.vn/analysis-center/report/download/b...    SSI  VNIndex có phiên điều chỉnh trước áp lực cung gia tăng t...  https://www.ssi.com.vn/analysis-center/report/download/b...  70a511a4aa64.pdf  2026-07-05T09:29:51+0700  [image]\n• Về SSI\n• Quan hệ nhà đầu tư\n• Cơ hội nghề n...
1  24e7c6a17664    ssi  Bản Tin Thị Trường 15/06/2026: Rung lắc trong biên hẹp  Bản Tin Thị Trường  15/06/2026  https://www.ssi.com.vn/analysis-center/report/download/b...    SSI  VNIndex quay lại diễn biến tích cực với sự ủng hộ của độ...  https://www.ssi.com.vn/analysis-center/report/download/b...  24e7c6a17664.pdf  2026-07-05T09:29:51+0700  [image]\n• Về SSI\n• Quan hệ nhà đầu tư\n• Cơ hội nghề n...
2  44e41cb62bfc    ssi      Bản tin thị trường 23/06/2026: Giảm tốc cuối phiên  Bản Tin Thị Trường  23/06/2026  https://www.ssi.com.vn/analysis-center/report/download/b...    SSI  VNIndex duy trì vận động tích cực về mặt điểm số khi dòn...  https://www.ssi.com.vn/analysis-center/report/download/b...  44e41cb62bfc.pdf  2026-07-05T09:29:51+0700  [image]\n• Về SSI\n• Quan hệ nhà đầu tư\n• Cơ hội nghề n...
```

### HSC Research Insights

```
             id source                                                        title          category  pub_date                                                          url author                                                         lead  pdf_url  pdf_filename              collected_at                                                         body
0  6296e3d5f4fd    hsc                   2025 Biannual Strategy: Flexing the Bamboo  Research Insight       NaN  https://www.hsc.com.vn/en/research-insights-detail/biann...    HSC  Vietnam was particularly exposed to initial US tariffs. ...      NaN           NaN  2026-07-05T09:36:37+0700  Strategy Reports2025 Biannual Strategy: Flexing the Bamb...
1  9d4b3b05bf78    hsc  Real Estate Development: Weathering the storm - SBV cred...  Research Insight       NaN  https://www.hsc.com.vn/en/research-insights-detail/weath...    HSC  SBV recently issued guidance on FY26 credit quotas, sett...      NaN           NaN  2026-07-05T09:36:37+0700  Sector InsightsReal Estate Development: Weathering the s...
2  e96211c53423    hsc  Information Technology: Signs of a structural shift to a...  Research Insight       NaN  https://www.hsc.com.vn/en/research-insights-detail/infor...    HSC  Global sentiment has turned cautious on Tech/IT services...      NaN           NaN  2026-07-05T09:36:38+0700  Sector InsightsInformation Technology: Signs of a struct...
```

## 9. Citation

If using this dataset in academic work, please cite as:

> ```bibtex
> @misc{crawl_data_2026,
>   author = {Quy, Nguyen T.},
>   title = {crawl\_data: Multi-Source Vietnamese Stock Market Dataset},
>   year = {2026},
>   howpublished = {\url{https://github.com/ntquy9901/crawl\_data}},
>   note = {Accessed: 2026-07-21}
> }
> ```

---

*Report generated by `data_catalog.py`*