"""Analysis Scheme PostgreSQL Repository 与 Git Prompt 一次性 bootstrap。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis.prompt_taxonomy import CONTENT_LABELING_PROMPT_PATH
from aima_ugc.modules.analysis.scheme_tables import (
    analysis_scheme_versions_table,
    analysis_schemes_table,
)
from aima_ugc.modules.analysis.schemes import (
    AnalysisSchemeVersionRecord,
    bootstrap_definition_from_prompt,
    compile_analysis_scheme,
)
from aima_ugc.platform.time import beijing_now

_ANALYSIS_SCHEME_ADVISORY_LOCK = 4_270_116_503_129_227_117


def _lock_scheme_registry(session: Session) -> None:
    """用事务级 PostgreSQL Advisory Lock 串行化低频 Scheme 配置写入。"""

    session.execute(select(func.pg_advisory_xact_lock(_ANALYSIS_SCHEME_ADVISORY_LOCK)))


def _version_from_row(row: RowMapping) -> AnalysisSchemeVersionRecord:
    """把数据库行恢复为经过 Pydantic 校验的 Scheme Version。"""

    return AnalysisSchemeVersionRecord(
        id=cast(UUID, row["id"]),
        scheme_id=cast(UUID, row["scheme_id"]),
        version=cast(int, row["version"]),
        status=cast(str, row["status"]),
        description=cast(str, row["description"]),
        definition=AnalysisSchemeDefinitionRequest.model_validate(row["definition"]),
        compiled_prompt=cast(str, row["compiled_prompt"]),
        prompt_sha256=cast(str, row["prompt_sha256"]),
        taxonomy_sha256=cast(str, row["taxonomy_sha256"]),
        created_by=cast(str, row["created_by"]),
        created_at=cast(datetime, row["created_at"]),
        published_at=cast(datetime | None, row["published_at"]),
    )


class PostgresAnalysisSchemeRepository:
    """Scheme、Version 和全局 active 指针的唯一数据库写 Owner。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方拥有的配置写事务。"""

        self._session = session

    def bootstrap_default(
        self, *, actor_ref: str = "system"
    ) -> tuple[AnalysisSchemeVersionRecord, bool]:
        """数据库为空时从 Git Prompt 建立唯一 bootstrap 发布版。"""

        _lock_scheme_registry(self._session)
        active = self.get_active_version()
        if active is not None:
            return active, False
        existing = self._session.scalar(select(func.count()).select_from(analysis_schemes_table))
        if int(existing or 0) > 0:
            raise RuntimeError("Analysis Scheme 存在但没有 active version")
        prompt_text = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
        definition = bootstrap_definition_from_prompt(prompt_text)
        compiled = compile_analysis_scheme(definition)
        now = beijing_now()
        scheme_id, version_id = uuid4(), uuid4()
        self._session.execute(
            insert(analysis_schemes_table).values(
                id=scheme_id,
                name="默认内容舆情分析方案",
                active_version_id=None,
                is_active=False,
                created_at=now,
                updated_at=now,
            )
        )
        row = (
            self._session.execute(
                insert(analysis_scheme_versions_table)
                .values(
                    id=version_id,
                    scheme_id=scheme_id,
                    version=1,
                    status="published",
                    description="由 Git Prompt bootstrap 的首个生产 Scheme",
                    definition=definition.model_dump(mode="json"),
                    compiled_prompt=compiled.prompt_text,
                    prompt_sha256=compiled.prompt_sha256,
                    taxonomy_sha256=compiled.taxonomy_sha256,
                    created_by=actor_ref,
                    created_at=now,
                    published_at=now,
                )
                .returning(analysis_scheme_versions_table)
            )
            .mappings()
            .one()
        )
        self._session.execute(
            update(analysis_schemes_table)
            .where(analysis_schemes_table.c.id == scheme_id)
            .values(active_version_id=version_id, is_active=True, updated_at=now)
        )
        return _version_from_row(row), True

    def create_draft(
        self,
        *,
        name: str,
        description: str,
        definition: AnalysisSchemeDefinitionRequest,
        actor_ref: str,
    ) -> AnalysisSchemeVersionRecord:
        """为现有同名 Scheme 追加版本，或创建新的 Scheme 草稿。"""

        _lock_scheme_registry(self._session)
        compiled = compile_analysis_scheme(definition)
        scheme = (
            self._session.execute(
                select(analysis_schemes_table)
                .where(analysis_schemes_table.c.name == name)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        now = beijing_now()
        if scheme is None:
            scheme_id = uuid4()
            self._session.execute(
                insert(analysis_schemes_table).values(
                    id=scheme_id,
                    name=name,
                    active_version_id=None,
                    is_active=False,
                    created_at=now,
                    updated_at=now,
                )
            )
            version = 1
        else:
            scheme_id = cast(UUID, scheme["id"])
            latest = self._session.scalar(
                select(func.max(analysis_scheme_versions_table.c.version)).where(
                    analysis_scheme_versions_table.c.scheme_id == scheme_id
                )
            )
            version = int(latest or 0) + 1
        row = (
            self._session.execute(
                insert(analysis_scheme_versions_table)
                .values(
                    id=uuid4(),
                    scheme_id=scheme_id,
                    version=version,
                    status="draft",
                    description=description,
                    definition=definition.model_dump(mode="json"),
                    compiled_prompt=compiled.prompt_text,
                    prompt_sha256=compiled.prompt_sha256,
                    taxonomy_sha256=compiled.taxonomy_sha256,
                    created_by=actor_ref,
                    created_at=now,
                )
                .returning(analysis_scheme_versions_table)
            )
            .mappings()
            .one()
        )
        return _version_from_row(row)

    def update_draft(
        self,
        version_id: UUID,
        *,
        expected_version: int,
        description: str,
        definition: AnalysisSchemeDefinitionRequest,
        actor_ref: str,
    ) -> AnalysisSchemeVersionRecord:
        """以追加新版本的方式保存草稿，并用旧版本身份防止并发覆盖。"""

        _lock_scheme_registry(self._session)
        compiled = compile_analysis_scheme(definition)
        target_row = (
            self._session.execute(
                select(analysis_scheme_versions_table)
                .where(
                    analysis_scheme_versions_table.c.id == version_id,
                    analysis_scheme_versions_table.c.version == expected_version,
                    analysis_scheme_versions_table.c.status == "draft",
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if target_row is None:
            raise RuntimeError("Scheme 草稿不存在、已发布或版本冲突")

        target = _version_from_row(target_row)
        next_version = int(
            self._session.scalar(
                select(func.max(analysis_scheme_versions_table.c.version)).where(
                    analysis_scheme_versions_table.c.scheme_id == target.scheme_id
                )
            )
            or 0
        ) + 1
        now = beijing_now()
        self._session.execute(
            update(analysis_scheme_versions_table)
            .where(analysis_scheme_versions_table.c.id == version_id)
            .values(status="retired")
        )
        row = (
            self._session.execute(
                insert(analysis_scheme_versions_table)
                .values(
                    id=uuid4(),
                    scheme_id=target.scheme_id,
                    version=next_version,
                    status="draft",
                    description=description,
                    definition=definition.model_dump(mode="json"),
                    compiled_prompt=compiled.prompt_text,
                    prompt_sha256=compiled.prompt_sha256,
                    taxonomy_sha256=compiled.taxonomy_sha256,
                    created_by=actor_ref,
                    created_at=now,
                )
                .returning(analysis_scheme_versions_table)
            )
            .mappings()
            .one()
        )
        self._session.execute(
            update(analysis_schemes_table)
            .where(analysis_schemes_table.c.id == target.scheme_id)
            .values(updated_at=now)
        )
        return _version_from_row(row)

    def activate_version(
        self,
        version_id: UUID,
        *,
        expected_version: int,
    ) -> AnalysisSchemeVersionRecord:
        """原子发布草稿或回滚历史版本，并退役旧 active。"""

        _lock_scheme_registry(self._session)
        target_row = (
            self._session.execute(
                select(analysis_scheme_versions_table)
                .where(
                    analysis_scheme_versions_table.c.id == version_id,
                    analysis_scheme_versions_table.c.version == expected_version,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if target_row is None:
            raise RuntimeError("Scheme Version 不存在或版本冲突")
        target = _version_from_row(target_row)
        now = beijing_now()
        self._session.execute(
            update(analysis_scheme_versions_table)
            .where(analysis_scheme_versions_table.c.status == "published")
            .values(status="retired")
        )
        self._session.execute(update(analysis_schemes_table).values(is_active=False))
        row = (
            self._session.execute(
                update(analysis_scheme_versions_table)
                .where(analysis_scheme_versions_table.c.id == version_id)
                .values(status="published", published_at=now)
                .returning(analysis_scheme_versions_table)
            )
            .mappings()
            .one()
        )
        self._session.execute(
            update(analysis_schemes_table)
            .where(analysis_schemes_table.c.id == target.scheme_id)
            .values(active_version_id=version_id, is_active=True, updated_at=now)
        )
        return _version_from_row(row)

    def get_version(self, version_id: UUID) -> AnalysisSchemeVersionRecord | None:
        """按稳定 Version ID 读取 Scheme 快照。"""

        row = (
            self._session.execute(
                select(analysis_scheme_versions_table).where(
                    analysis_scheme_versions_table.c.id == version_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _version_from_row(row)

    def get_active_version(self) -> AnalysisSchemeVersionRecord | None:
        """读取唯一 active Scheme Version。"""

        row = (
            self._session.execute(
                select(analysis_scheme_versions_table)
                .join(
                    analysis_schemes_table,
                    analysis_schemes_table.c.active_version_id
                    == analysis_scheme_versions_table.c.id,
                )
                .where(analysis_schemes_table.c.is_active.is_(True))
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _version_from_row(row)

    def list_schemes(
        self,
    ) -> tuple[tuple[RowMapping, tuple[AnalysisSchemeVersionRecord, ...]], ...]:
        """返回 Scheme 及其按版本倒序排列的完整版本。"""

        schemes = tuple(
            self._session.execute(
                select(analysis_schemes_table).order_by(
                    analysis_schemes_table.c.is_active.desc(),
                    analysis_schemes_table.c.name,
                )
            ).mappings()
        )
        result = []
        for scheme in schemes:
            versions = tuple(
                _version_from_row(row)
                for row in self._session.execute(
                    select(analysis_scheme_versions_table)
                    .where(analysis_scheme_versions_table.c.scheme_id == scheme["id"])
                    .order_by(analysis_scheme_versions_table.c.version.desc())
                ).mappings()
            )
            result.append((scheme, versions))
        return tuple(result)


__all__ = ["PostgresAnalysisSchemeRepository"]
