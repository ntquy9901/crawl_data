---
stepsCompleted: ["step-01", "step-02", "step-03"]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-crawl_data-2026-07-11/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-crawl_data-2026-07-11/ARCHITECTURE-SPINE.md
  - docs/guide/Vietnam_Stock_Objective_Data_Crawling_Guide.md
---

# Objective Vietnam Stock Data Crawler - Epic Breakdown

## Overview

Epic/story breakdown cho **Objective Vietnam Stock Data Crawler** — decompose PRD (15 FRs active) + Architecture spine (14 ADs) thành stories implementable. Scope v1 = **VN30 universe**, crawl+metadata layer (NLP/model downstream). Brownfield — reuse `base_news_crawler.py`, `body_extractor`, `anti_bot`, Vietstock/Cafef infra.

## Requirements Inventory

### Functional Requirements

**v1 MVP (VN30):**
- **FR-4**: Ingest VSDC corporate-action notices (`vsd.vn/vi/ad/{id}`, ASP.NET HTTP) — title, publish_time, company_code, event_type, attachments, raw HTML. (AD-2,6,7)
- **FR-5**: Backfill VSDC by sequential ID sweep (50000→current, multi-year, resumable).
- **FR-8**: Canonical ObjectiveRecord schema — `document_id, source, source_tier, url, publish_time, crawl_time, company_code, company_name, title, raw_text, language, category, event_type, attachment_urls, checksum, raw_path` (single source `objective/schema.py`, AD-1).
- **FR-9**: Preserve raw HTML/PDF bytes in raw layer (`data/raw/<source>/`), derivable to cleaned (AD-2).
- **FR-10**: Dedup by `(source, canonical_url)` AND content-checksum (AD-6, AD-13).
- **FR-11**: Resumable (url-seen dedup, skip on re-run — AD-6, ratified `_load_seen`).
- **FR-12**: Dataset versioning — `objective_v<YYYYMMDD>.csv` snapshots (AD-8).
- **FR-13**: Objective/opinion separation — `data/objective/` never merges opinion CSVs (AD-9).
- **FR-14**: Daily schedule — extend `run_daily_all.ps1` before 06:00 (AD-10).
- **FR-15**: Tier-2 news raw capture — 10 outlets (VnExpress, VnEconomy, VietnamPlus, Báo Đầu tư, Báo Chính phủ, TTXVN, Tuổi Trẻ, Thanh Niên, Người Lao Động, Kinh tế Sài Gòn), RSS, VN30-filtered; company_code nullable → companion file (AD-14).
- **FR-16**: VN30 disclosures via Vietstock per-company (browser/Playwright, reuse `VietstockCrawler`+`anti_bot`, objective sections only).
- **FR-17**: VN30 disclosures via Cafef (HTTP, reuse cafef pattern) — cross-check/dedup with Vietstock.

**Deferred/dropped (NOT v1):**
- FR-1,2,3 (HNX/UPCoM) — out of VN30 scope (wrong exchange). Demoted.
- FR-6 (HOSE-direct) — dropped; use Tier-3 (FR-16/17).
- FR-7 (SSC) — deferred (Playwright/ADF).

### NonFunctional Requirements

- **NFR-1 (Politeness)**: configurable fetch delay (`RANDOM_DELAY` pattern), respect server rate; 0 ban/403 from impolite crawling (counter-metric SM-C2).
- **NFR-2 (Reliability/Resumable)**: resume on failure (url-dedup), audit log per source, fail→log+continue (no crash).
- **NFR-3 (Observability)**: per-source audit log `logs/<source>_audit.log` (kept/dup/fail/oor counters).
- **NFR-4 (Legal)**: public-by-law data (TL 96/2020); Decree 13/2023 PDPD — redact personal data if captured (SSC/insider, deferred); no HOSE OAuth reverse-engineering.

### Additional Requirements

**Architecture invariants (ADs) governing implementation:**
- **AD-1**: ObjectiveRecord in `objective/schema.py` (single source of truth).
- **AD-2**: Layered storage raw (`data/raw/<source>/<doc_id>.{html,pdf}`) / cleaned (`data/objective/<source>_records.csv`).
- **AD-3**: Timestamps canonical UTC `YYYY-MM-DDTHH:MM:SSZ`; no-offset⇒+07; date-only⇒`T00:00:00Z`; build-time regex reject. (DIVERGENCE: base uses HN_TZ +07.)
- **AD-4**: `company_code` uppercase HOSE ticker `^[A-Z0-9]{3,5}$`, VN30-validated.
- **AD-5**: VN30 universe `config/vn30.yaml` (ticker + canonical company_name), single source.
- **AD-6**: `checksum = sha256(checksum_normalize(raw_text))`; `checksum_normalize` in schema.py (NFC→lowercase→strip tags→collapse ws→no truncate) + conformance fixture.
- **AD-7**: `BaseObjectiveCrawler(BaseNewsCrawler)` — override `_init_csv/_append/_load_seen/_fetch_and_parse` for ObjectiveRecord (UTC, checksum); keep hooks `listing_url/parse_listing/parse_article/next_page`.
- **AD-8**: Per-source isolation + `build_objective.py` merge → `objective_v<date>.csv`.
- **AD-9**: Objective/opinion separation at dataset boundary.
- **AD-10**: Scheduler extension `run_daily_all.ps1` (Task Scheduler `CrawlDailyNews` @ 05:00).
- **AD-11**: `event_type` enum (financial_statement, board_resolution, dividend, stock_issuance, stock_split, rights_issue, esop, insider_trading, shareholder_change, ma, exec_change, agm, bond_issuance, foreign_ownership, extraordinary_announcement, other).
- **AD-12**: `company_name` = VN30-canonical (from vn30.yaml) when code non-null; ticker never in name; null code⇒null name.
- **AD-13**: `canonicalize_url` (shared); `document_id` per-source identity only; checksum = sole cross-source identity.
- **AD-14**: Tier-2 unenriched → `news_unenriched_<source>_records.csv`; enrichment = separate build, no row mutation.

**Stack (seed, ratified existing):** Python 3.13 (uv), requests, playwright+chromium+playwright-stealth, lxml, PyMuPDF, pandas, Windows Task Scheduler.

**Brownfield reuse:** `base_news_crawler.py` (Template Method, ratified), `utils/body_extractor.py` (SOURCE_XPATH), `utils/anti_bot.py` (stealth/safe_goto), existing `crawler.py` (VietstockCrawler) + `cafef_crawler.py` infra.

### UX Design Requirements

_(N/A — data crawler, no UI. PRD §2.2 non-users: end-user UI out of scope.)_

### FR Coverage Map

```
FR-4,5      → Epic 1 (VSDC ingest + backfill)
FR-8,9,11   → Epic 1 (schema + raw layer + resumable — foundation via VSDC slice)
FR-16,17    → Epic 2 (Vietstock + Cafef VN30 disclosure)
FR-15       → Epic 3 (Tier-2 news corpus, 10 outlets)
FR-10,12,13,14 → Epic 4 (cross-source dedup + versioning + separation + daily schedule)
FR-1,2,3    → DEFERRED (HNX/UPCoM — wrong exchange, not VN30)
FR-6        → DEFERRED/DROPPED (HOSE-direct — use Tier-3)
FR-7        → DEFERRED (SSC — Playwright/ADF)
```

## Epic List

### Epic 1: VN30 Foundation + VSDC Corporate Actions
Vertical slice: xây foundation (ObjectiveRecord schema, BaseObjectiveCrawler, vn30.yaml, raw layer, UTC, checksum, resumable) CÙNG adapter VSDC đầu tiên — tránh epic "foundation" rỗng. Sau epic này: dữ liệu corporate actions VN30 (biến động cổ đông, cổ tức, hành động doanh nghiệp) từ VSDC ở dạng ObjectiveRecord, resumable, backfill đa năm.
**FRs covered:** FR-4, FR-5, FR-8, FR-9, FR-11
**ADs:** AD-1, AD-2, AD-3, AD-4, AD-5, AD-6, AD-7, AD-11, AD-12, AD-13

### Epic 2: VN30 Company Disclosures (Vietstock + Cafef)
Lấy disclosure VN30 (BC tài chính, nghị quyết HĐQT, cổ tức, phát hành, ESOP, insider...) qua Tier-3 per-company (Vietstock browser + Cafef HTTP), objective sections only. Gộp 2 nguồn (cùng concept disclosure, cross-dedup checksum). Build trên foundation E1.
**FRs covered:** FR-16, FR-17
**ADs:** AD-1..AD-7, AD-12, AD-13

### Epic 3: Tier-2 Objective News Corpus
Capture tin tức khách quan thô từ 10 báo (VnExpress, VnEconomy, VietnamPlus, Báo Đầu tư, Báo Chính phủ, TTXVN, Tuổi Trẻ, Thanh Niên, Người Lao Động, Kinh tế Sài Gòn) qua RSS, VN30-filtered. company_code nullable (chưa NLP) → companion file `news_unenriched_<source>_records.csv` (AD-14).
**FRs covered:** FR-15
**ADs:** AD-1, AD-2, AD-3, AD-7, AD-14

### Epic 4: Unified Dataset Build + Daily Schedule
Merge per-source cleaned → `objective_v<YYYYMMDD>.csv` versioned: checksum cross-source dedup (AD-6,13), UTC validate (AD-3), objective/opinion separation (AD-9), document_id per-source + checksum cross-source identity (AD-13). Extend `run_daily_all.ps1` (Task Scheduler @ 05:00). Consume E1-3 outputs.
**FRs covered:** FR-10, FR-12, FR-13, FR-14
**ADs:** AD-3, AD-6, AD-8, AD-9, AD-10, AD-13, AD-14

---

## Epic 1: VN30 Foundation + VSDC Corporate Actions
Vertical slice — foundation (schema/base/config/raw/UTC/checksum/resumable) xây CÙNG adapter VSDC đầu tiên.

### Story 1.1: ObjectiveRecord schema + canonical helpers
As a data engineer, I want a single canonical `ObjectiveRecord` schema + `event_type` enum + `checksum_normalize` + `canonicalize_url` in `objective/schema.py`, so that every adapter emits one consistent shape.
**Acceptance Criteria:**
**Given** `objective/schema.py` exists
**When** imported
**Then** exposes `ObjectiveRecord` dataclass with exactly 16 fields (AD-1); `EventType` enum with all 16 values (AD-11); `checksum_normalize` (NFC→lowercase→strip tags→collapse ws→NO truncate); `canonicalize_url` (query-param order + strip tracking).
**And** a conformance test: same disclosure text normalized 2 ways → identical checksum; `event_type` rejects non-enum.

### Story 1.2: VN30 universe config + loader
As a data engineer, I want `config/vn30.yaml` (ticker + canonical company_name) + loader, so all adapters filter to one consistent VN30 list.
**Acceptance Criteria:**
**Given** `config/vn30.yaml` lists 30 HOSE tickers + canonical names
**When** `load_vn30()` called
**Then** returns `{ticker: canonical_company_name}`; tickers uppercase match `^[A-Z0-9]{3,5}$` (AD-4,5); loader caches; missing/malformed file → clear error, never silent.

### Story 1.3: BaseObjectiveCrawler framework
As a data engineer, I want `BaseObjectiveCrawler(BaseNewsCrawler)` overriding CSV/dedup/fetch for ObjectiveRecord, so HTTP adapters subclass it without re-implementing wiring.
**Acceptance Criteria:**
**Given** `objective/base_objective_crawler.py` subclasses `BaseNewsCrawler`
**When** an adapter subclass runs
**Then** `_init_csv/_append/_load_seen` use ObjectiveRecord headers (NOT `CSV_HEADERS`); `_fetch_and_parse` emits ObjectiveRecord with `crawl_time`/`publish_time` UTC `...Z` (AD-3), `checksum` computed (AD-6), `document_id=sha1(source+canonicalize_url(url))[:16]` (AD-13), raw bytes saved to `data/raw/<source>/` (AD-2); resume by url (FR-11); CSV utf-8-sig.

### Story 1.4: VSDC adapter + VN30 filter + smoke
As a model owner, I want VSDC corporate-action data for VN30 (shareholder changes, dividends...) ingested + backfilled, so I have objective corporate-action features.
**Acceptance Criteria:**
**Given** `objective/adapters/vsdc_crawler.py` subclasses `BaseObjectiveCrawler`
**When** run `--range` (ID sweep 50000→current) or `--latest`
**Then** GET `vsd.vn/vi/ad/{id}` (HEAD 405 → use GET); parse title/publish_time/company_code/event_type/attachment_urls → ObjectiveRecord; records with `company_code ∉ VN30` dropped (AD-4,5); `company_name` from vn30.yaml (AD-12); raw HTML saved; resumable (FR-11); backfill multi-year (FR-5).
**And** smoke test on a saved VSDC fixture (no live site) passes; `--test` caps 5 records.

---

## Epic 2: VN30 Company Disclosures (Vietstock + Cafef)

### Story 2.1: Vietstock per-company disclosure adapter
As a model owner, I want VN30 company disclosures (BC tài chính, nghị quyết HĐQT, cổ tức...) from Vietstock, so I have structured primary disclosures.
**Acceptance Criteria:**
**Given** `objective/adapters/vietstock_disclosure.py` reuses `VietstockCrawler` + `utils/anti_bot`
**When** iterates 30 VN30 tickers' disclosure sections
**Then** fetches listing + detail via browser (stealth, stable UA — no fake-useragent); parses to ObjectiveRecord; **objective sections only** (công bố thông tin/BC tài chính — drops analysis/opinion/buy-sell); PDF attachments captured (AD-2 raw); resumable.

### Story 2.2: Cafef per-company disclosure adapter + cross-dedup
As a model owner, I want Cafef VN30 disclosures cross-checked with Vietstock, so duplicates are removed.
**Acceptance Criteria:**
**Given** `objective/adapters/cafef_disclosure.py` (HTTP, reuse cafef pattern)
**When** run
**Then** fetches Cafef per-company disclosure; parses ObjectiveRecord; same doc as Vietstock → same `checksum` (AD-6 conformance) → flagged for cross-source dedup at build (AD-13).

---

## Epic 3: Tier-2 Objective News Corpus

### Story 3.1: Tier-2 RSS framework + VnExpress + companion file
As a model owner, I want a Tier-2 RSS adapter framework (VnExpress first) writing unenriched news to a companion file, so I have a raw news corpus without polluting the VN30 dataset.
**Acceptance Criteria:**
**Given** `objective/adapters/tier2_rss/` base + `vnexpress.py`
**When** run
**Then** parses RSS `/rss/kinh-doanh.rss` (+chung-khoan); filters objective news (drops opinion/commentary); emits ObjectiveRecord with `company_code` nullable; null-`company_code` rows → `data/objective/news_unenriched_vnexpress_records.csv` (AD-14, NOT unified); smoke on saved RSS fixture passes.

### Story 3.2: Remaining 9 Tier-2 outlets
As a model owner, I want the other 9 outlets crawled, so the news corpus is comprehensive.
**Acceptance Criteria:**
**Given** 9 RSS subclasses (VnEconomy, VietnamPlus, Báo Đầu tư, Báo Chính phủ, TTXVN, Tuổi Trẻ, Thanh Niên, Người Lao Động, Kinh tế Sài Gòn)
**When** each run
**Then** each parses its RSS to ObjectiveRecord (same schema); unenriched → companion file; verify per-outlet RSS path at build (addendum).

---

## Epic 4: Unified Dataset Build + Daily Schedule

### Story 4.1: build_objective.py — merge + cross-source dedup + version
As a model owner, I want a versioned unified VN30 objective dataset, so the model trains on one clean, deduped, objective-only set.
**Acceptance Criteria:**
**Given** `objective/build_objective.py`
**When** run
**Then** merges per-source `*_records.csv` (NOT `news_unenriched_*` — AD-14, NOT opinion CSVs — AD-9); cross-source dedup by `checksum` (AD-6,13); UTC regex-validate, reject non-canonical (AD-3); writes `data/objective/objective_v<YYYYMMDD>.csv` (FR-12); only records with `company_code ∈ VN30`.

### Story 4.2: Daily schedule extension
As a data engineer, I want the objective crawlers + build scheduled daily before 06:00, so the dataset is fresh each morning.
**Acceptance Criteria:**
**Given** `run_daily_all.ps1` extended
**When** Task Scheduler `CrawlDailyNews` @ 05:00 fires
**Then** invokes VSDC/Vietstock/Cafef/Tier-2 objective crawlers (`--latest`) + `build_objective.py`; completes before 06:00; resumable (no re-crawl of seen); existing opinion/news daily flow unaffected.
