"""Keyword Pack / Collection Plan 产品资源生命周期 Application Service 与扩展路由。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response, status
from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.collection_plan_lifecycle import (
    PostgresCollectionPlanLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.keyword_lifecycle import (
    PostgresKeywordPackLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.bootstrap.collection_strategy_http import (
    PostgresCollectionStrategyHttpService,
    _validate_execution_surface,
)
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.contracts.http import (
    CollectionPlanResponse,
    HttpErrorResponse,
    KeywordPackResponse,
)
from aima_ugc.contracts.resource_lifecycle import (
    CollectionPlanCopyRequest,
    CollectionPlanUpdateRequest,
    KeywordPackCopyRequest,
    KeywordPackItemRemoveRequest,
    KeywordPackItemUpdateRequest,
    KeywordPackUpdateRequest,
    ResourceDeleteEligibilityResponse,
    ResourceLifecycleListResponse,
    ResourceLifecycleResponse,
)
from aima_ugc.modules.analysis import normalize_keyword_storage_text
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    PlanPlatformDefinition,
)
from aima_ugc.modules.collection.scheduler import ScheduleExpressionError, next_schedule_time
from aima_ugc.modules.collection.strategy_http import (
    CollectionStrategyConflict,
    CollectionStrategyInvalid,
    CollectionStrategyResourceNotFound,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver, Principal
from aima_ugc.modules.system.models import AuditEvent, Keyword
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime, create_platform_runtime


class PostgresResourceLifecycleHttpService:
    """配置资源写入、引用守卫和审计的业务事务编排。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def update_keyword_pack(
        self,
        pack_id: UUID,
        body: KeywordPackUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackResponse:
        """编辑词包名称/说明，使用现有 version 做乐观并发控制。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    repository = PostgresKeywordPackLifecycleRepository(session)
                    updated = repository.update_metadata(
                        pack_id,
                        expected_version=body.expected_version,
                        name=body.name,
                        description=body.description,
                    )
                    if updated is None:
                        if repository.delete_blockers(pack_id) == ("资源不存在",):
                            raise CollectionStrategyResourceNotFound
                        raise CollectionStrategyConflict("词包版本已经变化或资源已归档")
                    _audit(
                        session,
                        principal=principal,
                        request_id=request_id,
                        event_type="keyword_pack_updated",
                        object_type="keyword_pack",
                        object_id=str(pack_id),
                        detail={"version": updated.version},
                    )
            except IntegrityError as exc:
                raise CollectionStrategyConflict("同名词包已经存在") from exc
        finally:
            session.close()
        return PostgresImportHttpService(self._runtime).get_keyword_pack(pack_id)

    def update_keyword_pack_item(
        self,
        pack_id: UUID,
        keyword_id: UUID,
        body: KeywordPackItemUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackResponse:
        """安全替换当前词包成员；共享 Keyword 不做原地文本修改。"""

        principal.require_administrator()
        try:
            normalized = normalize_keyword_storage_text(body.text)
        except ValueError as exc:
            raise CollectionStrategyInvalid("关键词不合法") from exc
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    catalog = PostgresKeywordCatalogRepository(session)
                    replacement = catalog.get_or_create_keyword(
                        Keyword(
                            id=uuid4(),
                            text=body.text,
                            normalized_text=normalized,
                            enabled=True,
                        )
                    )
                    repository = PostgresKeywordPackLifecycleRepository(session)
                    try:
                        updated = repository.replace_item(
                            pack_id,
                            keyword_id,
                            source_platform_scope=body.source_platform_scope,
                            replacement_keyword_id=replacement.id,
                            platform_scope=body.platform_scope,
                            priority=body.priority,
                            enabled=body.enabled,
                            note=body.note,
                            expected_version=body.expected_version,
                        )
                    except LookupError as exc:
                        raise CollectionStrategyResourceNotFound from exc
                    except RuntimeError as exc:
                        raise CollectionStrategyConflict(str(exc)) from exc
                    if updated is None:
                        raise CollectionStrategyResourceNotFound
                    _audit(
                        session,
                        principal=principal,
                        request_id=request_id,
                        event_type="keyword_pack_keyword_updated",
                        object_type="keyword_pack",
                        object_id=str(pack_id),
                        detail={
                            "version": updated.version,
                            "platform_scope": body.platform_scope,
                            "priority": body.priority,
                            "enabled": body.enabled,
                        },
                    )
            except IntegrityError as exc:
                raise CollectionStrategyConflict("修改后的关键词与现有配置冲突") from exc
        finally:
            session.close()
        return PostgresImportHttpService(self._runtime).get_keyword_pack(pack_id)

    def remove_keyword_pack_item(
        self,
        pack_id: UUID,
        keyword_id: UUID,
        body: KeywordPackItemRemoveRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackResponse:
        """从停用词包移除一个关键词成员，不删除仍被其他词包复用的 Keyword。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresKeywordPackLifecycleRepository(session)
                try:
                    updated = repository.remove_item(
                        pack_id,
                        keyword_id,
                        platform_scope=body.platform_scope,
                        expected_version=body.expected_version,
                    )
                except LookupError as exc:
                    raise CollectionStrategyResourceNotFound from exc
                except RuntimeError as exc:
                    raise CollectionStrategyConflict(str(exc)) from exc
                if updated is None:
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="keyword_pack_keyword_removed",
                    object_type="keyword_pack",
                    object_id=str(pack_id),
                    detail={"keyword_id": str(keyword_id), "version": updated.version},
                )
        finally:
            session.close()
        return PostgresImportHttpService(self._runtime).get_keyword_pack(pack_id)

    def copy_keyword_pack(
        self,
        pack_id: UUID,
        body: KeywordPackCopyRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackResponse:
        """复制词包与当前成员/车型关系，副本默认停用。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    copied = PostgresKeywordPackLifecycleRepository(session).copy_pack(
                        pack_id,
                        name=body.name,
                    )
                    if copied is None:
                        raise CollectionStrategyResourceNotFound
                    _audit(
                        session,
                        principal=principal,
                        request_id=request_id,
                        event_type="keyword_pack_copied",
                        object_type="keyword_pack",
                        object_id=str(copied.id),
                        detail={"source_keyword_pack_id": str(pack_id), "enabled": False},
                    )
                    copied_id = copied.id
            except IntegrityError as exc:
                raise CollectionStrategyConflict("同名词包已经存在") from exc
        finally:
            session.close()
        return PostgresImportHttpService(self._runtime).get_keyword_pack(copied_id)

    def archive_keyword_pack(
        self,
        pack_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ResourceLifecycleResponse:
        """在没有活动引用时归档词包并停用。"""

        principal.require_administrator()
        archived_at = beijing_now()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresKeywordPackLifecycleRepository(session)
                blockers = repository.archive_blockers(pack_id)
                if blockers:
                    raise CollectionStrategyConflict("；".join(blockers))
                updated = repository.archive(pack_id, archived_at=archived_at)
                if updated is None:
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="keyword_pack_archived",
                    object_type="keyword_pack",
                    object_id=str(pack_id),
                    detail={"version": updated.version},
                )
                return ResourceLifecycleResponse(
                    id=updated.id,
                    resource_type="keyword_pack",
                    name=updated.name,
                    archived_at=archived_at,
                )
        finally:
            session.close()

    def restore_keyword_pack(
        self,
        pack_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackResponse:
        """恢复词包但保持停用，由用户显式决定是否重新启用。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                updated = PostgresKeywordPackLifecycleRepository(session).restore(pack_id)
                if updated is None:
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="keyword_pack_restored",
                    object_type="keyword_pack",
                    object_id=str(pack_id),
                    detail={"version": updated.version, "enabled": False},
                )
        finally:
            session.close()
        return PostgresImportHttpService(self._runtime).get_keyword_pack(pack_id)

    def list_archived_keyword_packs(
        self,
        *,
        principal: Principal,
    ) -> ResourceLifecycleListResponse:
        """列出已归档词包供“已归档”视图恢复。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                rows = PostgresKeywordPackLifecycleRepository(session).list_archived()
                return ResourceLifecycleListResponse(
                    items=tuple(
                        ResourceLifecycleResponse(
                            id=row.id,
                            resource_type="keyword_pack",
                            name=row.name,
                            archived_at=row.archived_at,
                        )
                        for row in rows
                    )
                )
        finally:
            session.close()

    def keyword_pack_delete_eligibility(
        self,
        pack_id: UUID,
        *,
        principal: Principal,
    ) -> ResourceDeleteEligibilityResponse:
        """只读返回永久删除阻塞原因。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                blockers = PostgresKeywordPackLifecycleRepository(session).delete_blockers(pack_id)
                return ResourceDeleteEligibilityResponse(
                    id=pack_id,
                    eligible=not blockers,
                    blocking_reasons=blockers,
                )
        finally:
            session.close()

    def delete_keyword_pack(
        self,
        pack_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        """永久删除从未进入业务历史的归档词包。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresKeywordPackLifecycleRepository(session)
                blockers = repository.delete_blockers(pack_id)
                if blockers == ("资源不存在",):
                    raise CollectionStrategyResourceNotFound
                if blockers:
                    raise CollectionStrategyConflict("；".join(blockers))
                if not repository.delete_archived(pack_id):
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="keyword_pack_deleted",
                    object_type="keyword_pack",
                    object_id=str(pack_id),
                    detail={},
                )
        finally:
            session.close()

    def update_collection_plan(
        self,
        plan_id: UUID,
        body: CollectionPlanUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> CollectionPlanResponse:
        """修改计划下一版本配置；历史 Occurrence/Run 不重写。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    planning = PostgresCollectionPlanningRepository(session)
                    current = planning.get_plan_for_update(plan_id)
                    if current is None or current.schedule_expr is None:
                        raise CollectionStrategyResourceNotFound
                    candidate = _plan_definition_from_update(body, current.created_by)
                    _validate_execution_surface(
                        session,
                        candidate,
                        require_relevance=body.enabled,
                        require_explicit_search_config=True,
                    )
                    try:
                        next_schedule_time(
                            body.schedule_expr,
                            "Asia/Shanghai",
                            datetime(2000, 1, 1, tzinfo=UTC),
                        )
                    except ScheduleExpressionError as exc:
                        raise CollectionStrategyInvalid("Cron 表达式不可执行") from exc
                    PostgresCollectionPlanLifecycleRepository(session).update_plan(
                        plan_id,
                        expected_schedule_version=body.expected_version,
                        name=body.name,
                        schedule_expr=body.schedule_expr,
                        enabled=body.enabled,
                        platforms=candidate.platforms,
                        keyword_pack_ids=body.keyword_pack_ids,
                        vehicle_model_ids=body.vehicle_model_ids,
                    )
                    _audit(
                        session,
                        principal=principal,
                        request_id=request_id,
                        event_type="collection_plan_updated",
                        object_type="collection_plan",
                        object_id=str(plan_id),
                        detail={
                            "schedule_version": body.expected_version + 1,
                            "enabled": body.enabled,
                        },
                    )
            except IntegrityError as exc:
                raise CollectionStrategyConflict("采集计划名称或关联配置冲突") from exc
            except RuntimeError as exc:
                raise CollectionStrategyConflict(str(exc)) from exc
        finally:
            session.close()
        return PostgresCollectionStrategyHttpService(self._runtime).get_plan(plan_id)

    def copy_collection_plan(
        self,
        plan_id: UUID,
        body: CollectionPlanCopyRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> CollectionPlanResponse:
        """复制当前计划执行面；副本默认停用，不复制调度游标。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    repository = PostgresCollectionPlanningRepository(session)
                    source = repository.get_plan(plan_id)
                    if source is None or source.schedule_expr is None:
                        raise CollectionStrategyResourceNotFound
                    definition = CollectionPlanDefinition(
                        name=body.name,
                        enabled=False,
                        schedule_expr=source.schedule_expr,
                        timezone=source.timezone,
                        schedule_version=1,
                        misfire_policy=source.misfire_policy,
                        max_catch_up_runs=source.max_catch_up_runs,
                        detail_policy=source.detail_policy,
                        comment_policy=source.comment_policy,
                        created_by=source.created_by,
                        platforms=source.platforms,
                        keyword_pack_ids=source.keyword_pack_ids,
                        vehicle_model_ids=source.vehicle_model_ids,
                        decision_policy=source.decision_policy,
                    )
                    _validate_execution_surface(
                        session,
                        definition,
                        require_relevance=False,
                        require_explicit_search_config=False,
                    )
                    copied = CollectionPlanningService(repository).create_plan(definition)
                    _audit(
                        session,
                        principal=principal,
                        request_id=request_id,
                        event_type="collection_plan_copied",
                        object_type="collection_plan",
                        object_id=str(copied.id),
                        detail={"source_collection_plan_id": str(plan_id), "enabled": False},
                    )
                    copied_id = copied.id
            except IntegrityError as exc:
                raise CollectionStrategyConflict("同名采集计划已经存在") from exc
            except ScheduleExpressionError as exc:
                raise CollectionStrategyInvalid("原计划 Cron 表达式不可执行") from exc
        finally:
            session.close()
        return PostgresCollectionStrategyHttpService(self._runtime).get_plan(copied_id)

    def archive_collection_plan(
        self,
        plan_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ResourceLifecycleResponse:
        """归档计划只停止未来调度，不取消已经创建的运行。"""

        principal.require_administrator()
        archived_at = beijing_now()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                planning = PostgresCollectionPlanningRepository(session)
                current = planning.get_plan_for_update(plan_id)
                if current is None:
                    raise CollectionStrategyResourceNotFound
                if not PostgresCollectionPlanLifecycleRepository(session).archive(
                    plan_id,
                    archived_at=archived_at,
                ):
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="collection_plan_archived",
                    object_type="collection_plan",
                    object_id=str(plan_id),
                    detail={"previous_schedule_version": current.schedule_version},
                )
                return ResourceLifecycleResponse(
                    id=plan_id,
                    resource_type="collection_plan",
                    name=current.name,
                    archived_at=archived_at,
                )
        finally:
            session.close()

    def restore_collection_plan(
        self,
        plan_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> CollectionPlanResponse:
        """恢复计划但保持停用，避免恢复操作本身触发调度。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                if not PostgresCollectionPlanLifecycleRepository(session).restore(plan_id):
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="collection_plan_restored",
                    object_type="collection_plan",
                    object_id=str(plan_id),
                    detail={"enabled": False},
                )
        finally:
            session.close()
        return PostgresCollectionStrategyHttpService(self._runtime).get_plan(plan_id)

    def list_archived_collection_plans(
        self,
        *,
        principal: Principal,
    ) -> ResourceLifecycleListResponse:
        """列出已归档计划供恢复入口消费。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                rows = PostgresCollectionPlanLifecycleRepository(session).list_archived()
                return ResourceLifecycleListResponse(
                    items=tuple(
                        ResourceLifecycleResponse(
                            id=row.id,
                            resource_type="collection_plan",
                            name=row.name,
                            archived_at=row.archived_at,
                        )
                        for row in rows
                    )
                )
        finally:
            session.close()

    def collection_plan_delete_eligibility(
        self,
        plan_id: UUID,
        *,
        principal: Principal,
    ) -> ResourceDeleteEligibilityResponse:
        """返回采集计划的永久删除资格。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                blockers = PostgresCollectionPlanLifecycleRepository(session).delete_blockers(
                    plan_id
                )
                return ResourceDeleteEligibilityResponse(
                    id=plan_id,
                    eligible=not blockers,
                    blocking_reasons=blockers,
                )
        finally:
            session.close()

    def delete_collection_plan(
        self,
        plan_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        """永久删除从未产生调度/运行历史的归档计划。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCollectionPlanLifecycleRepository(session)
                blockers = repository.delete_blockers(plan_id)
                if blockers == ("资源不存在",):
                    raise CollectionStrategyResourceNotFound
                if blockers:
                    raise CollectionStrategyConflict("；".join(blockers))
                if not repository.delete_archived(plan_id):
                    raise CollectionStrategyResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="collection_plan_deleted",
                    object_type="collection_plan",
                    object_id=str(plan_id),
                    detail={},
                )
        finally:
            session.close()


def install_resource_lifecycle_routes(
    application: FastAPI,
    *,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """安装不与原 CRUD 路径冲突的资源生命周期扩展路由。"""

    resolver = identity_resolver or DevelopmentIdentityResolver()
    runtime: PlatformRuntime | None = None

    def service() -> PostgresResourceLifecycleHttpService:
        """惰性复用正式 Platform Runtime，避免 import 阶段触碰数据库。"""

        nonlocal runtime
        if runtime is None:
            runtime = create_platform_runtime("api")
        return PostgresResourceLifecycleHttpService(runtime)

    router = cast(Any, application.router)
    original_lifespan = router.lifespan_context

    @asynccontextmanager
    async def lifecycle_lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with original_lifespan(app):
            try:
                yield
            finally:
                if runtime is not None:
                    runtime.close()

    router.lifespan_context = lifecycle_lifespan

    def principal(request: Request) -> Principal:
        """使用与主 API 相同的 Provider-neutral 身份解析器。"""

        return resolver.resolve(request)

    @application.put(
        "/api/v1/keyword-packs/{pack_id}",
        operation_id="updateKeywordPack",
        response_model=KeywordPackResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def update_keyword_pack(
        pack_id: UUID, body: KeywordPackUpdateRequest, request: Request
    ) -> KeywordPackResponse:
        return service().update_keyword_pack(
            pack_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.put(
        "/api/v1/keyword-packs/{pack_id}/keywords/{keyword_id}",
        operation_id="updateKeywordInPack",
        response_model=KeywordPackResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def update_keyword_in_pack(
        pack_id: UUID,
        keyword_id: UUID,
        body: KeywordPackItemUpdateRequest,
        request: Request,
    ) -> KeywordPackResponse:
        return service().update_keyword_pack_item(
            pack_id,
            keyword_id,
            body,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/keyword-packs/{pack_id}/keywords/{keyword_id}/remove",
        operation_id="removeKeywordFromPack",
        response_model=KeywordPackResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def remove_keyword_from_pack(
        pack_id: UUID, keyword_id: UUID, body: KeywordPackItemRemoveRequest, request: Request
    ) -> KeywordPackResponse:
        return service().remove_keyword_pack_item(
            pack_id, keyword_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.post(
        "/api/v1/keyword-packs/{pack_id}/copy",
        operation_id="copyKeywordPack",
        response_model=KeywordPackResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def copy_keyword_pack(
        pack_id: UUID, body: KeywordPackCopyRequest, request: Request
    ) -> KeywordPackResponse:
        return service().copy_keyword_pack(
            pack_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.post(
        "/api/v1/keyword-packs/{pack_id}/archive",
        operation_id="archiveKeywordPack",
        response_model=ResourceLifecycleResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def archive_keyword_pack(pack_id: UUID, request: Request) -> ResourceLifecycleResponse:
        return service().archive_keyword_pack(
            pack_id, principal=principal(request), request_id=_request_id(request)
        )

    @application.post(
        "/api/v1/keyword-packs/{pack_id}/restore",
        operation_id="restoreKeywordPack",
        response_model=KeywordPackResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def restore_keyword_pack(pack_id: UUID, request: Request) -> KeywordPackResponse:
        return service().restore_keyword_pack(
            pack_id, principal=principal(request), request_id=_request_id(request)
        )

    @application.get(
        "/api/v1/resource-lifecycle/keyword-packs/archived",
        operation_id="listArchivedKeywordPacks",
        response_model=ResourceLifecycleListResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["keywords"],
    )
    def list_archived_keyword_packs(request: Request) -> ResourceLifecycleListResponse:
        return service().list_archived_keyword_packs(principal=principal(request))

    @application.get(
        "/api/v1/keyword-packs/{pack_id}/delete-eligibility",
        operation_id="getKeywordPackDeleteEligibility",
        response_model=ResourceDeleteEligibilityResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["keywords"],
    )
    def get_keyword_pack_delete_eligibility(
        pack_id: UUID, request: Request
    ) -> ResourceDeleteEligibilityResponse:
        return service().keyword_pack_delete_eligibility(pack_id, principal=principal(request))

    @application.delete(
        "/api/v1/keyword-packs/{pack_id}",
        operation_id="deleteKeywordPack",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def delete_keyword_pack(pack_id: UUID, request: Request) -> Response:
        service().delete_keyword_pack(
            pack_id, principal=principal(request), request_id=_request_id(request)
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.put(
        "/api/v1/collection-plans/{plan_id}",
        operation_id="updateCollectionPlan",
        response_model=CollectionPlanResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def update_collection_plan(
        plan_id: UUID, body: CollectionPlanUpdateRequest, request: Request
    ) -> CollectionPlanResponse:
        return service().update_collection_plan(
            plan_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.post(
        "/api/v1/collection-plans/{plan_id}/copy",
        operation_id="copyCollectionPlan",
        response_model=CollectionPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def copy_collection_plan(
        plan_id: UUID, body: CollectionPlanCopyRequest, request: Request
    ) -> CollectionPlanResponse:
        return service().copy_collection_plan(
            plan_id, body, principal=principal(request), request_id=_request_id(request)
        )

    @application.post(
        "/api/v1/collection-plans/{plan_id}/archive",
        operation_id="archiveCollectionPlan",
        response_model=ResourceLifecycleResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}},
        tags=["collection-strategy"],
    )
    def archive_collection_plan(plan_id: UUID, request: Request) -> ResourceLifecycleResponse:
        return service().archive_collection_plan(
            plan_id, principal=principal(request), request_id=_request_id(request)
        )

    @application.post(
        "/api/v1/collection-plans/{plan_id}/restore",
        operation_id="restoreCollectionPlan",
        response_model=CollectionPlanResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}},
        tags=["collection-strategy"],
    )
    def restore_collection_plan(plan_id: UUID, request: Request) -> CollectionPlanResponse:
        return service().restore_collection_plan(
            plan_id, principal=principal(request), request_id=_request_id(request)
        )

    @application.get(
        "/api/v1/resource-lifecycle/collection-plans/archived",
        operation_id="listArchivedCollectionPlans",
        response_model=ResourceLifecycleListResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["collection-strategy"],
    )
    def list_archived_collection_plans(request: Request) -> ResourceLifecycleListResponse:
        return service().list_archived_collection_plans(principal=principal(request))

    @application.get(
        "/api/v1/collection-plans/{plan_id}/delete-eligibility",
        operation_id="getCollectionPlanDeleteEligibility",
        response_model=ResourceDeleteEligibilityResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["collection-strategy"],
    )
    def get_collection_plan_delete_eligibility(
        plan_id: UUID, request: Request
    ) -> ResourceDeleteEligibilityResponse:
        return service().collection_plan_delete_eligibility(plan_id, principal=principal(request))

    @application.delete(
        "/api/v1/collection-plans/{plan_id}",
        operation_id="deleteCollectionPlan",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def delete_collection_plan(plan_id: UUID, request: Request) -> Response:
        service().delete_collection_plan(
            plan_id, principal=principal(request), request_id=_request_id(request)
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


def _plan_definition_from_update(
    body: CollectionPlanUpdateRequest,
    created_by: UUID | None,
) -> CollectionPlanDefinition:
    """把公开更新 Contract 转换为与创建路径相同的领域计划定义。"""

    return CollectionPlanDefinition(
        name=body.name,
        enabled=body.enabled,
        schedule_expr=body.schedule_expr,
        timezone="Asia/Shanghai",
        schedule_version=body.expected_version + 1,
        misfire_policy="latest_only",
        max_catch_up_runs=0,
        detail_policy="on_change",
        comment_policy="adaptive",
        created_by=created_by,
        platforms=tuple(
            PlanPlatformDefinition(
                platform=item.platform,
                provider_config_id=item.provider_config_id,
                config=item.search_config.model_dump(mode="json", exclude_none=True),
            )
            for item in body.platforms
        ),
        keyword_pack_ids=body.keyword_pack_ids,
        vehicle_model_ids=body.vehicle_model_ids,
    )


def _audit(
    session: Session,
    *,
    principal: Principal,
    request_id: str,
    event_type: str,
    object_type: str,
    object_id: str,
    detail: dict[str, JsonValue],
) -> None:
    """在业务写事务中追加不含 Secret 的生命周期审计。"""

    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=principal.principal_id,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            safe_detail=detail,
            created_at=beijing_now(),
        )
    )


def _request_id(request: Request) -> str:
    """复用主 API middleware 的 request_id；直接装配测试时安全兜底。"""

    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else str(uuid4())


__all__ = [
    "PostgresResourceLifecycleHttpService",
    "install_resource_lifecycle_routes",
]
