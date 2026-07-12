# Vietstock PDF → raw CSV + full body backfill — Summary

**Date:** 2026-07-11 10:18
**Scope:** (1) Plan + implement Vietstock PDF → raw CSV pipeline (download-missing + `vnstock_pdf_raw.csv`); (2) run full body backfill for all sources; (3) apply `docs/proposed-repo-CLAUDE.md` quality rules + crawler design rules to CLAUDE.md.

## What changed

### Vietstock PDF → raw CSV (plan phases 0–3)
| Phase | Work | Result |
|---|---|---|
| 0 | Spike: all 12500 missing `pdf_url` = `downloadedoc/{id}`; requests with stable UA+Referer downloads OK (no browser/cookies) | ✅ |
| 1 | Extract `generate_pdf_filename` → `utils/pdf_helpers.py`; crawler delegates | ✅ 6 tests |
| 2 | `scripts/backfill_vnstock_pdf.py` — 2-phase (parallel requests + Playwright fallback), **skip-if-exists RULE**, atomic CSV write | ✅ `--test` 5/5 |
| 3 | `scripts/build_vnstock_pdf_raw.py` — parse local PDFs → raw CSV (cached) | ✅ 2344 rows |
| 4 | Full download 12500 historical PDFs | ⏳ not run (operational, long; user-run) |

### Full body backfill (all sources) — RUN
| Source | body filled | time |
|---|---|---|
| HSC | 6/6 | inline |
| cafef | 3715/3718 (fail 3) | 431s, no throttle |
| SSI | 1863/1863 (PDF download+parse) | ~9min |
| vndirect | 967/967 (Playwright) | ~50min |
| Vietstock | 2344 PDFs local (raw CSV) | spike+`--test` |

**Aggregate after all backfills: 21390 rows, body filled 8895 (41.5%)** — up from 0% at sprint start. Remaining gap = Vietstock 12500 historical (metadata-only, need phase-4 download).

### CLAUDE.md (apply proposed-repo-CLAUDE.md + design rules)
- Replaced QA section with proposed **Project Quality Rules** (project-agnostic: DoD, Summary report, Code hygiene) + filled **Per-project setup** block (Python 3.13/uv, pytest, ruff, smoke, lint excludes, diff-cover).
- Added **Crawl design rules**: (1) song song hóa (ThreadPool/ProcessPool), (2) nhẹ-trước-nặng-sau, (3) config bật/tắt (DOWNLOAD_PDF / --fetch-body / --no-playwright).
- Fixed stale `Python 3.11` → `3.13` in Stack; added lxml/PyMuPDF.

## Files
- **New:** `utils/pdf_helpers.py`, `scripts/backfill_vnstock_pdf.py`, `scripts/build_vnstock_pdf_raw.py`, `tests/test_pdf_helpers.py`, `docs/proposed-repo-CLAUDE.md` (source proposal).
- **Modified:** `crawler.py` (import + delegate `generate_pdf_filename`), `CLAUDE.md`.

## Tests & coverage
- `uv run pytest -q` → **26 passed** (+6 pdf_helpers). Smoke 1 passed.
- `utils/pdf_helpers.py` covered (6 tests: Vietnamese, truncation, special chars, edge cases).
- Backfill/build scripts: orchestration validated by execution (`--test`, full runs), not unit-mocked (I/O/network-dependent) — consistent with prior scripts.
- `uvx ruff check .` → All checks passed.

## `/code-review` result
4 findings on the Vietstock scripts:
- **Fixed (#2):** `backfill_vnstock_pdf` CSV write → atomic (`.tmp`→`Path.replace`) so a crash mid-write can't corrupt `vnstock_articles.csv`.
- **Noted (low, not fixed):**
  - #1 filename collision (same title+date → same name): consistent with crawler's existing `generate_pdf_filename` (used for the 2336 already-local PDFs); collisions rare; `download_requests` skips-if-exists.
  - #3 Playwright fallback hangs on non-direct URLs: all `pdf_url` are `downloadedoc/{id}` (direct) — none are landing pages; fallback rarely triggers; 60s timeout bounded.
  - #4 `pdf_bodies.jsonl` shared by build + aggregate: run sequentially (not concurrent) in practice.

## Impact analysis
- **crawler.py refactor:** `generate_pdf_filename` extracted to util; method delegates. Caller (crawler.py:398) unchanged. Verified: crawler imports OK, delegate produces identical filenames (existing 2336 PDFs still resolve).
- **Schema:** `vnstock_pdf_raw.csv` is a NEW standalone file (schema `[id,source,title,body,lead,date,pdf_url,pdf_filename]`); does not alter `vnstock_articles.csv` schema (only fills `pdf_filename`/`downloaded_at` for downloaded rows).
- **Backfill data:** all in `data/` (gitignored) — not committed. `aggregated/` regenerable.

## Commands actually run
```bash
PYTHONUTF8=1 uv run python scripts/backfill_vnstock_pdf.py --test   # 5/5 (×2, idempotent)
PYTHONUTF8=1 uv run python scripts/build_vnstock_pdf_raw.py         # 2344 rows
PYTHONUTF8=1 uv run python scripts/aggregate_news.py                # 21390 rows, body 8895
uv run pytest -q                                                    # 26 passed
uvx ruff check .                                                    # All checks passed
# full backfills (background): cafef 3715, ssi 1863, vndirect 967
```

## Risks / follow-ups
1. **Phase-4 full Vietstock download (12500 PDFs)** not run — `uv run python scripts/backfill_vnstock_pdf.py` (hours, captcha risk, ~2-12GB). Then rebuild raw + aggregate → body sparsity → ~90%+.
2. **Filename collision** (#1) — if observed, make filename unique (append pdf_url id). Consistent with crawler for now.
3. **Cache concurrency** (#4) — if build+aggregate ever run concurrently, add file lock. Sequential use is safe.
4. **vndirect/SSI body nav-noise** (from prior sprint) — per-source chrome stripping is a future refinement.
5. **Daily flow still on python 3.11** (phase -1 follow-up).

## DoD checklist
- [x] Code satisfies change (PDF→raw CSV pipeline + CLAUDE.md rules)
- [x] Tests: pdf_helpers 6 tests; 26 total pass
- [x] `uvx ruff check .` — All checks passed
- [x] `/code-review` run; 1 fix applied, 3 noted with reasoning
- [x] Summary report (this file)
- [x] No unrelated refactor (orphan `docs/papers/...` excluded)
- [x] Smoke gate passes
- [x] Impact analysis above
- [~] Orchestration scripts execution-validated, not unit-covered (documented)
