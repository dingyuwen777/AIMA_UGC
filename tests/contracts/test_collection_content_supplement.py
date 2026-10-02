from uuid import uuid4

import pytest
from aima_ugc.contracts.http import CollectionRunCreateRequest, CollectionSupplementPreviewRequest
from pydantic import ValidationError


def content_request(**options: object) -> CollectionRunCreateRequest:
    """从正式创建 Contract 构造用户显式选择请求。"""
    return CollectionRunCreateRequest.model_validate(
        {
            "mode": "content_supplement",
            "supplement_targets": {"kind": "selected", "content_ids": [str(uuid4())]},
            "expected_target_count": 1,
            "expected_target_fingerprint": "a" * 64,
            "platforms": [{"platform": "douyin", "provider_config_id": str(uuid4())}],
            **options,
        }
    )


def test_unified_content_supplement_accepts_explicit_selection() -> None:
    """新模式与 Preview 身份能够通过正式公开边界。"""
    request = content_request()
    assert request.mode == "content_supplement"
    assert request.supplement_targets is not None
    assert request.supplement_targets.kind == "selected"


@pytest.mark.parametrize(
    "field", ["supplement_targets", "expected_target_count", "expected_target_fingerprint"]
)
def test_content_supplement_requires_preview_identity(field: str) -> None:
    """确认不能省略用户已经预览的目标边界。"""
    with pytest.raises(ValidationError):
        content_request(**{field: None})


def test_selected_deduplicates_and_enforces_the_public_input_limit() -> None:
    identity = uuid4()
    request = content_request(
        supplement_targets={"kind": "selected", "content_ids": [identity, identity]}
    )
    assert request.supplement_targets.content_ids == (identity,)
    assert (
        len(
            content_request(
                supplement_targets={
                    "kind": "selected",
                    "content_ids": [uuid4() for _ in range(1000)],
                }
            ).supplement_targets.content_ids
        )
        == 1000
    )
    for ids in ([], [uuid4() for _ in range(1001)], ["not-a-uuid"]):
        with pytest.raises(ValidationError):
            content_request(supplement_targets={"kind": "selected", "content_ids": ids})


@pytest.mark.parametrize(
    "targets",
    [
        {"kind": "query", "query": {}},
        {"kind": "all"},
        {"kind": "selected", "content_ids": [str(uuid4())], "query": {}},
    ],
)
def test_supplement_does_not_accept_arbitrary_query_or_mixed_targets(
    targets: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        content_request(supplement_targets=targets)


def test_selected_cannot_disable_comments_or_filter_out_platforms() -> None:
    with pytest.raises(ValidationError):
        content_request(include_comments=False)
    with pytest.raises(ValidationError):
        CollectionSupplementPreviewRequest(
            targets={"kind": "selected", "content_ids": [uuid4()]}, platforms=("douyin",)
        )
