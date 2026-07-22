"""Phân loại dữ liệu (data taxonomy) cho dự án crawl CK Việt Nam.

3 loại chính — theo yêu cầu: tách **khách quan / chủ quan** và KHÔNG lấy dữ liệu tổng hợp:

  - ``objective``         — KHÁCH QUAN: có thể verify, không phụ thuộc ý kiến.
                            Sự kiện doanh nghiệp / công bố thông tin (VSDC, Vietstock
                            disclosure), tin tức fact (cafef, Tier-2 RSS vnexpress),
                            dữ liệu thị trường/macro (OHLCV, VNINDEX, DXY, USD/VND),
                            SSI daily bulletins (market recap).
  - ``subjective_expert`` — CHỦ QUAN CHUYÊN GIA: khuyến nghị / đánh giá / giá mục tiêu
                            của CTCK & analyst. Toàn bộ báo cáo phân tích trên Vietstock
                            (PDF, cột ``source`` = VNDS/VPX/MBS/KBSV/Vietcap/FPTS/...),
                            HSC Research Insights, VNDIRECT research notes.
  - ``subjective_crowd``  — CHỦ QUAN ĐÁM ĐÔNG: sentiment / ý kiến nhà đầu tư cá nhân.
                            Telegram channels (``telegram_crawler.py``). Forum/comment: sau.

KHÔNG thu thập "dữ liệu tổng hợp" (sentiment index đã aggregate, summary stats). Mọi
bản ghi đều là raw record nguyên bản (1 post / 1 report / 1 disclosure).

Quy tắc phân loại (xem ``classify``): toàn bộ dataset ``vnstock_articles`` là báo cáo
phân tích CTCK → ``subjective_expert``. Các nguồn tin tức phân theo ``source`` qua map.
Source không rõ → ``objective`` (default thận trọng).
"""
from __future__ import annotations

OBJECTIVE = "objective"
SUBJECTIVE_EXPERT = "subjective_expert"
SUBJECTIVE_CROWD = "subjective_crowd"

ALL = (OBJECTIVE, SUBJECTIVE_EXPERT, SUBJECTIVE_CROWD)

# Map cột `source` → data_type. Dùng cho news_articles (cafef/ssi/hsc/vndirect) +
# objective layer (vsdc/vietstock_disclosure/vnexpress/macro).
# - ssi  = daily market bulletins (factual recap) → objective (có thể lẫn ý kiến chiến
#          lược, nhưng phần lớn dữ liệu thị trường).
# - hsc  = Research Insights (analyst) → subjective_expert.
# - vndirect = research notes (company/sector/strategy/economics) → subjective_expert.
_BY_SOURCE: dict[str, str] = {
    # objective
    "vsdc": OBJECTIVE,
    "vietstock_disclosure": OBJECTIVE,
    "vnexpress": OBJECTIVE,
    "macro": OBJECTIVE,
    "cafef": OBJECTIVE,
    "cafebiz": OBJECTIVE,
    "thoibaotaichinhvietnam": OBJECTIVE,
    "vietnamfinance": OBJECTIVE,
    "ssi": OBJECTIVE,
    "tuoitre": OBJECTIVE,
    "thanhnien": OBJECTIVE,
    "vietnamplus": OBJECTIVE,
    "vietnambiz": OBJECTIVE,
    # subjective_expert
    "hsc": SUBJECTIVE_EXPERT,
    "vndirect": SUBJECTIVE_EXPERT,
    # subjective_crowd
    "telegram": SUBJECTIVE_CROWD,
}


def classify(source: str) -> str:
    """Phân loại theo cột ``source`` → data_type. Source không rõ → ``objective``.

    Lưu ý: dataset ``vnstock_articles`` (báo cáo phân tích CTCK, source = mã broker)
    KHÔNG đi qua hàm này — script tag gán thẳng ``subjective_expert`` cho toàn bộ.
    """
    return _BY_SOURCE.get((source or "").strip().lower(), OBJECTIVE)
