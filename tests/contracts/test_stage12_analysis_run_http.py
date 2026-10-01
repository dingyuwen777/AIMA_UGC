"""Stage 12C Analysis Run/Shard HTTP Contract。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aima_ugc.contracts.http import (
    AnalysisContentRunCreateRequest,
    AnalysisContentRunPreviewRequest,
    AnalysisContentRunResponse,
    AnalysisRunTargetSelection,
    ContentFilterSnapshot,
)
from pydantic import ValidationError


def test_analysis_run_requires_an_explicit_preview_count_and_idempotency_key() -> None:
    content_id = uuid4()
    targets = AnalysisRunTargetSelection(content_ids=(content_id,))

    preview = AnalysisContentRunPreviewRequest(targets=targets)
    created = AnalysisContentRunCreateRequest(
        client_idempotency_key="manual-analysis-20260826-1",
        targets=targets,
        expected_target_count=1,
        expected_configuration_hash="a" * 64,
        run_intent="manual_reanalysis",
    )

    assert preview.targets.scope == "selected"
    assert created.expected_target_count == 1
    assert created.run_intent == "manual_reanalysis"


def test_analysis_run_accepts_query_scope_with_filter_snapshot() -> None:
    """Query Scope 只提交稳定筛选快照，不向 HTTP Payload 搬运全量 Content ID。"""

    query_targets = AnalysisRunTargetSelection(
        scope="query",
        filters=ContentFilterSnapshot(
            platforms=("xiaohongshu",),
            sentiment="负面",
        ),
    )
    preview = AnalysisContentRunPreviewRequest(targets=query_targets)
    created = AnalysisContentRunCreateRequest(
        client_idempotency_key="query-run-approved",
        targets=query_targets,
        expected_target_count=12_856,
        expected_configuration_hash="a" * 64,
    )

    assert preview.targets.scope == "query"
    assert preview.targets.filters is not None
    assert preview.targets.filters.platforms == ("xiaohongshu",)
    assert preview.targets.content_ids == ()
    assert created.targets == query_targets


def test_analysis_run_rejects_invalid_confirmation_and_duplicate_selected_ids() -> None:
    content_id = uuid4()
    with pytest.raises(ValidationError):
        AnalysisContentRunCreateRequest(
            client_idempotency_key="invalid key with spaces",
            targets=AnalysisRunTargetSelection(content_ids=(content_id,)),
            expected_target_count=0,
            expected_configuration_hash="not-a-hash",
        )
    with pytest.raises(ValidationError):
        AnalysisRunTargetSelection(content_ids=(content_id, content_id))


def test_analysis_run_response_exposes_planner_terminal_error() -> None:
    run_id = uuid4()
    response = AnalysisContentRunResponse.model_validate(
        {
            "id": run_id,
            "planner_job_id": uuid4(),
            "sequence_no": 1,
            "status": "failed",
            "run_intent": "manual_reanalysis",
            "scope": "query",
            "target_count": 3,
            "shard_count": 3,
            "shard_size": 1,
            "prompt_version": "v3",
            "prompt_sha256": "1" * 64,
            "taxonomy_sha256": "2" * 64,
            "model_provider": "fake",
            "model": "fake-model",
            "generation_config": {"response_format": {"type": "json_object"}},
            "generation_config_hash": "3" * 64,
            "error_code": "content_analysis_target_changed",
            "created_at": datetime.now(UTC),
        }
    )

    assert response.id == run_id
    assert response.error_code == "content_analysis_target_changed"
