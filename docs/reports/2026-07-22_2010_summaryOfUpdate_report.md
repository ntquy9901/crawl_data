# Summary of Update — 3 New Sitemap Sources (CafeBiz, Thời báo Tài chính VN, VietnamFinance)

**Date:** 2026-07-22 20:10  
**Author:** opencode  
**Scope:** news_sitemap_crawler, merge_news, data_classification, run_daily_all.ps1  
**Status:** Complete (DoD verified)

---

## What Changed

### New sources added to `news_sitemap_crawler.py`

| Source | Sitemap type | Article suffix | Floor | Title source |
|--------|-------------|----------------|-------|-------------|
| **cafebiz** (cafebiz.vn) | Sharded index (`StaticSitemaps/sitemaps-YYYY-M-d1-d2.xml`) | `.chn` | 2019-10 | `image:title` embedded |
| **thoibaotaichinhvietnam** (thoibaotaichinhvietnam.vn) | Single sitemap (`sitemaparticles-site-1.xml`) | `.html` | 2015-01 | Slug-based |
| **vietnamfinance** (vietnamfinance.vn) | Single sitemap (`sitemap.xml`) | `.html` | 2020-01 | Slug-based |

### Engine changes

- **`crawl_backfill()`** — refactored into `_crawl_shards()` (sharded path) + new `sitemap_url` branch (single-sitemap path)
- **`_assess_title_quality()`** — new static method for test-mode title quality reporting
- **`_print_title_quality_report()`** — new method for formatted title quality output in `--test` mode
- **`url_stub()`** — new helper for extracting filename stem from URL (test-only)
- **`SLUG_BASED_SOURCES`** — new constant set for slug-based title sources
- **Mutual exclusion assertion** — `__init__` asserts `sitemap_url` XOR `shard_re`

### Related files updated

- `merge_news.py:14` — SOURCES dict + 3 entries (cafebiz, thoibaotaichinhvietnam, vietnamfinance)
- `data_classification.py:42` — `_BY_SOURCE` dict + 3 entries (→ `OBJECTIVE`)
- `run_daily_all.ps1` — daily commands for all 3 new sources

---

## Tests & Quality

| Gate | Result |
|------|--------|
| **pytest** (208 tests) | ✅ 208/208 passed |
| **Smoke** (9 tests) | ✅ 9/9 passed `(-m smoke)` |
| **Lint** (ruff) | ✅ All checks passed |
| **Diff-coverage** (news_sitemap_crawler) | ✅ **85.8%** (≥80% threshold met) |
| **Code review** (`/bmad-code-review`) | ✅ See below |

### Code Review Results (bmad-code-review)

**Subagents:** Blind Hunter + Edge Case Hunter (parallel)

**Triage routing:**
- **3 patches applied** — dead code `if not words` removed, `caph` regex → `(?:h|div)`, mutual exclusion assertion added
- **7 deferred** — pre-existing/cosmetic concerns (sitemap format risk, append timing, `index_url` fallback, daily full fetch, `url_stub` empty, `counters` accumulation)
- **2 dismissed** — noise (None title crash guarded, URL key guaranteed by `parse_shard`)

---

## Similar Check

Grep across repo for `SOURCES`, `crawl_backfill`, `sitemap_url`, `SLUG_BASED_SOURCES`:

- `forum_crawler.py` — `FORUM_SOURCES` dict (unrelated naming)
- `cafef_crawler.py:427` — independent `crawl_backfill` (unrelated implementation)
- `zalo_oa_crawler.py:225` — independent `crawl_backfill`
- `merge_news.py:14` — already updated
- `sitemap_url` — only in `news_sitemap_crawler.py` (new concept); no other file uses it

**Verdict:** No other idioms need updating. Changes are localized.

---

## Files Changed

| File | Lines | Purpose |
|------|-------|---------|
| `news_sitemap_crawler.py` | +151/-51 | 3 new SOURCES entries, `crawl_backfill` refactor, title quality, mutual exclusion |
| `merge_news.py` | +7 | 3 new SOURCES entries |
| `data_classification.py` | +3 | 3 new `_BY_SOURCE` entries |
| `run_daily_all.ps1` | +5 | 3 new daily commands |
| `tests/test_news_sitemap_crawler.py` | +174 | 18 new tests (url_stub, assess_title_quality, single-sitemap path, configs) |
| `tests/fixtures/news_sitemap/vietnamfinance_sitemap.xml` | +14 | Fixture for single-sitemap tests |

---

## Definition of Done Checklist

- [x] Code directly satisfies the requested change (3 new sources)
- [x] Tests: 34 tests for `news_sitemap_crawler` (16 old + 18 new), all pass
- [x] Diff-coverage: **85.8%** (≥80%)
- [x] Lint: ruff pass (Python files)
- [x] Smoke: 9/9 pass
- [x] Code review: `/bmad-code-review` completed, 3 patches applied
- [x] Summary report generated
- [x] Impact analysis: blast radius limited to `merge_news.py`, `data_classification.py`, `run_daily_all.ps1` — all updated
- [x] Similar check: no other idioms need updating

---

## Risks / Follow-ups

- **Stockbiz (RSS)** chưa thêm — cần crawler RSS riêng
- **Single-sitemap performance** — daily cron fetches entire sitemap (~10yr) → acceptable but suboptimal; optimize if becomes bottleneck
- **vietnamfinance sitemap format** — verified working in test, but uses `sitemap.xml` (conventionally an index); monitor for changes
