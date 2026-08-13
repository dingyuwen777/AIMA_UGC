"""Stage 3B Canonical V1 契约测试。"""

import json
from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "contracts" / "canonical" / "examples" / "content.aggregate.v1.json"


def example_payload() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_canonical_v1_contracts_are_available() -> None:
    canonical = import_module("aima_ugc.contracts.canonical")
    assert canonical.CanonicalContentV1.model_fields["schema_version"].default == "content.v1"
    assert canonical.CanonicalCommentV1.model_fields["schema_version"].default == "comment.v1"
    assert (
        canonical.CanonicalContentAggregateV1.model_fields["schema_version"].default
        == "content.aggregate.v1"
    )


def test_content_aggregate_example_represents_full_post_view() -> None:
    canonical = import_module("aima_ugc.contracts.canonical")
    aggregate = canonical.CanonicalContentAggregateV1.model_validate_json(
        EXAMPLE.read_text(encoding="utf-8")
    )

    assert aggregate.content.external_content_id == "note_123"
    assert aggregate.content.author is not None
    assert aggregate.content.author.external_account_id == "user_001"
    assert aggregate.content.metrics.like_count == 152
    assert aggregate.content.metrics.comment_count == 27
    assert aggregate.comment_coverage.status == "partial"
    assert aggregate.comment_coverage.reported_total == 27
    assert aggregate.comment_coverage.captured_count == 2
    assert aggregate.system.first_seen_at <= aggregate.system.last_seen_at
    assert len(aggregate.lineage) == 3

    thread = aggregate.comment_threads[0]
    assert thread.root_comment.external_comment_id == "comment_100"
    assert thread.root_comment.root_comment_id == "comment_100"
    assert thread.root_comment.parent_comment_id is None
    assert thread.root_comment.metrics.like_count == 8
    assert thread.replies[0].external_comment_id == "comment_101"
    assert thread.replies[0].root_comment_id == "comment_100"
    assert thread.replies[0].parent_comment_id == "comment_100"
    assert thread.replies[0].is_by_content_author is True


def test_null_means_unknown_and_zero_is_a_real_observation() -> None:
    canonical = import_module("aima_ugc.contracts.canonical")
    metrics = canonical.CanonicalMetricsV1(like_count=0, comment_count=None)
    assert metrics.like_count == 0
    assert metrics.comment_count is None


def test_observed_fields_reject_duplicates_and_coarse_nested_paths() -> None:
    canonical = import_module("aima_ugc.contracts.canonical")
    source = canonical.CanonicalSourceV1(
        provider_name="file_import",
        operation="fixture",
        observed_at="2026-08-13T04:00:00Z",
    )
    common = {
        "platform": "xiaohongshu",
        "external_content_id": "note_1",
        "content_type": "image_post",
        "observed_at": "2026-08-13T04:00:00Z",
        "source": source,
    }

    with pytest.raises(ValidationError):
        canonical.CanonicalContentV1(**common, observed_fields=["title", "title"])
    with pytest.raises(ValidationError):
        canonical.CanonicalContentV1(**common, observed_fields=["author"])
    with pytest.raises(ValidationError):
        canonical.CanonicalContentV1(**common, observed_fields=["provider.private_field"])


def test_aggregate_rejects_wrong_thread_root_and_coverage_count() -> None:
    canonical = import_module("aima_ugc.contracts.canonical")

    wrong_root = example_payload()
    wrong_root["comment_threads"][0]["replies"][0]["root_comment_id"] = "comment_other"
    with pytest.raises(ValidationError):
        canonical.CanonicalContentAggregateV1.model_validate(wrong_root)

    wrong_count = example_payload()
    wrong_count["comment_coverage"]["captured_count"] = 1
    with pytest.raises(ValidationError):
        canonical.CanonicalContentAggregateV1.model_validate(wrong_count)
