"""Stage 8F 采集策略 HTTP Application 边界与公开错误。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    CollectionPlanCreateRequest,
    CollectionPlanListQuery,
    CollectionPlanListResponse,
    CollectionPlanResponse,
    KeywordPackListQuery,
    KeywordPackListResponse,
    KeywordPackSummaryResponse,
    ResourceEnabledRequest,
)


class CollectionStrategyResourceNotFound(LookupError):
    """请求的 Keyword Pack、Plan 或 Provider Config 不存在。"""


class CollectionStrategyConflict(RuntimeError):
    """当前配置状态不允许完成采集策略写入。"""


class CollectionStrategyInvalid(ValueError):
    """请求字段通过 Pydantic 后仍不满足正式领域规则。"""


class CollectionStrategyHttpService(Protocol):
    """Router 可调用的 Stage 8F 配置 Application Service。"""

    def list_keyword_packs(self, query: KeywordPackListQuery) -> KeywordPackListResponse: ...

    def set_keyword_pack_enabled(
        self,
        pack_id: UUID,
        request: ResourceEnabledRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> KeywordPackSummaryResponse: ...

    def create_plan(
        self,
        request: CollectionPlanCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CollectionPlanResponse: ...

    def list_plans(self, query: CollectionPlanListQuery) -> CollectionPlanListResponse: ...

    def get_plan(self, plan_id: UUID) -> CollectionPlanResponse: ...

    def set_plan_enabled(
        self,
        plan_id: UUID,
        request: ResourceEnabledRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CollectionPlanResponse: ...


__all__ = [
    "CollectionStrategyConflict",
    "CollectionStrategyHttpService",
    "CollectionStrategyInvalid",
    "CollectionStrategyResourceNotFound",
]
