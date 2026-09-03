from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from aima_ugc.modules.collection.execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionScopeDefinition,
    DuplicateCollectionScopeError,
    InvalidCollectionRunPlanBindingError,
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
        manual_plan_id,
        occurrence_id,
        import_batch_id,
        data_import_campaign_id,
    ) -> CollectionExecution:
        self.calls.append(
            {
                "job_id": job_id,
                "trigger_type": trigger_type,
                "config_snapshot": config_snapshot,
                "scopes": scopes,
                "manual_plan_id": manual_plan_id,
                "occurrence_id": occurrence_id,
                "import_batch_id": import_batch_id,
                "data_import_campaign_id": data_import_campaign_id,
            }
        )
        return self.result


def test_service_creates_supported_run_with_immutable_scope_sequence() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    job_id = uuid4()
    scopes = [
        CollectionScopeDefinition(
            platform="xiaohongshu",
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
            "manual_plan_id": None,
            "occurrence_id": None,
            "import_batch_id": None,
            "data_import_campaign_id": None,
        }
    ]


def test_service_passes_optional_import_batch_binding_to_repository() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    import_batch_id = uuid4()

    service.create_run(
        job_id=uuid4(),
        trigger_type="api",
        config_snapshot={},
        scopes=(),
        import_batch_id=import_batch_id,
    )

    assert repository.calls[0]["import_batch_id"] == import_batch_id


def test_service_passes_optional_campaign_binding_to_repository() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    campaign_id = uuid4()

    service.create_run(
        job_id=uuid4(),
        trigger_type="api",
        config_snapshot={},
        scopes=(),
        data_import_campaign_id=campaign_id,
    )

    assert repository.calls[0]["data_import_campaign_id"] == campaign_id


@pytest.mark.parametrize("trigger_type", ["manual", "api", "backfill"])
def test_service_accepts_non_scheduled_trigger_types(trigger_type: str) -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)

    service.create_run(
        job_id=uuid4(),
        trigger_type=trigger_type,
        config_snapshot={},
        scopes=(),
    )

    assert repository.calls[0]["trigger_type"] == trigger_type


def test_service_accepts_scheduled_run_with_occurrence_only() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    occurrence_id = uuid4()

    service.create_run(
        job_id=uuid4(),
        trigger_type="scheduled",
        config_snapshot={},
        scopes=(),
        occurrence_id=occurrence_id,
    )

    assert repository.calls[0]["trigger_type"] == "scheduled"
    assert repository.calls[0]["occurrence_id"] == occurrence_id
    assert repository.calls[0]["manual_plan_id"] is None


@pytest.mark.parametrize(
    ("trigger_type", "manual_plan_id", "occurrence_id"),
    [
        ("scheduled", None, None),
        ("scheduled", uuid4(), uuid4()),
        ("manual", None, uuid4()),
        ("api", uuid4(), uuid4()),
        ("backfill", None, uuid4()),
    ],
)
def test_service_rejects_inconsistent_plan_occurrence_binding(
    trigger_type: str,
    manual_plan_id,
    occurrence_id,
) -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)

    with pytest.raises(InvalidCollectionRunPlanBindingError):
        service.create_run(
            job_id=uuid4(),
            trigger_type=trigger_type,
            config_snapshot={},
            scopes=(),
            manual_plan_id=manual_plan_id,
            occurrence_id=occurrence_id,
        )

    assert repository.calls == []


def test_service_rejects_unknown_trigger_before_repository_call() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)

    with pytest.raises(UnsupportedCollectionTriggerError):
        service.create_run(
            job_id=uuid4(),
            trigger_type="cron",
            config_snapshot={},
            scopes=(),
        )

    assert repository.calls == []


def test_service_rejects_duplicate_scope_identity_before_repository_call() -> None:
    repository = RecordingCollectionRepository()
    service = CollectionExecutionService(repository)
    scope = CollectionScopeDefinition(
        platform="douyin",
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
