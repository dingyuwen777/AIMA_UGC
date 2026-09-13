"""在正式 TikHub Scope 完成后 best-effort 预热小红书图片缓存。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.collection_run_executor import CollectionScopeExecutionResult
from aima_ugc.modules.collection.execution import CollectionRunRecord, CollectionScopeRecord
from aima_ugc.modules.collection.providers import ProviderTransport, RawArtifactService
from aima_ugc.modules.system.models import ProviderConfig
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.logging import log_exception_event
from aima_ugc.platform.storage import ArtifactService, ArtifactStore

from .collection_scope import TikHubCollectionScopeExecutor

logger = logging.getLogger(__name__)


class ContentMediaPrefetcher(Protocol):
    """Collection 装饰层需要的最小媒体预热边界。"""

    def prefetch_content(self, content_id: UUID) -> None: ...


class MediaCachingTikHubCollectionScopeExecutor(TikHubCollectionScopeExecutor):
    """保持原 Scope 状态机不变，只在辅助补采结束后追加非关键媒体预热。"""

    def __init__(
        self,
        *,
        media_prefetcher: ContentMediaPrefetcher,
        session_factory: Callable[[], Session],
        raw_artifacts: RawArtifactService,
        artifacts: ArtifactService,
        artifact_store: ArtifactStore,
        transport_factory: Callable[[ProviderConfig], ProviderTransport],
        secret_resolver: Callable[[str], SecretStr],
        observed_at: Callable[[], datetime] | None = None,
    ) -> None:
        """复用生产 Scope 依赖，并额外注入非关键媒体预热边界。"""

        super().__init__(
            session_factory=session_factory,
            raw_artifacts=raw_artifacts,
            artifacts=artifacts,
            artifact_store=artifact_store,
            transport_factory=transport_factory,
            secret_resolver=secret_resolver,
            observed_at=observed_at,
        )
        self._media_prefetcher = media_prefetcher

    def execute(
        self,
        *,
        run: CollectionRunRecord,
        scope: CollectionScopeRecord,
        context: JobExecutionContextProtocol,
    ) -> CollectionScopeExecutionResult:
        """先完整执行 Detail/Comments/SubComments，再尝试缓存当前小红书图片。"""

        result = super().execute(run=run, scope=scope, context=context)
        if (
            scope.platform == "xiaohongshu"
            and scope.source_type == "content"
            and scope.operation_group == "content_enrichment"
            and result.status in {"succeeded", "partial_success"}
        ):
            try:
                self._media_prefetcher.prefetch_content(UUID(scope.source_value))
            except (ValueError, RuntimeError, OSError) as exc:
                log_exception_event(
                    logger,
                    logging.WARNING,
                    "collection.media_cache_prefetch_failed",
                    "辅助补采已完成；图片缓存预热失败但不改变采集结果。",
                    exc,
                    run_id=str(run.id),
                    scope_id=str(scope.id),
                    platform=scope.platform,
                )
        return result


__all__ = ["ContentMediaPrefetcher", "MediaCachingTikHubCollectionScopeExecutor"]
