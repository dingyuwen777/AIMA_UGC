from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.contracts.http import CollectionRunCreateRequest
from pydantic import ValidationError


def date_request(**options: object) -> CollectionRunCreateRequest:
    return CollectionRunCreateRequest.model_validate(
        {
            "mode": "date_supplement",
            "published_from": "2026-09-01T00:00:00+08:00",
            "published_to": "2026-09-01T23:59:59.999+08:00",
            "platforms": [{"platform": "douyin", "provider_config_id": str(uuid4())}],
            **options,
        }
    )


def test_date_supplement_accepts_beijing_closed_range() -> None:
    request = date_request()
    assert request.mode == "date_supplement"
    assert request.published_from.isoformat() == "2026-09-01T00:00:00+08:00"


@pytest.mark.parametrize(
    "options",
    [
        {"published_from": None},
        {"published_to": None},
        {"published_from": "2026-09-01T00:00:00"},
        {"published_to": "2026-08-01T00:00:00+08:00"},
        {"import_batch_id": str(uuid4())},
        {"data_import_campaign_id": str(uuid4())},
        {"keyword_pack_ids": [str(uuid4())]},
        {"brand_ids": [str(uuid4())]},
        {"include_comments": False, "include_sub_comments": True},
    ],
)
def test_date_supplement_rejects_invalid_or_mixed_selection(options: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        date_request(**options)


def test_legacy_supplement_rejects_dates() -> None:
    with pytest.raises(ValidationError):
        date_request(mode="batch_supplement", import_batch_id=str(uuid4()))
