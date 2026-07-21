# Epic/Story Plan — Complete Data Coverage 2000-2026

> **Generated:** 2026-07-22
> **Scope:** All data sources → 2000-2026 coverage with quality gates per CLAUDE.md

## Macro View — Current vs Target

| Source | Current Coverage | Target Coverage | Status |
|--------|----------------|-----------------|--------|
| Vietstock (analysis reports) | 2001-2026 (14,836) | ✅ Complete (2006-2007 = real site gap) | DONE |
| Vietstock PDF body extraction | 2,500/14,836 | 14,836 full text | 🔴 Epic 6 |
| Vietstock stray-date fix | ~0.5% affected | 0% affected | 🔴 Epic 6 |
| SSI research | 2019-2026 (1,867) | ✅ Complete | DONE |
| HSC research | 6 records, no dates | ⚠️ Site limitation — may be impossible | DEFERRED |
| VNDIRECT research | 2016-2026 (2,043) | Fill 2017 gap + catch up 2024-2026 | 🟡 Epic 5 |
| Cafef news | 2016 + 2026 only (4,067) | 2010-2026 via proxy/Wayback | 🔴 Epic 5 |
| Tuoi Tre | 2011-2016 (283,568) | 2011-2026 (backfill 2016-2026) | 🔴 Epic 5 |
| Thanh Nien | 2011-2025 (387,169) | Investigate post-2014 collapse + backfill 2026 | 🟡 Epic 5 |
| VietnamPlus | 2010-2026 (773,152) | Check 2000-2009 availability | 🟡 Epic 5 |
| VnExpress | 2012-2026 (13,938) | More targets, better cadence | 🟡 Epic 5 |
| TraderViet forum | 2018-2026 (1,104; 99% recent) | Backfill to platform floor (2010) | 🟡 Epic 5 |
| VN30 Objective layer | 0 records | VN30 corporate actions 2010-2026 | 🟡 Epic 9 |
| Macro — DXY | 2006-2026 | 2000-2026 | 🟡 Epic 7 |
| Macro — SBV rates | 2011-2023 | 2000-2026 | 🟡 Epic 7 |
| Macro — CPI/PMI/Credit | 0 | 2000-2026 monthly | 🔴 Epic 7 |
| Macro — VNINDEX | 0 | 2000-2026 daily | 🔴 Epic 7 |

---

## Epic 5: Core Dataset Gap-Filling (2000-2026)

Close all date-coverage gaps in existing crawlers. Each source gets a backfill or re-crawl pass.

### Story 5.1: VNDIRECT — fill 2017 gap + latest records

**Acceptance Criteria:**
- Run VNDIRECT backfill with 2017 window for all 4 categories + both languages
- Verify VNDIRECT year-distribution has 0-year gaps for 2016-2026
- Catch up 2024-2026 records (currently 37/7/36 → target ~250/year like other years)
- Smoke test: `python vndirect_crawler.py --test --category company-note` returns ≥1 record

**Tasks:**
1.1 Re-crawl VNDIRECT `--range --from-date 2017-01-01 --end-date 2017-12-31` for all categories
1.2 Re-crawl VNDIRECT `--range --max-pages 120` for 2024, 2025, 2026
1.3 Validate year-distribution: no 0-year gaps 2016-2026
1.4 Write/update smoke test with VNDIRECT fixture

**Quality gates:**
- `uv run pytest -m smoke` passes
- `uvx ruff check vndirect_crawler.py` clean
- `/code-review` run and findings addressed

---

### Story 5.2: Mass media backfill (Tuoi Tre, Thanh Nien, VietnamPlus)

**Acceptance Criteria:**
- Tuoi Tre: backfill 2016-10 → present via sitemap crawl
- Thanh Nien: backfill 2026 (missing Jan-Dec 2026); investigate post-2014 sitemap collapse
- VietnamPlus: verify if sitemap offers pre-2010 data (backfill 2000-2009 if available)
- All three have year-continuous coverage from floor to 2026-07
- Smoke test per source: `--test` flag returns ≥1 record from each

**Tasks:**
2.1 Tuoi Tre: `python news_sitemap_crawler.py --source tuoitre --backfill --from-date 2016-10-01`
2.2 Thanh Nien: `python news_sitemap_crawler.py --source thanhnien --backfill --from-date 2026-01-01`; also investigate sitemap index for post-2014 shard structure
2.3 VietnamPlus: `python news_sitemap_crawler.py --source vietnamplus --test` to verify; then check if sitemap index contains pre-2010 shards
2.4 Write smoke tests for each source

**Quality gates:**
- Year-by-year analysis shows no gaps from floor to 2026
- `analyze_dates.py` output saved as baseline
- `/code-review` run

---

### Story 5.3: VnExpress Wayback expansion

**Acceptance Criteria:**
- Add 3 more VnExpress section targets: `thoi-su`, `the-gioi`, `dau-tu` (in addition to homepage + kinh-doanh)
- Wayback cadence documented per target (monthly vs daily)
- Coverage increased from 13,938 to ≥40,000 records
- Smoke test with `--test` flag

**Tasks:**
3.1 Research VnExpress section coverage on Wayback Machine (CDX API trial runs)
3.2 Add new targets to `vnexpress_wayback_backfill.py` TARGETS dict
3.3 Run backfill for new targets with `--workers 4`
3.4 Validate: run `analyze_dates.py` and check year-distribution improvement

**Quality gates:**
- At least 40k total VnExpress records
- `analyze_dates.py` year table shows improvement
- Smoke test passes

---

### Story 5.4: Cafef deep backfill — alternative strategies

**Acceptance Criteria:**
- Investigate and attempt ONE viable alternative for Cafef deep backfill (2010-2016, 2017-2025):
  1. **Proxy rotation**: test with 10 Webshare proxies → if 403 rate <20%, run full backfill
  2. **Wayback Machine fallback**: if proxy fails, build `cafef_wayback_backfill.py` parallel to `vnexpress_wayback_backfill.py`
  3. **Acceptance**: document the attempt + result in docs; if infeasible, mark as DEFERRED
- If proxy approach works: ≥20,000 additional Cafef records
- If Wayback approach: ≥50,000 records with approximate dates (documented as snapshot-date)

**Tasks:**
4.1 Test Cafef proxy rotation with `CAFEF_USE_PROXY=true` 50-request trial
4.2 If proxy <20% fail: run full `--backfill --from-date 2010-01-01 --workers 6`
4.3 If proxy fails: spike `cafef_wayback_backfill.py` (1 day), test with 2016 window
4.4 Document result in `docs/anti-throttle.md` + add to CLAUDE.md

**Quality gates:**
- Result documented regardless of success/failure
- No 403 cascade to other crawlers (proxy scoped to Cafef only)

---

### Story 5.5: Forum backfill to platform floor

**Acceptance Criteria:**
- TraderViet: backfill all available pages for stock-analysis (71) and trading-knowledge (77) sections
- Document actual floor (earliest thread date) per section
- Year-distribution: continuous coverage from floor to present
- Investigate + add VOZ backfill (currently only 15 pages)

**Tasks:**
5.1 Run `forum_crawler.py --source traderviet --range --max-pages 0` (unlimited pages)
5.2 Run `forum_crawler.py --source voz --range --max-pages 100` to get more VOZ data
5.3 Validate year-distribution via `analyze_dates.py`
5.4 Write smoke test with forum fixture

**Quality gates:**
- Year-distribution has no gaps from floor to present
- `uv run pytest -m smoke` passes

---

## Epic 6: Vietstock PDF Body Extraction

Extract full-text body for all 14,836 Vietstock analysis reports.

### Story 6.1: Mass PDF download for all years

**Acceptance Criteria:**
- Download PDFs for ALL 14,836 reports (not just recent years)
- Currently only ~2,500 of 14,836 have PDFs downloaded (2026 only)
- Use `scripts/backfill_vnstock_pdf.py` with enhanced fallback
- Target: ≥12,000 PDFs successfully downloaded
- Failed PDF URLs logged for manual recovery

**Tasks:**
6.1.1 Set `DOWNLOAD_PDF=true` in `.env`
6.1.2 Run `scripts/backfill_vnstock_pdf.py --workers 8` (Phase A: requests)
6.1.3 Run `scripts/backfill_vnstock_pdf.py --workers 4 --no-playwright` (Phase A only for speed)
6.1.4 Collect failures and run `--no-playwright false` for Phase B fallback

**Quality gates:**
- ≥12,000 PDF files in `data/pdf/`
- `scripts/backfill_vnstock_pdf.py` fail log has ≤2,000 entries

---

### Story 6.2: PDF text extraction → body population

**Acceptance Criteria:**
- Extract body text from all downloaded PDFs via PyMuPDF
- Body text written to `vnstock_pdf_raw.csv` with columns: `pdf_url, title, date, body, extracted_at`
- If body already exists (prior extract), skip (resumable)
- Target: ≥11,000 rows with non-empty body text
- Smoke test with a fixture PDF

**Tasks:**
6.2.1 Run extraction script for all PDFs (parallel, ProcessPoolExecutor for CPU-bound)
6.2.2 Validate body quality: min 100 chars per extracted body
6.2.3 Write/update smoke test

**Quality gates:**
- ≥11,000 rows with body length ≥100 chars
- Smoke test passes

---

### Story 6.3: Stray-date fix for Vietstock records

**Acceptance Criteria:**
- Identify all records in `vnstock_articles.csv` where `date` is "today" (stray-date bug)
- Currently ~0.5% affected (pitfall #5 in CLAUDE.md)
- Strategy: re-crawl those records by `pdf_url` directly to get real date
- Fix: update `date` column in CSV
- Regression: after fix, re-run `analyze_dates.py` and verify no date anomalies

**Tasks:**
6.3.1 Identify stray-date records: `date == today` but `pdf_url` contains date-encoded path
6.3.2 Build recovery script that fetches each affected PDF URL and extracts real date
6.3.3 Patch vnstock_articles.csv with corrected dates
6.3.4 Verify: `analyze_dates.py` shows 0 rows with future dates

**Quality gates:**
- `analyze_dates.py` shows 0 rows dated "today" for historical years
- Date range per year is realistic (not spanning to crawl date)

---

## Epic 7: Macro Data Expansion

Add critical macro-economic time series for model features.

### Story 7.1: VNINDEX daily historical (2000-2026)

**Acceptance Criteria:**
- VN-Index daily OHLCV from 2000-07-28 (inception) to present
- Source: Vietstock / Cafef / investing.com historical data
- Saved to `data/macro/vnindex.csv` with columns: `date, open, high, low, close, volume`
- Verify: date range continuous (no trading-day gaps > 5 business days)

**Tasks:**
7.1.1 Research best source for VNINDEX daily history
7.1.2 Write `scripts/fetch_vnindex.py` using requests (HTTP, no Playwright)
7.1.3 Run backfill from 2000 to present
7.1.4 Validate continuity: count missing trading days

**Quality gates:**
- ≤100 missing trading days (expected holidays)
- Date range: 2000-07-28 to present

---

### Story 7.2: Vietnamese CPI monthly (2000-2026)

**Acceptance Criteria:**
- CPI month-over-month and year-over-year from GSO (General Statistics Office)
- Source: GSO website (https://www.gso.gov.vn) or investing.com
- Saved to `data/macro/cpi_vietnam.csv` with columns: `month, cpi_mom, cpi_yoy`
- Coverage: 2000-01 to present (monthly)

**Tasks:**
7.2.1 Research data source and access method
7.2.2 Write `scripts/fetch_cpi.py`
7.2.3 Validate against known CPI values (cross-check published data)

**Quality gates:**
- Monthly granularity, no gaps >3 months
- Cross-validate 2020-2023 against published government figures

---

### Story 7.3: PMI Vietnam + SBV credit/rates expansion (2010-2026)

**Acceptance Criteria:**
- PMI Manufacturing Vietnam (S&P Global) monthly: 2012-04 to present
- SBV policy rates: extend from current 11 events to full daily timeseries
- Credit growth monthly: 2010 to present
- Saved to `data/macro/pmi_vietnam.csv`, `data/macro/sbv_daily_rates.csv`, `data/macro/credit_growth.csv`

**Tasks:**
7.3.1 Research PMI data access (investing.com or S&P Global API)
7.3.2 Research SBV daily interbank rates source
7.3.3 Research credit growth data source
7.3.4 Write respective fetch scripts

**Quality gates:**
- Each series has ≥80% of expected data points
- Sources documented in file headers

---

### Story 7.4: DXY extension + USD/VND (2000-2026)

**Acceptance Criteria:**
- DXY: extend back from 2006 to 2000-01-01
- USD/VND daily exchange rate: 2000 to present
- Saved to `data/macro/dxy.csv` (updated) and `data/macro/usdvnd.csv`

**Tasks:**
7.4.1 Research DXY pre-2006 source (FRED API: `DTWEXBGS` goes to 2006; find alternative)
7.4.2 Research USD/VND source (SBV or Vietcombank historical)
7.4.3 Write fetch scripts or extend existing macro_crawler.py

**Quality gates:**
- Date range 2000-01-01 to present for both series
- ≤1% missing data points

---

## Epic 8: Data Quality Framework

Implement CLAUDE.md quality gates as automated checks.

### Story 8.1: Automated smoke test suite

**Acceptance Criteria:**
- Each source has a smoke test (`@pytest.mark.smoke`) that runs on saved fixtures
- Smoke test verifies: at least 1 record returned, required columns present, date parses
- `uv run pytest -m smoke` completes in <30s
- Smoke tests cover: Vietstock, SSI, HSC, VNDIRECT, Cafef, Tuoi Tre, Thanh Nien, VietnamPlus, VnExpress, Forum, Macro, VN30 Objective

**Tasks:**
8.1.1 Create `tests/fixtures/` directory with saved response samples per source
8.1.2 Write smoke test per source in `tests/test_smoke_*.py`
8.1.3 Register `smoke` marker in `pyproject.toml`
8.1.4 Verify: `uv run pytest -m smoke` passes

**Quality gates:**
- All sources pass smoke test
- `uv run pytest -m smoke` <30s

---

### Story 8.2: Dataset profiler pipeline (continuous monitoring)

**Acceptance Criteria:**
- `utils/dataset_profiler.py` integrated into `run_daily_all.ps1`
- Daily snapshot saved to `data/dataset_profiles/<source>/<date>.json`
- Weekly diff report generated: row count delta, date range changes, quality metrics
- Alert if any source loses >10% rows week-over-week (crawl regression)

**Tasks:**
8.2.1 Add `python utils/dataset_profiler.py snapshot` to run_daily_all.ps1
8.2.2 Write `scripts/weekly_profile_report.py` that generates diff summary
8.2.3 Schedule weekly report via Task Scheduler (Sunday 06:30)
8.2.4 Alert integration: log warning if row count drops >10%

**Quality gates:**
- Daily snapshot runs without error
- Weekly report generated to `docs/reports/profile_weekly_*.md`

---

### Story 8.3: Date normalization pipeline

**Acceptance Criteria:**
- All source CSVs have a consistent ISO-8601 date column (not mixed DD/MM/YYYY)
- Cross-source date consistency validated
- `scripts/normalize_dates.py` that reads source CSV → produces date-normalized copy
- Date parsing error rate <1% per source

**Tasks:**
8.3.1 Write `scripts/normalize_dates.py` with per-source date column mapping
8.3.2 Run normalization for all sources
8.3.3 Validate: merged dataset has uniform date format
8.3.4 Add date-format validation to smoke tests

**Quality gates:**
- All date columns ISO-8601 (`YYYY-MM-DD`)
- `analyze_dates.py` shows ≤1% parse errors for all sources

---

### Story 8.4: Diff-coverage quality gate integration

**Acceptance Criteria:**
- CLAUDE.md diff-coverage gate automated: `uv run pytest --cov=<module> --cov-report=xml && uvx diff-cover coverage.xml --fail-under=80`
- Every story implementation must pass diff-coverage before merge
- `--cov-report=xml` produces coverage.xml compatible with diff-cover
- Instructions added to CLAUDE.md (ai) and run_daily_all.ps1 (human)

**Tasks:**
8.4.1 Verify diff-cover is in dev dependencies (`uv.lock`)
8.4.2 Update pyproject.toml [tool.pytest.ini_options] with correct --cov args
8.4.3 Test: make a small change, verify diff-coverage gate works

**Quality gates:**
- diff-cover command works with --fail-under=80
- Documented in CLAUDE.md Per-project setup

---

## Epic 9: VN30 Objective Layer Completion

Complete the VN30 objective data layer (Epic 1-4 from original plan).

### Story 9.1: Vietstock disclosure adapter — full VN30 backfill

**Acceptance Criteria:**
- `objective/adapters/vietstock_disclosure.py` backfills ALL pages (not just latest) for all 30 VN30 tickers
- Currently only `crawl_latest` implemented and untested (0 records in dataset)
- Target: ≥5,000 disclosure records across VN30
- `--range --max-pages 0` (unlimited) per ticker
- Smoke test with fixture

**Tasks:**
9.1.1 Run `python -m objective.adapters.vietstock_disclosure --range --max-pages 0`
9.1.2 Measure: records per ticker, total
9.1.3 Write smoke test with saved response fixture

**Quality gates:**
- ≥5,000 disclosure records
- Smoke test passes

---

### Story 9.2: VSDC adapter — full ID sweep + verify

**Acceptance Criteria:**
- VSDC corporate actions: run full ID sweep from ID=1 → current (not just 50000→current)
- Currently targets 50000→current; lower IDs may contain pre-2010 data
- If IDs <50000 exist and parse: ≥additional 2,000 records
- If IDs <50000 don't exist (VSDC ID scheme starts at 50000): document finding

**Tasks:**
9.2.1 Test ID=1→1000 sample to verify VSDC ID lower bound
9.2.2 If valid: run `python -m objective.adapters.vsdc_crawler --range --from-id 1 --end-id 50000`
9.2.3 Document VSDC ID scheme in CLAUDE.md

**Quality gates:**
- VSDC ID lower bound documented
- If valid: additional records ingested

---

### Story 9.3: Tier-2 remaining 6 outlets + daily schedule

**Acceptance Criteria:**
- Remaining 6 Tier-2 outlets implemented (3 already done: tuoitre, nld, thanhnien)
- Outlets: VnEconomy, Báo Đầu tư, Báo Chính phủ, TTXVN, Người Lao Động, Kinh tế Sài Gòn
- Each has per-outlet RSS path verified
- All 9 Tier-2 adapters run daily in `run_daily_all.ps1`
- Unenriched companion files written to `data/objective/news_unenriched_<source>_records.csv`

**Tasks:**
9.3.1 RSS discovery for remaining 6 outlets → document in addendum
9.3.2 Implement each as subclass of Tier-2 RSS base
9.3.3 Integrate into run_daily_all.ps1
9.3.4 Run for 1 week, verify companion files have >0 records

**Quality gates:**
- All 9 outlets in daily schedule
- Companion files non-empty after 1 week

---

## Dependency Graph

```
Epic 6 (PDF) ──→ isolated, depends only on existing Vietstock data
Epic 5 (Gaps) ──→ depends on existing crawlers only
Epic 7 (Macro) ──→ isolated, new scripts
Epic 8 (Quality) ──→ depends on Epic 5,6,7 completion for full coverage
Epic 9 (Objective) ──→ depends on existing Epic 1-4 base

E6 + E5 + E7 can run in PARALLEL
E8 starts AFTER E5/E6/E7 converge (needs final datasets for profiler)
E9 runs INDEPENDENTLY (separate data layer)
```

## Quality Gates Summary

| Gate | Applies To | Command |
|------|-----------|---------|
| Smoke test | Every story | `uv run pytest -m smoke` |
| Ruff lint | Every code change | `uvx ruff check .` |
| Pytest (all) | Every story | `uv run pytest` |
| Diff-coverage ≥80% | Every story | `uv run pytest --cov=... --cov-report=xml && uvx diff-cover coverage.xml --fail-under=80` |
| Code review | Every story | `/code-review` |
| Summary report | Every epic | `docs/reports/<date>_summary_*.md` |
| Impact analysis | Every story | grep callers + document blast radius |
| Similar check | Every story | grep same idiom across codebase |
