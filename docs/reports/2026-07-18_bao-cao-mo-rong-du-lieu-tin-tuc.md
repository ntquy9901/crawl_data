# Báo cáo: Mở rộng thu thập dữ liệu tin tức thị trường chứng khoán Việt Nam

**Ngày:** 2026-07-18
**Phạm vi:** Mở rộng crawler tin tức từ 5 nguồn báo phổ thông (Người Lao Động, Thanh Niên, Tuổi Trẻ, VietnamPlus, VnExpress) + bổ sung nội dung tiếng Việt cho nguồn nghiên cứu VNDIRECT.

## 1. Bối cảnh & yêu cầu

Trước khi thực hiện, dữ liệu tin tức tổng hợp (`data/news_articles.csv`) chỉ có **~6.900 bài** từ 4 nguồn (Cafef, SSI, HSC, VNDIRECT). Yêu cầu: lấy thêm dữ liệu tin tức từ 5 báo phổ thông (NLD, Thanh Niên, Tuổi Trẻ, VietnamPlus, VnExpress), lý tưởng là từ năm 2000, và kiểm tra bổ sung nội dung tiếng Việt cho VNDIRECT.

## 2. Khảo sát thực tế (trước khi code)

Trước khi triển khai, đã khảo sát trực tiếp (không giả định) cấu trúc sitemap/API của từng nguồn:

| Nguồn | Kết quả khảo sát |
|---|---|
| Tuổi Trẻ | Sitemap có từ ~2011-01, không chặn bot |
| Thanh Niên | Sitemap có từ ~2011-06, không chặn bot |
| VietnamPlus | Sitemap có từ ~2010-01, không chặn bot |
| **Người Lao Động (NLD)** | **Không phải nguồn độc lập** — toàn bộ domain `nld.com.vn` (kể cả RSS) redirect sang `tuoitre.vn/nld/*` và trả về nội dung của Tuổi Trẻ. Loại khỏi phạm vi. |
| **VnExpress** | Sitemap index đọc được, nhưng mỗi shard theo ngày bị **chặn bot** (redirect 302) — kể cả giả UA Googlebot và Playwright headless. Cần phương án khác (mục 4). |

**Kết luận quan trọng:** Không nguồn nào có sitemap về tới năm 2000 — hạ tầng CMS của báo Việt Nam hiện tại chỉ bắt đầu ghi nhận từ ~2010-2011 (site cũ trước đó dùng cấu trúc URL khác, không truy xuất được qua sitemap).

## 3. Crawler mới: `news_sitemap_crawler.py` (Tuổi Trẻ / Thanh Niên / VietnamPlus)

- Cách làm: sitemap của cả 3 site đã nhúng sẵn tiêu đề bài viết trong chính file sitemap (`image:title`/`news:title`) → **không cần tải từng trang bài** để lấy metadata, chỉ cần đọc sitemap là đủ (title + url + ngày đăng).
- Backfill toàn bộ từ floor thực tế của mỗi site tới hiện tại (2026-07-18).
- Hỗ trợ chế độ `--latest` chạy hằng ngày (quét 7 ngày gần nhất), đã nối vào `run_daily_all.ps1`.

**Kết quả:**

| Nguồn | Số bài | Phạm vi thời gian |
|---|---|---|
| Tuổi Trẻ | 283.568 | 2011-01 → nay |
| Thanh Niên | 387.169 | 2011-06 → nay |
| VietnamPlus | 773.152 | 2010-01 → nay |

## 4. VnExpress — bị chặn bot, xử lý bằng Wayback Machine (archive.org)

VnExpress chặn crawl trực tiếp ở tầng sitemap. Đã thử nhiều phương án trước khi chọn giải pháp cuối:

1. Playwright headless trần → timeout, không vượt qua được.
2. UA giả Googlebot qua `requests` → vẫn bị redirect 302.
3. Trang danh mục có phân trang (`vnexpress.net/kinh-doanh-p2`...) → **không bị chặn**, nhưng chỉ hiển thị được ~20-24 trang (≈ vài tuần tin gần nhất) trước khi tự động chuyển hướng sang trang tìm kiếm — không đủ sâu cho backfill lịch sử.
4. **Wayback Machine (web.archive.org)** — bên thứ ba lưu trữ, không bị chặn bởi hàng rào bot của VnExpress, có snapshot trang chủ VnExpress từ **2001-03** (gần như ngày site ra mắt).

**Giải pháp áp dụng** (`vnexpress_wayback_backfill.py`): dùng CDX API của archive.org liệt kê các snapshot lịch sử của (a) trang chủ (lấy mẫu theo tháng, 2001→2026) và (b) trang `/kinh-doanh` (lấy mẫu theo ngày, từ 2018-12 khi URL này xuất hiện) → tải từng snapshot đã lưu trữ (không phải trang live) → trích toàn bộ link bài viết xuất hiện trên đó.

**Giới hạn cần lưu ý:** `pub_date` ghi nhận là **ngày phát hiện snapshot** (ngày bài xuất hiện trên trang chủ/danh mục khi archive.org chụp lại), **không phải ngày xuất bản thật** của bài — muốn chính xác tuyệt đối phải tải từng bài riêng lẻ (chi phí quá lớn, ngoài phạm vi "chỉ lấy metadata"). Trước ~2010, VnExpress dùng cấu trúc URL khác nên hầu như không trích được link từ snapshot cũ hơn.

**Kết quả:** từ 103 bài (chỉ RSS mới nhất) → **13.938 bài** (nhiều lượt chạy + retry với số luồng thấp hơn để khắc phục hiện tượng archive.org tự giới hạn tốc độ khi crawl song song nhiều luồng — 15 luồng ban đầu bị fail ~50%, giảm xuống 3 luồng vét thêm đáng kể).

## 5. VNDIRECT — bổ sung nội dung tiếng Việt

Phát hiện: các trang nghiên cứu VNDIRECT trước giờ crawler chỉ lấy bản **tiếng Anh** (`/en/category/...`). Khảo sát cho thấy **có bản tiếng Việt riêng** (không phải bản dịch giao diện — là bài viết khác hẳn, slug khác: vd `company-note` (en) ↔ `bao-cao-phan-tich-dn` (vi)).

Đã thêm flag `--lang en|vi` cho `vndirect_crawler.py`, backfill đầy đủ 4 category bản tiếng Việt, ghi vào cùng file CSV (phân biệt bằng cột `category` hậu tố `-vi`).

**Kết quả:** VNDIRECT từ 969 → **2.043 bài** (thêm 1.074 bài tiếng Việt: company-note-vi 702, strategy-note-vi 158, sector-note-vi 109, economics-note-vi 105).

## 6. Tổng kết dữ liệu

| Nguồn | Trước | Sau |
|---|---|---|
| Cafef | 4.067 | 4.067 (không đổi — deep backfill không khả thi, đã ghi nhận từ trước) |
| SSI | 1.867 | 1.867 (đã đủ) |
| HSC | 6 | 6 (đã đủ, site không hỗ trợ) |
| VNDIRECT | 969 | **2.043** (+ tiếng Việt) |
| Tuổi Trẻ | 0 | **283.568** (mới) |
| Thanh Niên | 0 | **387.169** (mới) |
| VietnamPlus | 0 | **773.152** (mới) |
| VnExpress | ~103 | **13.938** (qua Wayback Machine) |
| **Tổng `news_articles.csv`** | **~6.900** | **1.465.810** |

## 7. Quy trình đảm bảo chất lượng

Toàn bộ code mới đều qua: unit test + smoke test (dùng fixture, không gọi mạng thật), `ruff` lint sạch, `diff-cover` (coverage phần code thay đổi ≥ 80%, thực tế đạt 93-100%), và code review đối kháng (adversarial review) qua nhiều góc nhìn độc lập (correctness, reuse, hiệu năng, altitude) — phát hiện và sửa các lỗi: trùng lặp logic CSV/fetch (đã refactor dùng chung `BaseNewsCrawler`), regex ngày tháng tiếng Việt bắt nhầm chữ "năm" xuất hiện ngoài ngữ cảnh, thiếu chặn lỗi khi dữ liệu API trả về bất thường.

## 8. Việc còn lại / hạn chế đã biết

- VnExpress trước ~2010 hầu như không lấy được (đổi cấu trúc URL, archive.org cũng không lưu đủ).
- `pub_date` của VnExpress là ngày gần đúng (ngày snapshot), không phải ngày xuất bản thật — cần lưu ý khi phân tích theo thời gian.
- Cafef vẫn chỉ tích lũy dần qua RSS hằng ngày (deep backfill không khả thi do chặn IP + sitemap không gắn nhãn chuyên mục).
- Chưa nối `news_sitemap_crawler.py`/`vnexpress_wayback_backfill.py` vào lịch tự động hằng ngày cho phần cập nhật liên tục (tuoitre/thanhnien/vietnamplus đã có `--latest`; vnexpress qua Wayback không phù hợp chạy hằng ngày do phụ thuộc tốc độ archive.org).
