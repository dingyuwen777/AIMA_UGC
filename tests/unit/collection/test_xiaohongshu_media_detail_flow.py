"""正式详情编排按已知类型选择一次调用，未知类型最多补一次视频详情。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.collection_scope import (
    TikHubCollectionScopeExecutor,
    _ExecutedCall,
    _ScopeStats,
)
from aima_ugc.contracts.canonical import CanonicalContentV1, CanonicalSourceV1

FIXTURES = Path(__file__).parents[2] / "fixtures/providers/tikhub/xiaohongshu"
NOTE_ID = "a00000000000000000000001"
NOW = datetime(2026, 10, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    ("content_type", "operations", "malformed"),
    [
        ("image", ["get_image_note_detail"], None),
        ("video", ["get_video_note_detail"], None),
        ("unknown", ["get_image_note_detail", "get_video_note_detail"], None),
        ("note", ["get_image_note_detail", "get_video_note_detail"], None),
        ("unknown", ["get_image_note_detail", "get_video_note_detail"], "empty"),
        ("unknown", ["get_image_note_detail", "get_video_note_detail"], "wrong_identity"),
        ("unknown", ["get_image_note_detail", "get_video_note_detail"], "mapping_invalid"),
    ],
)
def test_detail_flow_uses_checked_identity_and_bounded_video_followup(
    monkeypatch: pytest.MonkeyPatch,
    content_type: str,
    operations: list[str],
    malformed: str | None,
) -> None:
    calls: list[str] = []

    def execute_call(_self, **kwargs):
        call = kwargs["call"]
        calls.append(call.operation)
        assert call.params["note_id"] == NOTE_ID
        fixture = (
            "video_detail_20261009.sanitized.json"
            if call.operation == "get_video_note_detail"
            else "video_cover_detail_20261009.sanitized.json"
        )
        body = json.loads((FIXTURES / fixture).read_text("utf-8"))
        if call.operation == "get_video_note_detail":
            if malformed == "empty":
                body = {"data": {"data": []}}
            elif malformed == "wrong_identity":
                body["data"]["data"][0]["id"] = "other-note"
            elif malformed == "mapping_invalid":
                body["data"]["data"][0] = {"id": NOTE_ID, "note": {"type": "video"}}
        return _ExecutedCall(
            request_id=uuid4(),
            attempt_id=uuid4(),
            raw_artifact_id=uuid4(),
            observed_at=NOW,
            body=body,
        )

    executor = TikHubCollectionScopeExecutor(
        session_factory=lambda: None,
        raw_artifacts=None,
        artifacts=None,
        artifact_store=None,
        transport_factory=lambda _: None,
        secret_resolver=lambda _: None,
    )
    executor._content_writer = SimpleNamespace(
        discover_candidate=lambda **_: uuid4(), record_candidate_failure=lambda **_: None
    )
    executor._persistent_filter_inputs = lambda **kwargs: kwargs["expected"]
    monkeypatch.setattr(TikHubCollectionScopeExecutor, "_execute_call", execute_call)
    source = CanonicalSourceV1(
        provider_name="tikhub",
        operation="search_notes",
        source_type="keyword_search",
        source_value="fixture",
        provider_request_id=str(uuid4()),
        provider_attempt_id=str(uuid4()),
        raw_artifact_id=uuid4(),
        item_locator=f"note:{NOTE_ID}",
        observed_at=NOW,
    )
    content = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id=NOTE_ID,
        alternate_ids={"note_id": NOTE_ID},
        content_type=content_type,
        observed_at=NOW,
        source=source,
        observed_fields=[],
    )
    stats = _ScopeStats()
    result = executor._fetch_detail_candidates(
        run=SimpleNamespace(id=uuid4()),
        scope=SimpleNamespace(
            id=uuid4(), platform="xiaohongshu", source_type="content", source_value=str(uuid4())
        ),
        content=content,
        provider_config=SimpleNamespace(provider="tikhub"),
        context=SimpleNamespace(fence=None),
        stats=stats,
    )
    assert calls == operations
    assert stats.detail_requests == len(operations)
    assert result.candidates[-1].content.external_content_id == NOTE_ID
    if malformed is not None:
        assert (
            len(result.candidates) == 1
            and result.candidates[0].content.media[0].preview_url is not None
        )
        assert result.optional_provider_failure is not None
        assert (
            not result.optional_provider_failure.retryable and stats.technical_partial_results == 1
        )
        return
    assert result.optional_provider_failure is None
    if content_type in {"video", "unknown", "note"}:
        assert result.candidates[-1].content.media[0].url is not None
