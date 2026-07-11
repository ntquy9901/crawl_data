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
from datetime import UTC, datetime, time, timedelta, timezone
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
    deserialize_attachment_urls,
    make_document_id,
    serialize_attachment_urls,
)

_VN_TZ = timezone(timedelta(hours=7))  # Vietnam — AD-3 assumption for no-offset sources
_MIDNIGHT = time(0, 0)

# Canonical CSV columns = the ObjectiveRecord field set (AD-1), in declaration order.
OBJECTIVE_HEADERS = [f.name for f in dataclass_fields(ObjectiveRecord)]

_DATEONLY_FMTS = ("%d/%m/%Y", "%d-%m-%Y")  # non-ISO date-only (ISO handled by fromisoformat)


def now_utc() -> str:
    """Current time as canonical UTC ``YYYY-MM-DDTHH:MM:SSZ`` (AD-3)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc(value) -> str:
    """Normalize an arbitrary source timestamp to canonical UTC (AD-3).

    Rules: tz-aware (offset or ``Z``, incl. fractional seconds) → UTC; naive
    (no offset) → assume Vietnam +07 then convert, EXCEPT a naive midnight which
    uses the date-only form (so ``2026-07-10`` == ``2026-07-10 00:00:00`` ==
    ``2026-07-10T00:00:00``); date-only → ``YYYY-MM-DDT00:00:00Z``; unparseable
    → ``""`` (``build_objective`` rejects non-canonical rows).
    """
    if not value:
        return ""
    s = str(value).strip()
    # 1. ISO-8601 via fromisoformat — handles offset, 'Z', fractional seconds (3.11+).
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = None
    if dt is not None:
        if dt.tzinfo is None:
            if dt.time() == _MIDNIGHT:
                return f"{dt.date().isoformat()}T00:00:00Z"  # date-only canonical (consistency)
            dt = dt.replace(tzinfo=_VN_TZ)  # naive non-midnight → assume +07
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    # 2. non-ISO date-only formats (dd/mm/yyyy, dd-mm-yyyy)
    for fmt in _DATEONLY_FMTS:
        try:
            return f"{datetime.strptime(s, fmt).date().isoformat()}T00:00:00Z"
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
                    row["attachment_urls"] = serialize_attachment_urls(att)
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

    # ---- the core override: fetch → parse → universe-filter → build row ----
    def _fetch_and_parse(self, item: dict) -> dict | None:
        if not self._keep_item(item):  # pre-fetch universe filter (skip before network)
            return None
        url = item["url"]
        html_text = self.fetch(url)
        if not html_text:
            return None
        payload = self.parse_article(html_text, item) or {}
        if not self._keep_payload(payload):
            return None
        return self._build_row(url, html_text, payload, item)

    def _dedup_key(self, url: str) -> str:
        """Resume dedup on the CANONICAL url (AD-13) — fixes raw-vs-canonical
        mismatch with the inherited ``_process_items`` seen-set."""
        return canonicalize_url(url)

    def _keep_item(self, item: dict) -> bool:
        """Pre-fetch universe filter (AD-4/5). Default True; Tier-1 adapters
        whose listing already carries company_code override to skip non-VN30
        before the (expensive) network call."""
        return True

    def _keep_payload(self, payload: dict) -> bool:
        """Post-parse universe filter (AD-4/5). Default True; Tier-1 adapters
        override to keep only VN30 (covers sources where company_code is only
        extractable from the detail page)."""
        return True

    def _build_row(self, url: str, html_text: str, payload: dict, item: dict) -> dict:
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


def row_to_objective_record(row: dict) -> ObjectiveRecord:
    """Re-hydrate an ObjectiveRecord from a CSV row (build_objective uses this).

    Closes the CSV round-trip the foundation's append serializer implies:
    attachment_urls is JSON-deserialized back to a list."""
    return ObjectiveRecord(
        document_id=row.get("document_id", ""),
        source=row.get("source", ""),
        source_tier=row.get("source_tier", ""),
        url=row.get("url", ""),
        publish_time=row.get("publish_time", ""),
        crawl_time=row.get("crawl_time", ""),
        company_code=row.get("company_code", ""),
        company_name=row.get("company_name", ""),
        title=row.get("title", ""),
        raw_text=row.get("raw_text", ""),
        language=row.get("language", "vi"),
        category=row.get("category", ""),
        event_type=row.get("event_type", "") or EventType.OTHER,
        attachment_urls=deserialize_attachment_urls(row.get("attachment_urls", "")),
        checksum=row.get("checksum", ""),
        raw_path=row.get("raw_path", ""),
    )
