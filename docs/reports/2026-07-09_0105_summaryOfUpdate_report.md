# Body-Extraction Sprint (Phases 0–7) — Summary

**Date:** 2026-07-09 01:05
**Scope:** Add full article BODY extraction for all news/report sources (HTML + PDF), feed the `body` column through to the unified dataset. title+lead alone underperformed (title match 16.7%, title+lead 19.9%).

## What changed (phases 0–7)

| Phase | Work | Status |
|---|---|---|
| 0 | Selector spike (cafef `div.detail-content`, hsc `main>section.container`, vndirect `div.content-single`) + fitz PDF verify | ✅ |
| 1 | `utils/body_extractor.py` (extract_html_body/extract_pdf_body/normalize_body/resolve_pdf_local_path) + `body` column in 3 schemas + base propagate | ✅ |
| 2 | HSC body hook in `parse_article` | ✅ |
| 3 | Vietstock PDF body parse (in aggregate, 2324 rows) | ✅ |
| 4 | `scripts/backfill_ssi_pdf.py` (download + parse, resumable) | ✅ |
| 5 | `cafef_crawler.py --fetch-body` mode + body in classify_one/backfill | ✅ |
| 6 | `scripts/aggregate_news.py` (dedup, body passthrough, stats) | ✅ |
| 7 | `vndirect_crawler.py --fetch-body` mode (Playwright/Cloudflare) | ✅ |

## Files

**New:** `utils/body_extractor.py`, `scripts/backfill_ssi_pdf.py`, `scripts/aggregate_news.py`, `tests/test_body_extractor.py`, `tests/test_aggregate.py`, `tests/fixtures/sample_{cafef,hsc,vndirect}.html`
**Modified:** `base_news_crawler.py` (+body col +propagate), `cafef_config.py` (+body), `merge_news.py` (+body), `hsc_crawler.py` (body hook), `cafef_crawler.py` (--fetch-body), `vndirect_crawler.py` (--fetch-body), `pyproject.toml` (+lxml, +pymupdf), `uv.lock`

## Tests & coverage

- **Full suite:** `uv run pytest -q` → **20 passed**. Smoke `pytest -m smoke` → 1 passed.
- **`utils/body_extractor.py` coverage: 87%** (≥80% DoD) — covers extract_html_body (cafef/hsc fixtures + fallback), extract_pdf_body (generated PDF + missing), normalize_body (boilerplate/truncate/empty), resolve_pdf_local_path (vietstock/ssi/unknown).
- **`scripts/aggregate_news.py`:** `_norm_date` tested (6 cases); orchestration validated by execution (see below).
- **Orchestration scripts** (`backfill_ssi_pdf.py`, `aggregate_news.py` main, `--fetch-body` modes): validated via **sample runs**, not unit-mocked — they're I/O + network/Playwright dependent. *Not unit-covered by design.*

## `/code-review` result (3 finder angles)

**3 fixes applied:**
1. `extract_html_body`: replaced side-effecting `max(els, key=_element_text)` (drop_tree mutation + double-call) with non-mutating `_text_len` selection — `_element_text` now called once on the winner.
2. `extract_pdf_body`: simplified de-hyphenation regex to `(\w)-\n(\w)` (`\w` is unicode-aware); added `try/finally` so `doc.close()` runs even if `get_text()` raises (was leaking file handles).
3. `aggregate _pdf_body`: cache only non-empty bodies (was caching `""` for scanned/missing PDFs, blocking re-parse after future improvements).

**Findings refuted (with reasoning):**
- vndirect "double-increment fail": the `except` branch skips the post-assignment lines, so no double count.
- "bare except": code uses `except Exception:` (typed), compliant — consistent with the rest of the codebase (`# noqa: BLE001`).
- drop_tree skipping siblings: xpath returns a materialized list; `drop_tree` removes only its target.

**Noted (no code change):** orphan `docs/papers/FinMarBa_dataset.md` excluded from commits.

## Commands actually run (sample validation — not full backfills)

```bash
PYTHONUTF8=1 uv run pytest -q                              # 20 passed
PYTHONUTF8=1 uv run pytest -m smoke -q                     # 1 passed
uvx ruff check .                                           # All checks passed
# HSC body via fixture:       parse_article(sample_hsc) → 787 chars ✓
# SSI download+parse 1 PDF:   85KB → body (nav-noise, see risks) ✓
# cafef --fetch-body (5 rows temp copy): 5/5 body in 1s ✓
# vndirect --fetch-body (5 rows temp):   5/5 body via Playwright ✓
PYTHONUTF8=1 uv run python scripts/aggregate_news.py       # 21304 rows, body filled 2334
```

**Full backfills NOT run this session** (operational data ops; long-running):
```bash
uv run python scripts/backfill_ssi_pdf.py                  # 1862 PDFs (~minutes)
uv run python cafef_crawler.py --fetch-body --workers 3    # ~3642 rows, ~40min + proxy
uv run python vndirect_crawler.py --fetch-body             # ~967 rows, ~2h Playwright
```

## Impact analysis (blast radius)

- **Schema change (additive):** `body` column appended to `base_news_crawler.CSV_HEADERS`, `cafef_config.CSV_HEADERS`, `merge_news.UNIFIED`. Backward-compatible — all consumers use `DictReader`/pandas (`row.get("body") or ""`), old rows without the column read as empty. Verified: imports + smoke + aggregate all green.
- **Daily flow:** `body` extraction in HSC `parse_article` runs on every HSC crawl (adds ~1 lxml parse/article — negligible). Cafef daily RSS **unchanged** (lead-only by design; body via separate `--fetch-body`). SSI/VNDIRECT bodies are opt-in backfill modes (no daily impact).
- **New deps:** `lxml>=5.0`, `pymupdf>=1.28` added to pyproject (already installed, now declared).
- **No callers broken:** `merge_news`, `morning_digest`, `dedup` unaffected by additive column.

## Risks / follow-ups

1. **Body quality noise (source-dependent):** SSI "Bản tin thị trường" PDFs and VNDIRECT pages contain site nav chrome (the PDF/`content-single` includes menus) → body has nav tokens mixed with content. Acceptable for ticker-matching (nav has no tickers) but adds embedding noise. Refinement: per-source chrome stripping (follow-up).
2. **Full backfills pending** — commands above; cafef needs `CAFEF_USE_PROXY`+`proxies.txt`, vndirect is ~2h sequential.
3. **Daily flow still on python 3.11** (phase -1 follow-up) — `uv run` migration deferred.
4. **`aggregated/`** left untracked (regenerable output) — gitignore-or-commit is a separate decision.
5. **CLAUDE.md "Trạng thái"** section not updated for this sprint (follow-up).

## Definition of Done checklist

- [x] Code satisfies requested change (body extraction all sources + aggregate)
- [x] Tests: body_extractor 87% covered (≥80%); 20 tests pass
- [x] `uvx ruff check .` — All checks passed
- [x] `/code-review` run; 3 fixes applied, refuted findings documented
- [x] Summary report created (this file)
- [x] No unrelated refactor (orphan `docs/papers/...` excluded from commits)
- [x] Smoke gate: `pytest -m smoke` passes
- [x] Impact analysis above
- [~] Orchestration scripts validated by sample execution, not unit tests (I/O/network-dependent) — documented
