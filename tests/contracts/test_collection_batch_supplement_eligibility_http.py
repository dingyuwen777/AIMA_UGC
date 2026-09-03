from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.contracts.http import (
    CollectionBatchSupplementEligibilityResponse,
    CollectionRunCreateRequest,
    CollectionRunPlatformRequest,
)
from pydantic import ValidationError


def test_batch_supplement_eligibility_exposes_only_platform_target_counts() -> None:
    batch_id = uuid4()
    response = CollectionBatchSupplementEligibilityResponse(
        batch_id=batch_id,
        targets=(
            {"platform": "xiaohongshu", "target_count": 3},
            {"platform": "weibo", "target_count": 1},
        ),
    )

    assert response.batch_id == batch_id
    assert len(response.targets) == 2
    assert [(item.platform, item.target_count) for item in response.targets] == [
        ("xiaohongshu", 3),
        ("weibo", 1),
    ]
    assert response.model_dump(mode="json") == {
        "batch_id": str(batch_id),
        "targets": [
            {"platform": "xiaohongshu", "target_count": 3},
            {"platform": "weibo", "target_count": 1},
        ],
    }


def test_campaign_is_a_first_class_batch_supplement_source() -> None:
    campaign_id = uuid4()
    request = CollectionRunCreateRequest(
        mode="batch_supplement",
        data_import_campaign_id=campaign_id,
        platforms=(
            CollectionRunPlatformRequest(
                platform="xiaohongshu",
                provider_config_id=uuid4(),
            ),
        ),
    )

    assert request.data_import_campaign_id == campaign_id
    assert request.import_batch_id is None


def test_batch_supplement_source_is_exactly_one_of_batch_or_campaign() -> None:
    with pytest.raises(ValidationError):
        CollectionRunCreateRequest(
            mode="batch_supplement",
            import_batch_id=uuid4(),
            data_import_campaign_id=uuid4(),
            platforms=(
                CollectionRunPlatformRequest(
                    platform="xiaohongshu",
                    provider_config_id=uuid4(),
                ),
            ),
        )
