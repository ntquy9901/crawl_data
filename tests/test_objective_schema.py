"""Unit tests for objective/schema.py — the canonical contract (AD-1,6,11,13)."""
from __future__ import annotations

from objective.schema import (
    EventType,
    ObjectiveRecord,
    canonicalize_url,
    checksum_normalize,
    compute_checksum,
    is_valid_event_type,
    make_document_id,
)

# ---- checksum_normalize (AD-6) ----

def test_checksum_normalize_lowercases():
    assert checksum_normalize("Công Bố Thông Tin") == "công bố thông tin"


def test_checksum_normalize_nfc_collapses_diacritics():
    # NFC composed vs decomposed (NFD) of the same Vietnamese text must normalize equal.
    import unicodedata
    composed = "Việt Nam Holding"
    decomposed = unicodedata.normalize("NFD", composed)
    assert checksum_normalize(composed) == checksum_normalize(decomposed)


def test_checksum_normalize_strips_html_tags():
    assert checksum_normalize("<p>Cổ tức <b>10%</b></p>") == "cổ tức 10%"


def test_checksum_normalize_collapses_whitespace():
    assert checksum_normalize("  a\n\tb   c  ") == "a b c"


def test_checksum_normalize_does_not_truncate():
    long_text = "cổ tức " * 1000
    out = checksum_normalize(long_text)
    # full length preserved (no truncation) — conformance across sources depends on it
    assert out.startswith("cổ tức cổ tức")
    assert out.count("cổ tức") == 1000


def test_checksum_normalize_empty_and_none():
    assert checksum_normalize("") == ""
    assert checksum_normalize(None) == ""


# ---- compute_checksum (AD-6, AD-13 cross-source identity) ----

def test_compute_checksum_conformance_across_capture_paths():
    """The adversarial conformance test: the same disclosure captured via
    different paths (HTML tags, NFD diacritics, case, whitespace) must yield
    ONE checksum — otherwise cross-source dedup over- or under-fires."""
    base = "Công ty cổ phần VNM thông báo cổ tức bằng tiền mặt 10%"
    variants = [
        base,
        base.upper(),
        "<div><p>" + base + "</p></div>",
        "  " + base.replace(" ", "   ") + "\n",
        __import__("unicodedata").normalize("NFD", base),
    ]
    checksums = {compute_checksum(v) for v in variants}
    assert len(checksums) == 1, f"expected 1 checksum, got {checksums}"


def test_compute_checksum_differing_for_different_text():
    assert compute_checksum("cổ tức 10%") != compute_checksum("cổ tức 11%")


def test_compute_checksum_is_sha256_hex():
    h = compute_checksum("x")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


# ---- EventType (AD-11) ----

def test_event_type_enum_has_16_values():
    assert len(EventType.ALL) == 16


def test_event_type_includes_bond_and_foreign_ownership():
    assert EventType.BOND_ISSUANCE in EventType.ALL
    assert EventType.FOREIGN_OWNERSHIP in EventType.ALL


def test_is_valid_event_type():
    assert is_valid_event_type("dividend")
    assert is_valid_event_type("other")
    assert not is_valid_event_type("cash_dividend")  # taxonomy drift must be rejected
    assert not is_valid_event_type("")


# ---- canonicalize_url (AD-13) ----

def test_canonicalize_url_sorts_query_params():
    assert canonicalize_url("https://vsd.vn/vi/ad/123?b=2&a=1") == \
        "https://vsd.vn/vi/ad/123?a=1&b=2"


def test_canonicalize_url_strips_tracking():
    a = canonicalize_url("https://x.vn/p?utm_source=news&id=5&gclid=abc")
    assert "utm_" not in a and "gclid" not in a
    assert a.endswith("id=5")


def test_canonicalize_url_lowercases_host_drops_fragment_and_trailing_slash():
    # scheme + host are case-insensitive (lowercased); PATH is case-sensitive and
    # MUST be preserved (lowercasing it would falsely merge distinct resources).
    out = canonicalize_url("HTTPS://Site.VN/Path/?x=1#frag")
    assert out == "https://site.vn/Path?x=1"
    assert "#" not in out  # fragment dropped


def test_canonicalize_url_empty():
    assert canonicalize_url("") == ""


# ---- make_document_id (AD-13, per-source) ----

def test_make_document_id_stable():
    assert make_document_id("vsdc", "https://vsd.vn/vi/ad/123") == \
        make_document_id("vsdc", "https://vsd.vn/vi/ad/123")


def test_make_document_id_differs_per_source_same_url():
    # same url across sources → different document_id (per-source identity only)
    assert make_document_id("vsdc", "https://x.vn/p?id=1") != \
        make_document_id("vietstock", "https://x.vn/p?id=1")


def test_make_document_id_url_canonicalization_invariant():
    assert make_document_id("vsdc", "https://x.vn/p?a=1&b=2") == \
        make_document_id("vsdc", "https://x.vn/p?b=2&a=1")


def test_make_document_id_length():
    assert len(make_document_id("s", "u")) == 16


# ---- ObjectiveRecord (AD-1) ----

def test_objective_record_has_exactly_16_fields():
    from dataclasses import fields
    names = [f.name for f in fields(ObjectiveRecord)]
    expected = [
        "document_id", "source", "source_tier", "url", "publish_time", "crawl_time",
        "company_code", "company_name", "title", "raw_text", "language", "category",
        "event_type", "attachment_urls", "checksum", "raw_path",
    ]
    assert names == expected
    assert len(names) == 16


def test_objective_record_attachment_urls_default_isolated():
    # mutable default must not leak between instances
    r1 = _minimal_record()
    r2 = _minimal_record()
    r1.attachment_urls.append("a.pdf")
    assert r2.attachment_urls == []


def _minimal_record() -> ObjectiveRecord:
    return ObjectiveRecord(
        document_id="x" * 16, source="vsdc", source_tier="tier1",
        url="https://vsd.vn/vi/ad/1", publish_time="2026-07-11T00:00:00Z",
        crawl_time="2026-07-11T00:00:00Z", company_code="VNM",
        company_name="Vietnam Dairy", title="t", raw_text="cổ tức 10%",
        language="vi", category="cbtt", event_type="dividend",
    )
