---
title: Objective Vietnam Stock Data Crawler
status: final
created: 2026-07-11
updated: 2026-07-11
---

# PRD: Objective Vietnam Stock Data Crawler
*Status: FINAL (2026-07-11). Fast path — iterated with stakeholder; OQ-3/4/5 deferred to architecture.*

## 0. Document Purpose

PRD cho hệ thống **crawl dữ liệu khách quan, primary-source** thị trường chứng khoán Việt Nam, phục vụ dataset cho model dự báo biến động giá (theo `docs/guide/Vietnam_Stock_Objective_Data_Crawling_Guide.md`). Dành cho: chủ sở hữu model (downstream), kiến trúc sư (architecture kế tiếp), dev thực thi (stories). Cấu trúc: Glossary-anchored vocabulary, Features gộp nhóm với FR lồng trong và ID toàn cục ổn định, giả định đánh tag inline `[ASSUMPTION]` và liệt kê ở §9. Chi tiết kỹ thuật truy cập từng nguồn nằm trong `addendum.md` (không thuộc PRD).

**Bối quan trọng:** downstream consumer thực sự là **model dự báo biến động VN30** (LSTM-GNN Parkinson, `docs/MACRO_FEATURES_PLAN.md`, horizon 1/5/10/22-day) — KHÔNG phải FinMarBa (dataset sentiment Mỹ/toàn cầu, không liên quan VN). Brownfield: mở rộng `crawl_data` hiện có, tái dùng `BaseNewsCrawler`, `utils/body_extractor`, dedup, config layers, scheduler.

## 1. Vision

Hệ thống thu thập **dữ liệu khách quan, chính thống** từ các nguồn primary (sàn giao dịch, lưu ký, ủy ban) — những thông tin mà pháp luật bắt buộc công bố (Thông tư 96/2020/TT-BTC) — thay vì ý kiến/broker research/aggregated analysis. Mỗi tài liệu được giữ nguyên dạng raw (HTML/PDF) kèm metadata chuẩn, tách bạch lớp raw/cleaned/feature, dedup theo checksum+URL, timestamp UTC, dataset có version — tạo dataset tái lập được cho model dự báo biến động.

Matters vì: model dự báo biến động cần tín hiệu sự kiện khách quan (công bố thông tin, hành động doanh nghiệp, biến động cổ đông); dataset hiện tại của project thiên về opinion (Vietstock analysis, broker research) — thứ mà guide và FinMarBa đều khuyến cáo **tránh** để không thêm thiên kiến.

## 2. Target User

### 2.1 Jobs To Be Done
- **Functional:** "Là người xây model volatility, tôi cần dataset sự kiện khách quan (công bố thông tin, corporate actions) của các mã VN mục tiêu, cập nhật hằng ngày và backfill sâu, để làm feature cho model — mà không lo lẫn opinion/độ tin cậy nguồn."
- **Functional:** "Là data engineer, tôi cần crawler resumable, lịch chạy hằng ngày, audit rõ, để vận hành tin cậy lâu dài mà không cào lại dữ liệu đã có."
- **Contextual:** tách bạch raw (giữ nguyên cho reproduce) khỏi cleaned/feature (cho model).

### 2.2 Non-Users (v1)
- Người dùng cuối sản phẩm tài chính (không có UI; đây là data pipeline nội bộ).
- Consumer của NLP/sentiment/embedding — thuộc downstream layer riêng (ngoài scope v1, xem §5).

### 2.3 Key User Journey (light)
- **UJ-1. Ntquy nạp feature sự kiện trước phiên giao dịch.** Mỗi sáng (sau job scheduled 05:00), dataset objective mới nhất đã sẵn sàng ở cleaned layer: các công bố thông tin + corporate actions của mã VN30 hôm qua, deduped, có company_code/event_type. Mở dataset → join với price/macro → train/feature. *Climax:* dataset sẵn sàng dùng, metadata đủ trường để join theo company_code + publish_time.

## 3. Glossary

- **Disclosure (Công bố thông tin)** — thông tin pháp định công ty niêm yết bắt buộc công bố (TL 96/2020). Cardinality: nhiều disclosure / công ty / ngày.
- **Primary Source (Nguồn chính thống)** — bên phát hành gốc (sàn HOSE/HNX/UPCoM, lưu ký VSDC, ủy ban SSC, IR công ty). Đối lập secondary/aggregated.
- **Objective Data (Dữ liệu khách quan)** — sự kiện/số liệu thực từ primary source, loại trừ opinion/recommendation/commentary.
- **Corporate Action (Hành động doanh nghiệp)** — dividend, stock split, rights issue, bond issuance, M&A, exec change, shareholder change, ESOP, stock issuance.
- **company_code** — mã ticker (vd VNM, HPG). Khóa join với price/macro.
- **event_type** — phân loại disclosure theo taxonomy sự kiện (xem §8 OQ-4).
- **Metadata Schema** — bộ trường chuẩn lưu cho mỗi document (§4.5, FR-8).
- **Raw / Cleaned / Feature layer** — 3 lớp dữ liệu: raw (bytes gốc, reproduce), cleaned (text + metadata chuẩn), feature (downstream NLP/model — ngoài v1).
- **Resumable crawl** — re-run bỏ qua URL đã seen (URL-dedup), không cào lại.
- **VN30 Universe** — 30 cổ phiếu bluechip lớn nhất **HOSE** (chỉ số VN30, rebalance 6 tháng/lần). Toàn bộ scope crawler filter theo list này. **Lưu ý cấu trúc: HNX/UPCoM (sàn Hà Nội) KHÔNG chứa mã VN30** → disclosure chính thức của VN30 nằm ở **HOSE** (khó) hoặc republish Tier-3 (Vietstock/Cafef).

## 4. Features

### 4.1 HNX & UPCoM Disclosure Ingestion (NOT VN30 — demoted)
> ⚠️ **Scope note (sau khi chốt universe VN30):** HNX/UPCoM là sàn Hà Nội; **VN30 = mã HOSE** → HNX/UPCoM **KHÔNG chứa mã VN30**. FR-1,2,3 **demoted — out of VN30 MVP**. Giữ adapter-note (addendum) để re-enable nếu universe mở rộng ra HNX/UPCoM sau này.
**Description:** Crawl công bố thông tin của công ty niêm yết trên HNX và UPCoM từ `hnx.vn` (cùng site/stack, tab khác). Server-rendered HTML + phân trang AJAX, không anti-bot, backfill đa năm theo disclosure-ID tuần tự. Realizes UJ-1. Chi tiết endpoint trong `addendum.md`.

**Functional Requirements:**

#### FR-1: Ingest HNX disclosures
Hệ thống thu thập mọi disclosure mới công bố trên HNX (`thong-tin-cong-bo-up-hnx.html`) cho các mã trong target universe: listing (server-rendered page 1) + phân trang AJAX với session ấm + header `X-Requested-With`, rồi lấy chi tiết từng disclosure.
**Consequences:**
- Mọi disclosure ID mới xuất hiện trong listing được capture trong ≤1 chu kỳ crawl.
- Phân trang AJAX trả về HTML dòng (không phải JSON) — parse được title/pub_date/attachment.
- Không bị block (no Cloudflare/captcha đã verify).

#### FR-2: Ingest UPCoM disclosures
Như FR-1 nhưng cho thị trường UPCoM (`thong-tin-cong-bo-up-com.html`, endpoint `NextPageTinUpCoM`) — chia sẻ adapter, khác tab/endpoint.
**Consequences:**
- UPCoM disclosures capture song song HNX, cùng schema.

#### FR-3: Backfill lịch sử HNX/UPCoM
Backfill đa năm qua quét disclosure-ID tuần tự (~600k+, depth đa năm đã verify).
**Consequences:**
- Re-run backfill resumable (bỏ qua ID đã có), không cào lại.

### 4.2 VSDC Corporate-Action Ingestion (MVP)
**Description:** Crawl thông báo hành động doanh nghiệp + biến động cổ đông từ `vsd.vn` (`/vi/ad/{id}`, ASP.NET server-rendered) bằng quét ID tuần tự (50k→198k+, đa năm). Nguồn sạch nhất cho shareholder changes/corporate actions. Realizes UJ-1.

#### FR-4: Ingest VSDC corporate actions
Hệ thống thu thập mọi thông báo VSDC (`/vi/ad/{id}`): parse title, publish_time, company_code, event_type, attachments, raw HTML.
**Consequences:**
- GET trực tiếp trả full HTML (63KB), không cần JS.
- HEAD trả 405 — dùng GET.

#### FR-5: Backfill VSDC
Quét ID tuần tự 50000→hiện tại, đa năm.
**Consequences:**
- Mọi ID HTTP 200 (đã verify) → backfill full depth.

### 4.3 HOSE Disclosure Ingestion (OUT — superseded by Tier-3)
**Description:** HOSE (`hsx.vn`) React SPA + `api.hsx.vn` **OAuth-gated** — HARD, ToS risk. **Quyết định (OQ-2 resolved): dùng Tier-3 republish (Vietstock/Cafef disclosure sections — §4.9) thay vì HOSE-direct.** FR-6 dropped khỏi scope; re-evaluate chỉ nếu Tier-3 thiếu data HOSE-exclusive mà model cần.

#### FR-6: Ingest HOSE disclosures (deferred)
Hệ thống thu thập disclosure HOSE qua Playwright headless (render SPA, để page tự gọi API).
**Out of Scope (MVP):** OAuth reverse-engineering (ToS risk).

### 4.4 SSC Regulatory Ingestion (DEFERRED — Playwright)
**Description:** SSC (`ssc.gov.vn`) dùng Oracle ADF/WebCenter (JSF postback); plain GET trả shell rỗng 0 nội dung → cần Playwright render. Penalty/announcement archive đa năm.

#### FR-7: Ingest SSC penalties/announcements (deferred)
Hệ thống thu thập quyết định xử phạt/thông báo SSC qua Playwright.

### 4.5 Unified Metadata Schema & Raw Preservation (cross-cutting)
**Description:** Mọi document lưu theo Metadata Schema chuẩn (guide §Metadata Schema), giàu hơn schema `BaseNewsCrawler` hiện tại (thêm company_code, company_name, event_type, attachment_urls, checksum, publish_time UTC). Giữ raw bytes ở raw layer để reproduce.

#### FR-8: Canonical Metadata Schema
Mỗi document lưu đủ trường: `document_id, source, url, publish_time(UTC), crawl_time(UTC), company_code, company_name, title, raw_text, language, category, event_type, attachment_urls, checksum`.
**Consequences:**
- ≥ [ASSUMPTION: 95%] rows có company_code + event_type không null (sau parse).
- publish_time/crawl_time ở UTC (guide best practice).

#### FR-9: Preserve raw layer
Giữ raw HTML/PDF bytes (raw layer) tách khỏi cleaned/feature layer.
**Consequences:**
- Dataset tái lập được từ raw tại mọi thời điểm.

### 4.6 Data Quality, Dedup & Governance (cross-cutting)
#### FR-10: Dedup by checksum + URL
Dedup nội dung (checksum) VÀ url — tránh trùng gần-duplicate (cùng sự kiện repub nhiều nguồn).
#### FR-11: Resumable
Re-run bỏ qua URL đã seen (URL-dedup, pattern `BaseNewsCrawler._load_seen`) — không re-fetch.
#### FR-12: Dataset versioning
Snapshot version dataset (mỗi release có version) cho reproduce model.
#### FR-13: Separate objective from opinion
Không bao giờ mix objective events với analyst opinions trong cùng training dataset — tách lớp, objective-only.
**Out of Scope:** refactor opinion crawlers hiện tại (giữ nguyên tách riêng, theo quyết định scope).

### 4.7 Scheduling & Freshness
#### FR-14: Daily scheduled ingestion
Job scheduled hằng ngày (mở rộng Task Scheduler / `run_daily_all.ps1` hiện có) thu thập disclosure mới + macro (reuse). Hoàn thành trước 06:00.
**Consequences:**
- Dataset cleaned layer cập nhật mỗi sáng trước phiên.

### 4.8 Tier-2 News Media Ingestion (raw capture v1; enrichment needs NLP)
**Description:** Crawl **toàn bộ** tin tức khách quan từ báo chí chính thống Tier-2 (guide list + VnExpress theo yêu cầu): **VnExpress, VnEconomy, VietnamPlus, Báo Đầu tư, Báo Chính phủ, TTXVN, Tuổi Trẻ, Thanh Niên, Người Lao Động, Kinh tế Sài Gòn**. Đa số báo VN có RSS/sitemap → **raw capture EASY HTTP** (reuse `BaseNewsCrawler` + pattern RSS crawler cafef — mỗi báo 1 subclass nhỏ, section kinh doanh/chứng khoán). Đã verify VnExpress: RSS `/rss/kinh-doanh.rss` + `/rss/kinh-doanh/chung-khoan.rss`, sitemaps (incl. `google-news-sitemap.xml`), `robots Allow: /`. `[ASSUMPTION: raw capture rẻ, làm được v1; NHƯNG tin tức KHÔNG có company_code/event_type native như disclosure sàn → enrichment (extract ticker + event_type) cần NLP/NER downstream. Tức corpus raw có sớm, gắn ticker cho model thì chờ NLP phase.]`

#### FR-15: Ingest Tier-2 objective news (raw capture)
Hệ thống thu thập tin tức kinh doanh/chứng khoán từ **toàn bộ** 10 báo Tier-2 — filter chỉ objective company/industry/macro news, **tránh** opinion/commentary/market-recommendation (guide Tier-2 rule). Mỗi nguồn 1 adapter subclass `BaseNewsCrawler` (RSS/sitemap).
**Consequences:**
- Raw news capture đủ 10 outlet, metadata chuẩn (`title, pub_date, url, body, source, section`); `company_code`/`event_type` = null tới khi có NLP.
**Out of Scope:** event/ticker extraction từ text tin tức (NLP layer — downstream PRD).

### 4.9 VN30 Disclosure via Tier-3 Republish (MVP)
**Description:** Lấy disclosure VN30 (BC tài chính, nghị quyết HĐQT, cổ tức, phát hành cổ phiếu, ESOP, insider...) từ **Tier-3 per-company disclosure sections**: Vietstock (`finance.vietstock.vn/<ticker>` — công bố thông tin/BC tài chính, **browser** reuse `VietstockCrawler` infra) + Cafef (**HTTP** reuse cafef adapter). Iterate 30 mã VN30. `[NOTE: đây là section OBJECTIVE (announcements/financial-reports) theo guide Tier-3 rule — KHÔNG phải 'báo cáo phân tích' (opinion) mà crawler Vietstock hiện tại đang lấy. Loại trừ analyst recs / editorial / buy-sell.]` Realizes UJ-1.

#### FR-16: VN30 disclosures via Vietstock (browser)
Crawl công bố thông tin + BC tài chính per-company cho 30 mã VN30 từ Vietstock (browser/Playwright, reuse `VietstockCrawler` infra — stealth browser, safe_goto). Filter objective sections, bỏ analysis/opinion.
**Consequences:**
- Mỗi mã VN30: lấy danh sách disclosure + chi tiết + attachment PDF.
- Tuân thủ no-JSON-API constraint (browser-only như crawler Vietstock hiện tại).

#### FR-17: VN30 disclosures via Cafef (HTTP)
Như FR-16 qua Cafef (HTTP, reuse cafef adapter pattern) — cross-check + dedup với Vietstock (checksum).

## 5. Non-Goals (Explicit)
- **NLP layer** (event extraction, sentiment PhoBERT/FinBERT, NER, embedding) — downstream riêng, PRD khác.
- **Volatility model** — downstream consumer, không build ở đây.
- **Refactor opinion crawlers** (Vietstock analysis/SSI/HSC/VNDIRECT/Cafef) — giữ nguyên, tách riêng.
- **Company IR websites** — heterogeneous, N adapters, trùng dữ liệu sàn đã pub → không đáng (xem `addendum.md`).
- **Social media / forums / broker recs / prediction articles** — excluded per guide (opinion/bias).
- **HOSE OAuth reverse-engineering** — ToS risk (xem OQ-2).

## 6. MVP Scope

### 6.1 In Scope
- **Universe = VN30** (30 mã HOSE; list chính thức, rebalance 6 tháng/lần) — mọi source filter theo list này.
- VSDC corporate-action ingestion **filtered VN30** (FR-4,5) — EASY HTTP.
- VN30 disclosures via **Tier-3 republish** — Vietstock (FR-16, browser) + Cafef (FR-17, HTTP), reuse existing crawler infra.
- Tier-2 news raw capture (10 báo) **VN30-filtered** (FR-15) — RSS-easy; enrichment NLP deferred.
- Canonical Metadata Schema + raw preservation (FR-8,9).
- Dedup/checksum, resumable, versioning, objective/opinion separation (FR-10..13).
- Daily schedule (FR-14).

### 6.2 Out of Scope for MVP (deferred)
- HNX + UPCoM (FR-1,2,3) — **out of VN30 scope** (sàn Hà Nội ≠ HOSE/VN30). Re-enable nếu universe mở rộng.
- HOSE-direct (FR-6) — **dropped**; dùng Tier-3 republish (§4.9: Vietstock/Cafef) thay — reuse infra, guide-allowed, tránh OAuth/ToS.
- SSC (FR-7) — Playwright; epic sau.
- NLP/feature layer — PRD downstream.
- Tier-2 news **enrichment** (company_code/event_type từ text) — cần NLP layer; phase sau. (Raw capture ở §6.1.)
- Macro gap (CPI/PMI/credit/FDI monthly) — `[ASSUMPTION: ngoài scope v1, PRD macro riêng]` (xem OQ-3).

## 7. Success Metrics

**Primary**
- **SM-1**: Coverage — % mã target universe có disclosure capture hằng ngày (target ≥ [ASSUMPTION: 95%] mã hoạt động). Validates FR-1,2,4,14.
- **SM-2**: Backfill depth — số năm lịch sử đạt được cho HNX/UPCoM + VSDC (target ≥ [ASSUMPTION: 5 năm]). Validates FR-3,5.

**Secondary**
- **SM-3**: Metadata quality — % rows có company_code + event_type non-null (target ≥ 95%); dedup rate. Validates FR-8,10.

**Counter-metrics (do not optimize)**
- **SM-C1**: Raw volume — không optimize số lượng crawl; ưu tiên chất lượng primary-source, không cào trùng/opinion. Counterbalances SM-1.
- **SM-C2**: Rate-limit violations — giữ 0 ban/403 do impolite crawling; counterbalances tốc độ.

## 8. Open Questions
1. **OQ-1 Target universe** — VN30? VN100? toàn bộ HOSE/HNX? `[ASSUMPTION: VN30 — khớp model volatility MACRO_FEATURES_PLAN]`. Cần confirm với chủ model.
2. **OQ-2 HOSE** — ✅ RESOLVED: chọn **Tier-3 republish** (Vietstock/Cafef disclosure, §4.9) thay HOSE-direct. FR-6 dropped.
3. **OQ-3 Macro gap** — CPI/PMI/credit/FDI (monthly) thuộc PRD này hay riêng? (macro Tier-1 đã có crawler reuse.)
4. **OQ-4 event_type taxonomy** — chuẩn hóa category: earnings, dividend, split, rights, bond, M&A, exec change, insider trade, shareholder change, ESOP, stock issuance...? (cần thống nhất enum.)
5. **OQ-5 PDPD** — có trường nào bắt personal data (tên cá nhân trong quyết định xử phạt SSC / insider) không? Cần redaction/loại bỏ theo Nghị định 13/2023.

## 9. Assumptions Index
- §1 — downstream = VN30 volatility model (MACRO_FEATURES_PLAN), not FinMarBa.
- §4.3/4.9 — HOSE-direct dropped (OAuth/ToS); VN30 disclosures qua Tier-3 Vietstock (browser, FR-16) + Cafef (HTTP, FR-17), reuse infra.
- §4.5/FR-8 — target ≥95% rows có company_code+event_type.
- §6.2 — macro gap ngoài scope v1.
- §6.1 — MVP = **VN30 universe**; disclosures Tier-3 (Vietstock FR-16 / Cafef FR-17) + VSDC corporate actions (FR-4,5) + Tier-2 news (FR-15). HNX/UPCoM demoted (wrong exchange).
- §7 — universe = VN30; backfill target ≥5 năm.
- §8/OQ-1 — universe VN30.
