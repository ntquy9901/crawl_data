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
Mỗi crawler có cột `source` ghi nguồn (lưu vết/phân loại) + dedup riêng (resumable). Chạy định kỳ qua Windows Task Scheduler (`run_daily_all.ps1`).

## Stack & ràng buộc
- Python 3.11 (async) + Playwright (chromium, stealth) + playwright-stealth + fake-useragent; requests (download), pandas (CSV), python-dotenv, aiohttp.
- **KHÔNG dùng Vietstock JSON API** (giới hạn truy cập) — chỉ browser crawl.

## Cấu trúc
- `crawler.py` — script chính, class `VietstockCrawler`. Flow: `init_browser` → loop {navigate/paginate → `extract_report_links` → `_collect_reports` (date-filter → dedup → `download_pdf` nếu `DOWNLOAD_PDF` → `save_to_csv`)}. Hai mode: `crawl()` (pagination thường, trong window mặc định ~1 năm) và `crawl_by_windows()` (`--from-date` — set filter `#fromDate/#toDate` + click `#btnSearchEDoc` để tới dữ liệu cũ).
- `config.py` — constants từ `.env` (`CAPTCHA_PAUSE_MINUTES=5`, `CAPTCHA_MAX_RETRIES=3`, `RANDOM_DELAY` 3–8s, `DOWNLOAD_PDF=false`, paths, CSV_HEADERS).
- `merge_csv.py` — gộp nhiều CSV backfill song song vào `data/data.csv`, dedup theo `pdf_url`, ưu tiên row có PDF. `python merge_csv.py --inputs <files> [--dry-run]`.
- `cafef_crawler.py` + `cafef_config.py` — crawler tin tức Cafef (sibling của Vietstock): daily RSS (`--daily`) + backfill sitemap shards (`--backfill`, classify section bằng breadcrumb). Self-contained (riêng dedup, không đụng `utils/dedup.py`). Output `data/cafef_articles.csv`.
- `base_news_crawler.py` — khung crawler tin tức **tổng quát** (Template Method: subclass override `source`/`listing_url`/`parse_listing`/`parse_article`/`next_page`; base lo flow + dedup + `--workers`/`--batch` + audit log `logs/<source>_audit.log` + resume theo url). Mode `--latest` (daily) / `--range --from-date --end-date`.
- `ssi_crawler.py` (PDF bulletins, listing-complete), `hsc_crawler.py` (Research Insights, daily-only, không có pub_date), `vndirect_crawler.py` (research notes, **Playwright-stealth vượt Cloudflare**, `--category company/sector/strategy/economics-note`) — 3 subclass. Output `data/<source>_articles.csv` (cột `source` ghi nguồn).
- `merge_news.py` — gộp cafef/ssi/hsc/vndirect → `data/news_articles.csv` (schema chung, cột `source`, dedup theo url). `morning_digest.py` — tạo bản tin sáng markdown (`data/digest_YYYY-MM-DD.md`) từ bài mới nhất, nhóm theo nguồn — đọc trước khi đầu tư.
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
powershell -ExecutionPolicy Bypass -File run_daily_all.ps1                      # chạy tất cả daily 1 lệnh
```
Flags: `--start-date/--end-date` (per-report filter trong window mặc định), `--from-date` (window-crawl tới dữ liệu cũ, `--window-months N` mặc định 6), `--max-pages N` (0=∞), `--test`, `--headless true|false`.
`DOWNLOAD_PDF=false` (mặc định `.env`) = chỉ metadata, bỏ download + delay → crawl nhanh nhất. Bật `DOWNLOAD_PDF=true` để tải PDF.
Luôn set `PYTHONUTF8=1` trên Windows (CSV luôn UTF-8 BOM).

## Trạng thái (2026-07-05)
- ✅ Pagination (JS `#report-paging`), ✅ Captcha pause 5 phút + retry 3 lần, ✅ Download (browser UA + retry + `context.request.get()`), ✅ Date-bounded crawl, ✅ `--max-pages`/`--start-page`, ✅ `DOWNLOAD_PDF` toggle (default false = metadata-only nhanh), ✅ **Window-crawl `--from-date`** (lấy dữ liệu cũ qua date filter — listing mặc định khoá ~1 năm), ✅ `merge_csv.py` (gộp backfill song song).
- **Dataset Vietstock**: `data/vnstock_articles.csv` = **14.825 reports unique** (theo `pdf_url`; gộp `data.csv` + `data_archive.csv` + `data_2021_2025.csv` + re-crawl 2015–2018), **2001–2026**, **2.336 PDF** (chỉ 2026; 2001-2025 metadata-only).
- **News datasets** (cột `source`, schema chung): `cafef_articles.csv` ~3.348 (daily RSS tích lũy; **backfill sâu bị cafef throttle ở mọi concurrency** — workers=4 vẫn 0 kept — nên defer, dựa vào daily RSS), `ssi_articles.csv` ~1.860 (đã đủ ~217 trang), `hsc_articles.csv` ~6 (HSC ít + **không pub_date**), `vndirect_articles.csv` ~967 (đã đủ 4 category company/sector/strategy/economics-note, 2016–2026, Playwright-stealth).
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
