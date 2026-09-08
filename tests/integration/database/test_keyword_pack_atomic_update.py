"""统一词包表单必须原子保存，并保持版本与共享关键词隔离。"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.resource_lifecycle_http import PostgresResourceLifecycleHttpService
from aima_ugc.bootstrap.runtime import PlatformRuntime
from aima_ugc.contracts.http import KeywordPackCreateRequest, KeywordPackKeywordCreateRequest
from aima_ugc.contracts.resource_lifecycle import KeywordPackUpdateRequest
from aima_ugc.modules.collection.strategy_http import CollectionStrategyConflict
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.system.tables import (
    audit_events_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import delete, update

ADMIN = Principal(
    principal_id="keyword-editor-test",
    display_name="测试管理员",
    role="administrator",
    source="development",
)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[PlatformRuntime]:
    settings = load_settings()
    database = DatabaseRuntime(settings)
    value = PlatformRuntime(
        service="keyword-editor-test",
        settings=settings,
        database=database,
        artifact_store=LocalArtifactStore(tmp_path),
        logger=logging.getLogger("keyword-editor-test"),
    )
    yield value
    database.dispose()


@pytest.mark.parametrize("enabled", [False, True])
def test_atomic_pack_update_preserves_members_and_allows_append(
    runtime: PlatformRuntime, enabled: bool
) -> None:
    prefix = f"atomic-{uuid4()}"
    reader = PostgresImportHttpService(runtime)
    writer = PostgresResourceLifecycleHttpService(runtime)
    first = reader.create_keyword_pack(
        KeywordPackCreateRequest(
            name=prefix,
            keywords=(KeywordPackKeywordCreateRequest(text=prefix, note="保留备注", priority=7),),
        )
    )
    try:
        with runtime.database.new_session() as session, session.begin():
            changed = PostgresKeywordCatalogRepository(session).set_pack_enabled(
                first.id, enabled=enabled
            )
            assert changed is not None
            version = changed.version
        request = KeywordPackUpdateRequest.model_validate(
            {
                "expected_version": version,
                "name": f"{prefix}-新名称",
                "description": "统一保存说明",
                "keywords": [
                    {"text": prefix, "priority": 7, "note": "保留备注"},
                    {"text": f"{prefix}-追加", "platform_scope": "douyin", "priority": 9},
                ],
            }
        )
        result = writer.update_keyword_pack(first.id, request, principal=ADMIN, request_id=prefix)
        assert result.name == f"{prefix}-新名称"
        assert result.description == "统一保存说明"
        assert result.version == version + 1
        assert {
            (item.text, item.platform_scope, item.priority, item.note) for item in result.keywords
        } == {
            (prefix, "all", 7, "保留备注"),
            (f"{prefix}-追加", "douyin", 9, ""),
        }
    finally:
        _cleanup(runtime, prefix)


@pytest.mark.parametrize("failure", ["enabled", "version", "duplicate"])
def test_failed_atomic_update_rolls_back_metadata_and_new_keywords(
    runtime: PlatformRuntime, failure: str
) -> None:
    prefix = f"atomic-{uuid4()}"
    reader = PostgresImportHttpService(runtime)
    writer = PostgresResourceLifecycleHttpService(runtime)
    first = reader.create_keyword_pack(
        KeywordPackCreateRequest(
            name=prefix, keywords=(KeywordPackKeywordCreateRequest(text=prefix),)
        )
    )
    try:
        request = KeywordPackUpdateRequest.model_validate(
            {
                "expected_version": first.version - 1 if failure == "version" else first.version,
                "name": f"{prefix}-不应保存",
                "description": "不应保存",
                "keywords": [{"text": f"{prefix}-替换"}] * (2 if failure == "duplicate" else 1),
            }
        )
        expected_error = {
            "enabled": "请先停用词包，再修改或移除已有关键词",
            "version": "词包版本已经变化或资源已归档",
            "duplicate": "同一平台范围的关键词不能重复",
        }[failure]
        with pytest.raises(CollectionStrategyConflict, match=expected_error):
            writer.update_keyword_pack(first.id, request, principal=ADMIN, request_id=prefix)
        assert reader.get_keyword_pack(first.id) == first
        with runtime.database.new_session() as session, session.begin():
            assert (
                PostgresKeywordCatalogRepository(session).get_keyword_by_normalized_text(
                    f"{prefix}-替换"
                )
                is None
            )
    finally:
        _cleanup(runtime, prefix)


def test_disabled_pack_replacement_keeps_other_pack_and_old_request_compatible(
    runtime: PlatformRuntime,
) -> None:
    prefix = f"atomic-{uuid4()}"
    reader = PostgresImportHttpService(runtime)
    writer = PostgresResourceLifecycleHttpService(runtime)
    shared = KeywordPackKeywordCreateRequest(text=prefix, note="共享配置")
    first = reader.create_keyword_pack(KeywordPackCreateRequest(name=prefix, keywords=(shared,)))
    second = reader.create_keyword_pack(
        KeywordPackCreateRequest(name=f"{prefix}-另一词包", keywords=(shared,))
    )
    try:
        with runtime.database.new_session() as session, session.begin():
            disabled = PostgresKeywordCatalogRepository(session).set_pack_enabled(
                first.id, enabled=False
            )
            assert disabled is not None
        result = writer.update_keyword_pack(
            first.id,
            KeywordPackUpdateRequest.model_validate(
                {
                    "expected_version": disabled.version,
                    "name": prefix,
                    "keywords": [
                        {
                            "text": f"{prefix}-修改",
                            "platform_scope": "xiaohongshu",
                            "priority": 2,
                            "enabled": False,
                            "note": "修改备注",
                        }
                    ],
                }
            ),
            principal=ADMIN,
            request_id=prefix,
        )
        assert result.keywords[0].text == f"{prefix}-修改"
        assert result.keywords[0].platform_scope == "xiaohongshu"
        assert result.keywords[0].enabled is False
        assert reader.get_keyword_pack(second.id) == second
        updated = writer.update_keyword_pack(
            first.id,
            KeywordPackUpdateRequest(
                expected_version=result.version, name=prefix, description="只改说明"
            ),
            principal=ADMIN,
            request_id=prefix,
        )
        assert updated.keywords == result.keywords
        assert updated.description == "只改说明"
    finally:
        _cleanup(runtime, prefix)


def test_existing_pack_over_creation_limit_preserves_every_member(runtime: PlatformRuntime) -> None:
    prefix = f"atomic-{uuid4()}"
    reader = PostgresImportHttpService(runtime)
    writer = PostgresResourceLifecycleHttpService(runtime)
    first = reader.create_keyword_pack(
        KeywordPackCreateRequest(
            name=prefix,
            keywords=tuple(
                KeywordPackKeywordCreateRequest(text=f"{prefix}-{i}") for i in range(500)
            ),
        )
    )
    try:
        current = reader.add_keyword(
            first.id, KeywordPackKeywordCreateRequest(text=f"{prefix}-500")
        )
        result = writer.update_keyword_pack(
            first.id,
            KeywordPackUpdateRequest(
                expected_version=current.version,
                name=f"{prefix}-改名",
                keywords=tuple(
                    KeywordPackKeywordCreateRequest(
                        text=item.text,
                        platform_scope=item.platform_scope,
                        priority=item.priority,
                        enabled=item.enabled,
                        note=item.note,
                    )
                    for item in current.keywords
                ),
            ),
            principal=ADMIN,
            request_id=prefix,
        )
        assert len(result.keywords) == 501
        assert result.keywords == current.keywords
        assert result.version == current.version + 1
    finally:
        _cleanup(runtime, prefix)


def test_enabled_pack_metadata_update_preserves_existing_note_whitespace(
    runtime: PlatformRuntime,
) -> None:
    prefix = f"atomic-{uuid4()}"
    reader = PostgresImportHttpService(runtime)
    writer = PostgresResourceLifecycleHttpService(runtime)
    first = reader.create_keyword_pack(
        KeywordPackCreateRequest(
            name=prefix,
            keywords=(KeywordPackKeywordCreateRequest(text=prefix),),
        )
    )
    try:
        # 模拟既有成员编辑接口允许保存的原始备注，不能在整包回传时重新裁剪。
        with runtime.database.new_session() as session, session.begin():
            session.execute(
                update(keyword_pack_items_table)
                .where(
                    keyword_pack_items_table.c.pack_id == first.id,
                )
                .values(note="  保留原始备注  ")
            )
        result = writer.update_keyword_pack(
            first.id,
            KeywordPackUpdateRequest(
                expected_version=first.version,
                name=f"{prefix}-改名",
                keywords=(KeywordPackKeywordCreateRequest(text=prefix, note="  保留原始备注  "),),
            ),
            principal=ADMIN,
            request_id=prefix,
        )
        assert result.keywords[0].note == "  保留原始备注  "
        assert result.name == f"{prefix}-改名"
    finally:
        _cleanup(runtime, prefix)


def test_concurrent_pack_updates_with_reversed_new_keywords_complete(
    runtime: PlatformRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = f"atomic-{uuid4()}"
    reader = PostgresImportHttpService(runtime)
    packs = [
        reader.create_keyword_pack(
            KeywordPackCreateRequest(
                name=f"{prefix}-{i}",
                keywords=(KeywordPackKeywordCreateRequest(text=f"{prefix}-old-{i}"),),
            )
        )
        for i in range(2)
    ]
    barrier = threading.Barrier(2, timeout=5)
    local = threading.local()
    original = PostgresKeywordCatalogRepository.get_or_create_keyword

    def synchronized_create(repository, keyword):
        first = not getattr(local, "started", False)
        if first:
            local.started = True
            barrier.wait()
        result = original(repository, keyword)
        if first:
            # 让两个真实事务同时持有首个新词锁，覆盖相反输入顺序。
            time.sleep(0.2)
        return result

    def save(index):
        pack = packs[index]
        words = [f"{prefix}-new-a", f"{prefix}-new-b"]
        if index:
            words.reverse()
        return PostgresResourceLifecycleHttpService(runtime).update_keyword_pack(
            pack.id,
            KeywordPackUpdateRequest(
                expected_version=pack.version,
                name=pack.name,
                keywords=tuple(
                    KeywordPackKeywordCreateRequest(text=text)
                    for text in [*words, f"{prefix}-old-{index}"]
                ),
            ),
            principal=ADMIN,
            request_id=prefix,
        )

    try:
        monkeypatch.setattr(
            PostgresKeywordCatalogRepository, "get_or_create_keyword", synchronized_create
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, range(2)))
        assert [len(result.keywords) for result in results] == [3, 3]
        assert all(
            result.version == pack.version + 1 for result, pack in zip(results, packs, strict=True)
        )
    finally:
        _cleanup(runtime, prefix)


def _cleanup(runtime: PlatformRuntime, prefix: str) -> None:
    """只删除本用例创建的隔离资源。"""
    with runtime.database.new_session() as session, session.begin():
        ids = (
            session.query(keyword_packs_table.c.id)
            .filter(keyword_packs_table.c.name.startswith(prefix))
            .scalar_subquery()
        )
        session.execute(delete(audit_events_table).where(audit_events_table.c.request_id == prefix))
        session.execute(
            delete(keyword_pack_items_table).where(keyword_pack_items_table.c.pack_id.in_(ids))
        )
        session.execute(
            delete(keyword_packs_table).where(keyword_packs_table.c.name.startswith(prefix))
        )
        session.execute(delete(keywords_table).where(keywords_table.c.text.startswith(prefix)))
