from __future__ import annotations

from uuid import uuid4

from aima_ugc.contracts.http import CollectionBatchSupplementEligibilityResponse


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
