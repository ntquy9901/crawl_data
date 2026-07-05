---
name: source-news-download
description: Chọn nguồn uy tín để lấy báo cáo/phân tích/tin tức thị trường chứng khoán Việt Nam hằng ngày. Dùng khi người dùng muốn tìm, đọc, hoặc cào dữ liệu về phân tích thị trường, báo cáo ngày/tuần, dòng tiền, hoặc tin tài chính Việt Nam. Cung cấp bản đồ nguồn theo mục đích (PDF nghiên cứu CTCK: SSI/HSC/VNDIRECT; cổng tin/dữ liệu: Vietstock/Cafef/FireAnt) kèm lưu ý về thời gian phát hành và thiên kiến.
---

# Nguồn dữ liệu phân tích thị trường chứng khoán Việt Nam

Khi cần báo cáo phân tích hoặc tin tức thị trường CK Việt Nam, **ưu tiên CTCK lớn (Top Market Share) hoặc chuyên trang tài chính được cấp phép**. Chọn nguồn theo **mục đích**.

## Quyết định nhanh
- Cần **báo cáo PDF phân tích chuyên sâu** (nhận định ngày/tuần, chiến lược tháng) → mục **1** (SSI / HSC / VNDIRECT).
- Cần **tin tức nhanh, dòng tiền, biểu đồ real-time** → mục **2** (Vietstock / Cafef / FireAnt).

## 1. Báo cáo phân tích chuyên sâu (Daily Report — PDF)
Các CTCK lớn có đội Research hùng hậu. Không cần mở tài khoản vẫn vào mục **"Trung tâm phân tích"** / **"Báo cáo phân tích"** trên site để tải PDF — thường phát hành vào **cuối ngày** hoặc **trước giờ giao dịch sáng**.

| Nguồn | Site | Điểm mạnh |
|---|---|---|
| **SSI Research** | `ssi.com.vn` | Nhận định ngày (Daily)/tuần, chiến lược tháng rất chất lượng; góc nhìn vĩ mô chuẩn xác, chặt chẽ |
| **HSC Research** | `hsc.com.vn` | Nổi tiếng phân tích kỹ thuật, dòng tiền, nhận định thị trường (nội + ngoại); khách quan, thực tế |
| **VNDIRECT Research** | `vndirect.com.vn` | Giao diện báo cáo trực quan, dễ đọc cho nhà đầu tư cá nhân; danh mục khuyến nghị rõ ràng |

## 2. Tin tức, dòng tiền & biểu đồ real-time
Theo dõi biến động bảng điện, bộ lọc cổ phiếu, biểu đồ kỹ thuật, và Mua/bán ròng (tự doanh, nước ngoài) trong ngày.

| Nguồn | Site | Điểm mạnh |
|---|---|---|
| **Vietstock** | `vietstock.vn` | Cổng thông tin tài chính lâu đời, toàn diện nhất. Lịch sự kiện (cổ tức, ĐHĐCĐ) và công cụ lọc chỉ số tài chính doanh nghiệp |
| **Cafef** | `cafef.vn` | Kênh cập nhật tin tức nhanh nhất về thị trường, doanh nghiệp, dòng sự kiện vĩ mô. Tiện đọc tin nhanh sáng/tối |
| **FireAnt / FiinTrade** | `fireant.vn` | Nền tảng biểu đồ & dữ liệu real-time cực tốt; cộng đồng thảo luận đông → nắm "tâm lý đám đông" và tin đồn |

## 3. Lời khuyên khi đọc báo cáo hằng ngày
- **Thời gian đọc**: Báo cáo nhận định cho ngày hôm sau thường được các CTCK xuất bản từ **17h00–20h00 hằng ngày**. Đọc khung giờ này để chuẩn bị kế hoạch cho phiên sáng mai.
- **Bộ lọc tâm lý**: Báo cáo nhận định của CTCK **chỉ mang tính tham khảo** — thị trường luôn có xác suất. **Kết hợp đọc ≥2 CTCK** (ví dụ SSI + HSC) để có góc nhìn đa chiều, tránh thiên kiến (bias) theo một hướng.

## Liên kết với crawler trong repo này
Dự án `crawl_data` đang hiện thực hoá từng nhóm nguồn ở trên:
- **PDF báo cáo phân tích từ Vietstock** → `crawler.py` (đã xong, metadata 2001–2026 + PDF kỳ gần).
- **Tin tức thị trường hằng ngày từ Cafef** → `cafef_crawler.py`: dùng `cafef.vn/<section>.rss` (chạy hằng ngày) + `cafef.vn/<section>.chn?page=N` (backfill). Section = `thi-truong-chung-khoan`, `tai-chinh-ngan-hang`, `vi-mo-dau-tu`.
- **SSI** (Bản Tin Thị Trường — PDF) → `ssi_crawler.py` ✅ đã cào (listing-complete, `?page=N`).
- **HSC** (Research Insights — article HTML) → `hsc_crawler.py` ✅ đã cào (daily-only; HSC không lộ publish date → cột `pub_date` rỗng).
- **VNDIRECT** → **Cloudflare chặn** plain HTTP (403), cần Playwright — chưa build.
- Cả SSI/HSC dùng khung chung `base_news_crawler.py` (`BaseNewsCrawler`, Template Method) — thêm nguồn = 1 subclass nhỏ. Chi tiết: `docs/design.md` §3 (Playwright) + §4 (framework).
