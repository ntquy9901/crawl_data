# Addendum — Objective Vietnam Stock Data Crawler PRD

*Technical-how, source-access detail, options-considered. Lives here, not in the PRD. Distilled from empirical probes (2026-07-11) + existing-project extraction.*

## A. Source Access Digest (empirically probed 2026-07-11)

### HNX (`hnx.vn`) — EASY HTTP ✅
- Listing: `https://hnx.vn/thong-tin-cong-bo-up-hnx.html` — **server-rendered HTML** (~95KB, 10 dòng đầu inline).
- Pagination: POST AJAX `/ModuleArticles/ArticlesCPEtfs/NextPageTCPHUpCoM` (+ `NextPageTinUpCoM`, `PopupTinCongBoDetail`, `ArticlesFileAttach`) — cần `Content-Length` + `X-Requested-With: XMLHttpRequest` + session cookie ấm.
- Anti-bot: không (no Cloudflare/captcha). `X-Frame-Options: DENY`.
- Backfill: disclosure-ID tuần tự (~600k+), đa năm.
- **Adapter:** subclass `BaseNewsCrawler`, override `parse_listing` (server HTML) + `next_page` (POST AJAX).

### UPCoM (cùng `hnx.vn`) — EASY HTTP ✅
- Listing: `/thong-tin-cong-bo-up-com.html` (tab `TinTCPHChuaGD`/`TinUpCoM`).
- Cùng stack HNX, endpoint `NextPageTinUpCoM`. **Chia sẻ adapter HNX**, khác tab/endpoint.

### VSDC (`vsd.vn`) — EASY HTTP ✅ (cleanest)
- Detail: `https://vsd.vn/vi/ad/{id}` — **server-rendered ASP.NET (IIS/10.0)**, GET trả full ~63KB HTML. ID **50000→198000+** đều HTTP 200 (quét sweep full backfill).
- Listing gần đây: `/vi/tin-tuc` expose link `/vi/ad/*`.
- Anti-bot: không Cloudflare. Cookie `__VPToken` (ASP.NET anti-forgery) chỉ cần cho POST form, không cho GET read. **HEAD trả 405 — dùng GET.**
- **Adapter:** subclass `BaseNewsCrawler`, `listing_url` = ID sweep (range 50000→current), `parse_article` = detail HTML.

### SSC (`ssc.gov.vn`) — NEEDS PLAYWRIGHT ⚠️
- Stack: **Oracle ADF / WebCenter Portal** (JSF postback). Plain GET `/webcenter/portal/ubck` trả shell 6.7KB, **0 content tag** (render via ADF postback + JS — `AdfLoopbackUtils`, `_afrLoop` cookie, `javax.faces.ViewState`).
- Penalty detail: `/webcenter/portal/ssc/.../chitit?dDocName=APPSSCGOVVN...`.
- **Adapter:** override `fetch()` dùng Playwright (`safe_goto` + `page.content()`), pattern như VNDIRECT.

### HOSE (`hsx.vn`) — HARD 🔴 (ToS risk)
- **React SPA** — HTML chỉ shell `<div id="HOSE">` + `<noscript>`. Bundle gọi `https://api.hsx.vn/{n,c,l,mk,s,q,i,hub}/api/v1/...` với **Bearer token** (OAuth qua `gateway-delight.cocome.vn/.../refresh_token` — SSO "cocome"). Mọi probe **404/empty không token**.
- **Options-considered:**
  1. Reverse-engineer OAuth cocome → **loại** (vi phạm ToS, brittle).
  2. Playwright headless → để SPA tự gọi API trong-browser → **khả thi nhưng tốn** (chỉ FR-6 deferred).
  3. **Skip / defer** → ưu tiên HNX/VSDC repub phần lớn disclosure → **khuyến nghị** (xem OQ-2).

### Company IR — KHÔNG đáng ❌
- Heterogeneous (mỗi công ty 1 site: `l40.com.vn`, `tteg.vn`, `bidv.com.vn`...). Vài HTML paginate sạch (TTEG `?page=N`), vài custom. **N adapter cho N công ty**, trùng dữ liệu sàn đã pub → không worth.

### Tier-2 News: VnExpress (`vnexpress.net`) — EASY HTTP ✅ (deferred, needs NLP)
- RSS: `/rss/kinh-doanh.rss` (~60 items), `/rss/kinh-doanh/chung-khoan.rss`. Sitemaps: `sitemap.xml`, `google-news-sitemap.xml`. `robots.txt: Allow: /`. HEAD 406 (cần UA/Accept header đúng). Không Cloudflare.
- **Caveat:** news không có `company_code`/`event_type` native → cần NLP/NER (downstream).

## B. Reuse Infrastructure (brownfield)

`BaseNewsCrawler` (`base_news_crawler.py`) — Template Method. Adapter Tier-1 mới override:
- `source` — CSV column + audit-log key.
- `base_url`, `listing_url(page)` — URL listing (hoặc ID sweep cho VSDC).
- `parse_listing(html, page) -> list[dict]` — mỗi item: `url`, optional `title/pub_date/category`.
- `parse_article(html, item) -> dict` — trả `lead/author/category/pdf_url/body` (default `og:description`).
- `next_page(cur, html)` — pagination (POST AJAX cho HNX, ID increment cho VSDC).

Base cung cấp: `fetch()` (retry `requests` stable UA), date-range filter (`--from-date/--end-date`), resume URL-dedup (`_load_seen`), ThreadPoolExecutor (`--workers`), batch append (`--batch`), audit log, shared CLI (`--latest`/`--range`).
- Body extraction: `utils/body_extractor.py` — thêm XPath/source vào `SOURCE_XPATH`, gọi `extract_html_body(html, source)` trong `parse_article`; PDF qua `extract_pdf_body()`.
- Dedup: tự động trong base (URL-based). `utils/dedup.py` (`DedupManager`, key `pdf_url`) là legacy Vietstock-only — không cần cho adapter mới.
- Cloudflare/JS: override `fetch()` dùng Playwright (pattern VNDIRECT).
- Config: sibling file `<source>_config.py`; output `data/<source>_articles.csv` (`utf-8-sig` BOM).

## C. Schema Mapping (current → guide target)

Current canonical (`BaseNewsCrawler`, ssi/hsc/vndirect): `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`.
Vietstock (legacy): `id, title, source, date, pdf_url, pdf_filename, downloaded_at` (schema cũ). Cafef: `id, title, section, pub_date, article_url, author, lead, collected_at, body`.

Guide target (FR-8): `document_id, source, url, publish_time(UTC), crawl_time(UTC), company_code, company_name, title, raw_text, language, category, event_type, attachment_urls, checksum`.

**Delta cần thêm:** `company_code`, `company_name`, `event_type`, `attachment_urls`, `checksum`, `publish_time`/`crawl_time` (UTC chuẩn hóa), `language`. `raw_text` ≈ `body`/`lead`. Giữ `pdf_url`/`pdf_filename` mapping sang `attachment_urls`.

## D. Legal/ToS Posture
- **Thông tư 96/2020/TT-BTC** — công ty niêm yết bắt buộc công bố thông tin trên sàn/VSDC/IR → **public by law**. Không ToS nào cấm scrape, không Cloudflare/captcha ở HNX/VSDC/SSC.
- **Nghị định 13/2023 (PDPD)** — áp dụng nếu bắt personal data (tên cá nhân trong quyết định xử phạt SSC, insider trading) → cần redaction/loại bỏ (xem OQ-5).
- **HOSE OAuth** — reverse-engineer token vi phạm ToS → tránh, dùng HTML path (HNX/VSDC).
