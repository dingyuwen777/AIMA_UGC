"""工作台 HTTP Application Service 边界。"""

from __future__ import annotations

from typing import Protocol

from aima_ugc.contracts.workbench import (
    WorkbenchLayoutResponse,
    WorkbenchLayoutUpdateRequest,
    WorkbenchMindResponse,
    WorkbenchQuery,
    WorkbenchStreamResponse,
    WorkbenchTrendResponse,
)


class WorkbenchAnalysisUnavailable(RuntimeError):
    pass


class WorkbenchLayoutConflict(RuntimeError):
    pass


class WorkbenchHttpService(Protocol):
    def get_stream(self, query: WorkbenchQuery) -> WorkbenchStreamResponse: ...

    def get_trend(self, query: WorkbenchQuery) -> WorkbenchTrendResponse: ...

    def get_mind(self, query: WorkbenchQuery) -> WorkbenchMindResponse: ...

    def get_layout(self, *, principal_id: str) -> WorkbenchLayoutResponse: ...

    def update_layout(
        self,
        body: WorkbenchLayoutUpdateRequest,
        *,
        principal_id: str,
    ) -> WorkbenchLayoutResponse: ...


__all__ = [
    "WorkbenchAnalysisUnavailable",
    "WorkbenchHttpService",
    "WorkbenchLayoutConflict",
]
