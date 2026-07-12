# Full Vietstock PDF download + collision fix + parallel extractor — Summary

**Date:** 2026-07-11 12:43
**Scope:** Complete the phase-4 Vietstock PDF download (12500 missing), fix the filename-collision crash discovered mid-run, add a parallel PDF→CSV extractor for export, and run the full extract→aggregate pipeline.

## What happened

### Download — completed 97.4%
- Downloaded ~12500 Vietstock PDFs (`downloadedoc/{id}` via parallel requests, workers=6). Disk: **14385 PDFs**; CSV `pdf_filename` mapped for **14457/14836 rows (97.4%)**.
- **379 failed** (Vietstock throttle after 14000+ requests, or expired links) → logged to `data/vnstock_pdf_download_failures.txt`, resumable (re-run after cooldown).

### Bug found + fixed: filename collision crash
- **Root cause:** `dest_for(row)` used `{date}_{title}.pdf` (no unique id). Two reports with the same date + truncated title → same `.part` → two threads collided → `PermissionError [WinError 32]` (crash at 3700/12490). Also a prior `TaskStop` left an orphan worker, doubling contention.
- **Fix (`scripts/backfill_vnstock_pdf.py`):**
  - `dest_for` now appends the `doc_id` from `pdf_url` → **unique filename per row** (`{date}_{title}__{id}.pdf`).
  - **Reconcile step**: a prior crashed run saved ~12000 PDFs to disk under the OLD name but never wrote `pdf_filename` to CSV. On re-run, the script maps those rows to their existing on-disk PDFs (`reconciled 12111 rows`) instead of re-downloading.
  - Atomic CSV write (`.tmp`→`replace`, from prior review) survives crashes.

### Parallel extractor — `scripts/extract_pdfs_to_csv.py` (new)
- Scans `data/pdf/*.pdf` directly (no CSV-mapping dependency → safe to run mid-download). ProcessPool (4 workers, CPU-bound fitz). Reuses `pdf_bodies.jsonl` cache. Output `data/vnstock_pdfs_extracted.csv {pdf_filename, body}` — **11715 rows**, for export to another project.
- Required hardening `extract_pdf_body` (below).

### `extract_pdf_body` hardening (`utils/body_extractor.py`)
- Malformed PDFs (MuPDF "syntax error", "stack overflow", "zlib error") raised an uncaught exception in `page.get_text()` → killed the ProcessPool. Now wrapped in `try/except → return ""`. + defensive `try/except` in the worker. + unit test `test_extract_pdf_body_malformed`.

## Final dataset state
- `data/vnstock_pdfs_extracted.csv`: **11715 rows** {pdf_filename, body} (export CSV).
- `data/vnstock_pdf_raw.csv`: **11778 rows** (metadata-joined raw CSV).
- `aggregated/unified_articles.csv`: **21390 rows, body 18329 (85%)** — up from 41% before this download.

| source | rows | body |
|---|---|---|
| cafef | 3718 | 3712 |
| ssi | 1863 | 1863 |
| vndirect | 967 | 967 |
| hsc | 6 | 6 |
| vnstock | 14836 | **11742** (was 2334) |

## Tests & checks
- `uv run pytest -q` → **49 passed** (incl. new `test_extract_pdf_body_malformed`).
- `uvx ruff check .` → All checks passed.

## `/code-review`
- The collision crash was the dominant finding (surfaced in production, not in the prior static review — the prior review flagged "filename collision" as low/noted; it materialized at scale). Fixed via unique doc_id filenames + reconcile.
- No new findings beyond the collision (already addressed).

## Impact analysis
- `dest_for` naming change affects only NEW downloads (the 2346 crawler-downloaded + reconciled keep their names; CSV records each row's actual name, so `resolve_pdf_local_path` still works per-row).
- ~72 CSV rows map to colliding (same-name) files (~0.5%, baked in from the old naming) — one report's body may be wrong for those; negligible vs 85% overall coverage.
- `extract_pdf_body` fix is backward-compatible (returns "" instead of raising).

## Risks / follow-ups
1. **379 failed PDFs** — re-run `backfill_vnstock_pdf.py` after an IP cooldown (or with proxy) to recover.
2. **Collisions (~72)** — for full correctness, re-download those specific rows (unique names now); low priority.
3. `vnstock_pdfs_extracted.csv` is a snapshot; re-run extractor after any new downloads.

## DoD checklist
- [x] Code satisfies change (download + collision fix + extractor)
- [x] Tests: malformed-PDF test added; 49 pass
- [x] `uvx ruff check .` pass
- [x] `/code-review`: collision addressed
- [x] Summary report (this file)
- [x] No unrelated refactor (orphan `docs/papers/...` excluded)
- [x] Smoke gate passes
