"""Stage 12 Analysis Run Planner 的 HTTP 边界回归测试。"""

from __future__ import annotations

from contextlib import AbstractContextManager
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from aima_ugc.bootstrap import content_http
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.contracts.http import AnalysisContentRunCreateRequest, AnalysisRunTargetSelection
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity


class _Transaction(AbstractContextManager[None]):
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class _Session:
    def begin(self) -> _Transaction:
        return _Transaction()

    def close(self) -> None:
        return None


class _Database:
    def new_session(self) -> _Session:
        return _Session()


class _AnalysisRepository:
    def __init__(self, session: _Session) -> None:
        del session

    def get_run_by_client_key(self, client_idempotency_key: str) -> None:
        del client_idempotency_key
        return None

    def create_run_header(self, **values: object) -> dict[str, object]:
        return values


class _JobRepository:
    def __init__(self, session: _Session) -> None:
        del session

    def enqueue(self, **values: object) -> SimpleNamespace:
        del values
        return SimpleNamespace(id=uuid4())


class _AuditRepository:
    def __init__(self, session: _Session) -> None:
        del session

    def append(self, event: object) -> None:
        del event


def test_new_analysis_run_defers_target_freeze_to_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新版创建请求必须保持短事务，不在 HTTP 内扫描或冻结全部目标。"""

    identity = AnalysisConfigurationIdentity(
        prompt_version="v3",
        prompt_sha256="1" * 64,
        taxonomy_sha256="2" * 64,
        model_provider="fake",
        model="fake-model",
    )
    generation_config: dict[str, object] = {"response_format": {"type": "json_object"}}
    generation_hash = "3" * 64
    provider_config_id = uuid4()
    runtime_config_snapshot: dict[str, object] = {
        "provider_config_id": str(provider_config_id),
        "provider_kind": "llm",
        "provider": "fake",
        "base_url": "https://provider.example/v1",
        "secret_ref": "providers/test/key-1.key",
        "model": "fake-model",
        "timeout_seconds": 45,
        "max_retries": 1,
        "max_concurrency": 5,
        "max_rps": None,
        "extra_config": {},
        "revision": 1,
    }
    configuration_hash = content_http._analysis_configuration_hash(
        prompt_version=identity.prompt_version,
        prompt_sha256=identity.prompt_sha256,
        taxonomy_sha256=identity.taxonomy_sha256,
        model_provider=identity.model_provider,
        model=identity.model,
        generation_config_hash=generation_hash,
        runtime_config_snapshot=runtime_config_snapshot,
    )
    monkeypatch.setattr(content_http, "PostgresAnalysisRepository", _AnalysisRepository)
    monkeypatch.setattr(content_http, "PostgresJobRepository", _JobRepository)
    monkeypatch.setattr(content_http, "PostgresAuditRepository", _AuditRepository)
    monkeypatch.setattr(
        content_http,
        "current_analysis_generation_config",
        lambda: (generation_config, generation_hash),
    )
    runtime = SimpleNamespace(
        database=_Database(),
        settings=SimpleNamespace(analysis_run_shard_size=100),
    )
    service = PostgresContentHttpService(runtime)  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "_load_active_analysis_configuration",
        lambda: SimpleNamespace(
            identity=identity,
            llm_provider=SimpleNamespace(
                id=provider_config_id,
                max_concurrency=5,
                max_rps=None,
                safe_runtime_snapshot=lambda: runtime_config_snapshot,
            ),
            scheme=SimpleNamespace(id=uuid4()),
            taxonomy=SimpleNamespace(prompt_text="frozen-prompt"),
        ),
    )

    def reject_http_target_scan(session: object, targets: object) -> Any:
        del session, targets
        raise AssertionError("新版 Analysis Run 不得在 HTTP 请求内扫描目标")

    monkeypatch.setattr(service, "_analysis_target_statement", reject_http_target_scan)
    response = service.create_analysis_run(
        AnalysisContentRunCreateRequest(
            client_idempotency_key="stage12-async-plan",
            targets=AnalysisRunTargetSelection(content_ids=(uuid4(),)),
            expected_target_count=1,
            expected_configuration_hash=configuration_hash,
            run_intent="manual_reanalysis",
        ),
        request_id="stage12-unit",
    )

    assert response.target_count == 1
    assert response.shard_count == 1
    assert isinstance(response.run_id, UUID)
