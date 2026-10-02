from uuid import uuid4

import pytest
from aima_ugc.contracts.http import (
    CollectionRunCreateRequest,
    CollectionSupplementPreviewRequest,
)


@pytest.mark.parametrize("kind", ["selected", "published_date_range"])
def test_supplement_preview_defaults_to_root_comments_and_replies(kind: str) -> None:
    targets = (
        {"kind": kind, "content_ids": [str(uuid4())]}
        if kind == "selected"
        else {
            "kind": kind,
            "published_from": "2026-09-01T00:00:00+08:00",
            "published_to": "2026-09-01T23:59:59+08:00",
        }
    )
    request = CollectionSupplementPreviewRequest.model_validate({"targets": targets})
    assert request.include_comments is True
    assert request.include_sub_comments is True


def test_manual_discovery_defaults_to_root_comments_and_replies() -> None:
    request = CollectionRunCreateRequest.model_validate(
        {
            "mode": "discovery",
            "keyword_pack_ids": [str(uuid4())],
            "platforms": [{"platform": "douyin", "provider_config_id": str(uuid4())}],
        }
    )
    assert request.include_comments is True
    assert request.include_sub_comments is True
