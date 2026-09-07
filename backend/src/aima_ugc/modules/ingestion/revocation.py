"""Data Import Campaign 撤销的领域状态机与稳定业务语义。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

_REVOCABLE_STATUSES = frozenset({"succeeded", "partial_failed"})


class ImportCampaignRevocationNotFound(LookupError):
    """请求撤销的 Data Import Campaign 不存在。"""


class ImportCampaignRevocationConflict(RuntimeError):
    """Campaign 当前状态不允许撤销。"""


@dataclass(frozen=True, slots=True)
class ImportCampaignRevocationImpact:
    """撤销一次 Campaign 后对当前业务可见 Content 的影响。"""

    affected_content_count: int
    hidden_content_count: int
    retained_shared_content_count: int

    def __post_init__(self) -> None:
        if min(
            self.affected_content_count,
            self.hidden_content_count,
            self.retained_shared_content_count,
        ) < 0:
            raise ValueError("撤销影响计数不能为负数")
        if self.hidden_content_count + self.retained_shared_content_count != self.affected_content_count:
            raise ValueError("撤销影响计数不一致")


@dataclass(frozen=True, slots=True)
class ImportCampaignRevocationRecord:
    """已经提交的不可变 Campaign 撤销事实。"""

    campaign_id: UUID
    actor_ref: str
    request_id: str | None
    reason: str | None
    impact: ImportCampaignRevocationImpact
    revoked_at: datetime

    def __post_init__(self) -> None:
        if not self.actor_ref.strip():
            raise ValueError("撤销 actor_ref 不能为空")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("撤销 reason 只能为空或非空文本")
        if self.revoked_at.utcoffset() is None:
            raise ValueError("撤销时间必须包含时区")


@dataclass(frozen=True, slots=True)
class ImportCampaignRevocationPreview:
    """执行撤销前的只读业务影响预览。"""

    campaign_id: UUID
    eligible: bool
    already_revoked: bool
    impact: ImportCampaignRevocationImpact


class ImportCampaignRevocationRepository(Protocol):
    """Ingestion Owner 的撤销持久化边界。"""

    def get_campaign_status(self, campaign_id: UUID, *, for_update: bool) -> str | None: ...

    def get_revocation(self, campaign_id: UUID) -> ImportCampaignRevocationRecord | None: ...

    def calculate_impact(self, campaign_id: UUID) -> ImportCampaignRevocationImpact: ...

    def create_revocation(
        self,
        *,
        campaign_id: UUID,
        actor_ref: str,
        request_id: str | None,
        reason: str | None,
        impact: ImportCampaignRevocationImpact,
        revoked_at: datetime,
    ) -> ImportCampaignRevocationRecord: ...


class ImportCampaignRevocationService:
    """只撤销来源贡献，不改写 Campaign 终态或共享 Content 历史。"""

    def __init__(self, repository: ImportCampaignRevocationRepository) -> None:
        self._repository = repository

    def preview(self, campaign_id: UUID) -> ImportCampaignRevocationPreview:
        """返回稳定的影响预览；运行中的 Campaign 不计算会漂移的影响。"""

        status = self._repository.get_campaign_status(campaign_id, for_update=False)
        if status is None:
            raise ImportCampaignRevocationNotFound
        existing = self._repository.get_revocation(campaign_id)
        if existing is not None:
            return ImportCampaignRevocationPreview(
                campaign_id=campaign_id,
                eligible=True,
                already_revoked=True,
                impact=existing.impact,
            )
        if status not in _REVOCABLE_STATUSES:
            return ImportCampaignRevocationPreview(
                campaign_id=campaign_id,
                eligible=False,
                already_revoked=False,
                impact=ImportCampaignRevocationImpact(0, 0, 0),
            )
        return ImportCampaignRevocationPreview(
            campaign_id=campaign_id,
            eligible=True,
            already_revoked=False,
            impact=self._repository.calculate_impact(campaign_id),
        )

    def revoke(
        self,
        campaign_id: UUID,
        *,
        actor_ref: str,
        request_id: str | None,
        reason: str | None,
        revoked_at: datetime,
    ) -> tuple[ImportCampaignRevocationRecord, bool]:
        """串行提交撤销；重复调用返回同一事实且不重复产生副作用。"""

        normalized_actor = actor_ref.strip()
        normalized_reason = reason.strip() if reason is not None else None
        if not normalized_actor:
            raise ValueError("撤销 actor_ref 不能为空")
        if revoked_at.utcoffset() is None:
            raise ValueError("撤销时间必须包含时区")

        status = self._repository.get_campaign_status(campaign_id, for_update=True)
        if status is None:
            raise ImportCampaignRevocationNotFound
        existing = self._repository.get_revocation(campaign_id)
        if existing is not None:
            return existing, False
        if status not in _REVOCABLE_STATUSES:
            raise ImportCampaignRevocationConflict(
                "只有成功或部分成功的数据导入可以撤销"
            )
        impact = self._repository.calculate_impact(campaign_id)
        created = self._repository.create_revocation(
            campaign_id=campaign_id,
            actor_ref=normalized_actor,
            request_id=request_id,
            reason=normalized_reason,
            impact=impact,
            revoked_at=revoked_at,
        )
        return created, True


__all__ = [
    "ImportCampaignRevocationConflict",
    "ImportCampaignRevocationImpact",
    "ImportCampaignRevocationNotFound",
    "ImportCampaignRevocationPreview",
    "ImportCampaignRevocationRecord",
    "ImportCampaignRevocationRepository",
    "ImportCampaignRevocationService",
]
