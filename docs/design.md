# Thiết kế hệ thống crawl `crawl_data`

Project có **2 crawler sibling**, cùng output dạng CSV (UTF-8 BOM) trong `data/`:

| Crawler | File | Nguồn | Dữ liệu | Kỹ thuật |
|---|---|---|---|---|
| **Vietstock** | `crawler.py` | `finance.vietstock.vn/bao-cao-phan-tich` | Báo cáo phân tích (PDF) | Playwright (stealth) — site khoá listing ~1 năm |
| **Cafef** | `cafef_crawler.py` + `cafef_config.py` | `cafef.vn` (tin tức) | Bài viết thị trường | Plain HTTP (requests) — site mở, không cần browser |

Output: `data/vnstock_articles.csv` (~14.825 reports, 2001–2026) và `data/cafef_articles.csv` (tin tức 3 section).

---

## 1. Cafef crawler — kiến trúc

```
                       CAFEF CRAWLER — 2 mode
═══════════════════════════════════════════════════════════════════════════

 MODE 1 — DAILY (RSS)                  MODE 2 — BACKFILL (sitemap shards)
 ─────────────────────                 ───────────────────────────────────

 cafef.vn/<section>.rss                cafef.vn/sitemap.xml   (index)
        │                                     │
        ▼                                     ▼
 parse <item>                          shards_in_range(2016..nay)   ← lọc theo tháng
 (title, link, pubDate, lead)                 │
        │                                     ▼  (chỉ lần ĐẦU hoặc --refresh-shards)
        ▼                               quét 757 shard → parse <url>
 dedup (bỏ URL đã seen)                 (article_url, lastmod, image:title)
        │                                     │
        ▼                                     ▼
 append ──► cafef_articles.csv          ┌─────────────────────────────────┐
                                       │ CACHE  candidates                │
                                       │ data/cafef_candidates.jsonl     │ ◄─ resume lần sau:
                                       └─────────────────────────────────┘    load cache, BỎ qua quét shard
                                                     │
                                                     ▼
                                       todo = candidates − seen(cafef_articles.csv)
                                                     │
                                                     ▼
                          ┌──────── CLASSIFY song song (workers=10 luồng) ─────────┐
                          │  fetch trang bài (1 GET/bài)                           │
                          │    → breadcrumb @id  → slug section (CK/TC/Nhận định)  │
                          │    → og:description → lead                             │
                          │  GIỮ nếu section thuộc 3 mục; bỏ qua nếu không         │
                          └────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
                                       dedup + append (lô 200) ──► cafef_articles.csv
                                       dừng khi kept ≥ cap (--max-articles)
```

### 1.1. Hai mode

**Daily (RSS)** — `cafef_crawler.py --daily`
- Lấy `cafef.vn/<slug>.rss` mỗi section (50 item, ~3 ngày).
- Mỗi `<item>` đã có sẵn title/link/pubDate/description(lead) → không cần fetch trang bài.
- Dedup theo `article_url`, append vào `cafef_articles.csv`.
- Để chạy hằng ngày (Task Scheduler).

**Backfill (sitemap shards)** — `cafef_crawler.py --backfill --from-date YYYY-MM-DD`
- `cafef.vn/sitemap.xml` liệt kê 757 shard theo tháng (`sitemaps-YYYY-M-*.xml`, 2016→2026).
- Mỗi shard chứa `<url>` (article_url, lastmod, image:title) — **không tag section**.
- Phải fetch từng bài để classify section (qua breadcrumb JSON-LD `item.@id` → slug) + lấy lead (`og:description`). **1 GET/bài.**

### 1.2. Tham số

| Tham số | Ý nghĩa | Vì sao |
|---|---|---|
| `--max-articles` (cap) | Số bài **đã giữ** (thuộc 3 section) tối đa / 1 lần chạy. `0` = ∞ | Toàn bộ 2016–2026 ~1,5M bài, chỉ ~12–15% đúng section ⇒ classify hết = ~1,5M request ≈ 28h + dễ bị block IP. Cap tránh chạy vô tận. |
| `--workers` | Số luồng fetch song song (`ThreadPoolExecutor`) | `workers=10` = 10 trang bài tải cùng lúc → nhanh ~10×. Quá cao → cafef block (429/403). |
| `cache` (`cafef_candidates.jsonl`) + `--refresh-shards` | Snapshot danh sách candidate (URL+date+title) lấy từ shard | Lần đầu quét shard ~15–20 phút → ghi cache. Lần sau **load cache (giây)**, bỏ quét shard, chỉ classify tiếp bài chưa thu. `--refresh-shards` = xoá+build lại cache (lấy bài mới publish). |

### 1.3. Resumability
Backfill có thể bị kill giữa chừng (timeout/block) và chạy lại rẻ nhờ 2 cơ chế:
1. **Cache candidate** (`data/cafef_candidates.jsonl`): không phải quét lại 757 shard.
2. **Dedup theo `article_url`**: đọc `cafef_articles.csv` thành set `seen` → bỏ qua bài đã thu, chỉ classify phần còn lại.

### 1.4. Section mapping
Người dùng chọn 3 nhóm → slug thật của cafef (lấy từ `cafef.vn/sitemaps/category.rss`; cafef **không** có `tai-chinh`/`nhan-dinh`/`chung-khoan` — đều 404):

| Nhóm | Slug |
|---|---|
| Chứng khoán | `thi-truong-chung-khoan` |
| Tài chính | `tai-chinh-ngan-hang` |
| Nhận định | `vi-mo-dau-tu` |

### 1.5. Ràng buộc / phát hiện
- **Sitemap floor = 2016** (757 shard, 2016-01 → 2026-07). Cafef không sitemap hoá 2001–2015 ⇒ "backfill đến 2001" thực tế bắt đầu 2016.
- **Scale**: ~400 bài/ngày toàn section ⇒ ~1,5M bài 2016–2026, ~12–15% thuộc 3 section. Full classify ~28h + risk block → dùng cap.
- **`articleSection` (JSON-LD) = null** → phải dùng breadcrumb `item.@id` (URL section) để classify, không dùng label text (giảm brittle).
- **robots.txt `Allow: /`**, server-rendered HTML, không Cloudflare → plain HTTP đủ, không cần Playwright.

---

## 2. Vietstock crawler — tóm tắt (`crawler.py`)

Khác Cafef ở chỗ Vietstock **khoá listing mặc định ~1 năm** và nhạy UA → **bắt buộc Playwright stealth**.

- 2 mode: `crawl()` (pagination thường, window mặc định) và `crawl_by_windows()` (`--from-date` — set `#fromDate/#toDate` + click `#btnSearchEDoc` để tới dữ liệu cũ, chia window 6 tháng).
- Reuse: `utils/anti_bot.py` (stealth browser, `safe_goto`/`safe_click`), `utils/dedup.py` (DedupManager, hardcoded `pdf_url`), `utils/alert.py` (captcha detect), `utils/proxy_manager.py` (dormant).
- Download PDF: browser UA ổn định + retry + `context.request.get()` (không `page.goto()` → "Download is starting").
- Resilience (2026-07-05): `crawl_by_windows` retry navigate/apply + cảnh báo window 0-yield (vì backfill dài từng miss cục bộ 2015–2016 do captcha/timeout tạm thời).

---

## 3. Playwright — khi nào & cách dùng (tái sử dụng cho dự án khác)

### Khi nào dùng Playwright (vs plain HTTP `requests`)
Dùng Playwright (browser thật) khi site có ≥1 dấu hiệu:
- **Cloudflare / anti-bot** (challenge "Just a moment", HTTP 403 với `requests` dù UA đúng). VD: **VNDIRECT** (verify 2026-07-05: 403, `server: cloudflare`, `cf-ray`).
- **JS-rendered** (nội dung load bằng JS/AJAX, HTML thô trống). VD: Vietstock (`#report-content` refresh qua AJAX).
- **Listing khoá theo thời gian** cần click UI / set datepicker để tới dữ liệu cũ. VD: Vietstock (`#fromDate/#toDate` + `#btnSearchEDoc`).
- **Download trigger** cần session/cookie của browser.

Còn nếu site **server-rendered HTML, không Cloudflare** (SSI, HSC, Cafef) → `requests` đủ, **không** dùng Playwright (chậm hơn nhiều).

### Layer tái sử dụng: `utils/anti_bot.py` (site-agnostic)
Toàn bộ setup browser tách sẵn trong `utils/anti_bot.py`, dùng lại cho mọi site:

```python
from utils.anti_bot import (create_stealth_browser, safe_goto, safe_click,
                             human_like_scroll, random_delay)
from utils.alert import CaptchaDetector, AlertManager

browser, context, page = await create_stealth_browser(headless=True)   # playwright-stealth + fake-useragent + chromium
ok = await safe_goto(page, url, max_retries=3)                          # retry + captcha detect
await safe_click(page, "#btnSearchEDoc", timeout=10000)                 # retry click
await human_like_scroll(page, max_scrolls=3)                            # giả hành vi người
# download file: DÙNG context.request.get (share cookie+UA), KHÔNG page.goto(url_pdf)
resp = await context.request.get(pdf_url, headers={"User-Agent": browser_ua})
```

`create_stealth_browser` đã bật stealth (che `navigator.webdriver`), locale `vi-VN`, timezone `Asia/Ho_Chi_Minh`, viewport thật. Capture UA thật (`await page.evaluate("navigator.userAgent")`) rồi **dùng cố định** cho mọi HTTP download (Vietstock reject UA đổi mỗi request).

### Flow chuẩn (template)
```
init_browser  (create_stealth_browser + capture UA)
loop {
  navigate_to_target  (safe_goto + CaptchaDetector → pause 5 phút + retry nếu captcha)
  extract items       (page.query_selector_all / page.eval_on_selector_all)
  for each item:      (date-filter → dedup →) download via context.request.get
  handle_pagination   (click control CỤ THỂ, đợi DOM đổi) → next page
}
close_browser
```

### ĐỪNG tái phạm (từng bug — xem memory `crawler-pitfalls-to-avoid`)
1. **UA download**: dùng UA **cố định** (browser UA), không fake-useragent per-request → Vietstock trả 4xx.
2. **Pagination selector**: scope **cụ thể** (`#report-paging li.next a`), KHÔNG `[class*="next"]`/`a[href*="page"]` (khớp sidebar → lạc trang).
3. **Download**: `context.request.get(url)`, KHÔNG `page.goto(url)` (→ exception "Download is starting").
4. **Captcha**: detect (keyword + HTTP 403/429/5xx) → pause 5 phút + retry, đừng crash.
5. **Dedup**: đánh dấu seen cả khi download fail → re-run skip bản fail (cần xoá row trước khi crawl lại).
6. **Date**: KHÔNG fallback `now()` khi card thiếu date (→ stray-date). Để rỗng hoặc parse kỹ.

### Áp dụng cho VNDIRECT (Cloudflare)
VNDIRECT trả **403** với `requests` (Cloudflare "Just a moment") → cần Playwright: subclass `BaseNewsCrawler`, override `fetch()` bằng `safe_goto(page, url)` + đọc `page.content()` (browser thật vượt challenge). Giữ nguyên hooks `parse_listing`/`parse_article`. Trade-off: chậm hơn (1 browser tuần tự), nhưng vượt được Cloudflare. (Chưa build — quyết định của user.)

---

## 4. News crawler framework — `BaseNewsCrawler` (SSI / HSC / VNDIRECT)

Khung chung (Template Method) cho crawler tin tức/báo cáo **plain HTTP**. Subclass chỉ
override vài hook → thêm nguồn mới = 1 file ~50 dòng. File: `base_news_crawler.py`.

**Hooks (subclass ghi đè):** `source` (→ cột `source`), `listing_url(page)`, `parse_listing(html,page)` → items, `parse_article(html,item)` → fields, `next_page(cur,html)`.
**Flow chung (base):** listing → parse → dedup theo `url` (resume không lấy lại) → fetch song song (`--workers`) → append theo lô (`--batch`) → audit log `logs/<source>_audit.log`.
**Modes:** `--latest` (tin mới nhất / daily), `--range --from-date --end-date` (khoảng ngày). **Schema** có cột `source` bắt buộc (lưu vết nguồn).

**Subclass đã build:**
| Nguồn | File | Kiểu | Login | Đặc điểm |
|---|---|---|---|---|
| **SSI** | `ssi_crawler.py` | PDF bulletins (Bản Tin Thị Trường) | Không | Listing-complete (title+lead+date+pdf link trong listing → không fetch từng bài); `?page=N`, ~217 trang |
| **HSC** | `hsc_crawler.py` | HTML article (Research Insights) | Không | Next.js SSR, listing 1 trang (daily-only); **không lộ publish date** → cột `pub_date` rỗng (HSC site limitation) |
| **VNDIRECT** | *(chưa build)* | HTML + PDF | — | **Cloudflare 403** với plain HTTP → cần Playwright (xem §3); chưa build |

**Output:** `data/ssi_articles.csv`, `data/hsc_articles.csv` (cùng schema, cột `source`).

**Reuse cho dự án khác:** copy `base_news_crawler.py` + viết 1 subclass override `source`/`listing_url`/`parse_listing`/`parse_article`. Nếu site Cloudflare/JS → dùng Playwright (§3) thay `requests`.

---

## 5. Vị trí dữ liệu & file

```
data/
  vnstock_articles.csv      # 14.825 reports Vietstock (gộp 3 nguồn + re-crawl 2015-2018)
  cafef_articles.csv        # tin tức Cafef (daily + backfill)
  cafef_candidates.jsonl    # cache candidate cho backfill (gitignored cùng data/)
  pdf/                      # 2.336 PDF Vietstock (kỳ gần)
docs/
  design.md                 # file này
  vnstock_articles.md       # dataset card Vietstock
  source-news-download-guideline/  # guideline gốc → skill
.claude/skills/source-news-download/SKILL.md   # skill chọn nguồn
```

`data/`, `logs/`, `.env`, `proxies.txt`, `cafef_candidates.jsonl` đều gitignored (nặng / local).
