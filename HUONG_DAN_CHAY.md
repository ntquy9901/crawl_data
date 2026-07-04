# HƯỚNG DẪN CHAY CRAWLER VIETSTOCK

Cào "Báo cáo phân tích" từ `finance.vietstock.vn` cho một khoảng thời gian bất kỳ.

---

## 1. Lệnh cơ bản (cốt lõi)

Mở terminal ở thư mục `D:\bmad-projects\crawl_data`, rồi chạy:

```bash
PYTHONUTF8=1 python crawler.py --start-date 2026-01-01 --end-date 2026-06-30 --headless true
```

- `--start-date` / `--end-date`: ngày dạng `YYYY-MM-DD`. Crawler đi từ mới nhất lùi về, **dừng tự động** khi gặp trang toàn báo cáo cũ hơn `start-date`.
- `PYTHONUTF8=1`: bắt buộc trên Windows để log in đúng tiếng Việt (CSV luôn UTF-8 dù có hay không).

> Lệnh này hoạt động ngay trên **Git Bash**. Nếu dùng **PowerShell**:
> ```powershell
> $env:PYTHONUTF8=1; python crawler.py --start-date 2026-01-01 --end-date 2026-06-30 --headless true
> ```
> Nếu dùng **CMD**:
> ```cmd
> set PYTHONUTF8=1 && python crawler.py --start-date 2026-01-01 --end-date 2026-06-30 --headless true
> ```

---

## 2. Các tham số (flags)

| Flag | Mặc định | Ý nghĩa |
|------|----------|---------|
| `--start-date YYYY-MM-DD` | (không) | Chỉ cào báo cáo từ ngày này trở đi. Có thì mới có điểm dừng. |
| `--end-date YYYY-MM-DD` | (không) | Chỉ cào báo cáo đến ngày này. Bỏ qua báo cáo mới hơn. |
| `--headless true\|false` | `true` | `false` = mở cửa sổ trình duyệt (để nhìn trực tiếp, debug). |
| `--max-pages N` | `0` (∞) | Giới hạn số trang (đếm an toàn / test). `0` = không giới hạn. |
| `--start-page N` | `1` | Bắt đầu cào từ trang N (bỏ qua trang 1..N-1). Dùng để **chạy lại đúng 1 trang** cần phục hồi. |
| `--test` | off | Chỉ cào trang 1 rồi dừng (test nhanh). |

> Lệnh cũ `--date` đã bị bỏ — dùng `--start-date`/`--end-date`.

---

## 3. Ví dụ theo kịch bản

```bash
# Cào cả năm 2026 (tới hiện tại)
PYTHONUTF8=1 python crawler.py --start-date 2026-01-01 --end-date 2026-12-31

# Chỉ tháng 6/2026
PYTHONUTF8=1 python crawler.py --start-date 2026-06-01 --end-date 2026-06-30

# Một quý (Q1/2026)
PYTHONUTF8=1 python crawler.py --start-date 2026-01-01 --end-date 2026-03-31

# 30 ngày gần nhất (không cần biết chính xác ngày hôm nay)
PYTHONUTF8=1 python crawler.py --start-date 2026-06-01

# Test nhanh: mở trình duyệt, chỉ 1 trang
PYTHONUTF8=1 python crawler.py --test --headless false

# Chạy giới hạn 5 trang (kiểm tra tốc độ)
PYTHONUTF8=1 python crawler.py --start-date 2026-01-01 --max-pages 5

# CHỈ chạy lại trang 12 (phục hồi trang bị lỗi ghi CSV, không đụng trang khác)
PYTHONUTF8=1 python crawler.py --start-page 12 --start-date 2026-01-01 --end-date 2026-06-30
```

---

## 4. Dữ liệu ra ở đâu

- **CSV (metadata):** `data/data.csv` — các cột `id,title,source,date,pdf_url,pdf_filename,downloaded_at`.
- **PDF:** `data/pdf/` — tên file dạng `DD-MM-YYYY_<tiêu đề>.pdf`.
- **Log:** `logs/vietstock_crawler_YYYYMMDD.log` (+ ảnh chụp `captcha_*.png` nếu bị chặn).

---

## 5. Theo dõi khi đang chạy

Trong terminal khác, tại thư mục project:

```bash
# Xem log realtime
tail -f logs/vietstock_crawler_$(date +%Y%m%d).log

# Đếm số PDF đã tải
ls data/pdf/*.pdf | wc -l

# Đếm số record trong CSV
tail -n +2 data/data.csv | wc -l
```

Trong log, các dòng quan trọng:
- `Processing page N...` — đang xử lý trang N.
- `Downloaded PDF: ...` — tải thành công.
- `Skipping duplicate: ...` — đã có rồi (bỏ qua, không tải lại).
- `CAPTCHA detected - pausing 5 minutes` — bị chặn, **đang nghỉ 5 phút rồi tự retry** (bình thường, cứ để vậy).
- `Reached page fully before start-date ... - stopping` — **đã xong** khoảng thời gian.
- `Error saving to CSV: Permission denied` — **`data.csv` đang bị app khác mở (Excel/VS Code…)** → record trang đó chưa ghi được. Đóng app đó ra; trang thiếu sẽ tự chữa ở lần chạy lại.

> ⚠️ **KHÔNG mở `data/data.csv` bằng Excel/Notepad/VS Code khi crawler đang chạy** — Windows khóa file độc quyền, mọi lần lưu sau đó sẽ fail và mất record CSV. Muốn xem, **copy** file ra chỗ khác rồi mở bản copy. Các lệnh `tail`/`wc` ở trên chỉ đọc thuần, an toàn.

---

## 6. RESUME — bị gián đoạn thì sao?

Crawler **resumable**. Nếu bị dừng (tắt máy, Ctrl-C, mất mạng, captcha), chỉ cần **chạy lại đúng lệnh cũ**:
- Các báo cáo đã cào sẽ bị `Skipping duplicate` và **đi qua rất nhanh** (không tải lại).
- Tự tiếp tục từ chỗ dừng.

⚠️ **Lưu ý quan trọng:** nếu một báo cáo **download PDF bị fail** (dòng `Downloaded PDF` không xuất), nó vẫn bị ghi vào CSV và đánh dấu "đã thấy" → khi re-run sẽ bị skip mãi. Muốn retry các bản fail:
```bash
cp data/data.csv data/data.csv.bak        # backup trước
# Mở data/data.csv, xoá các dòng có cột pdf_filename rỗng, save lại
# Rồi chạy lại lệnh crawl
```

### Phục hồi đúng 1 trang (ví dụ trang 12 bị lỗi ghi CSV)

Nếu log có `Error saving to CSV: Permission denied` (do `data.csv` đang mở trong Excel), crawler giờ đã **tự chịu lỗi**: thử lại 3 lần, nếu vẫn khóa thì ghi tạm ra `data/data_pending_*.csv` rồi **tự gộp ngược** về `data.csv` khi ghi được lại (cả trong run hiện tại lẫn lần chạy sau). Nên phần lớn trường hợp **không cần can thiệp**.

Nếu vẫn thiếu record của một trang cụ thể (PDF đã tải nhưng chưa có trong CSV), chạy lại **chỉ trang đó** — bỏ qua toàn bộ trang khác, dữ liệu cũ vẫn giữ:
```bash
PYTHONUTF8=1 python crawler.py --start-page 12 --start-date 2026-01-01 --end-date 2026-06-30
```
- `--start-page 12` nhảy thẳng tới trang 12 (không extract/download trang 1–11).
- Trang 12: PDF đã có trên disk → dùng lại, **thêm lại** vào CSV. Trang 13+ đã có → dedup bỏ qua nhanh. Dừng khi hết khoảng `--start-date/--end-date`.
- **Đừng chạy lệnh này khi crawl lớn vẫn đang chạy** (2 crawler cùng ghi `data.csv` sẽ xung đột). Chờ crawl hiện tại xong hẵng chạy.

---

## 7. Bắt đầu hoàn toàn từ đầu (clean rebuild)

Muốn xóa dữ liệu cũ, cào lại sạch sẽ (giữ lại PDF đã tải để không phải tải lại):
```bash
cp data/data.csv data/data.csv.bak     # backup CSV
rm data/data.csv                       # xoá CSV (GIỮ NGUYÊN data/pdf/)
# Chạy lại lệnh crawl — các PDF đã có sẽ được "PDF already exists" (dùng lại), chỉ tải phần mới
```

---

## 8. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|------------|-------------|-------|
| Log tiếng Việt thành `Khuy?n ngh?` | Quên `PYTHONUTF8=1` | Thêm flag đó (CSV vẫn đúng nên dữ liệu OK). |
| `CAPTCHA detected - pausing 5 minutes` | Vietstock phát hiện bot | Bình thường — để nó nghỉ 5 phút + tự retry (tối đa 3 lần). Nếu liên tục, tăng `RANDOM_DELAY_MAX` trong `.env`. |
| Trang nào đó toàn download fail | Hiếm (đã fix UA) | Xem mục 6 để retry sau. |
| `Browser initialized` rồi treo | Lần đầu cần tải chromium | Chạy `python -m playwright install chromium`. |
| Crawler chạy quá chậm | Delay 3–8s mỗi bản | Đã đặt theo yêu cầu anti-bot. Đừng giảm nếu không muốn bị chặn. |

---

## 9. Chạy tự động hằng ngày (đã setup)

Windows Task Scheduler chạy `run_crawler.ps1` lúc **2h sáng mỗi ngày** (xem `task_scheduler.xml`). Bản này cào từ mới nhất (không có date filter) → mỗi ngày lấy báo cáo mới.

Muốn đổi khoảng thời gian cho lịch tự động: sửa `run_crawler.ps1`, dòng chạy crawler thành:
```powershell
& $PythonExe crawler.py --start-date 2026-01-01 --end-date 2026-12-31 *>> $LogFile
```

---

## 10. Checklist nhanh trước khi chạy lớn

1. ✅ Đang ở thư mục `D:\bmad-projects\crawl_data`.
2. ✅ `data/data.csv` đã backup nếu có dữ liệu cũ quan trọng.
3. ✅ Dùng `--start-date` (để có điểm dừng, không chạy vô tận).
4. ✅ Có `PYTHONUTF8=1`.
5. ✅ Đủ dung lượng ổ cứng (mỗi PDF ~200KB–2MB).
