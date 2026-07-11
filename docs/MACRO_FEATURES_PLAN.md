# Kế Hoạch Macro Features — Stock Volatility Prediction (VN30)

## 1. Bối Cảnh

- **Project**: Parallel LSTM-GNN dự đoán Parkinson volatility (horizon 1, 5, 10, 22 ngày)
- **Data hiện tại**: OHLCV 134 stocks (2009–2026), sentiment từ news (đã test 3 baselines → no-lift)
- **Vấn đề**: Không có bất kỳ macro feature nào đang được dùng (chỉ HAR features từ volatility history)
- **Target metric**: Directional Accuracy (DirAcc) — hiện tại best ~70%
- **Kỳ vọng**: Macro features mang tín hiệu hệ thống, dày đặc (daily), bổ sung cho price action

## 2. Danh Sách Macro Features — Theo Priority

### Tier 1: Daily, sẵn có, high impact (ưu tiên làm trước)

| # | Feature | Source | Tần suất | Lý do impact | Cách crawl |
|---|---------|--------|----------|-------------|------------|
| 1 | **VNINDEX daily return** | VNDIRECT / Cafef / TradingView | Daily | Chỉ số thị trường chung — tương quan mạnh với volatility các stock | Từ OHLCV của VN30, hoặc fetch index data |
| 2 | **VNINDEX volume** | VNDIRECT / Cafef | Daily | Volume toàn thị trường → mức độ tham gia | Từ dữ liệu index |
| 3 | **USD/VND central rate** | SBV (https://www.sbv.gov.vn) | Daily | Biến động tỷ giá → capital flow, import/export | Crawl SBV hoặc từ Vietcombank |
| 4 | **VNDIBOR overnight + 1W** | SBV | Daily | Chi phí vốn ngắn hạn → thanh khoản hệ thống | Crawl SBV |

### Tier 2: Weekly/Monthly, medium-to-high impact

| # | Feature | Source | Tần suất | Lý do impact |
|---|---------|--------|----------|-------------|
| 5 | **SBV lãi suất điều hành** (refinancing rate, discount rate, OMO rate) | SBV (https://www.sbv.gov.vn) | Khi có thay đổi | Ảnh hưởng trực tiếp đến bank stocks (30%+ VN30) và chi phí vốn |
| 6 | **DXY (US Dollar Index)** | FRED / Investing.com | Daily | Dollar mạnh/yếu → tác động dòng vốn ngoại |
| 7 | **Fed Funds Rate** | FRED | Khi có thay đổi | Lãi suất toàn cầu → áp lực tỷ giá, dòng vốn |

### Tier 3: Monthly, slower signal

| # | Feature | Source | Tần suất | Ghi chú |
|---|---------|--------|----------|---------|
| 8 | **CPI (inflation)** | GSO (https://www.gso.gov.vn) | Monthly | Ảnh hưởng đến chính sách tiền tệ |
| 9 | **PMI Sản xuất** | S&P Global / Cafef | Monthly | Chỉ báo sức khỏe kinh tế |
| 10 | **Tín dụng tăng trưởng** | SBV | Monthly | Thanh khoản hệ thống ngân hàng |
| 11 | **FDI giải ngân** | GSO | Monthly | Dòng vốn ngoại thực tế |

## 3. Chi Tiết Crawl Từng Nguồn

### 3.1 VNINDEX (OHLCV)
**Nguồn thay thế**: VNINDEX có sẵn trên TradingView, Investing.com, hoặc Cafef.

**Cách lấy hiệu quả nhất**:
- Crawl VNINDEX trực tiếp từ `https://finfo-api.vndirect.com.vn/v4/stock_prices?sort=date&limit=5000&symbol=VNINDEX`
- Hoặc dùng `yfinance` với mã `^VNINDEX` (không chính thức)
- Hoặc tự tính từ dữ liệu 134 stocks đã có (aggregate cap-weighted)

**Output**: `date, open, high, low, close, volume` (giống schema stock hiện tại)

### 3.2 USD/VND Exchange Rate
**Nguồn chính thức**: SBV — Tỷ giá trung tâm
**URL**: `https://www.sbv.gov.vn/TyGia/faces/tygia.jspx`

**Cách crawl**:
- SBV cập nhật tỷ giá trung tâm mỗi ngày (~9h sáng)
- Hoặc crawl từ Vietcombank (VCB là NHTM nhà nước, tỷ giá niêm yết sát với thị trường)
- URL VCB: `https://portal.vietcombank.com.vn/UserControls/TVPortal.TyGia/pListTyGia.aspx`

**Format output**:
```csv
date,usd_vnd_buy,usd_vnd_sell,usd_vnd_central
2024-01-02,24350,24450,24400
```

### 3.3 VNDIBOR / Interbank Rates
**Nguồn**: SBV — Lãi suất liên ngân hàng

**URL tham khảo**: `https://www.sbv.gov.vn/webcenter/portal/vi/menu/trangchu/dulieuhienthi/laisuat/laisuatliennganhang`

**Crawling strategy**:
- SBV cập nhật VNDIBOR overnight, 1W, 2W, 1M hàng ngày
- Dùng Selenium nếu trang SBV dùng JS
- Hoặc lấy từ Bloomberg / Investing.com (dễ hơn)

### 3.4 DXY (US Dollar Index)
**Nguồn dễ nhất**: FRED (https://fred.stlouisfed.org/series/DTWEXBGS)
- API: `https://fred.stlouisfed.org/graph/fredgraph.csv?bgcolor=%23e1e9f0&chart_type=line&drp=0&fo=open%20sans&graph_bgcolor=%23ffffff&height=450&mode=fred&recession_bars=on&txtcolor=%23444444&ts=12&tts=12&width=1168&nt=0&thu=0&trc=0&show_legend=yes&show_axis_titles=yes&show_tooltip=yes&id=DTWEXBGS&scale=left&cosd=2006-01-03&coed=2026-07-10&line_color=%234572a7&link_values=false&line_style=solid&mark_type=none&mw=3&lw=2&ost=-99999&oet=99999&mma=0&fml=a&fq=Daily&fam=avg&fgst=lin&fgsnd=2020-02-01&line_index=1&transformation=lin&vintage_date=2026-07-11&revision_date=2026-07-11&nd=2006-01-03`

Hoặc dùng `pandas-datareader`:
```python
import pandas_datareader.data as web
import datetime
dxy = web.DataReader('DTWEXBGS', 'fred', start='2009-01-01')
```

### 3.5 SBV Policy Rates
**Nguồn**: SBV — Các quyết định lãi suất điều hành

**Các feature cần**:
- Lãi suất tái cấp vốn (Refinancing rate)
- Lãi suất chiết khấu (Discount rate)
- Lãi suất cho vay OMO
- Trần lãi suất huy động

**Crawl strategy**: SBV thay đổi lãi suất không thường xuyên. Có thể:
- Crawl từ Investing.com Vietnam Interest Rate page
- Hoặc manually ghi lại các lần thay đổi từ 2009 đến nay (~30-40 lần)

## 4. Tích Hợp Vào Codebase Hiện Tại

### 4.1 Pipeline xử lý

```
Crawl macro data → CSV raw → Align theo trading calendar → Merge vào processed data
```

**Gợi ý**: Thêm thư mục `data/macro/`:
```
data/macro/
├── raw/          # Dữ liệu gốc crawl về
│   ├── vnindex.csv
│   ├── usd_vnd.csv
│   ├── vndibor.csv
│   └── dxy.csv
├── processed/    # Aligned theo trading days
│   └── macro_features.csv   # date, feature_1, ..., feature_n
└── macro_crawler.py         # Script crawl tất cả
```

### 4.2 Feature Engineering (từ macro features)

| Feature | Công thức | Kỳ vọng |
|---------|-----------|---------|
| `vni_return_1d` | log(VNI_t / VNI_t-1) | Biến động thị trường chung |
| `vni_return_5d` | rolling 5-day return | Xu hướng ngắn hạn |
| `vni_volume_zscore` | (volume_t - mean_20d) / std_20d | Khối lượng bất thường |
| `usd_vnd_change_1d` | % change USD/VND | Áp lực tỷ giá |
| `usd_vnd_volatility_5d` | std of 5-day change | Bất ổn tỷ giá |
| `vndibor_1d_change` | delta VNDIBOR overnight | Căng thẳng thanh khoản |
| `dxy_return_1d` | % change DXY | Sức mạnh USD toàn cầu |
| `refinancing_rate` | SBV refinancing rate (categorical khi thay đổi) | Chính sách tiền tệ |

**Lưu ý**: Các macro features không cần phải "dự đoán" future. Chúng chỉ là các biến số kinh tế hiện tại — model sẽ tự học temporal patterns nếu chúng có predictive power.

### 4.3 Tích hợp với model hiện tại

Trong `src/lstm_gat_hybrid/config.py`, tăng `num_features_per_stock` từ 3 lên 3 + n_macro_features.

**Macro features là global features** — áp dụng cho tất cả các stocks cùng lúc. Cách tích hợp:
1. **Option A** (khuyến nghị): Concatenate macro features vào input của mỗi stock node (mỗi stock node có cùng giá trị macro). Không thay đổi kiến trúc.
2. **Option B** (nâng cao): Thêm global node vào đồ thị GNN, kết nối với tất cả stock nodes (tốn công hơn, cần thay đổi kiến trúc).

Option A đơn giản, nên làm trước. Nếu có lift, mới thử Option B.

## 5. Lộ Trình Ước Lượng

| Bước | Task | Người | Thời gian |
|------|------|-------|-----------|
| 1 | Crawl VNINDEX OHLCV (tính từ 134 stocks hoặc fetch) | 0.5 ngày |
| 2 | Crawl USD/VND từ SBV/VCB (script) | 1 ngày |
| 3 | Crawl VNDIBOR từ SBV | 0.5 ngày |
| 4 | Crawl DXY từ FRED | 0.5 ngày |
| 5 | Crawl SBV policy rates history (manual + automation) | 1 ngày |
| 6 | Align macro data với trading calendar, fill missing | 0.5 ngày |
| 7 | Thêm feature columns vào config, train model | 1 ngày |
| 8 | Đánh giá kết quả, so sánh với baseline | 0.5 ngày |
| | **Tổng** | **~5-6 ngày** |

## 6. Rủi Ro & Lưu Ý

1. **SBV website**: Cổng thông tin SBV cũ, dùng JS phức tạp → có thể cần Selenium. Cân nhắc nguồn thay thế (Investing.com, TradingEconomics).
2. **Holiday alignment**: SBV/GSO cập nhật theo lịch Việt Nam — cần align với trading calendar.
3. **Frequency mismatch**: CPI (monthly) và GDP (quarterly) quá thưa so với daily model. Chỉ dùng làm features dạng "giá trị hiện tại lặp lại mỗi ngày trong tháng".
4. **Data snooping**: Macro features thường được công bố chậm (ví dụ CPI công bố cuối tháng, nhưng là số liệu của tháng hiện tại). Cần xử lý look-ahead bias: chỉ dùng macro features đã biết tại ngày dự đoán.

## 7. File Output Mẫu

```csv
date,vni_return_1d,vni_volume_1d,usd_vnd_change_1d,vndibor_1d,dxy_return_1d,refinancing_rate
2024-01-02,0.012,1.25e10,-0.0005,4.5,-0.001,4.5
2024-01-03,-0.005,1.1e10,0.0003,4.5,0.002,4.5
...
```

**Look-ahead safe**: Giá trị tại ngày T là giá trị đã biết tại ngày T (không phải giá trị tương lai). Đối với monthly features (CPI), sử dụng giá trị tháng trước.
