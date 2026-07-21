"""
SSI crawler — Bản Tin Thị trường (PDF bulletins hằng ngày) từ ssi.com.vn.

Nguồn listing-complete: trang `ban-tin-thi-truong?page=N` đã có sẵn mỗi bulletin
(title + sapo + date + link download PDF) → KHÔNG cần fetch từng bài. Override
`_fetch_and_parse` để build record từ item luôn (bypass fetch).

Dùng: python ssi_crawler.py --latest              # tin mới nhất
       python ssi_crawler.py --range --from-date 2026-06-01 --end-date 2026-06-30
       python ssi_crawler.py --latest --test       # 5 bài thử
"""

import re

from base_news_crawler import BaseNewsCrawler, now_iso, short_id, strip_html


class SsiCrawler(BaseNewsCrawler):
    source = "ssi"
    base_url = "https://www.ssi.com.vn"
    LISTING = f"{base_url}/khach-hang-ca-nhan/ban-tin-thi-truong"

    def listing_url(self, page: int) -> str:
        return f"{self.LISTING}?page={page}"

    def parse_listing(self, html_text: str, page: int) -> list:
        """Mỗi card `chart__content__item--undetail` → 1 bulletin (title/lead/date/pdf)."""
        items = []
        for card in re.split(r"chart__content__item--undetail", html_text)[1:]:
            card = card[:3000]  # giới hạn trong 1 card
            m_title = re.search(r'<a class="titlePost"[^>]*>(.*?)</a>', card, re.S)  # noqa: S8786
            m_date = re.search(r"<span>(\d{2}/\d{2}/\d{4})</span>", card)
            m_pdf = re.search(r'href="(https://[^"]*/analysis-center/report/download/[^"]+)"', card)  # noqa: S8786
            if not (m_date and m_pdf):
                continue
            m_lead = re.search(r'chart__content__item__desc__info">(.*?)</div>', card, re.S)  # noqa: S8786
            lead = strip_html(m_lead.group(1))[:500] if m_lead else ""
            items.append({
                "url": m_pdf.group(1),                       # id ổn định = link download
                "pdf_url": m_pdf.group(1),
                "title": strip_html(m_title.group(1)) if m_title else "",
                "pub_date": m_date.group(1),                 # DD/MM/YYYY
                "lead": lead,
                "category": "Bản Tin Thị Trường",
            })
        return items

    def next_page(self, cur: int, html_text: str):
        """Có link ?page=cur+1 thì đi tiếp, không thì hết."""
        return cur + 1 if f"?page={cur + 1}" in html_text else None

    def _fetch_and_parse(self, item: dict):
        """Listing đã đủ metadata → không fetch trang bài (link là PDF)."""
        return {
            "id": short_id(item["url"]),
            "source": self.source,
            "title": item.get("title", ""),
            "category": item.get("category", ""),
            "pub_date": item.get("pub_date", ""),
            "url": item["url"],
            "author": "SSI",
            "lead": item.get("lead", ""),
            "pdf_url": item.get("pdf_url", ""),
            "pdf_filename": "",
            "collected_at": now_iso(),
        }


if __name__ == "__main__":
    SsiCrawler.cli()
