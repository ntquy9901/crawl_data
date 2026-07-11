"""BaseObjectiveCrawler — framework for objective-data HTTP adapters (AD-7).

Subclasses ``BaseNewsCrawler`` and overrides the CSV/dedup/fetch seams so an
objective adapter emits the canonical ObjectiveRecord schema (AD-1) with UTC
timestamps (AD-3), content checksum (AD-6), per-source document_id (AD-13), and
raw-bytes preservation (AD-2) — without re-implementing the listing/paginate/
resume flow it inherits.

Contract for subclasses (the Template-Method hooks, same names as the base):
  - ``source`` / ``source_tier``  — adapter key + tier ("tier1"|"tier2"|"tier3")
  - ``listing_url(page)``         — listing URL for page N
  - ``parse_listing(html, page)`` -> list[dict] (each item needs ``url``)
  - ``parse_article(html, item)`` -> dict of objective payload fields:
        title, publish_time, company_code, company_name, raw_text, language,
        category, event_type, attachment_urls (list[str])
  - ``next_page(cur, html)``      — next page number or None

``_fetch_and_parse`` returns a dict keyed by ``OBJECTIVE_HEADERS`` (so the base
``_process_items`` resume/append flow keeps working); ``build_objective`` (4.1)
re-hydrates these rows back into ``ObjectiveRecord`` dataclasses.
"""
from __future__ import annotations

import csv
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from base_news_crawler import (
    DATA_PATH,  # project-root/data
    BaseNewsCrawler,
)
from objective.schema import (
    EventType,
    ObjectiveRecord,  # noqa: F401  (re-exported for adapters)
    canonicalize_url,
    compute_checksum,
    make_document_id,
)

_VN_TZ = timezone(timedelta(hours=7))  # Vietnam — AD-3 assumption for no-offset sources

# Canonical CSV columns = the ObjectiveRecord field set (AD-1), in declaration order.
OBJECTIVE_HEADERS = [f.name for f in dataclass_fields(ObjectiveRecord)]

_DATEONLY_FMTS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
_NAIVE_DT_FMTS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")
_TZ_DT_FMTS = ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z")


def now_utc() -> str:
    """Current time as canonical UTC ``YYYY-MM-DDTHH:MM:SSZ`` (AD-3)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc(value) -> str:
    """Normalize an arbitrary source timestamp to canonical UTC (AD-3).

    Rules (the adversarial conformance): tz-aware (offset or ``Z``) → UTC;
    naive (no offset) → assume Vietnam +07 then convert; date-only →
    ``YYYY-MM-DDT00:00:00Z``; unparseable/empty → ``""`` (``build_objective``
    rejects non-canonical rows).
    """
    if not value:
        return ""
    s = str(value).strip()
    # 1. full datetime with offset/Z
    for fmt in _TZ_DT_FMTS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    # 2. naive datetime → assume +07
    for fmt in _NAIVE_DT_FMTS:
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=_VN_TZ)
            return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    # 3. date-only → midnight UTC
    for fmt in _DATEONLY_FMTS:
        try:
            d = datetime.strptime(s, fmt).date()
            return f"{d.isoformat()}T00:00:00Z"
        except ValueError:
            pass
    return ""


class BaseObjectiveCrawler(BaseNewsCrawler):
    """Objective-data adapter base. Subclass + override the hooks; do not
    override the flow methods (crawl_latest/crawl_range/_process_items)."""

    source = "objective-base"
    source_tier = "tier1"

    def __init__(self, csv_file=None, raw_root: Path | None = None, **kwargs):
        # default output: data/objective/<source>_records.csv (AD-2 cleaned layer)
        if csv_file is None:
            csv_file = DATA_PATH / "objective" / f"{self.source}_records.csv"
        super().__init__(csv_file=csv_file, **kwargs)
        self.raw_dir = (raw_root or (DATA_PATH / "raw")) / self.source
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    # ---- CSV seam: ObjectiveRecord headers, not the base CSV_HEADERS ----
    def _init_csv(self):
        if not self.csv_file.exists():
            with open(self.csv_file, "w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow(OBJECTIVE_HEADERS)

    def _append(self, records):
        self._init_csv()
        with open(self.csv_file, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OBJECTIVE_HEADERS)
            for r in records:
                row = dict(r)
                att = row.get("attachment_urls")
                if isinstance(att, list):
                    row["attachment_urls"] = "|".join(att)
                w.writerow({k: row.get(k, "") for k in OBJECTIVE_HEADERS})

    def _load_seen(self) -> set:
        seen: set[str] = set()
        if self.csv_file.exists():
            try:
                with open(self.csv_file, encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        u = row.get("url")
                        if u:
                            seen.add(u)
            except Exception as e:  # noqa: BLE001
                print(f"warn: load seen: {e}")
        return seen

    # ---- raw preservation (AD-2) ----
    def _save_raw(self, document_id: str, content: str, ext: str = "html") -> str:
        p = self.raw_dir / f"{document_id}.{ext}"
        try:
            p.write_text(content, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            self._audit(f"RAW SAVE FAIL {p} -> {e}")
            return ""
        # store path relative to project root for portability
        try:
            return str(p.relative_to(DATA_PATH.parent))
        except ValueError:
            return str(p)

    # ---- the core override: build an objective row from a fetched page ----
    def _fetch_and_parse(self, item: dict) -> dict | None:
        url = item["url"]
        html_text = self.fetch(url)
        if not html_text:
            return None
        payload = self.parse_article(html_text, item) or {}
        raw_text = payload.get("raw_text", "")
        doc_id = make_document_id(self.source, url)
        return {
            "document_id": doc_id,
            "source": self.source,
            "source_tier": self.source_tier,
            "url": canonicalize_url(url),
            "publish_time": to_utc(payload.get("publish_time", "")),
            "crawl_time": now_utc(),
            "company_code": (payload.get("company_code") or "").strip().upper(),
            "company_name": payload.get("company_name", ""),
            "title": payload.get("title") or item.get("title", ""),
            "raw_text": raw_text,
            "language": payload.get("language", "vi"),
            "category": payload.get("category", ""),
            "event_type": payload.get("event_type") or EventType.OTHER,
            "attachment_urls": list(payload.get("attachment_urls", [])),
            "checksum": compute_checksum(raw_text),
            "raw_path": self._save_raw(doc_id, html_text),
        }
