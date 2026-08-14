from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionScopeDefinition,
    DuplicateCollectionScopeError,
    UnsupportedCollectionTriggerError,
)


class RecordingCollectionRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = cast(CollectionExecution, object())

    def create_queued_run(
        self,
        *,
        job_id,
        trigger_type,
        config_snapshot,
        scopes,
    ) -> CollectionExecution:
        self.calls.append(
            {
                "job_id": job_id,
                "trigger_type": trigger_type,
                "config_snapshot": config_snapshot,
                "scopes": scopes,
            }
        )
        return self.result


def test_service_creates_supported_run_with_immutable_scope_sequence() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    job_id = uuid4()
    scopes = [
        CollectionScopeDefinition(
            platform="xhs",
            source_type="keyword_search",
            source_value="爱玛",
            operation_group="content_discovery",
        )
    ]

    result = service.create_run(
        job_id=job_id,
        trigger_type="manual",
        config_snapshot={"schema_version": "collection-run-config.v1"},
        scopes=scopes,
    )

    assert result is repository.result
    assert repository.calls == [
        {
            "job_id": job_id,
            "trigger_type": "manual",
            "config_snapshot": {"schema_version": "collection-run-config.v1"},
            "scopes": tuple(scopes),
        }
    ]


@pytest.mark.parametrize("trigger_type", ["manual", "api", "backfill"])
def test_service_accepts_only_stage5b_trigger_types(trigger_type: str) -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)

    service.create_run(
        job_id=uuid4(),
        trigger_type=trigger_type,
        config_snapshot={},
        scopes=(),
    )

    assert repository.calls[0]["trigger_type"] == trigger_type


def test_service_rejects_scheduled_run_before_repository_call() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)

    with pytest.raises(UnsupportedCollectionTriggerError):
        service.create_run(
            job_id=uuid4(),
            trigger_type="scheduled",
            config_snapshot={},
            scopes=(),
        )

    assert repository.calls == []


def test_service_rejects_duplicate_scope_identity_before_repository_call() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    scope = CollectionScopeDefinition(
        platform="dy",
        source_type="keyword_search",
        source_value="爱玛电动车",
        operation_group="content_discovery",
    )

    with pytest.raises(DuplicateCollectionScopeError):
        service.create_run(
            job_id=uuid4(),
            trigger_type="api",
            config_snapshot={},
            scopes=(scope, scope),
        )

    assert repository.calls == []
