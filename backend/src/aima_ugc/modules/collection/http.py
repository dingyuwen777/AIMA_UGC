"""Stage 8E Collection HTTP Application 边界与公开错误。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    CollectionCapabilitiesResponse,
    CollectionRunCreatedResponse,
    CollectionRunCreateRequest,
    CollectionRunResponse,
    CollectionRuntimeListQuery,
    CollectionRuntimeListResponse,
    CollectionRuntimeSummaryResponse,
)


class CollectionResourceNotFound(LookupError):
    """请求的 Run、Batch、Content 或 Provider Config 不存在。"""


class CollectionConflict(RuntimeError):
    """当前配置或业务状态不能创建 Collection Run。"""


class InvalidCollectionRuntimeCursor(ValueError):
    """统一运行列表 Cursor 非法、过期、篡改或跨查询复用。"""


class CollectionRuntimeCursorUnavailable(RuntimeError):
    """统一运行列表 Cursor Secret 当前不可用。"""


class CollectionHttpService(Protocol):
    """Router 可调用的 Stage 8E 最小 Application Service。"""

    def get_capabilities(self) -> CollectionCapabilitiesResponse: ...

    def create_run(
        self,
        request: CollectionRunCreateRequest,
        *,
        request_id: str,
    ) -> CollectionRunCreatedResponse: ...

    def get_run(self, run_id: UUID) -> CollectionRunResponse: ...

    def list_runtime_runs(
        self,
        query: CollectionRuntimeListQuery,
    ) -> CollectionRuntimeListResponse: ...

    def get_runtime_summary(self) -> CollectionRuntimeSummaryResponse: ...


__all__ = [
    "CollectionConflict",
    "CollectionHttpService",
    "CollectionResourceNotFound",
    "CollectionRuntimeCursorUnavailable",
    "InvalidCollectionRuntimeCursor",
]
