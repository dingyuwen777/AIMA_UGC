"""Canonical Replay HTTP Application Service 的稳定边界。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.http import (
    CanonicalReplayAllCreatedResponse,
    CanonicalReplayAllCreateRequest,
    CanonicalReplayAllOperationResponse,
    CanonicalReplayCreatedResponse,
    CanonicalReplayCreateRequest,
    CanonicalReplayRunResponse,
)


class CanonicalReplayResourceNotFound(LookupError):
    """Replay Run 或输入资源不存在。"""


class CanonicalReplayConflict(RuntimeError):
    """幂等键、当前状态或来源结构发生冲突。"""


class CanonicalReplayInputInvalid(ValueError):
    """Replay 输入不是当前支持且可证明 lineage 的 Canonical。"""


class CanonicalReplayHttpService(Protocol):
    def create_all_replays(
        self,
        body: CanonicalReplayAllCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllCreatedResponse: ...

    def create_replay(
        self,
        body: CanonicalReplayCreateRequest,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayCreatedResponse: ...

    def get_replay(self, run_id: UUID) -> CanonicalReplayRunResponse: ...

    def cancel_replay(
        self,
        run_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayRunResponse: ...

    def cancel_and_revoke_all(
        self,
        replay_request_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllOperationResponse: ...

    def revoke_all(
        self,
        replay_request_id: UUID,
        *,
        actor_ref: str,
        request_id: str,
    ) -> CanonicalReplayAllOperationResponse: ...


__all__ = [
    "CanonicalReplayConflict",
    "CanonicalReplayHttpService",
    "CanonicalReplayInputInvalid",
    "CanonicalReplayResourceNotFound",
]
