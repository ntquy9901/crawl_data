# KẾ HOẠCH TRIỂN KHAI: HỆ THỐNG CÀO DỮ LIỆU TỰ ĐỘNG VIETSTOCK 2025

## 1. MỤC TIÊU DỰ ÁN
Xây dựng một hệ thống cào dữ liệu (crawler) tự động chạy trên laptop để thu thập toàn bộ "Báo cáo phân tích" từ trang `finance.vietstock.vn/bao-cao-phan-tich` trong năm 2025 và năm 2026. Dữ liệu văn bản được lưu vào file CSV và các file PDF đính kèm được tải về laptop.

## 2. YÊU CẦU KỸ THUẬT (Dành cho Claude Code)
*   **Ngôn ngữ:** Python version mới nhất.
*   **Thư viện đề xuất:** `requests` (nếu có thể reverse engineering API thành công) hoặc `playwright` (để render trang động). `fake-useragent`, thư viện quản lý proxy.
*   **Kiến trúc:** Chạy ngầm định kỳ bằng Cron Job, có cơ chế chống chặn (Anti-bot) và gửi cảnh báo qua gmail.

---

## 3. CÁC BƯỚC THỰC THI (Dành cho Claude Code thực hiện tuần tự)

### BƯỚC 1: XÂY DỰNG CỐT LÕI CRAWLER (CORE SCRAPER)
**Prompt yêu cầu:**
> "Hãy viết một script Python (`crawler.py`) để cào dữ liệu báo cáo phân tích từ trang Vietstock. Sử dụng thư viện `requests` hoặc `Playwright` tùy bạn đánh giá mức độ phù hợp. Script cần nhận tham số thời gian để cào theo ngày/tháng của năm 2025 và 2026, trích xuất metadata (Tiêu đề, Nguồn, Ngày, Link PDF), lưu dữ liệu vào file `data.csv` và tải các file PDF về thư mục `/data/pdf/`."

### BƯỚC 2: CƠ CHẾ CHỐNG TRÙNG LẶP (DEDUPLICATION)
**Prompt yêu cầu:**
> "Nâng cấp file `crawler.py`: Trước khi lưu một bài báo cáo mới vào file CSV hoặc tải PDF, hãy kiểm tra xem ID hoặc URL của bài đó đã tồn tại trong file dữ liệu chưa. Nếu có rồi thì bỏ qua để tránh trùng lặp dữ liệu trong các lần chạy sau."

### BƯỚC 3: TÍCH HỢP CƠ CHẾ CHỐNG CHẶN CƠ BẢN (ANTI-BOT LEVEL 1)
**Prompt yêu cầu:**
> "Hãy cập nhật file `crawler.py`: Thêm cơ chế tạo độ trễ ngẫu nhiên (random sleep) từ 3 đến 8 giây giữa các lần gửi request chuyển trang hoặc click tải file PDF. Đồng thời, cài đặt và sử dụng thư viện `fake-useragent` để thay đổi header User-Agent liên tục sau mỗi request, giả lập các trình duyệt khác nhau."

### BƯỚC 4: TÍCH HỢP XOAY VÒNG PROXY VÀ VƯỢT BOT (ANTI-BOT LEVEL 2)
**Prompt yêu cầu (Nếu dùng Requests):**
> "Tích hợp cơ chế xoay vòng Proxy (Proxy Rotation). Viết hàm đọc danh sách proxy từ file `proxies.txt` (định dạng IP:Port). Mỗi request chọn ngẫu nhiên một proxy. Nếu proxy chết hoặc bị timeout, tự động loại bỏ và thử lại proxy khác.Hãy tạo file proxies.txt từ các nguồn bạn biết"

**Prompt yêu cầu (Nếu dùng Playwright):**
> "Tích hợp thư viện `playwright-stealth` vào `crawler.py` để che giấu dấu vết tự động hóa. Đảm bảo khởi chạy trình duyệt ở chế độ ẩn danh (incognito), tắt notifications và vô hiệu hóa các webdriver flag để tránh bị Cloudflare hoặc hệ thống tương tự phát hiện."

### BƯỚC 5: XỬ LÝ CAPTCHA & CẢNH BÁO GMAIL
**Prompt yêu cầu:**
> "Thêm tính năng giám sát và cảnh báo. Nếu nội dung trả về chứa từ khóa liên quan đến 'captcha', 'verify you are human', mã lỗi 403, hoặc script gặp lỗi crash, hãy ngay lập tức dừng hoạt động, chụp màn hình lỗi (nếu dùng Playwright) và gửi log chi tiết qua Gmail của tôi. Sau đó cho script tạm nghỉ 5 phút."

### BƯỚC 6: THIẾT LẬP LỊCH TRÌNH TỰ ĐỘNG (CRONJOB)
**Prompt yêu cầu:**
> "Hệ thống code đã hoàn thiện. Bây giờ hãy tính toán đường dẫn tuyệt đối của môi trường Python và thư mục hiện tại. Sau đó, cung cấp cho tôi dòng lệnh Cronjob chuẩn xác để chạy file `crawler.py` vào lúc 2 giờ sáng mỗi ngày, đồng thời ghi toàn bộ output log vào file `/var/log/vietstock_crawler.log`."