"""Extract full article body text from HTML pages or PDF files.

Per-source XPath selectors (discovered empirically — see tests/fixtures/) plus a
generic fallback chain. Feeds the `body` column: title+lead alone underperform
for ticker matching / embeddings (title match 16.7%, title+lead 19.9%).
"""
from __future__ import annotations

import html as html_mod
import re
from pathlib import Path

import fitz  # PyMuPDF
from lxml import etree
from lxml import html as lxml_html

_MAIN_XPATH = '//main'

# Per-source XPath for the article body container (discovered via spike).
# cafef: div.detail-content is the scoped article text (excludes the 26k-char
#        contentdetail wrapper that drags in related-news + comments).
# hsc:   main > section.container holds the research-insight summary.
# vndirect: article-content (confirmed at phase-7 Cloudflare/Playwright spike).
SOURCE_XPATH: dict[str, list[str]] = {
    "cafef": ['//div[contains(@class,"detail-content")]'],
    "hsc": [
        '//main/section[contains(@class,"container")]',
        _MAIN_XPATH,
    ],
    "vndirect": [
        '//div[contains(@class,"content-single")]',
        '//div[contains(@class,"section-content")]',
        _MAIN_XPATH,
    ],
}

# Generic fallback chain tried after the source-specific selectors.
FALLBACK_XPATH = [
    '//article',
    '//div[contains(@class,"article-body")]',
    '//div[contains(@class,"post-content")]',
    '//div[contains(@class,"entry-content")]',
    '//div[@itemprop="articleBody"]',
    _MAIN_XPATH,
]

# Short all-caps boilerplate lines to drop (site widgets prefixed to body text).
_BOILERPLATE = re.compile(r"^(TIN MỚI|XEM THÊM|ĐỌC THÊM|MỚI NHẤT|LIÊN QUAN|HOT)$")
_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n\s*\n+")


_SKIP_TAGS = {"script", "style", "noscript"}


def _text_len(el) -> int:
    """Non-mutating visible-text length of an element (excludes script/style)."""
    total = 0
    for node in el.iter():
        if node.tag in _SKIP_TAGS:
            continue
        if node.text:
            total += len(node.text)
        if node is not el and node.tail:
            total += len(node.tail)
    return total


def _element_text(el) -> str:
    """All visible text of an lxml element (script/style dropped), as a string.

    Mutating (drops script/style subtrees) — call once on the chosen element."""
    for bad in el.xpath(".//script | .//style | .//noscript"):
        bad.drop_tree()
    return etree.tostring(el, method="text", encoding="unicode")


def normalize_body(text: str, max_chars: int | None = None) -> str:
    """Clean extracted text: unescape entities, drop boilerplate/short junk lines,
    collapse whitespace, keep paragraphs joined by single newlines. Optional
    head+tail truncation."""
    if not text:
        return ""
    text = html_mod.unescape(text)
    lines = []
    for raw in text.splitlines():
        line = _WS.sub(" ", raw).strip()
        if not line or _BOILERPLATE.match(line.upper()):
            continue
        lines.append(line)
    out = _BLANK.sub("\n", "\n".join(lines)).strip()
    if max_chars and len(out) > max_chars:
        keep = max_chars // 2
        out = f"{out[:keep]}\n[…truncated…]\n{out[-keep:]}"
    return out


def extract_html_body(html_text: str, source: str, max_chars: int = 20000) -> str:
    """Extract article body from a full article-page HTML string.

    Tries per-source XPath, then a generic fallback. Returns normalized plain
    text (paragraphs joined by newline), or "" if no container yields ≥200 chars.
    """
    if not html_text:
        return ""
    try:
        tree = lxml_html.fromstring(html_text)
    except Exception:  # noqa: BLE001
        return ""
    for xp in [*SOURCE_XPATH.get(source, []), *FALLBACK_XPATH]:
        try:
            els = tree.xpath(xp)
        except Exception:  # noqa: BLE001
            continue
        if not els:
            continue
        best = max(els, key=_text_len)  # non-mutating selection
        if _text_len(best) >= 200:
            return normalize_body(_element_text(best), max_chars=max_chars)
    return ""


def extract_pdf_body(pdf_path: str | Path, max_chars: int = 30000) -> str:
    """Extract body text from a PDF via PyMuPDF. Joins pages, fixes hyphenation
    across line breaks, drops short boilerplate lines. Returns '' for
    scanned/image PDFs (no extractable text)."""
    p = Path(pdf_path)
    if not p.exists():
        return ""
    try:
        doc = fitz.open(p)
    except Exception:  # noqa: BLE001
        return ""
    try:
        raw = "\n".join(page.get_text() for page in doc)
    except Exception:  # noqa: BLE001 — malformed PDF (syntax error / stack overflow)
        return ""
    finally:
        doc.close()
    if not raw.strip():
        return ""  # likely scanned/image
    raw = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)  # de-hyphenate line breaks (\w is unicode-aware)
    return normalize_body(raw, max_chars=max_chars)


def resolve_pdf_local_path(
    source: str, row: dict, data_path: Path | None = None
) -> Path | None:
    """Map a CSV row to its local PDF path, or None if not downloaded.

    vietstock: data/pdf/{pdf_filename}
    ssi:       data/pdf_ssi/{id}.pdf  (id = short_id(url), unique)
    """
    base = Path(data_path) if data_path else Path(__file__).resolve().parent.parent / "data"
    if source == "vietstock":
        fn = (row.get("pdf_filename") or "").strip()
        return base / "pdf" / fn if fn else None
    if source == "ssi":
        sid = str(row.get("id") or "").strip()
        return base / "pdf_ssi" / f"{sid}.pdf" if sid else None
    return None
