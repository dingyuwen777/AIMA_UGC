"""PR #65 final corrective Red→Green helper. Temporary; self-removed after Green."""

from __future__ import annotations

import sys
from pathlib import Path


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"patch anchor missing: {label}")
    return text.replace(old, new, 1)


def write_tests() -> None:
    path = Path("tests/integration/collection/test_comprehensive_corrective_runtime.py")
    text = path.read_text(encoding="utf-8")
    anchor = """from aima_ugc.adapters.persistence.postgres.collection_run_execution import (\n    PostgresCollectionRunExecutionGateway,\n)\n"""
    addition = anchor + """from aima_ugc.adapters.persistence.postgres.collection_content import (\n    PostgresFencedCollectionIngestionWriter,\n)\n"""
    if "PostgresFencedCollectionIngestionWriter" not in text:
        text = _replace_once(text, anchor, addition, label="comprehensive writer import")
    old_tail = """            assert thread_coverage[\"root_comment_id\"] == \"xhs-comment-root-1\"\n            assert thread_coverage[\"coverage\"] == \"complete\"\n            assert thread_coverage[\"reported_total\"] == 1\n            assert thread_coverage[\"captured_count\"] == 1\n    finally:\n        session.close()\n"""
    new_tail = """            assert thread_coverage[\"root_comment_id\"] == \"xhs-comment-root-1\"\n            assert thread_coverage[\"coverage\"] == \"complete\"\n            assert thread_coverage[\"reported_total\"] == 1\n            assert thread_coverage[\"captured_count\"] == 1\n            persisted_thread_id = thread_coverage[\"id\"]\n            persisted_thread = dict(thread_coverage)\n    finally:\n        session.close()\n\n    writer = PostgresFencedCollectionIngestionWriter(database_runtime.new_session)\n    replayed_id = writer.record_thread_coverage(\n        content_id=persisted_thread[\"content_id\"],\n        root_comment_id=persisted_thread[\"root_comment_id\"],\n        provider_attempt_id=persisted_thread[\"provider_attempt_id\"],\n        raw_artifact_id=persisted_thread[\"raw_artifact_id\"],\n        platform=\"xhs\",\n        fence=fence,\n        coverage=persisted_thread[\"coverage\"],\n        reported_total=persisted_thread[\"reported_total\"],\n        captured_count=persisted_thread[\"captured_count\"],\n        target_count=persisted_thread[\"target_count\"],\n        stop_reason=persisted_thread[\"stop_reason\"],\n        observed_at=persisted_thread[\"observed_at\"],\n    )\n    assert replayed_id == persisted_thread_id\n\n    with pytest.raises(ValueError, match=\"complete\"):\n        writer.record_thread_coverage(\n            content_id=persisted_thread[\"content_id\"],\n            root_comment_id=persisted_thread[\"root_comment_id\"],\n            provider_attempt_id=persisted_thread[\"provider_attempt_id\"],\n            raw_artifact_id=persisted_thread[\"raw_artifact_id\"],\n            platform=\"xhs\",\n            fence=fence,\n            coverage=\"complete\",\n            reported_total=2,\n            captured_count=1,\n            target_count=2,\n            stop_reason=\"provider_exhausted\",\n            observed_at=persisted_thread[\"observed_at\"],\n        )\n"""
    text = _replace_once(text, old_tail, new_tail, label="thread coverage tail")
    path.write_text(text, encoding="utf-8")

    path = Path("tests/integration/collection/test_collection_scope_replies_runtime.py")
    text = path.read_text(encoding="utf-8")
    if "collection_candidate_ingestions_table" not in text:
        text = _replace_once(
            text,
            "from aima_ugc.modules.collection.execution import (\n",
            "from aima_ugc.modules.collection.candidate_tables import (\n"
            "    collection_candidate_ingestions_table,\n"
            "    collection_candidates_table,\n"
            ")\n"
            "from aima_ugc.modules.collection.execution import (\n",
            label="reply candidate imports",
        )
    if "comment_thread_coverage_observations_table" not in text:
        text = _replace_once(
            text,
            "from aima_ugc.modules.content.tables import comments_table\n",
            "from aima_ugc.modules.content.extended_tables import (\n"
            "    comment_thread_coverage_observations_table,\n"
            ")\n"
            "from aima_ugc.modules.content.tables import comments_table\n",
            label="thread coverage import",
        )
    old_sub = """def _sub_comments_response() -> dict[str, object]:\n    body = _fixture(\"sub_comments_page1.sanitized.json\")\n    outer = body[\"data\"]\n    assert isinstance(outer, dict)\n    page = outer[\"data\"]\n    assert isinstance(page, dict)\n    replies = page[\"comments\"]\n    assert isinstance(replies, list) and replies\n    reply = replies[0]\n    assert isinstance(reply, dict)\n    reply[\"note_id\"] = \"note-fixture-1\"\n    page[\"comments\"] = [reply]\n    page[\"has_more\"] = False\n    return body\n"""
    new_sub = """def _sub_comments_response(\n    *,\n    has_more: bool = False,\n    note_id: str = \"note-fixture-1\",\n    empty: bool = False,\n) -> dict[str, object]:\n    body = _fixture(\"sub_comments_page1.sanitized.json\")\n    outer = body[\"data\"]\n    assert isinstance(outer, dict)\n    page = outer[\"data\"]\n    assert isinstance(page, dict)\n    replies = page[\"comments\"]\n    assert isinstance(replies, list) and replies\n    reply = replies[0]\n    assert isinstance(reply, dict)\n    reply[\"note_id\"] = note_id\n    page[\"comments\"] = [] if empty else [reply]\n    page[\"has_more\"] = has_more\n    page[\"cursor\"] = \"cursor-next\" if has_more else \"cursor-end\"\n    return body\n"""
    text = _replace_once(text, old_sub, new_sub, label="sub comments helper")
    start = text.index("def test_scope_runtime_fetches_sub_comments_through_formal_operation(")
    new_tail = r'''def _execute_reply_case(
    *,
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
    sub_comments: dict[str, object],
    decision_policy: dict[str, object] | None = None,
):
    session = database_runtime.new_session()
    try:
        with session.begin():
            provider_config = PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=uuid4(),
                    provider="tikhub",
                    display_name="TikHub Scope Replies Runtime",
                    base_url="https://api.tikhub.io",
                    secret_ref=f"providers/tikhub/test/scope-replies-runtime-{uuid4()}",
                    enabled=True,
                )
            )
            job = PostgresJobRepository(session).enqueue(
                job_type="collection.run.v1",
                payload_version="collection.run.v1",
                payload={"schema_version": "collection.run.v1"},
                internal_idempotency_key=f"scope-replies-runtime:{uuid4()}",
                request_id=None,
                priority=10,
                max_attempts=2,
                timeout_seconds=300,
            )
            snapshot: dict[str, object] = {
                "schema_version": "collection-run-config.v1",
                "detail_policy": "on_change",
                "comment_policy": "adaptive",
                "platforms": [
                    {
                        "platform": "xhs",
                        "provider_config_id": str(provider_config.id),
                        "config": {
                            "sort_mode": "latest",
                            "published_within": "1d",
                            "content_type": "all",
                        },
                    }
                ],
            }
            if decision_policy is not None:
                snapshot["decision_policy"] = decision_policy
            CollectionExecutionService(PostgresCollectionRepository(session)).create_run(
                job_id=job.id,
                trigger_type="api",
                config_snapshot=snapshot,
                scopes=(
                    CollectionScopeDefinition(
                        platform="xhs",
                        source_type="keyword_search",
                        source_value="爱玛",
                        operation_group="content_discovery",
                    ),
                ),
            )
        with session.begin():
            claimed = PostgresJobRepository(session).claim_next(
                supported_job_types=("collection.run.v1",),
                worker_id=f"scope-replies-runtime-worker-{uuid4()}",
                lease_seconds=120,
            )
        assert claimed is not None and claimed.lease_token is not None
    finally:
        session.close()

    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(status_code=200, body=_search_response()),
            ProviderTransportResponse(status_code=200, body=_detail_response()),
            ProviderTransportResponse(status_code=200, body=_comments_response()),
            ProviderTransportResponse(status_code=200, body=sub_comments),
        )
    )
    fence = JobExecutionFence(job_id=job.id, lease_token=claimed.lease_token)
    result = CollectionRunExecutor(
        gateway=PostgresCollectionRunExecutionGateway(database_runtime.new_session),
        scope_executor=TikHubCollectionScopeExecutor(
            session_factory=database_runtime.new_session,
            raw_artifacts=_raw_service(database_runtime, tmp_path / f"artifacts-{uuid4()}"),
            transport_factory=lambda _config: transport,
            secret_resolver=lambda secret_ref: (
                SecretStr("fixture-secret")
                if secret_ref == provider_config.secret_ref
                else (_ for _ in ()).throw(AssertionError("unexpected secret_ref"))
            ),
            observed_at=lambda: _OBSERVED_AT,
        ),
    ).execute(fence=fence, context=_Context(fence))
    return result, transport, job.id


def test_scope_runtime_reply_target_is_partial_when_provider_has_more(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    result, transport, job_id = _execute_reply_case(
        database_runtime=database_runtime,
        tmp_path=tmp_path,
        sub_comments=_sub_comments_response(has_more=True),
        decision_policy={"reply_target_per_root": 1},
    )
    assert result.outcome == "succeeded"
    assert transport.call_count == 4
    assert all(request.credential is None for request in transport.seen_requests)
    session = database_runtime.new_session()
    try:
        with session.begin():
            comments = {
                row["external_comment_id"]: row
                for row in session.execute(select(comments_table)).mappings().all()
            }
            run_comment_count = session.scalar(
                select(collection_runs_table.c.comment_count).where(
                    collection_runs_table.c.job_id == job_id
                )
            )
            coverage = session.execute(
                select(comment_thread_coverage_observations_table)
            ).mappings().one()
        assert set(comments) == {"xhs-comment-root-1", "xhs-comment-reply-2"}
        assert run_comment_count == 2
        assert coverage["coverage"] == "partial"
        assert coverage["reported_total"] == 1
        assert coverage["captured_count"] == 1
        assert coverage["stop_reason"] == "target_reached"
    finally:
        session.close()


def test_sub_comments_empty_page_overrides_stale_root_reply_count(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    result, transport, _job_id = _execute_reply_case(
        database_runtime=database_runtime,
        tmp_path=tmp_path,
        sub_comments=_sub_comments_response(empty=True),
    )
    assert result.outcome == "succeeded"
    assert transport.call_count == 4
    session = database_runtime.new_session()
    try:
        with session.begin():
            coverage = session.execute(
                select(comment_thread_coverage_observations_table)
            ).mappings().one()
            comment_ids = set(session.scalars(select(comments_table.c.external_comment_id)))
        assert comment_ids == {"xhs-comment-root-1"}
        assert coverage["coverage"] == "complete"
        assert coverage["reported_total"] == 0
        assert coverage["captured_count"] == 0
        assert coverage["stop_reason"] == "empty_page"
    finally:
        session.close()


def test_reply_content_identity_mismatch_records_invalid_candidate(
    database_runtime: DatabaseRuntime,
    tmp_path: Path,
) -> None:
    result, transport, _job_id = _execute_reply_case(
        database_runtime=database_runtime,
        tmp_path=tmp_path,
        sub_comments=_sub_comments_response(note_id="different-note"),
    )
    assert result.outcome == "failed"
    assert transport.call_count == 4
    session = database_runtime.new_session()
    try:
        with session.begin():
            rows = session.execute(
                select(
                    collection_candidate_ingestions_table.c.result,
                    collection_candidate_ingestions_table.c.error_code,
                )
                .select_from(
                    collection_candidate_ingestions_table.join(
                        collection_candidates_table,
                        collection_candidate_ingestions_table.c.candidate_id
                        == collection_candidates_table.c.id,
                    )
                )
                .where(collection_candidates_table.c.item_kind == "comment")
            ).all()
        assert any(
            row.result == "invalid"
            and row.error_code == "reply_content_identity_mismatch"
            for row in rows
        )
    finally:
        session.close()
'''
    path.write_text(text[:start] + new_tail, encoding="utf-8")

    path = Path("tests/unit/collection/test_comprehensive_corrective_invariants.py")
    text = path.read_text(encoding="utf-8")
    anchor = "def test_scheduled_job_deadline_rejects_non_forward_slot() -> None:\n"
    new_test = """def test_scheduled_job_deadline_has_provider_execution_floor_for_short_cadence() -> None:\n    scheduled_for = datetime(2026, 8, 18, 0, 0, tzinfo=UTC)\n    next_run_at = datetime(2026, 8, 18, 0, 1, tzinfo=UTC)\n\n    one_scope = _scheduled_job_timeout_seconds(scheduled_for, next_run_at)\n    two_scopes = _scheduled_job_timeout_seconds(\n        scheduled_for,\n        next_run_at,\n        scope_count=2,\n    )\n    assert one_scope > 60\n    assert two_scopes > one_scope\n\n\n"""
    if "test_scheduled_job_deadline_has_provider_execution_floor_for_short_cadence" not in text:
        text = _replace_once(text, anchor, new_test + anchor, label="deadline test anchor")
    path.write_text(text, encoding="utf-8")


def apply_fixes() -> None:
    Path("backend/src/aima_ugc/modules/collection/execution_limits.py").write_text(
        '''"""Collection 生产执行技术上限与 Job Deadline sizing。\n\n这些值只用于技术分页防护和 Deadline 容量下限，不是费用/请求 Budget，也不在发送前拦截请求。\n"""\n\nMAX_SEARCH_PAGES = 100\nMAX_COMMENT_PAGES = 100\nMAX_SUB_COMMENT_PAGES = 100\nDEADLINE_SAFETY_PERCENT = 20\nMIN_DEADLINE_SAFETY_SECONDS = 60\n\n\ndef provider_execution_window_floor_seconds(*, scope_count: int, request_timeout_seconds: float) -> int:\n    """按 Scope 数、技术分页深度和单请求 timeout 推导有限 Deadline 下限。"""\n    if scope_count < 1:\n        raise ValueError("scope_count 必须至少为 1")\n    if request_timeout_seconds <= 0:\n        raise ValueError("request_timeout_seconds 必须大于 0")\n    depth_per_scope = MAX_SEARCH_PAGES + MAX_COMMENT_PAGES + MAX_SUB_COMMENT_PAGES\n    base_seconds = max(1, int(scope_count * depth_per_scope * request_timeout_seconds))\n    percentage_margin = (base_seconds * DEADLINE_SAFETY_PERCENT + 99) // 100\n    return base_seconds + max(MIN_DEADLINE_SAFETY_SECONDS, percentage_margin)\n\n\n__all__ = [\n    "DEADLINE_SAFETY_PERCENT",\n    "MAX_COMMENT_PAGES",\n    "MAX_SEARCH_PAGES",\n    "MAX_SUB_COMMENT_PAGES",\n    "MIN_DEADLINE_SAFETY_SECONDS",\n    "provider_execution_window_floor_seconds",\n]\n''',
        encoding="utf-8",
    )

    path = Path("backend/src/aima_ugc/adapters/providers/tikhub/transport.py")
    text = path.read_text(encoding="utf-8")
    if "DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS" not in text:
        text = _replace_once(
            text,
            'DEFAULT_TIKHUB_BASE_URL = "https://api.tikhub.io"\n',
            'DEFAULT_TIKHUB_BASE_URL = "https://api.tikhub.io"\nDEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS = 45.0\n',
            label="transport timeout constant",
        )
        text = _replace_once(
            text,
            "        timeout_seconds: float = 45.0,\n",
            "        timeout_seconds: float = DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS,\n",
            label="transport default timeout",
        )
        text = _replace_once(
            text,
            '    "DEFAULT_TIKHUB_BASE_URL",\n',
            '    "DEFAULT_TIKHUB_BASE_URL",\n    "DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS",\n',
            label="transport all",
        )
    path.write_text(text, encoding="utf-8")

    path = Path("backend/src/aima_ugc/bootstrap/collection_scope.py")
    text = path.read_text(encoding="utf-8")
    import_anchor = "from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord\n"
    if "MAX_SEARCH_PAGES," not in text:
        text = _replace_once(
            text,
            import_anchor,
            import_anchor
            + "from aima_ugc.modules.collection.execution_limits import (\n"
            + "    MAX_COMMENT_PAGES,\n    MAX_SEARCH_PAGES,\n    MAX_SUB_COMMENT_PAGES,\n)\n",
            label="scope limits import",
        )
    text = text.replace(
        "_MAX_SEARCH_PAGES = 100\n_MAX_COMMENT_PAGES = 100\n_MAX_SUB_COMMENT_PAGES = 100\n",
        "",
        1,
    )
    text = text.replace("_MAX_SEARCH_PAGES", "MAX_SEARCH_PAGES")
    text = text.replace("_MAX_COMMENT_PAGES", "MAX_COMMENT_PAGES")
    text = text.replace("_MAX_SUB_COMMENT_PAGES", "MAX_SUB_COMMENT_PAGES")
    text = _replace_once(
        text,
        '''                if reply.external_content_id != root_comment.external_content_id:\n                    raise ValueError("TikHub Reply 与 Content 身份不一致")\n                if reply.root_comment_id != root_comment.external_comment_id:\n                    raise ValueError("TikHub Reply 与 Root Comment 身份不一致")\n''',
        '''                if reply.external_content_id != root_comment.external_content_id:\n                    self._content_writer.record_candidate_failure(\n                        candidate_id=candidate_id,\n                        provider_attempt_id=executed.attempt_id,\n                        fence=context.fence,\n                        result="invalid",\n                        error_code="reply_content_identity_mismatch",\n                    )\n                    raise ValueError("TikHub Reply 与 Content 身份不一致")\n                if reply.root_comment_id != root_comment.external_comment_id:\n                    self._content_writer.record_candidate_failure(\n                        candidate_id=candidate_id,\n                        provider_attempt_id=executed.attempt_id,\n                        fence=context.fence,\n                        result="invalid",\n                        error_code="reply_root_identity_mismatch",\n                    )\n                    raise ValueError("TikHub Reply 与 Root Comment 身份不一致")\n''',
        label="reply identity ledger",
    )
    text = _replace_once(
        text,
        '''            if not advance.should_continue:\n                stop_reason = advance.stop_reason or "provider_exhausted"\n                coverage = _coverage_for_stop(\n                    stop_reason,\n                    reported_total,\n                    len(reply_ids),\n                )\n''',
        '''            if not advance.should_continue:\n                stop_reason = advance.stop_reason or "provider_exhausted"\n                if stop_reason == "empty_page" and not reply_ids:\n                    reported_total = 0\n                coverage = _coverage_for_stop(\n                    stop_reason,\n                    reported_total,\n                    len(reply_ids),\n                )\n''',
        label="reply empty page freshness",
    )
    text = _replace_once(
        text,
        '''            if reply_target is not None and len(reply_ids) >= reply_target:\n                coverage = (\n                    "complete"\n                    if reported_total is not None and len(reply_ids) >= reported_total\n                    else "partial"\n                )\n                self._content_writer.record_thread_coverage(\n''',
        '''            if reply_target is not None and len(reply_ids) >= reply_target:\n                coverage = "partial"\n                self._content_writer.record_thread_coverage(\n''',
        label="reply target coverage",
    )
    path.write_text(text, encoding="utf-8")

    path = Path("backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace("from uuid import UUID, uuid4\n", "from uuid import UUID\n", 1)
    text = text.replace("from sqlalchemy.dialects.postgresql import insert as pg_insert\n", "", 1)
    text = text.replace(
        "from aima_ugc.modules.content.extended_tables import comment_thread_coverage_observations_table\n",
        "",
        1,
    )
    start = text.index("    def record_thread_coverage(")
    end = text.index("\n\ndef _lock_matching_attempt", start)
    method = '''    def record_thread_coverage(\n        self,\n        *,\n        content_id: UUID,\n        root_comment_id: str,\n        provider_attempt_id: UUID,\n        raw_artifact_id: UUID,\n        platform: str,\n        fence: JobExecutionFence,\n        coverage: str,\n        reported_total: int | None,\n        captured_count: int,\n        target_count: int | None,\n        stop_reason: str,\n        observed_at: datetime,\n    ) -> UUID:\n        session = self._session_factory()\n        try:\n            with session.begin():\n                attempt_platform = _lock_matching_attempt(\n                    session,\n                    attempt_id=provider_attempt_id,\n                    raw_artifact_id=raw_artifact_id,\n                    fence=fence,\n                )\n                content_platform = session.scalar(\n                    select(contents_table.c.platform).where(contents_table.c.id == content_id)\n                )\n                if content_platform is None:\n                    raise LookupError("Thread Coverage Content 不存在")\n                if content_platform != platform or attempt_platform != platform:\n                    raise ValueError("Thread Coverage Content/Attempt 平台不一致")\n                return PostgresCompleteContentRepository(session).record_thread_coverage(\n                    content_id=content_id,\n                    root_comment_id=root_comment_id,\n                    provider_attempt_id=provider_attempt_id,\n                    raw_artifact_id=raw_artifact_id,\n                    coverage=coverage,\n                    reported_total=reported_total,\n                    captured_count=captured_count,\n                    target_count=target_count,\n                    stop_reason=stop_reason,\n                    observed_at=observed_at,\n                )\n        finally:\n            session.close()\n'''
    path.write_text(text[:start] + method + text[end:], encoding="utf-8")

    path = Path("backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace("from typing import Any\n", "from typing import Any, cast\n", 1)
    text = text.replace(
        "from sqlalchemy import Table, delete, insert, select, update\n",
        "from sqlalchemy import Table, delete, insert, select, update\nfrom sqlalchemy.dialects.postgresql import insert as pg_insert\n",
        1,
    )
    anchor = '''    def record_comment_coverage(self, **kwargs: Any) -> UUID:\n        return self._core.record_comment_coverage(**kwargs)\n\n'''
    method = anchor + '''    def record_thread_coverage(\n        self,\n        *,\n        content_id: UUID,\n        root_comment_id: str,\n        provider_attempt_id: UUID,\n        raw_artifact_id: UUID,\n        coverage: str,\n        reported_total: int | None,\n        captured_count: int,\n        target_count: int | None,\n        stop_reason: str,\n        observed_at: datetime,\n    ) -> UUID:\n        if coverage not in {"complete", "partial", "not_requested", "unavailable"}:\n            raise ValueError("Thread Coverage 状态非法")\n        if not root_comment_id.strip():\n            raise ValueError("Thread Coverage root_comment_id 不能为空")\n        if reported_total is not None and reported_total < 0:\n            raise ValueError("Thread Coverage reported_total 不能为负数")\n        if captured_count < 0:\n            raise ValueError("Thread Coverage captured_count 不能为负数")\n        if target_count is not None and target_count < 0:\n            raise ValueError("Thread Coverage target_count 不能为负数")\n        if observed_at.utcoffset() is None:\n            raise ValueError("Thread Coverage observed_at 必须包含时区")\n        if not stop_reason.strip():\n            raise ValueError("Thread Coverage stop_reason 不能为空")\n        if coverage in {"not_requested", "unavailable"} and captured_count != 0:\n            raise ValueError("未请求/不可用 Thread Coverage 不能包含已采集回复")\n        if coverage == "complete" and reported_total is not None and captured_count < reported_total:\n            raise ValueError("complete Thread Coverage 的采集数不能小于 Provider 报告总数")\n        statement = pg_insert(comment_thread_coverage_observations_table).values(\n            id=uuid4(),\n            content_id=content_id,\n            root_comment_id=root_comment_id.strip(),\n            provider_attempt_id=provider_attempt_id,\n            raw_artifact_id=raw_artifact_id,\n            coverage=coverage,\n            reported_total=reported_total,\n            captured_count=captured_count,\n            target_count=target_count,\n            stop_reason=stop_reason.strip(),\n            observed_at=observed_at,\n        )\n        row_id = self._session.execute(\n            statement.on_conflict_do_update(\n                constraint="uq_comment_thread_coverage_source",\n                set_={\n                    "coverage": statement.excluded.coverage,\n                    "reported_total": statement.excluded.reported_total,\n                    "captured_count": statement.excluded.captured_count,\n                    "target_count": statement.excluded.target_count,\n                    "stop_reason": statement.excluded.stop_reason,\n                    "observed_at": statement.excluded.observed_at,\n                },\n            ).returning(comment_thread_coverage_observations_table.c.id)\n        ).scalar_one()\n        return cast(UUID, row_id)\n\n'''
    if "def record_thread_coverage(" not in text:
        text = _replace_once(text, anchor, method, label="content owner thread coverage")
    path.write_text(text, encoding="utf-8")

    for filename, is_migration in (
        ("backend/src/aima_ugc/modules/content/extended_tables.py", False),
        ("migrations/versions/20260818_0018_stage1_stage7_comprehensive_corrective.py", True),
    ):
        path = Path(filename)
        text = path.read_text(encoding="utf-8")
        if "complete_count_consistent" in text:
            continue
        prefix = "        " if is_migration else "    "
        class_prefix = "sa." if is_migration else ""
        anchor = (
            f'{prefix}{class_prefix}CheckConstraint(\n'
            f'{prefix}    "target_count is null or target_count >= 0",\n'
            f'{prefix}    name="target_nonneg",\n'
            f'{prefix}),\n'
        )
        addition = anchor + (
            f'{prefix}{class_prefix}CheckConstraint(\n'
            f'{prefix}    "coverage <> \'complete\' or reported_total is null or captured_count >= reported_total",\n'
            f'{prefix}    name="complete_count_consistent",\n'
            f'{prefix}),\n'
            f'{prefix}{class_prefix}CheckConstraint(\n'
            f'{prefix}    "coverage not in (\'not_requested\',\'unavailable\') or captured_count = 0",\n'
            f'{prefix}    name="nonfetch_count_zero",\n'
            f'{prefix}),\n'
        )
        text = _replace_once(text, anchor, addition, label=f"thread checks {filename}")
        path.write_text(text, encoding="utf-8")

    path = Path("backend/src/aima_ugc/bootstrap/scheduler.py")
    text = path.read_text(encoding="utf-8")
    if "DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS" not in text:
        text = _replace_once(
            text,
            "from aima_ugc.adapters.providers.registry import build_default_provider_registry\n",
            "from aima_ugc.adapters.providers.registry import build_default_provider_registry\n"
            "from aima_ugc.adapters.providers.tikhub.transport import (\n"
            "    DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS,\n"
            ")\n",
            label="scheduler timeout import",
        )
    if "provider_execution_window_floor_seconds" not in text:
        marker = "from aima_ugc.modules.collection.collection_run_job import (\n"
        idx = text.index(marker)
        text = text[:idx] + (
            "from aima_ugc.modules.collection.execution_limits import (\n"
            "    DEADLINE_SAFETY_PERCENT,\n"
            "    MAX_COMMENT_PAGES,\n"
            "    MAX_SEARCH_PAGES,\n"
            "    MAX_SUB_COMMENT_PAGES,\n"
            "    provider_execution_window_floor_seconds,\n"
            ")\n"
        ) + text[idx:]
    text = _replace_once(
        text,
        '''                    job = PostgresJobRepository(session).enqueue(\n                        job_type=COLLECTION_RUN_JOB_TYPE,\n                        payload_version=COLLECTION_RUN_PAYLOAD_VERSION,\n                        payload=CollectionRunJobPayload().model_dump(mode="json"),\n                        internal_idempotency_key=_scheduled_job_idempotency_key(\n                            plan, decision.enqueue_for\n                        ),\n                        request_id=None,\n                        priority=10,\n                        max_attempts=2,\n                        timeout_seconds=_scheduled_job_timeout_seconds(\n                            decision.enqueue_for,\n                            decision.next_run_at,\n                        ),\n                    )\n''',
        '''                    job_timeout_seconds = _scheduled_job_timeout_seconds(\n                        decision.enqueue_for,\n                        decision.next_run_at,\n                        scope_count=len(scope_snapshot.scopes),\n                    )\n                    job = PostgresJobRepository(session).enqueue(\n                        job_type=COLLECTION_RUN_JOB_TYPE,\n                        payload_version=COLLECTION_RUN_PAYLOAD_VERSION,\n                        payload=CollectionRunJobPayload().model_dump(mode="json"),\n                        internal_idempotency_key=_scheduled_job_idempotency_key(\n                            plan, decision.enqueue_for\n                        ),\n                        request_id=None,\n                        priority=10,\n                        max_attempts=2,\n                        timeout_seconds=job_timeout_seconds,\n                    )\n''',
        label="scheduler job timeout call",
    )
    text = _replace_once(
        text,
        "                            keyword_scope_count=len(scope_snapshot.scopes),\n",
        "                            keyword_scope_count=len(scope_snapshot.scopes),\n"
        "                            job_timeout_seconds=job_timeout_seconds,\n",
        label="scheduler snapshot timeout arg",
    )
    text = _replace_once(
        text,
        '''def _scheduled_job_timeout_seconds(scheduled_for: datetime, next_run_at: datetime) -> int:\n    """Scheduled Run 的不可续期 Deadline 与下一逻辑 slot 对齐，不使用固定 300 秒魔数。"""\n    seconds = int((next_run_at - scheduled_for).total_seconds())\n    if seconds < 1:\n        raise ValueError("Scheduler 下一逻辑 slot 必须晚于当前 scheduled_for")\n    return seconds\n''',
        '''def _scheduled_job_timeout_seconds(\n    scheduled_for: datetime,\n    next_run_at: datetime,\n    *,\n    scope_count: int = 1,\n) -> int:\n    """Deadline 不短于 Cron 间隔，也不短于 Provider 技术执行窗口。"""\n    cadence_seconds = int((next_run_at - scheduled_for).total_seconds())\n    if cadence_seconds < 1:\n        raise ValueError("Scheduler 下一逻辑 slot 必须晚于当前 scheduled_for")\n    provider_floor = provider_execution_window_floor_seconds(\n        scope_count=scope_count,\n        request_timeout_seconds=DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS,\n    )\n    return max(cadence_seconds, provider_floor)\n''',
        label="scheduler timeout function",
    )
    text = _replace_once(
        text,
        "    keyword_scope_count: int,\n) -> dict[str, object]:\n",
        "    keyword_scope_count: int,\n    job_timeout_seconds: int,\n) -> dict[str, object]:\n",
        label="scheduler snapshot signature",
    )
    text = _replace_once(
        text,
        '''        "decision_policy": plan.decision_policy.model_dump(mode="json"),\n        "platforms": list(provider_snapshots),\n''',
        '''        "decision_policy": plan.decision_policy.model_dump(mode="json"),\n        "job_timeout_seconds": job_timeout_seconds,\n        "execution_limits": {\n            "scope_count": keyword_scope_count,\n            "max_search_pages": MAX_SEARCH_PAGES,\n            "max_comment_pages": MAX_COMMENT_PAGES,\n            "max_sub_comment_pages": MAX_SUB_COMMENT_PAGES,\n            "provider_request_timeout_seconds": DEFAULT_TIKHUB_REQUEST_TIMEOUT_SECONDS,\n            "deadline_safety_percent": DEADLINE_SAFETY_PERCENT,\n        },\n        "platforms": list(provider_snapshots),\n''',
        label="scheduler execution limit snapshot",
    )
    path.write_text(text, encoding="utf-8")


def cleanup_trigger() -> None:
    path = Path("tests/unit/collection/test_comprehensive_corrective_invariants.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "\n# Temporary trigger for the registered Stage 5B corrective runner; the runner removes this line.\n",
        "\n",
    )
    text = text.replace(
        "\n# Temporary trigger v2 for the registered Stage 5B corrective runner; the runner removes this line.\n",
        "\n",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: _final_corrective_runner.py write-tests|apply-fixes|cleanup-trigger")
    command = sys.argv[1]
    if command == "write-tests":
        write_tests()
    elif command == "apply-fixes":
        apply_fixes()
    elif command == "cleanup-trigger":
        cleanup_trigger()
    else:
        raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    main()
