# Summary — Macro Features Crawler (VN30 volatility prediction)

**Date:** 2026-07-11 11:50 · **Branch:** main · **Plan:** `C:\Users\ntquy\.claude\plans\tranquil-snacking-tarjan.md`

## Context
ML project (Parallel LSTM-GNN, VN30, horizon 1/5/10/22 ngày) hiện không có macro feature nào. Plan `docs/MACRO_FEATURES_PLAN.md` đề xuất thêm daily macro. **Repo này chỉ sản xuất raw + processed macro CSV** (model integration ở repo khác). Dữ liệu crawl vào subfolder `data/macro/` riêng — cô lập hoàn toàn khỏi news raw (cafef/ssi/vndirect/vnstock).

## Đã làm
Thêm subsystem macro: crawler (raw) + build pipeline (processed) cô lập, theo convention repo.

### Files (path → purpose)
- `macro_config.py` (mới) — paths, stable UA, timeout/retry, per-source `RAW_*` + `HEADERS_*`, `SOURCES`, `ensure_paths_exist()`. Mirror `cafef_config.py`.
- `macro_crawler.py` (mới) — class `MacroCrawler`: fetch_dxy (FRED CSV), fetch_vnindex (VNDIRECT finfo JSON paginate), fetch_usd_vnd_vcb (HTML table per-date + early-exit), fetch_usd_vnd_sbv (stub v1). Pure `parse_*` helpers. Resume theo **date** (`_max_date`/`_window`/`_save`). `ThreadPoolExecutor` qua nguồn. CLI `--from-date/--end-date/--workers/--sources/--test`.
- `scripts/build_macro_features.py` (mới) — VNINDEX `date` = trading-calendar anchor → `align_to_calendar()` (`merge_asof` + offset `shift_days`, look-ahead-safe) → feature engineering → `data/macro/processed/macro_features.csv` + `macro_features_stats.txt`.
- `data/macro/raw/dxy.csv` (mới, **real data 5349 rows 2006-01-02→2026-07-02** từ FRED, đã seed) + `sbv_policy_rates.csv` (mới, hand-curated 2011–2026, **VERIFY trước khi dùng**).
- `tests/test_macro_parse.py`, `tests/test_build_macro.py`, `tests/test_macro_crawler.py`, `tests/smoke/test_smoke_macro.py` (mới) + `tests/fixtures/macro/` (fred_dxy.csv, vndirect_vnindex.json, vcb_rates.html, raw/).
- `.gitignore` (sửa) — `data/*` + `!data/macro/` (commit macro; gotcha: bare `data/` chặn git descend).
- `.env.example` (sửa) — append `MACRO_*` knobs.

### Raw schema (mỗi nguồn 1 file, append-resumable, utf-8-sig)
`vnindex_prices.csv` (date,OHLCV,source,collected_at) · `dxy.csv` (date,dxy,...) · `usd_vnd_commercial_vcb.csv` (date,buy,sell,...) · `usd_vnd_central_sbv.csv` (stub) · `sbv_policy_rates.csv` (effective_date,refinancing,discount,omo,source).

### Processed — `macro_features.csv` (19 cột, look-ahead-safe)
`date, vni_{open,high,low,close,volume}, vni_return_{1d,5d}, vni_volume_zscore, dxy, dxy_return_1d, usd_vnd_{sell,buy,central}, usd_vnd_change_1d, usd_vnd_volatility_5d, refinancing_rate, discount_rate, omo_rate`.
Anchor = bộ ngày trade VN (từ VNINDEX). DXY `shift=1` (US-time: value dated D usable từ anchor day sau D); nguồn VN-local + policy `shift=0`. NaN KHÔNG drop (DXY từ 2006 → NaN 2000-2005, báo trong stats).

## Verification (commands thực chạy)
- `uv run pytest -q` → **48 passed**. `uv run pytest -m smoke` → **2 passed**.
- `uvx ruff check <files>` → **All checks passed**.
- Coverage: `uvx diff-cover coverage.xml --compare-branch=HEAD --fail-under=80` → **90% tổng** (macro_config 100%, macro_crawler 86.9%, build 95.4%). Pass ≥80%.
- DXY real-data E2E: feed FRED CSV qua `parse_fred_csv` + crawler `_save` thật → 5349 rows seeded đúng schema (210 sentinel `.` xử lý OK). Build E2E trên real DXY + real policy: VNINDEX 100%, DXY 85% (ngày đầu NaN do shift=1 — đúng), policy 100% (ffill).
- ⚠️ **Live `requests` tới FRED/VNDIRECT/VCB timeout trong sandbox** (curl FRED = 0.4s/103KB; `requests` hang 120s) → đặc thù egress python của sandbox, **KHÔNG phải bug**. Phải verify trên máy user.

## `/code-review` (high effort, 3 agents × 8 angles) — result + actions
**6 findings đã fix:**
1. `_max_date` crash `ValueError` khi 1 row date hỏng → kill ALL sources resume vĩnh viễn → **fix**: try/except skip bad date (+test).
2. `np.log(0)`/zscore div-by-0 → `±inf` nhiễm CSV → **fix**: `df.replace([inf,-inf], NaN)` (+test).
3. Anchor VNINDEX rỗng → `NaT.strftime` crash pipeline hằng ngày → **fix**: guard `if vni.empty: SystemExit`.
4. `if "policy"/"sbv" in name` string-dispatch yếu (+ mislabel policy-missing) → **fix**: `date_col` explicit trong tuple spec.
5. `fetch_usd_vnd_vcb` không early-exit → hàng nghìn requests rỗng khi backfill rộng → **fix**: break sau 15 ngày trống liên tục.
6. `run()` failure-isolation branch chưa test → **fix**: +test inject fetcher raise.

**Deferred (có lý do):** join-suffix (latent YAGNI), VCB sell-column heuristic (unverifiable — đã flag "verify trên máy"), `_save` re-read CSV (sub-ms, premature opt), dedup `now_iso/HN_TZ` ra utils (vi phạm Surgical Changes — sẽ chạm cafef/base_news).

## Risks / follow-ups
1. **USD/VND history rất sparse** (VCB ~3-4 tháng, SBV stub) → `usd_vnd_*` ~99% NaN cho model 2000-2026. v1 ship sparse; long-history FX cần one-time manual pull sang static CSV.
2. **VNDIRECT finfo + VCB reachability** — verify trên máy user (`python macro_crawler.py --sources vnindex`, `--sources usd_vnd_vcb`). Fallback VNDIRECT nếu block: Playwright-stealth shim như `vndirect_crawler.py:66-83`.
3. **`sbv_policy_rates.csv` BEST-EFFORT** — verify các giá trị 2011-2019 với SBV trước khi train model.
4. **VNDIBOR descope v1** (không source sạch) — columns NaN; thêm khi có source.
5. (Optional) wire macro vào `run_daily_all.ps1` sau khi verify máy user.

## Definition of Done
- [x] Code thoả request, không refactor unrelated.
- [x] Tests: 48 passed, diff-coverage **90%** ≥ 80% (macro_config 100 / macro_crawler 86.9 / build 95.4).
- [x] Checks chạy: pytest, ruff, diff-cover — tất cả pass (thực chạy).
- [x] Lint scope: file mới, exclude vendored/generated theo pyproject.
- [x] Code review: `/code-review` chạy, 6 findings fix, 4 deferred có lý do.
- [x] Smoke gate: `tests/smoke/test_smoke_macro.py` pass (build trên fixtures, no network).
- [x] Impact analysis: blast radius THẤP — toàn additive, không đụng entry point có sẵn (`crawler.py`, `run_daily_all.ps1`, `merge_news.py`, Task Scheduler).
- [x] Similar check: date-resume lệch cafef URL-dedup có chủ đích (time-series), KHÔNG backport (không crawler time-series nào khác).
- [x] Summary report: file này.
