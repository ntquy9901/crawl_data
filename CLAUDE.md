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
- `merge_csv.py` — gộp nhiều CSV backfill song song vào `data/data.csv`, dedup theo `pdf_url`, ưu tiên row có PDF.
- `cafef_crawler.py` + `cafef_config.py` — crawler tin tức Cafef: daily RSS (`--daily`) + backfill sitemap shards (`--backfill`).
- `base_news_crawler.py` — khung crawler tin tức tổng quát (Template Method). Mode `--latest` / `--range --from-date --end-date`.
- `ssi_crawler.py`, `hsc_crawler.py`, `vndirect_crawler.py` — 3 subclass CTCK research.
- `news_sitemap_crawler.py` — sitemap-shard metadata crawler cho 20+ nguồn (tuoitre/thanhnien/vietnamplus/vneconomy/baodautu/tinnhanhchungkhoan/vietnamnet/fica/theinvestor/nhipsongkinhdoanh/thuonghieucongluan/coin68/nhadautu/vietbao + cafebiz/thoibaotaichinhvietnam/vietnamfinance). Hỗ trợ: `ym_swapped` (VietnamNet MM-YYYY), `fetch_all_shards` (Fica non-date, coin68), slug-based title fallback, `news:title`/`image:title` embedded. `--source <tên> [--latest | --from-date/--end-date]`.
- `vietnambiz_crawler.py` — VietnamBiz RSS + listing backfill, 9 categories (thoi-su/doanh-nghiep/chung-khoan/tai-chinh/hang-hoa/nha-dat/kinh-doanh/quoc-te/du-bao). Subclass `BaseNewsCrawler`.
- `vnexpress_wayback_backfill.py` — Wayback Machine backfill cho vnexpress.net. `--target homepage|kinh-doanh`.
- `merge_news.py` — gộp tất cả nguồn → `data/news_articles.csv`. `morning_digest.py` — bản tin sáng markdown.
- `telegram_crawler.py` — Telegram public channel crawler, 8 channels.
- `overnight_process*.ps1` — 3 background processes chạy continuous crawl loop (30-60 min cycles).
- `utils/anti_bot.py`, `utils/dedup.py`, `utils/proxy_manager.py`, `utils/alert.py`.
- `run_crawler.ps1` + `task_scheduler.xml`. `run_daily_all.ps1` — daily schedule.
- `data/`: `*_articles.csv`, `news_articles.csv`, `pdf/`, `logs/`.

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

## Trạng thái (2026-07-23)
- ✅ Pagination (JS `#report-paging`), ✅ Captcha pause 5 phút + retry 3 lần, ✅ Download (browser UA + retry + `context.request.get()`), ✅ Date-bounded crawl, ✅ `--max-pages`/`--start-page`, ✅ `DOWNLOAD_PDF` toggle, ✅ **Window-crawl `--from-date`**, ✅ `merge_csv.py`.
- **Dataset Vietstock**: `data/vnstock_articles.csv` = **14.825 reports unique**, **2001–2026**, **2.336 PDF** (chỉ 2026).
- **News datasets** (cột `source`, schema chung): Dataset đã mở rộng 25+ nguồn (~2.48M rows merged):
  - Nguồn gốc: cafef 39.2k, ssi 210.5k, hsc 30, vndirect 53.7k
  - Sitemap cổ điển: tuoitre 283.6k, thanhnien 387.2k, vietnamplus 773.2k
  - Bổ sung 2026-07-22: vneconomy 224.9k, baodautu 158.5k, tinnhanhchungkhoan 329.9k, vnexpress 13.9k, forum 1.1k, telegram 4 channels 2.4k
  - Bổ sung 2026-07-23: **vietnamnet 1,191.6k** (MM-YYYY shards), **thuonghieucongluan 243.9k** (daily shards, 2013-2026), **coin68 23.9k** (crypto, fetch_all_shards), **fica 19.3k** (fetch_all_shards), **nhipsongkinhdoanh 17.5k** (21 shards 429), **vietbao 12.9k**, **cafebiz 7.0k**, **vietnambiz 1.7k** (9 categories), **vietnamfinance 1.0k**, **nhadautu 500**, **thoibaotaichinhvietnam 400**, **theinvestor 149**
  - Telegram: 8 channels ~4.3k rows
- **Vietstock verify**: dataset 14.825 tin cậy.
- **Hằng ngày**: Task Scheduler `CrawlDailyNews` @ 05:00 chạy `run_daily_all.ps1`. 3 `overnight_process*.ps1` chạy continuous crawl loop (30-60 min cycles).
- ✅ **Gap 2006-2007** = gap thật của site.
- ⚠️ **nhipsongkinhdoanh**: 21 shards HTTP 429, cần retry.
- ❌ CHƯA XONG: Gmail alert, proxy chưa verify, PDF 2001-2025 download, schtasks chưa cài.

## Pitfall đã fix — ĐỪNG tái phạm (chi tiết trong memory `crawler-pitfalls-to-avoid`)
1. Download **không** dùng UA ngẫu nhiên/fake-useragent mỗi request → Vietstock trả 4xx. Dùng **browser UA ổn định**.
2. Pagination **không** dùng selector rộng (`[class*="next"]`, `a[href*="page"]`) — khớp sidebar → đi lạc trang. Scope vào `#report-paging`.
3. Playwright `page.goto()` tới URL download → lỗi "Download is starting". Dùng `context.request.get()`.
4. **Dedup đánh dấu "đã thấy" ngay cả khi download fail** → re-run không retry bản fail. Cần xoá row khỏi CSV trước khi crawl lại.
5. **CHƯA fix — extraction gán `date`=hôm nay khi card thiếu date rõ** → cột `date` sai (phồng năm gần, hút năm xa). `pdf_url` vẫn đúng. Xem Trạng thái.

## 6. Clean Code (strict — tất cả ngôn ngữ)

- Viết code thể hiện rõ ý định qua tên có nghĩa và luồng điều khiển tường minh.
- Mỗi hàm một trách nhiệm, một mức trừu tượng. Dùng guard clause và early return thay cho if lồng sâu.
- Tách domain logic khỏi UI, HTTP, database, file I/O, framework.
- Không có global state biến đổi được, không cache in-process vô hạn (phải có TTL/size limit).
- Validate untrusted input tại biên hệ thống.
- Xử lý lỗi tường minh; không swallow exception, không dùng exception cho luồng điều khiển bình thường.
- Không duplicate business rule giữa các module. Ưu tiên small duplication hơn premature abstraction sai.
- Áp dụng KISS/YAGNI: không thêm speculative framework hay extension point.
- Comment phải giải thích **why** (ràng buộc, quyết định không hiển nhiên) — không restate code.
- Không hardcode secret, URL môi trường cụ thể, absolute local path, credential.
- Thay magic value bằng named constant có nghĩa.
- Module phải cohesive; không có dumping ground như `utils`, `helpers`, `misc`.
- Production logic trong module version-controlled/testable — không chỉ trong notebook.
- Tách pure computation khỏi I/O để business logic deterministic và testable.
- Inject dependency bên ngoài (clock, randomness, HTTP client, v.v.).
- Test deterministic, độc lập, Arrange–Act–Assert rõ ràng.
- Log actionable context (structured); không log secret hay dữ liệu cá nhân.
- Tối ưu chỉ sau khi đo lường, trừ khi ràng buộc hệ thống đã được ghi nhận.
- Xoá dead code — không comment out.
- Trong một focused change: không refactor không liên quan.
- Theo convention hiện tại của dự án, trừ khi thay đổi convention là một phần scope.

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
