"""Stage 8F Keyword/Relevance/Collection Plan HTTP Application Service。"""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import (
    KeywordPackSummaryRecord,
    PostgresKeywordCatalogRepository,
)
from aima_ugc.adapters.persistence.postgres.relevance import (
    GlobalRelevanceUnavailable,
    PostgresGlobalRelevanceRepository,
)
from aima_ugc.adapters.persistence.postgres.scheduled_keywords import (
    MissingScheduledKeywordPackError,
    PostgresScheduledKeywordSnapshotReader,
)
from aima_ugc.adapters.persistence.postgres.system import (
    PostgresAuditRepository,
    PostgresProviderConfigRepository,
)
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.adapters.providers.registry import build_default_provider_registry
from aima_ugc.contracts.http import (
    CollectionPlanCreateRequest,
    CollectionPlanListQuery,
    CollectionPlanListResponse,
    CollectionPlanPlatformResponse,
    CollectionPlanResponse,
    CollectionSearchConfig,
    KeywordPackListQuery,
    KeywordPackListResponse,
    KeywordPackSummaryResponse,
    ResourceEnabledRequest,
)
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    CollectionPlanRecord,
    PlanPlatformDefinition,
)
from aima_ugc.modules.collection.scheduler import ScheduleExpressionError
from aima_ugc.modules.collection.search_config import normalize_search_config
from aima_ugc.modules.collection.strategy_http import (
    CollectionStrategyConflict,
    CollectionStrategyInvalid,
    CollectionStrategyResourceNotFound,
)
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime


class PostgresCollectionStrategyHttpService:
    """复用 System/Collection Owner Repository 的短事务配置编排。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def list_keyword_packs(self, query: KeywordPackListQuery) -> KeywordPackListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresKeywordCatalogRepository(session)
                records = repository.list_pack_summaries(
                    search=query.search,
                    enabled=query.enabled,
                    offset=query.offset,
                    limit=query.limit,
                )
                total = repository.count_packs(search=query.search, enabled=query.enabled)
                return KeywordPackListResponse(
                    items=tuple(_keyword_pack_summary(item) for item in records),
                    total=total,
                    offset=query.offset,
                    limit=query.limit,
                )
        finally:
            session.close()

    def set_keyword_pack_enabled(
        self,
        pack_id: UUID,
        request: ResourceEnabledRequest,
        *,
        actor_ref: str = "system:direct-service-call",
        request_id: str = "direct-service-call",
    ) -> KeywordPackSummaryResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                keywords = PostgresKeywordCatalogRepository(session)
                current = keywords.get_pack_for_update(pack_id)
                if current is None:
                    raise CollectionStrategyResourceNotFound
                if not request.enabled and current.enabled:
                    relevance = PostgresGlobalRelevanceRepository(session).get()
                    if relevance is not None and relevance.keyword_pack_id == pack_id:
                        raise CollectionStrategyConflict("全局 Relevance 正在引用该词包")
                    if PostgresCollectionPlanningRepository(
                        session
                    ).has_enabled_plan_for_keyword_pack(pack_id):
                        raise CollectionStrategyConflict("启用中的 Collection Plan 正在引用该词包")
                updated = keywords.set_pack_enabled(pack_id, enabled=request.enabled)
                if updated is None:  # pragma: no cover - 当前事务持有父记录锁
                    raise CollectionStrategyResourceNotFound
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="keyword_pack_enabled_updated",
                    object_type="keyword_pack",
                    object_id=str(pack_id),
                    detail={"enabled": updated.enabled, "version": updated.version},
                )
                return KeywordPackSummaryResponse(
                    id=updated.id,
                    name=updated.name,
                    description=updated.description,
                    enabled=updated.enabled,
                    version=updated.version,
                    keyword_count=len(keywords.list_items(pack_id)),
                )
        finally:
            session.close()

    def create_plan(
        self,
        request: CollectionPlanCreateRequest,
        *,
        actor_ref: str = "system:direct-service-call",
        request_id: str = "direct-service-call",
    ) -> CollectionPlanResponse:
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    repository = PostgresCollectionPlanningRepository(session)
                    definition = _plan_definition(request, actor_ref=actor_ref)
                    _validate_execution_surface(
                        session,
                        definition,
                        require_relevance=request.enabled,
                        require_explicit_search_config=True,
                    )
                    created = CollectionPlanningService(repository).create_plan(definition)
                    _audit_configuration(
                        session,
                        actor_ref=actor_ref,
                        request_id=request_id,
                        event_type="collection_plan_created",
                        object_type="collection_plan",
                        object_id=str(created.id),
                        detail={
                            "enabled": created.enabled,
                            "schedule_version": created.schedule_version,
                        },
                    )
                    return _plan_response(created)
            except IntegrityError as exc:
                raise CollectionStrategyConflict("同名 Plan 或关联配置冲突") from exc
            except ScheduleExpressionError as exc:
                raise CollectionStrategyInvalid("Cron 表达式不可执行") from exc
        finally:
            session.close()

    def list_plans(self, query: CollectionPlanListQuery) -> CollectionPlanListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCollectionPlanningRepository(session)
                records = repository.list_plans(
                    search=query.search,
                    enabled=query.enabled,
                    platform=query.platform,
                    offset=query.offset,
                    limit=query.limit,
                )
                return CollectionPlanListResponse(
                    items=tuple(_plan_response(item) for item in records),
                    total=repository.count_plans(
                        search=query.search,
                        enabled=query.enabled,
                        platform=query.platform,
                    ),
                    enabled_count=repository.count_enabled_plans(),
                    offset=query.offset,
                    limit=query.limit,
                )
        finally:
            session.close()

    def get_plan(self, plan_id: UUID) -> CollectionPlanResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                record = PostgresCollectionPlanningRepository(session).get_plan(plan_id)
                if record is None or record.schedule_expr is None:
                    raise CollectionStrategyResourceNotFound
                return _plan_response(record)
        finally:
            session.close()

    def set_plan_enabled(
        self,
        plan_id: UUID,
        request: ResourceEnabledRequest,
        *,
        actor_ref: str = "system:direct-service-call",
        request_id: str = "direct-service-call",
    ) -> CollectionPlanResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresCollectionPlanningRepository(session)
                current = repository.get_plan_for_update(plan_id)
                if current is None or current.schedule_expr is None:
                    raise CollectionStrategyResourceNotFound
                if request.enabled and not current.enabled:
                    _validate_execution_surface(
                        session,
                        current,
                        require_relevance=True,
                        require_explicit_search_config=False,
                    )
                updated = repository.set_plan_enabled(plan_id, enabled=request.enabled)
                if updated is None:  # pragma: no cover - 当前事务持有 Plan 锁
                    raise CollectionStrategyResourceNotFound
                _audit_configuration(
                    session,
                    actor_ref=actor_ref,
                    request_id=request_id,
                    event_type="collection_plan_enabled_updated",
                    object_type="collection_plan",
                    object_id=str(plan_id),
                    detail={
                        "enabled": updated.enabled,
                        "schedule_version": updated.schedule_version,
                    },
                )
                return _plan_response(updated)
        finally:
            session.close()


def _plan_definition(
    request: CollectionPlanCreateRequest,
    *,
    actor_ref: str,
) -> CollectionPlanDefinition:
    return CollectionPlanDefinition(
        name=request.name,
        enabled=request.enabled,
        schedule_expr=request.schedule_expr,
        timezone="Asia/Shanghai",
        schedule_version=1,
        misfire_policy="latest_only",
        max_catch_up_runs=0,
        detail_policy="on_change",
        comment_policy="adaptive",
        created_by=None,
        platforms=tuple(
            PlanPlatformDefinition(
                platform=item.platform,
                provider_config_id=item.provider_config_id,
                config=item.search_config.model_dump(mode="json", exclude_none=True),
            )
            for item in request.platforms
        ),
        keyword_pack_ids=request.keyword_pack_ids,
        vehicle_model_ids=request.vehicle_model_ids,
    )


def _audit_configuration(
    session: Session,
    *,
    actor_ref: str,
    request_id: str,
    event_type: str,
    object_type: str,
    object_id: str,
    detail: dict[str, JsonValue],
) -> None:
    """在配置写事务内追加不含 Secret 的安全审计摘要。"""

    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=actor_ref,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            safe_detail=detail,
            created_at=beijing_now(),
        )
    )


def _validate_execution_surface(
    session: Session,
    plan: CollectionPlanDefinition | CollectionPlanRecord,
    *,
    require_relevance: bool,
    require_explicit_search_config: bool,
) -> None:
    keyword_repository = PostgresKeywordCatalogRepository(session)
    for pack_id in sorted(plan.keyword_pack_ids, key=str):
        pack = keyword_repository.get_pack_for_update(pack_id)
        if pack is None:
            raise CollectionStrategyResourceNotFound
        if not pack.enabled:
            raise CollectionStrategyConflict("Plan 引用的 Discovery 词包已停用")

    if plan.keyword_pack_ids:
        try:
            catalog = PostgresScheduledKeywordSnapshotReader(session).read(plan.keyword_pack_ids)
        except MissingScheduledKeywordPackError as exc:  # pragma: no cover - 已持锁逐项验证
            raise CollectionStrategyResourceNotFound from exc
        keyword_terms = tuple(
            dict.fromkeys(
                entry.keyword_text
                for entry in catalog.entries
                if entry.pack_enabled and entry.keyword_enabled and entry.item_enabled
            )
        )
    else:
        keyword_terms = ()
    try:
        vehicle_snapshot = PostgresVehicleCatalogRepository(session).snapshot(
            plan.vehicle_model_ids
        )
    except LookupError as exc:
        raise CollectionStrategyResourceNotFound from exc
    if not keyword_terms and not vehicle_snapshot.resolved_aliases:
        raise CollectionStrategyConflict("目标平台没有可用 Discovery 关键词或车型别名")

    providers = PostgresProviderConfigRepository(session)
    registry = build_default_provider_registry()
    for item in plan.platforms:
        config = providers.get(item.provider_config_id)
        if config is None:
            raise CollectionStrategyResourceNotFound
        try:
            route = registry.resolve(config=config, platform=item.platform)
            normalize_search_config(
                route.capability,
                item.config,
                require_complete=require_explicit_search_config,
            )
        except ValueError as exc:
            raise CollectionStrategyConflict("Provider Config 当前不可执行") from exc

    if require_relevance:
        try:
            PostgresGlobalRelevanceRepository(session).snapshot()
        except GlobalRelevanceUnavailable as exc:
            raise CollectionStrategyConflict("全局 Relevance 当前不可用") from exc


def _keyword_pack_summary(record: KeywordPackSummaryRecord) -> KeywordPackSummaryResponse:
    return KeywordPackSummaryResponse(
        id=record.pack.id,
        name=record.pack.name,
        description=record.pack.description,
        enabled=record.pack.enabled,
        version=record.pack.version,
        keyword_count=record.keyword_count,
    )


def _plan_response(record: CollectionPlanRecord) -> CollectionPlanResponse:
    if record.schedule_expr is None:
        raise CollectionStrategyResourceNotFound
    if (
        record.timezone != "Asia/Shanghai"
        or record.misfire_policy != "latest_only"
        or record.max_catch_up_runs != 0
        or record.detail_policy != "on_change"
        or record.comment_policy != "adaptive"
    ):
        raise RuntimeError("Collection Plan 策略事实不满足 Stage 8F 首版约束")
    return CollectionPlanResponse(
        id=record.id,
        name=record.name,
        enabled=record.enabled,
        schedule_expr=record.schedule_expr,
        timezone=cast(Literal["Asia/Shanghai"], record.timezone),
        schedule_version=record.schedule_version,
        next_run_at=record.next_run_at,
        last_scheduled_at=record.last_scheduled_at,
        detail_policy=cast(Literal["on_change"], record.detail_policy),
        comment_policy=cast(Literal["adaptive"], record.comment_policy),
        platforms=tuple(
            CollectionPlanPlatformResponse(
                platform=item.platform,
                provider_config_id=item.provider_config_id,
                search_config=CollectionSearchConfig.model_validate(item.config),
            )
            for item in record.platforms
        ),
        keyword_pack_ids=record.keyword_pack_ids,
        vehicle_model_ids=record.vehicle_model_ids,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


__all__ = ["PostgresCollectionStrategyHttpService"]
