"""Data Import Campaign 撤销领域语义测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from aima_ugc.modules.ingestion.revocation import (
    ImportCampaignRevocationConflict,
    ImportCampaignRevocationImpact,
    ImportCampaignRevocationNotFound,
    ImportCampaignRevocationRecord,
    ImportCampaignRevocationService,
)

_BEIJING = ZoneInfo("Asia/Shanghai")
_NOW = datetime(2026, 9, 7, 9, 0, tzinfo=_BEIJING)


@dataclass
class _FakeRepository:
    """只记录撤销状态机所需的最小持久化行为。"""

    status: str | None
    impact: ImportCampaignRevocationImpact
    existing: ImportCampaignRevocationRecord | None = None
    lock_requested: bool = False
    create_count: int = 0

    def get_campaign_status(self, campaign_id: UUID, *, for_update: bool) -> str | None:
        """返回固定 Campaign 状态并记录是否请求父记录锁。"""

        del campaign_id
        self.lock_requested = self.lock_requested or for_update
        return self.status

    def get_revocation(self, campaign_id: UUID) -> ImportCampaignRevocationRecord | None:
        """返回固定的既有撤销事实。"""

        del campaign_id
        return self.existing

    def calculate_impact(self, campaign_id: UUID) -> ImportCampaignRevocationImpact:
        """返回固定影响，用于验证领域服务是否在正确状态下计算。"""

        del campaign_id
        return self.impact

    def create_revocation(
        self,
        *,
        campaign_id: UUID,
        actor_ref: str,
        request_id: str | None,
        reason: str | None,
        impact: ImportCampaignRevocationImpact,
        revoked_at: datetime,
    ) -> ImportCampaignRevocationRecord:
        """创建一条内存撤销事实并记录调用次数。"""

        self.create_count += 1
        self.existing = ImportCampaignRevocationRecord(
            campaign_id=campaign_id,
            actor_ref=actor_ref,
            request_id=request_id,
            reason=reason,
            impact=impact,
            revoked_at=revoked_at,
        )
        return self.existing


def test_preview_rejects_missing_campaign() -> None:
    """不存在的 Campaign 不能被伪装成可撤销。"""

    repository = _FakeRepository(status=None, impact=ImportCampaignRevocationImpact(0, 0, 0))
    with pytest.raises(ImportCampaignRevocationNotFound):
        ImportCampaignRevocationService(repository).preview(uuid4())


def test_preview_does_not_calculate_running_campaign_impact() -> None:
    """运行中的 Campaign 影响会漂移，因此预览明确返回不可撤销。"""

    repository = _FakeRepository(
        status="running",
        impact=ImportCampaignRevocationImpact(5, 3, 2),
    )
    preview = ImportCampaignRevocationService(repository).preview(uuid4())

    assert preview.eligible is False
    assert preview.already_revoked is False
    assert preview.ineligible_reason == "campaign_not_completed"
    assert preview.impact == ImportCampaignRevocationImpact(0, 0, 0)


def test_preview_fails_closed_when_reversible_evidence_is_missing() -> None:
    """已完成 Campaign 只要存在缺失 Delta 的写入，也不能进入自动撤销。"""

    repository = _FakeRepository(
        status="succeeded",
        impact=ImportCampaignRevocationImpact(5, 3, 2, 1),
    )
    preview = ImportCampaignRevocationService(repository).preview(uuid4())

    assert preview.eligible is False
    assert preview.ineligible_reason == "reversible_evidence_missing"
    assert preview.impact.unreversible_content_count == 1

    with pytest.raises(ImportCampaignRevocationConflict):
        ImportCampaignRevocationService(repository).revoke(
            uuid4(),
            actor_ref="admin",
            request_id="request-unsafe",
            reason=None,
            revoked_at=_NOW,
        )
    assert repository.create_count == 0


def test_revoke_locks_campaign_and_persists_normalized_fact() -> None:
    """首次撤销锁定父 Campaign，并保存一次规范化撤销事实。"""

    campaign_id = uuid4()
    repository = _FakeRepository(
        status="partial_failed",
        impact=ImportCampaignRevocationImpact(7, 4, 3),
    )
    record, created = ImportCampaignRevocationService(repository).revoke(
        campaign_id,
        actor_ref=" admin ",
        request_id="request-1",
        reason=" 误导入 ",
        revoked_at=_NOW,
    )

    assert created is True
    assert repository.lock_requested is True
    assert repository.create_count == 1
    assert record.campaign_id == campaign_id
    assert record.actor_ref == "admin"
    assert record.reason == "误导入"
    assert record.impact == ImportCampaignRevocationImpact(7, 4, 3)


def test_revoke_is_idempotent_after_first_commit() -> None:
    """重复撤销返回原事实，不重新计算或创建第二条撤销记录。"""

    campaign_id = uuid4()
    existing = ImportCampaignRevocationRecord(
        campaign_id=campaign_id,
        actor_ref="admin",
        request_id="request-1",
        reason=None,
        impact=ImportCampaignRevocationImpact(2, 1, 1),
        revoked_at=_NOW,
    )
    repository = _FakeRepository(
        status="succeeded",
        impact=ImportCampaignRevocationImpact(99, 99, 0),
        existing=existing,
    )

    record, created = ImportCampaignRevocationService(repository).revoke(
        campaign_id,
        actor_ref="other-admin",
        request_id="request-2",
        reason="再次点击",
        revoked_at=_NOW,
    )

    assert created is False
    assert record == existing
    assert repository.create_count == 0


def test_revoke_rejects_non_terminal_campaign() -> None:
    """未进入成功或部分成功终态的 Campaign 不能执行撤销。"""

    repository = _FakeRepository(status="failed", impact=ImportCampaignRevocationImpact(0, 0, 0))
    with pytest.raises(ImportCampaignRevocationConflict):
        ImportCampaignRevocationService(repository).revoke(
            uuid4(),
            actor_ref="admin",
            request_id="request-1",
            reason=None,
            revoked_at=_NOW,
        )
