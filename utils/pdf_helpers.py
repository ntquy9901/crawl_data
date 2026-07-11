"""PDF filename + path helpers shared by crawler and backfill scripts."""
from __future__ import annotations


def generate_pdf_filename(title: str, date_str: str) -> str:
    """Sanitized PDF filename: {date}_{title}.pdf.

    Title truncated to 50 chars; only alnum/space/-/_ kept (Vietnamese
    alphanumerics preserved — str.isalnum is unicode-aware); spaces→underscores.
    Date '/' and spaces → '-'/'_'.
    """
    clean_title = (title or "").strip()[:50]
    clean_title = "".join(c for c in clean_title if c.isalnum() or c in (" ", "-", "_"))
    clean_title = clean_title.replace(" ", "_")
    clean_date = (date_str or "").replace("/", "-").replace(" ", "_")
    return f"{clean_date}_{clean_title}.pdf"
