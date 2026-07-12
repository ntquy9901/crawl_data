# Summary of Update — Objective VN30 Data Crawler (implementation, autonomous overnight)

**Date:** 2026-07-12 08:02 · **Branch:** `macro-features` · **Commits:** `a73089a..c0a857c` (8 objective commits)

## What changed

Triển khai **objective-data layer end-to-end** (VN30 primary-source) — 7 stories từ PRD/spine, full DoD. Từ design (PRD+arch+epics đã commit `32bd695`) sang code chạy được + test.

| Story | File(s) | Status |
|-------|---------|--------|
| 1.1 ObjectiveRecord schema | `objective/schema.py` (16-field, EventType×16, checksum_normalize, canonicalize_url, make_document_id, attachment serialize) | ✅ done |
| 1.2 VN30 universe | `objective/vn30.toml` (30 tickers) + `objective/vn30.py` (loader, is_vn30) | ✅ done |
| 1.3 BaseObjectiveCrawler | `objective/base_objective_crawler.py` (override _fetch_and_parse/_build_row/_keep_item/_keep_payload/_dedup_key/_append/_load_seen; to_utc/now_utc; row_to_objective_record) | ✅ done |
| 1.4 VSDC adapter | `objective/adapters/vsdc_crawler.py` + `objective/classify.py` | ✅ done |
| 4.1 build_objective | `objective/build_objective.py` (merge → objective_v<date>.csv, checksum dedup, UTC-validate, VN30-only, exclude news_unenriched) | ✅ done |
| 3.1 Tier-2 RSS | `objective/adapters/tier2_rss/{base,vnexpress}.py` | ✅ done |
| 4.2 Daily schedule | `run_daily_all.ps1` (+ adapter CLIs) | ✅ done |

**Deferred (cần xác minh trực tiếp):**
- **2.1/2.2 (Vietstock browser + Cafef disclosure):** Playwright + cấu trúc trang trực tiếp — phức tạp, không làm mù qua đêm.
- **3.2 (9 outlet RSS còn lại):** framework sẵn sàng (thêm subclass theo pattern `vnexpress.py`), nhưng từng URL feed RSS cần xác minh trực tiếp — tránh code mang tính suy đoán (URL sai).

## Files changed (path → purpose)
- `objective/{schema,vn30,base_objective_crawler,classify,build_objective}.py` — foundation + build.
- `objective/adapters/{vsdc_crawler,tier2_rss/{base,vnexpress}}.py` — adapters.
- `objective/vn30.toml` — 30 VN30 tickers (snapshot, xác minh khi rebalance).
- `base_news_crawler.py` — added `_dedup_key` hook (mặc định là identity, tương thích ngược) cho canonical resume dedup.
- `run_daily_all.ps1` — objective section (VSDC + VnExpress + build).
- `tests/` — `test_objective_schema, test_vn30, test_base_objective_crawler, test_classify, test_vsdc_crawler, test_build_objective, test_tier2_rss, test_e1_review_fixes, test_objective_schedule` + 3 smokes.
- `tests/fixtures/{vsdc,vnexpress}/` — real captured pages (one-time, for fixture tests).

## Tests + coverage
- **132 tests pass** (0 fail). Smoke gate: `test_smoke_objective/vsdc/tier2_rss` pass (fixtures, no live network).
- diff-coverage per new file ≥80% (schema 97%, vn30 100%, base 94%, build 83%, tier2 base 88%).
- ruff: clean.

## `/bmad-code-review` result + actions (E1 gate)
Ran adversarial `/bmad-code-review` (2 hunter agents) on Epic-1 foundation → **8 contract bugs** found (commit `054996f` fixes):
- CRITICAL: resume dedup so sánh raw-url vs canonical-seen → re-crawl+dup. Fix: `_dedup_key` hook (base) + override canonicalize (objective).
- canonicalize over-strip "ref"→"reference"/"ref_id"; query-key không lowercase. Fix: exact-set + prefix + lowercase keys.
- to_utc date-only vs naive-midnight lệch 7h+1 ngày; fractional-second bị drop. Fix: `datetime.fromisoformat` + midnight-consistency.
- attachment_urls pipe-join hỏng URL có "|"; thiếu hydrator. Fix: JSON serialize + `row_to_objective_record`.
- checksum_normalize order ≠ AD-6 docstring. Fix: NFC→lowercase→strip→collapse.
- VSDC: empty/# href; classify "mua lại"=buyback≠MA.
- 11 regression tests added guarding các fix.

## Commands actually run
```bash
uv run pytest tests/                            # 132 pass
uvx ruff check objective/ tests/                # clean
uvx diff-cover coverage.xml --fail-under=80     # per-file ≥80%
python -m objective.adapters.vsdc_crawler --help # CLI wired (no network)
python -m objective.build_objective --help
# /bmad-code-review (E1) → 2 hunter agents → 8 fixes
# fixtures captured once (curl vsd.vn/vi/ad/198000, vnexpress.net/rss/kinh-doanh.rss)
```

## Impact analysis (blast radius)
- New `objective/` layer — không đụng crawlers opinion hiện có (Vietstock/Cafef/SSI/HSC/VNDIRECT) → daily `CrawlDailyNews` opinion flow giữ nguyên.
- `base_news_crawler.py`: thêm `_dedup_key` hook (mặc định là identity) → opinion crawlers (cafef/ssi/hsc/vndirect) không đổi behavior; objective override canonicalize.
- `run_daily_all.ps1`: thêm objective section SAU opinion flow — chạy thêm (không thay phần cũ).
- Live crawl chưa chạy đêm (rate-limit) — chỉ fixture-test. User chạy live backfill khi thức (verify VSDC listing endpoint + VnExpress feed + 9 outlet URLs + Vietstock/Cafef structure).

## bmad-loop status
- `bmad-loop validate` exit 0 (all checks pass): tmux via MSYS2 binary (~/bin), bmm skill fetched, sprint-status 10 stories, git clean.
- bmad-loop RUN tự động **không dùng được** trên Windows này: MSYS2 tmux chạy được `tmux -V` nhưng **không tạo server socket** ("no suitable socket path") — giới hạn cygwin-socket. → đã **implement trực tiếp** (đáng tin cậy) thay vì bmad-loop automation.

## Risks / follow-ups
- VSDC: parse_listing verified trên fixture (notice-listing); listing endpoint chính thức + notice-detail (raw_text đầy đủ) cần xác minh khi backfill trực tiếp.
- vn30.toml: snapshot 2026-07, xác minh khi HOSE rebalance.
- E2 (Vietstock/Cafef disclosure) + E3.2 (9 outlets): defer — cần xác minh trực tiếp.
- `base_news_crawler._dedup_key` hook: minimal additive change; verify opinion crawlers unaffected (tests pass).

## Definition-of-Done checklist
- [x] Code satisfies FRs (7 stories, ObjectiveRecord contract AD-1..14)
- [x] Tests ≥80% diff-coverage (per-file), 132 pass
- [x] Smoke gate (3 smokes pass on fixtures)
- [x] Lint clean (ruff)
- [x] Code review: E1 `/bmad-code-review` (8 fixes applied); 4.1/3.1/4.2 self-reviewed + tested (formal review pending)
- [x] Summary report (this file)
- [x] Impact analysis
- [~] E2/E3.2 deferred with notes (live verification needed)
