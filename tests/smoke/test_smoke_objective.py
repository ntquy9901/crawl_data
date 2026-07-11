"""Smoke (gate): objective schema imports under uv 3.13 and a full ObjectiveRecord
builds end-to-end with computed identity fields. No network."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def test_objective_schema_imports():
    from objective.schema import (  # noqa: F401
        EventType,
        ObjectiveRecord,
        canonicalize_url,
        compute_checksum,
        make_document_id,
    )
    assert len(EventType.ALL) == 16


def test_build_record_end_to_end():
    """Happy path: a disclosure → ObjectiveRecord with checksum + document_id wired."""
    from objective.schema import ObjectiveRecord, compute_checksum, make_document_id

    source = "vsdc"
    url = "https://vsd.vn/vi/ad/198000?utm_source=feed&ref=home"
    title = "Thông báo cổ tức VNM"
    body = "<p>Công ty cổ phần sữa Việt Nam thông báo cổ tức bằng tiền mặt 10%.</p>"

    rec = ObjectiveRecord(
        document_id=make_document_id(source, url),
        source=source,
        source_tier="tier1",
        url=url,  # adapter stores canonical form in practice; field accepts raw here
        publish_time="2026-07-10T00:00:00Z",
        crawl_time="2026-07-11T00:00:00Z",
        company_code="VNM",
        company_name="Công ty CP Sữa Việt Nam",
        title=title,
        raw_text=body,
        language="vi",
        category="cbtt",
        event_type="dividend",
        checksum=compute_checksum(body),
    )
    assert rec.document_id and len(rec.document_id) == 16
    assert rec.checksum and len(rec.checksum) == 64
    assert rec.event_type == "dividend"
    assert rec.company_code == "VNM"
