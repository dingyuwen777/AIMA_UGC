from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from aima_ugc.contracts.provider import ProviderRequestV1
from aima_ugc.modules.collection.provider_persistence import (
    PreparedProviderAttempt,
    ProviderAttemptRecord,
    ProviderPersistenceService,
    ProviderRequestRecord,
)
from aima_ugc.modules.collection.tables import (
    provider_request_attempts_table,
    provider_requests_table,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex


class RecordingProviderRepository:
    def __init__(self) -> None:
        self.request_calls: list[ProviderRequestV1] = []
        self.get_request_calls: list[object] = []
        self.attempt_calls: list[tuple[object, object]] = []
        self.request_result = cast(ProviderRequestRecord, SimpleNamespace(id=uuid4()))
        self.attempt_result = cast(ProviderAttemptRecord, object())

    def create_or_get_request(self, request: ProviderRequestV1) -> ProviderRequestRecord:
        self.request_calls.append(request)
        return self.request_result

    def create_or_get_non_billable_attempt(
        self,
        *,
        provider_request_id,
        attempt_id,
    ) -> ProviderAttemptRecord:
        self.attempt_calls.append((provider_request_id, attempt_id))
        return self.attempt_result

    def get_request(self, provider_request_id) -> ProviderRequestRecord | None:
        self.get_request_calls.append(provider_request_id)
        return self.request_result


def test_service_prepares_request_and_non_billable_attempt_in_order() -> None:
    repository = RecordingProviderRepository()
    service = ProviderPersistenceService(repository)
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake",
        platform="xhs",
        operation="search_notes",
        request_params={"keyword": "爱玛"},
        pagination_input={"page": 1},
    )
    attempt_id = uuid4()

    prepared = service.prepare_non_billable_attempt(
        request=request,
        attempt_id=attempt_id,
    )

    assert prepared == PreparedProviderAttempt(
        request=repository.request_result,
        attempt=repository.attempt_result,
    )
    assert repository.request_calls == [request]
    assert repository.attempt_calls == [(repository.request_result.id, attempt_id)]
    assert repository.get_request_calls == [repository.request_result.id]


def test_service_can_idempotently_ensure_request_without_creating_attempt() -> None:
    repository = RecordingProviderRepository()
    service = ProviderPersistenceService(repository)
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=uuid4(),
        scope_id=uuid4(),
        provider="fake",
        platform="dy",
        operation="search_videos",
    )

    persisted = service.ensure_request(request)

    assert persisted is repository.request_result
    assert repository.request_calls == [request]
    assert repository.attempt_calls == []
    assert repository.get_request_calls == []


def test_provider_index_names_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()
    for table in (provider_requests_table, provider_request_attempts_table):
        for index in table.indexes:
            assert str(CreateIndex(index).compile(dialect=dialect))
