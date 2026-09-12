"""Collection Scope 未预期异常的安全诊断日志测试。"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from aima_ugc.bootstrap.collection_scope import _log_scope_execution_failed
from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord


def test_scope_execution_failure_logs_safe_identity_and_exception_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id = uuid4()
    job_id = uuid4()
    scope_id = uuid4()
    run = cast(CollectionRunRecord, SimpleNamespace(id=run_id, job_id=job_id))
    scope = cast(
        CollectionScopeRecord,
        SimpleNamespace(
            id=scope_id,
            platform="xiaohongshu",
            operation_group="content_enrichment",
        ),
    )

    with caplog.at_level(logging.ERROR, logger="aima_ugc.bootstrap.collection_scope"):
        _log_scope_execution_failed(
            run=run,
            scope=scope,
            error=RuntimeError("provider-secret-must-not-leak"),
        )

    record = next(
        item
        for item in caplog.records
        if getattr(item, "event", None) == "collection.scope.execution_failed"
    )
    assert record.run_id == str(run_id)
    assert record.job_id == str(job_id)
    assert record.scope_id == str(scope_id)
    assert record.platform == "xiaohongshu"
    assert record.operation_group == "content_enrichment"
    assert record.error_type == "RuntimeError"
    assert "provider-secret-must-not-leak" not in caplog.text
