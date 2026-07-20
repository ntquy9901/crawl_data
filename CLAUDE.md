# CLAUDE.md — Vietstock Analysis Reports Crawler


Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## Mục tiêu
Thu thập dữ liệu phân tích/tin tức thị trường CK Việt Nam đa nguồn (theo skill `.claude/skills/source-news-download`):
- **Vietstock** — "Báo cáo phân tích" PDF từ `finance.vietstock.vn/bao-cao-phan-tich` → `data/vnstock_articles.csv` + `data/pdf/`. Metadata toàn kỳ 2001–2026, PDF kỳ gần.
- **Cafef** — tin tức thị trường hằng ngày (RSS + sitemap backfill) → `data/cafef_articles.csv`.
- **SSI / HSC / VNDIRECT** — research/notes CTCK → `data/{ssi,hsc,vndirect}_articles.csv` (qua khung `base_news_crawler.py`).
- **Tuổi Trẻ / Thanh Niên / VietnamPlus** — tin tức phổ thông, metadata-only (title/url/pub_date), qua `news_sitemap_crawler.py` → `data/{tuoitre,thanhnien,vietnamplus}_articles.csv`.
Mỗi crawler có cột `source` ghi nguồn (lưu vết/phân loại) + dedup riêng (resumable). Chạy định kỳ qua Windows Task Scheduler (`run_daily_all.ps1`).

## Stack & ràng buộc
- Python 3.13 (async) + Playwright (chromium, stealth) + playwright-stealth + fake-useragent; requests (download), pandas (CSV), python-dotenv, aiohttp, lxml, PyMuPDF. (`uv` env — `.python-version`)
- **KHÔNG dùng Vietstock JSON API** (giới hạn truy cập) — chỉ browser crawl.
  - **EXCEPTION (authorized 2026-07-12):** the objective VN30 disclosure adapter
    (`objective/adapters/vietstock_disclosure.py`, FR-16) MAY call Vietstock's
    `/data/EventsTypeData` POST endpoint directly (token extracted from the page
    hidden input + session cookie). Scope-limited to VN30 corporate-action
    events; the analysis-reports crawler (`crawler.py`) still browser-only.

## Crawl design rules
1. **Song song hóa** (luôn nghĩ tới khi plan/design/code): fetch/parse độc lập phải chạy song song để crawl nhanh — I/O-bound (HTTP) → `ThreadPoolExecutor` (`--workers`); CPU-bound (parse PDF) → `ProcessPoolExecutor`.
2. **Nhẹ trước, nặng sau**: ưu tiên nội dung nhẹ (HTML head/body, RSS) TRƯỚC nội dung nặng (PDF, Playwright/Cloudflare). Nội dung nặng chạy nền/chạy sau để có kết quả nhanh.
3. **Config bật/tắt các chức năng tốn thời gian**:
   - Download nội dung nặng (PDF): `DOWNLOAD_PDF` (`config.py`), `--no-playwright` (backfill scripts).
   - Head/body/file tách lớp: metadata (head) luôn crawl; body opt-in (`--fetch-body` cafef/vndirect, `scripts/build_vnstock_pdf_raw.py`); daily cafef lead-only (`--daily`). Mỗi lớp chạy độc lập, bật/tắt bằng flag/env.

## Cấu trúc
- `crawler.py` — script chính, class `VietstockCrawler`. Flow: `init_browser` → loop {navigate/paginate → `extract_report_links` → `_collect_reports` (date-filter → dedup → `download_pdf` nếu `DOWNLOAD_PDF` → `save_to_csv`)}. Hai mode: `crawl()` (pagination thường, trong window mặc định ~1 năm) và `crawl_by_windows()` (`--from-date` — set filter `#fromDate/#toDate` + click `#btnSearchEDoc` để tới dữ liệu cũ).
- `config.py` — constants từ `.env` (`CAPTCHA_PAUSE_MINUTES=5`, `CAPTCHA_MAX_RETRIES=3`, `RANDOM_DELAY` 3–8s, `DOWNLOAD_PDF=false`, paths, CSV_HEADERS).
- `merge_csv.py` — gộp nhiều CSV backfill song song vào `data/data.csv`, dedup theo `pdf_url`, ưu tiên row có PDF. `python merge_csv.py --inputs <files> [--dry-run]`.
- `cafef_crawler.py` + `cafef_config.py` — crawler tin tức Cafef (sibling của Vietstock): daily RSS (`--daily`) + backfill sitemap shards (`--backfill`, classify section bằng breadcrumb). Self-contained (riêng dedup, không đụng `utils/dedup.py`). Output `data/cafef_articles.csv`.
- `base_news_crawler.py` — khung crawler tin tức **tổng quát** (Template Method: subclass override `source`/`listing_url`/`parse_listing`/`parse_article`/`next_page`; base lo flow + dedup + `--workers`/`--batch` + audit log `logs/<source>_audit.log` + resume theo url). Mode `--latest` (daily) / `--range --from-date --end-date`.
- `ssi_crawler.py` (PDF bulletins, listing-complete), `hsc_crawler.py` (Research Insights, daily-only, không có pub_date), `vndirect_crawler.py` (research notes, **Playwright-stealth vượt Cloudflare**, `--category company/sector/strategy/economics-note`) — 3 subclass. Output `data/<source>_articles.csv` (cột `source` ghi nguồn).
- `news_sitemap_crawler.py` — crawler tin tức phổ thông metadata-only (subclass `base_news_crawler.BaseNewsCrawler`, chỉ override `crawl_backfill` — topology sitemap-shard khác paginated-listing nên không dùng `crawl_latest`/`crawl_range`/`parse_listing`). Nguồn: tuoitre/thanhnien/vietnamplus — sitemap 3 site này nhúng sẵn title (`image:title`/`news:title`) nên KHÔNG cần fetch từng bài. `--source <tên> [--latest | --from-date/--end-date]`. nld/vnexpress KHÔNG có: nld.com.vn redirect toàn bộ sang tuoitre.vn/nld/* (trùng nội dung); vnexpress chặn bot ở sitemap-shard theo ngày (xem docstring file để biết chi tiết khảo sát).
- `merge_news.py` — gộp cafef/ssi/hsc/vndirect/tuoitre/thanhnien/vietnamplus → `data/news_articles.csv` (schema chung, cột `source`, dedup theo url). `morning_digest.py` — tạo bản tin sáng markdown (`data/digest_YYYY-MM-DD.md`) từ bài mới nhất, nhóm theo nguồn — đọc trước khi đầu tư.
- `utils/anti_bot.py` — stealth browser, `safe_goto`/`safe_click`, `human_like_scroll`, `get_random_user_agent`.
- `utils/dedup.py` — `DedupManager` (check URL/ID trong CSV).
- `utils/proxy_manager.py` — xoay vòng proxy (`USE_PROXY=false`, chưa dùng thật).
- `utils/alert.py` — phát hiện captcha (keyword + HTTP 403/429/5xx). **CHỈ log, chưa gửi Gmail.**
- `run_crawler.ps1` + `task_scheduler.xml` — Windows Task Scheduler Vietstock 2h/day. `run_daily_all.ps1` — chạy tất cả nguồn (cafef --daily + ssi/hsc/vndirect --latest + Vietstock recent) 1 lệnh; **đã cài Task Scheduler `CrawlDailyNews` @ 05:00 daily** (xong trước 6h sáng). `docs/anti-throttle.md` — research SOTA chống throttle + design proxy cho Cafef.
- `data/`: `vnstock_articles.csv` (14.825), `cafef_articles.csv`, `ssi/hsc/vndirect_articles.csv`, `cafef_candidates.jsonl` (cache backfill cafef), `pdf/`, `logs/`.

## Chạy
```bash
# PDF download (trong window mặc định ~1 năm gần nhất):
PYTHONUTF8=1 python crawler.py --start-date 2026-01-01 --headless true

# Backfill metadata về cũ (window-crawl qua date filter; nhanh vì bỏ PDF):
PYTHONUTF8=1 python crawler.py --from-date 2001-01-01 --headless true

# Chạy song song ra CSV riêng rồi gộp:
CSV_FILE=data/backfill.csv PYTHONUTF8=1 python crawler.py --from-date 2021-01-01 --headless true
python merge_csv.py --inputs data/backfill.csv

# News crawlers (daily + backfill):
PYTHONUTF8=1 python cafef_crawler.py --daily                                    # Cafef RSS hằng ngày
PYTHONUTF8=1 python cafef_crawler.py --backfill --from-date 2016-01-01 --workers 4   # Cafef backfill (sitemap, workers thấp tránh throttle)
PYTHONUTF8=1 python ssi_crawler.py --latest                                     # SSI mới nhất
PYTHONUTF8=1 python ssi_crawler.py --range --max-pages 220                      # SSI backfill toàn bộ
PYTHONUTF8=1 python hsc_crawler.py --latest                                     # HSC (daily-only)
PYTHONUTF8=1 python vndirect_crawler.py --latest --category company-note        # VNDIRECT (Playwright; cần cho Cloudflare)
PYTHONUTF8=1 python vndirect_crawler.py --range --max-pages 80 --category company-note
PYTHONUTF8=1 python news_sitemap_crawler.py --source tuoitre                    # backfill floor→nay (~15 năm, chạy 1 lần)
PYTHONUTF8=1 python news_sitemap_crawler.py --source thanhnien --latest         # daily (7 ngày gần nhất)
powershell -ExecutionPolicy Bypass -File run_daily_all.ps1                      # chạy tất cả daily 1 lệnh
```
Flags: `--start-date/--end-date` (per-report filter trong window mặc định), `--from-date` (window-crawl tới dữ liệu cũ, `--window-months N` mặc định 6), `--max-pages N` (0=∞), `--test`, `--headless true|false`.
`DOWNLOAD_PDF=false` (mặc định `.env`) = chỉ metadata, bỏ download + delay → crawl nhanh nhất. Bật `DOWNLOAD_PDF=true` để tải PDF.
Luôn set `PYTHONUTF8=1` trên Windows (CSV luôn UTF-8 BOM).

## Trạng thái (2026-07-06)
- ✅ Pagination (JS `#report-paging`), ✅ Captcha pause 5 phút + retry 3 lần, ✅ Download (browser UA + retry + `context.request.get()`), ✅ Date-bounded crawl, ✅ `--max-pages`/`--start-page`, ✅ `DOWNLOAD_PDF` toggle (default false = metadata-only nhanh), ✅ **Window-crawl `--from-date`** (lấy dữ liệu cũ qua date filter — listing mặc định khoá ~1 năm), ✅ `merge_csv.py` (gộp backfill song song).
- **Dataset Vietstock**: `data/vnstock_articles.csv` = **14.825 reports unique** (theo `pdf_url`; gộp `data.csv` + `data_archive.csv` + `data_2021_2025.csv` + re-crawl 2015–2018), **2001–2026**, **2.336 PDF** (chỉ 2026; 2001-2025 metadata-only).
- **News datasets** (cột `source`, schema chung): `cafef_articles.csv` ~3.450 (daily RSS tích lũy; **deep backfill KHÔNG khả thi** — cafef throttle IP + sitemap không tag section → classify-all cost, xem `docs/anti-throttle.md`), `ssi_articles.csv` 1.859 (đã đủ ~217 trang), `hsc_articles.csv` 6 (HSC ít + **không pub_date**), `vndirect_articles.csv` 967 (đã đủ 4 category, archive chỉ từ 2016). `tuoitre_articles.csv` 283.568 (floor 2011-01), `thanhnien_articles.csv` 387.169 (floor 2011-06), `vietnamplus_articles.csv` 773.152 (floor 2010-01) — backfill đầy đủ 2026-07-18, metadata-only qua `news_sitemap_crawler.py` (xem file đó để biết vì sao nld/vnexpress không có). **Gộp** `news_articles.csv` = 1.450.798 rows (`merge_news.py`).
- **Vietstock verify (2026-07-06)**: re-crawl 2008-2025 → **không miss hệ thống** (2016 là transient cô lập). Dataset 14.825 tin cậy.
- **Hằng ngày**: Task Scheduler `CrawlDailyNews` @ 05:00 chạy `run_daily_all.ps1` (crawl tất cả nguồn + `merge_news` + `morning_digest` → `data/digest_YYYY-MM-DD.md` đọc trước 6h). `cafef_crawler` có sẵn proxy xoay vòng (`CAFEF_USE_PROXY` + `proxies.txt`, 10 Webshare).
- ✅ **Gap 2006-2007 = gap THẬT của site** (verify 2026-07-04: date filter trả ~0) — không sửa được.
- ✅ **Backfill-miss 2015-2016 đã lấp**: re-crawl từng window rồi gộp (2016: 18→387, 2015: 450→513; 2017/2018 vốn đủ). Nguyên nhân: captcha/timeout **tạm thời** trong lần chạy dài `--from-date 2001`, KHÔNG phải bug logic mọi window. `crawl_by_windows()` đã thêm **retry navigate/apply + cảnh báo window 0-yield**.
- ⚠️ **stray-date**: **ĐÃ FIX** (2026-07-05) — `extract_report_links` fallback `date_str` từ `now()` → `""`. Card thiếu date không còn bị gán ngày crawl.
- ➕ **Cafef news crawler** (`cafef_crawler.py` + `cafef_config.py`): daily RSS (`cafef.vn/<section>.rss`) + backfill qua sitemap shards (2016–2026, classify section bằng breadcrumb `@id`). Output `data/cafef_articles.csv`. Plain HTTP, không Playwright. Skill `source-news-download` ở `.claude/skills/`.
- ❌ CHƯA XONG khác: **Gmail alert** (skill BƯỚC 5 — `alert.py` chỉ logging); ❌ Proxy chưa verify; ❌ mode download-theo-thiếu (tải PDF 2001-2025); ❌ Windows Task Scheduler task chưa cài trong schtasks (chỉ có .xml).

## Pitfall đã fix — ĐỪNG tái phạm (chi tiết trong memory `crawler-pitfalls-to-avoid`)
1. Download **không** dùng UA ngẫu nhiên/fake-useragent mỗi request → Vietstock trả 4xx. Dùng **browser UA ổn định**.
2. Pagination **không** dùng selector rộng (`[class*="next"]`, `a[href*="page"]`) — khớp sidebar → đi lạc trang. Scope vào `#report-paging`.
3. Playwright `page.goto()` tới URL download → lỗi "Download is starting". Dùng `context.request.get()`.
4. **Dedup đánh dấu "đã thấy" ngay cả khi download fail** → re-run không retry bản fail. Cần xoá row khỏi CSV trước khi crawl lại.
5. **CHƯA fix — extraction gán `date`=hôm nay khi card thiếu date rõ** → cột `date` sai (phồng năm gần, hút năm xa). `pdf_url` vẫn đúng. Xem Trạng thái.


# Project Quality Rules

> Project-agnostic quality gates. Stack specifics live in **Per-project setup** below (the only place). Source: `docs/proposed-repo-CLAUDE.md` (v1.0, 2026-07-09).

## Definition of Done
A task is done only when ALL are true:
- Code directly satisfies the requested change; no unrelated refactor.
- **Tests:** when behavior changes, write/run unit tests and ensure **>= 80% of the CHANGED lines are covered**, measured by **diff-coverage** (NOT total): produce a coverage report for the change, then run a diff-coverage gate. Ensure the change is committed/staged so the diff is measurable. (Commands in Per-project setup.)
- **Checks run:** run the project's test + lint commands — or mark `Not run` with a reason. Never claim a command passed unless it actually ran.
- **Lint scope:** exclude vendored / generated / third-party tooling directories from lint.
- **Code review (always):** must run `/bmad-code-review` and address findings before marking done. **Required for every change — including non-production (docs/config/scripts) — no exception.** Summarize result + actions in the report.
- **Summary report:** generate `docs/reports/<YYYY-MM-DD_HHMM>_summaryOfUpdate_report.md` (context-appropriate, not a rigid template).
- **Smoke (gate):** at least one smoke test (tagged `smoke`) runs one happy-path of a crawler/script on saved fixtures (no live sites). The smoke command **must pass before done**. Register the marker in `pyproject [tool.pytest.ini_options] markers`.
- **Impact analysis:** before a non-trivial change, identify blast radius — find callers/dependents/consumers (grep the symbol; check entry points: `merge_news.py`, `run_daily_all.ps1`, Task Scheduler `CrawlDailyNews`). Summarize what's affected + verified. Flag risk if blast radius is high and not fully test-covered.
- **Similar check:** after a fix/pattern change, grep the same idiom across the repo (e.g. the shared parse pattern in cafef/ssi/hsc/vndirect crawlers). Apply where applicable, or list remaining as follow-up. Don't fix one of N copies silently.

## Summary report (generated per change)
Generate a concise, context-appropriate markdown summary — `docs/reports/<YYYY-MM-DD_HHMM>_summaryOfUpdate_report.md`.
- Fit THIS change: include what's relevant, omit what's not — **except code review, which is always required and always summarized.**
- Cover, as applicable: what changed, files changed (path → purpose), tests + coverage %, `/code-review` result + actions, commands actually run, risks/follow-ups, a Definition-of-Done checklist.
- Be honest: state only what truly happened; write `Not run` (with reason) for anything skipped.

## Code hygiene (all languages)
- No hidden global state / unbounded in-process caches (use bounded TTL/size caches; externalize shared state to a managed store).
- No secrets in code (use `.env` / secrets manager).
- No hardcoded absolute local paths.
- No production logic that lives only in a notebook.

---

## Per-project setup (toolchain — the ONLY place stack specifics go)
- **Language / toolchain:** Python 3.13 (`.python-version`) + `uv`; async + Playwright (chromium, stealth) + requests + pandas.
- **Test command:** `uv run pytest`
- **Coverage + diff-coverage:** `uv run pytest --cov=<module> --cov-report=xml` then `uvx diff-cover coverage.xml --fail-under=80` (`diff-cover` in dev deps).
- **Lint command:** `uvx ruff check .`
- **Lint excludes (vendored/generated):** `.claude data aggregated docs pdf` (in `pyproject.toml [tool.ruff] extend-exclude`).
- **Smoke command:** `uv run pytest -m smoke`
- **Code-review tool:** `/code-review`
- **Language-specific extras (Python):** avoid bare `except` and mutable default args; type hints for public functions; `pathlib`; `PYTHONUTF8=1` on Windows; CSV `utf-8-sig`.
- **Domain constraint:** KHÔNG dùng Vietstock JSON API — chỉ browser/HTTP crawl. *(Exception: objective VN30 disclosure FR-16 uses `/data/EventsTypeData` — see Stack section above, authorized 2026-07-12.)*
