"""Canonical contract for the objective-data layer (Architecture AD-1, AD-6, AD-11, AD-13).

Single source of truth for:
  - ObjectiveRecord — the 16-field record every objective adapter emits (AD-1).
  - EventType — the governed event_type enum (AD-11).
  - checksum_normalize / compute_checksum — content identity for cross-source dedup (AD-6).
  - canonicalize_url / make_document_id — per-source identity (AD-13).

No adapter may redefine these; import from here.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field


class EventType:
    """Governed event_type enum (AD-11). VN30 is equity but VSDC carries bond /
    foreign-ownership, so the set is extensible. ``category`` is a separate,
    UNGOVERNED free-text field — do not confuse the two."""

    FINANCIAL_STATEMENT = "financial_statement"
    BOARD_RESOLUTION = "board_resolution"
    DIVIDEND = "dividend"
    STOCK_ISSUANCE = "stock_issuance"
    STOCK_SPLIT = "stock_split"
    RIGHTS_ISSUE = "rights_issue"
    ESOP = "esop"
    INSIDER_TRADING = "insider_trading"
    SHAREHOLDER_CHANGE = "shareholder_change"
    MA = "ma"
    EXEC_CHANGE = "exec_change"
    AGM = "agm"
    BOND_ISSUANCE = "bond_issuance"
    FOREIGN_OWNERSHIP = "foreign_ownership"
    EXTRAORDINARY_ANNOUNCEMENT = "extraordinary_announcement"
    OTHER = "other"

    ALL = frozenset({
        FINANCIAL_STATEMENT, BOARD_RESOLUTION, DIVIDEND, STOCK_ISSUANCE,
        STOCK_SPLIT, RIGHTS_ISSUE, ESOP, INSIDER_TRADING, SHAREHOLDER_CHANGE,
        MA, EXEC_CHANGE, AGM, BOND_ISSUANCE, FOREIGN_OWNERSHIP,
        EXTRAORDINARY_ANNOUNCEMENT, OTHER,
    })


# Canonical 16-field record (AD-1). Adapters fill the required fields; the base
# crawler computes ``checksum`` / ``document_id`` via the helpers below.
@dataclass
class ObjectiveRecord:
    document_id: str          # sha1(source + canonicalize_url(url))[:16] — per-source (AD-13)
    source: str               # adapter key, e.g. "vsdc", "vietstock", "vnexpress"
    source_tier: str          # "tier1" | "tier2" | "tier3"
    url: str                  # canonical (canonicalize_url applied)
    publish_time: str         # ISO-8601 UTC "YYYY-MM-DDTHH:MM:SSZ" (AD-3)
    crawl_time: str           # ISO-8601 UTC
    company_code: str         # uppercase HOSE ticker or "" (AD-4); null⇒"" not None
    company_name: str         # VN30-canonical or "" (AD-12); null code ⇒ null name
    title: str
    raw_text: str             # cleaned body text fed to checksum_normalize (AD-6)
    language: str             # "vi" | "en" | ...
    category: str             # free-text source section — UNGOVERNED (vs event_type)
    event_type: str           # EventType.* value (AD-11)
    attachment_urls: list[str] = field(default_factory=list)
    checksum: str = ""        # sha256(checksum_normalize(raw_text)) (AD-6)
    raw_path: str = ""        # data/raw/<source>/<document_id>.<ext> (AD-2)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def checksum_normalize(text: str) -> str:
    """Content normalizer for cross-source dedup (AD-6).

    NFC unicode → lowercase → strip HTML tags → collapse whitespace.
    Deliberately does NOT truncate (truncation would break conformance across
    sources that capture different lengths of the same disclosure).
    """
    if not text:
        return ""
    # NFC first so diacritics compare equal regardless of source encoding path
    # (HTTP NFC vs Playwright NFD drift — adversarial finding).
    s = unicodedata.normalize("NFC", str(text))
    s = _TAG_RE.sub(" ", s)      # strip HTML tags
    s = s.lower()                # case-insensitive
    s = _WS_RE.sub(" ", s).strip()  # collapse whitespace
    return s


def compute_checksum(raw_text: str) -> str:
    """sha256 hex of the normalized text — the SOLE cross-source identity (AD-6, AD-13)."""
    return hashlib.sha256(checksum_normalize(raw_text).encode("utf-8")).hexdigest()


# Tracking params stripped during URL canonicalization (AD-13).
_TRACKING_PREFIXES = ("utm_", "gclid", "fbclid", "mc_", "ref", "ref_src")


def canonicalize_url(url: str) -> str:
    """Canonical URL for per-source identity + resume dedup (AD-13).

    Lowercase scheme/host, drop fragment, sort query params, strip tracking
    params (utm_*, gclid, fbclid, ...) so ``?a=1&b=2`` and ``?b=2&a=1`` (and
    tracking-laden variants) resolve to one key.
    """
    if not url:
        return ""
    try:
        u = urllib.parse.urlsplit(str(url).strip())
    except ValueError:
        return str(url)
    scheme = u.scheme.lower()
    netloc = u.netloc.lower()
    path = u.path.rstrip("/") or "/"  # treat "" and "/" alike; collapse trailing /
    # Sort + filter query params.
    if u.query:
        pairs = urllib.parse.parse_qsl(u.query, keep_blank_values=False)
        kept = sorted(
            (k, v) for k, v in pairs
            if not any(k.lower() == p or k.lower().startswith(_TRACKING_PREFIXES)
                       for p in ("gclid", "fbclid"))
            and not k.lower().startswith("utm_")
            and not k.lower().startswith("mc_")
            and k.lower() not in ("ref", "ref_src")
        )
        query = urllib.parse.urlencode(kept)
    else:
        query = ""
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))  # drop fragment


def make_document_id(source: str, url: str) -> str:
    """Per-source document identity (AD-13). sha1(source+canonicalize_url(url))[:16].

    Per-source ONLY — never join cross-source on this; use ``checksum`` for that.
    """
    key = f"{source}|{canonicalize_url(url)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def is_valid_event_type(value: str) -> bool:
    return value in EventType.ALL
