# vnstock_articles.csv — Thông tin dataset

File dữ liệu: `data/vnstock_articles.csv` (local, gitignored — không nằm trên GitHub do nặng).
File này mô tả schema, nguồn gốc, thống kê và **caveat chất lượng dữ liệu**.

## Tổng quan
Bản đồ dữ liệu **Báo cáo phân tích** từ `https://finance.vietstock.vn/bao-cao-phan-tich`,
gồm metadata toàn kỳ + PDF cho kỳ gần. Phục vụ thu thập dữ liệu phân tích thị trường
chứng khoán Việt Nam **2001–2026**.

- **Số dòng (unique)**: 14.825 — khử trùng lặp theo `pdf_url` (tăng từ 14.393 sau khi re-crawl + gộp 2015–2018).
- **Có PDF thật**: 2.336 dòng (cột `pdf_filename` ≠ rỗng); phần còn lại metadata-only.
- **Phạm vi năm**: 2001–2026. Cột `date` đáng tin cậy (stray-date chỉ ~0,5%, xem caveat).

## Schema
| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | string | ID nội bộ (theo thời điểm cào, dạng `date_count`). |
| `title` | string | Tiêu đề báo cáo. |
| `source` | string | Tổ chức phát hành (CTCK / rating agency / cơ quan nhà nước). |
| `date` | string `DD/MM/YYYY` | Ngày phát hành — **xem caveat**, có thể sai do bug stray-date. |
| `pdf_url` | string (URL) | Link download PDF — **khóa duy nhất, đúng 100%**. |
| `pdf_filename` | string | Tên file PDF đã tải (rỗng nếu chưa tải). |
| `downloaded_at` | string | Timestamp lúc cào dòng đó. |

## Nguồn gốc (provenance)
Gộp từ 3 file backfill cũ thành 1 file duy nhất (không đụng file gốc):
`data.csv` (14.393) + `data_archive.csv` (10.449) + `data_2021_2025.csv` (6.524)
= 31.366 dòng thô → **dedup theo `pdf_url`, ưu tiên dòng có `pdf_filename`** → 14.393 unique.

> `data_archive.csv` và `data_2021_2025.csv` vốn là subset của `data.csv` (đã gộp từ
> trước), nên kết quả merge = đúng `data.csv`. File mới chỉ là tên gộp duy nhất.

Sinh bởi `crawler.py` (class `VietstockCrawler`, Playwright). Logic gộp giống `merge_csv.py`.

> **Cập nhật 2026-07-04**: re-crawl riêng các window 2015–2018 (`data/verify_201[5-8].csv`) rồi
> gộp thêm → lấp gap 2016 (18→387) và 2015 (450→513); 2017/2018 vốn đã đủ. Tổng 14.393→14.825.

## Phân bố theo nguồn (top)
Vietstock 1.344 · BVS 786 · MBS 773 · KBSV 757 · VNDS 674 · MAS 644 · Vietcap 651 ·
VCBS 587 · SSI 553 · ACBS 509 · BSC 497 · PHS 476 · FPTS 456 · VDS 405 · ABS 381 · …
(còn ~90 tổ chức khác, mỗi tổ chức vài dòng; nhóm `Khác` 743).

## Phân bố theo năm (từ cột `date`)
```
2001: 3    2002: 1    2003: 2    2004: 1    2005: 1
2006: 0    2007: 0              ← GAP thật: site index ~0 (đã verify 2026-07-04)
2008: 182  2009: 203  2010: 392  2011: 757  2012: 387
2013: 504  2014: 513  2015: 513  2016: 387  2017: 369
2018: 307  2019: 455  2020: 990  2021: 1285  2022: 1193
2023: 1179 2024: 1378 2025: 1482 2026: 2335
```
6 dòng không parse được `date`. **Tổng ≤ 2008 = 190 bài** (2008: 182 + 2001–2005: 8 + 2006–2007: 0).
`2016` (387) và `2015` (513) đã được lấp bằng re-crawl + gộp — chi tiết caveat 4.

## ⚠️ Caveat chất lượng dữ liệu
1. **Cột `date` đủ tin cậy cho file này** (kiểm tra thực nghiệm 2026-07-04): các giá trị
   `date` rải đều trên 3.506 ngày khác nhau (date phổ biến nhất chỉ 43 dòng — không có
   cụm ngày crawl), và `date` ≠ `downloaded_at` ở mọi dòng (`downloaded_at` luôn có, = ngày
   crawl). → **không phát hiện dấu vết stray-date hàng loạt** trong dataset đã gộp.
2. **2026 = 2.335 chính là window PDF gần**: cả 2.335 dòng `date`=2026 đều có
   `pdf_filename` (PDF chỉ tải cho kỳ gần). Đây là báo cáo thật sự mới, **không phải
   stray-date inflate** (sửa lại nhận định cũ từng ghi ở đây).
3. **`pdf_url` là nguồn sự thật**: đúng 100%, làm khóa dedup. Lưu ý `pdf_url` **không**
   mã hoá năm (chỉ là `/downloadedoc/<số>`); `id` = `<date>_<count>` nên cũng phát sinh
   từ `date` → không thể phục hồi năm độc lập với `date`.
4. **Hai gap có 2 nguyên nhân KHÁC nhau (verify re-crawl 2026-07-04)**:
   - **2006–2007 = gap THẬT của site**: date filter trả về ~0 (mỗi window 6 tháng chỉ 1
     page, "last page reached" ngay). Vietstock gần như không index "Báo cáo phân tích"
     cho 2006–2007 → **không sửa được** (site không có).
   - **2015–2016 = backfill-miss TẠM THỜI (đã lấp)**: re-crawl cho thấy 2016 site có 388
     nhưng file cũ chỉ gom 19 (thiếu 95%); 2015 thiếu ~12% (514 vs 450); còn **2017/2018
     đủ** (370/307). → miss **cục bộ ~2015–2016, KHÔNG phải bug logic mọi window** — rất có
     thể captcha/timeout tạm thời trong lần chạy dài `--from-date 2001`. Đã gộp verify:
     2016→387, 2015→513. `crawler.py` đã thêm **retry navigate/apply + cảnh báo window
     0-yield** để giảm tái diễn.
5. **Độ đủ của các năm backfill**: 2008–2014 và 2019–2025 **chưa re-crawl lại** để đối chiếu
   — có thể còn miss nhỏ lẻ. Muốn chắc, re-crawl từng window rồi gộp (dedup tự skip bài cũ).
6. **Bug stray-date**: còn thật trong `crawler.py` nhưng **tỷ lệ thấp** (~0,5%: re-crawl
   2016 chỉ 1/388 dòng bị gán `now()`). Không phải nguyên nhân chính của gap hay inflate
   2026 (sửa lại nhận định cũ).

## Tái tạo / liên kết
- Tạo file: chạy `crawler.py` backfill rồi gộp bằng `merge_csv.py` (hoặc script gộp tương
  đương dedup theo `pdf_url`, ưu tiên dòng có PDF).
- Bug stray-date + gap 2006–2007: xem `CLAUDE.md` (mục "Trạng thái") và memory
  `crawler-pitfalls-to-avoid`.
