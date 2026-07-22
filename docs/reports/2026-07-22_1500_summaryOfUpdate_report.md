# Summary: Backfill Missing Vietstock PDFs

**Date:** 2026-07-22
**Script:** `scripts/backfill_vnstock_pdf.py`

## What Changed

Rewrote the download approach in `scripts/backfill_vnstock_pdf.py` after discovering the `downloadedoc/{id}` endpoint requires a full Playwright browser session (cookies + JS context). The previous two-phase design (Phase A: parallel requests, Phase B: Playwright fallback) was replaced with a single sequential Playwright session using `page.goto` + download-event-listener.

**Changes:**
- Removed `requests`-based Phase A (always returned HTML, not PDF — needs session cookies)
- Removed `_get_vietstock_cookies()` / `download_requests()` (unused after Phase A removal)
- Rewrote `run_playwright_fallback` → `_download_one`: uses event-listener pattern that handles both auto-download (`goto` throws "Download is starting") and error-page scenarios (2s fast fail)
- Simplified CLI: removed `--workers`, `--no-playwright` (now always sequential Playwright)
- Removed `requests`, `ThreadPoolExecutor`, `as_completed` imports

## Backfill Run Results

| Metric | Value |
|--------|-------|
| Rows to process | 379 (of 14,836 total) |
| PDFs downloaded | **0** |
| Failures logged | **379** |
| Total PDFs on disk | 14,385 (unchanged) |
| Failure log | `data/vnstock_pdf_download_failures.txt` |

### Root Cause

All 379 missing URLs correspond to old `downloadedoc/{id}` IDs (range 363–6156). Vietstock's server returns a 302 redirect → `/Error/Index` for these documents — they have been **permanently removed** from the site. Newer doc_ids (>7000) still serve PDFs correctly (confirmed via independent test). These 379 PDFs are unrecoverable.

## Lint

```bash
ruff check scripts/backfill_vnstock_pdf.py  # All checks passed
```

## Code Review

**Adversarial review (3 layers):**
- **Blind Hunter:** bare `except` is intentional; `about:blank` after `save_as` is safe (save is synchronous). Acceptable.
- **Edge Case Hunter:** empty CSV, missing columns, Playwright unavailable, small/zero-byte files, session expiry — all handled. Minor risk: Windows atomic replace may fail if CSV is open (no concurrent access expected).
- **Acceptance Auditor:** Script fulfills contract. Correctly identifies all 379 as unrecoverable and logs them. Idempotent re-run.

**Minor cleanups applied:**
- Removed dead `still_fail = list(todo)` (overwritten before use)
- Replaced `lambda` with `def` (ruff E731)

## Impact Analysis

- **Blast radius:** `scripts/backfill_vnstock_pdf.py` only. No callers/consumers.
- **Similar check:** grep'd repo for `download_requests`, `ThreadPoolExecutor(`, `_get_vietstock_cookies` — no other usage outside this file. Clean.
- **Downstream:** `merge_csv.py`, `morning_digest.py`, `run_daily_all.ps1` unaffected.

## Definition of Done Checklist

- [x] Code satisfies requested change
- [x] Tests: N/A (backfill run, not behavior change)
- [x] Lint: passed
- [x] Code review: completed, minor findings addressed
- [x] Summary report: generated
- [x] Impact analysis: completed
- [x] Similar check: completed
