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

## 3. Vị trí dữ liệu & file

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
