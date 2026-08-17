"""Collection Run 预算/Provider 路由的 PostgreSQL 运行前准备。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from aima_ugc.modules.collection.execution import CollectionExecution
from aima_ugc.modules.collection.provider_routing import ProviderRegistry
from aima_ugc.modules.collection.run_budget import allocate_run_budget_envelopes
from aima_ugc.platform.jobs import JobExecutionFence, LeaseLostError

from .jobs import PostgresJobRepository
from .provider_budget_envelope import PostgresProviderBudgetEnvelopeProvisioner
from .system import PostgresProviderConfigRepository


class PostgresCollectionRunPreparer:
    """在首个 Scope 前按冻结 Run 快照建立 Provider Run 预算包络。"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        provider_registry: ProviderRegistry,
        max_verified_unit_price: Decimal,
    ) -> None:
        if not max_verified_unit_price.is_finite() or max_verified_unit_price <= 0:
            raise ValueError("max_verified_unit_price 必须为有限正数")
        self._session_factory = session_factory
        self._provider_registry = provider_registry
        self._max_verified_unit_price = max_verified_unit_price

    def prepare(
        self,
        *,
        execution: CollectionExecution,
        fence: JobExecutionFence,
    ) -> None:
        if execution.run.job_id != fence.job_id:
            raise LeaseLostError("Collection Run 不属于当前 Job Fence")

        request_budget, platform_configs = _parse_run_snapshot(execution.run.config_snapshot)
        provider_scope_weights: dict[UUID, int] = {}
        used_platforms: set[str] = set()
        for scope in execution.scopes:
            provider_config_id = platform_configs.get(scope.platform)
            if provider_config_id is None:
                raise ValueError(f"Run Snapshot 缺少 Scope 平台配置: {scope.platform}")
            provider_scope_weights[provider_config_id] = (
                provider_scope_weights.get(provider_config_id, 0) + 1
            )
            used_platforms.add(scope.platform)

        envelopes = allocate_run_budget_envelopes(
            total_request_budget=request_budget,
            provider_scope_weights=provider_scope_weights,
            max_verified_unit_price=self._max_verified_unit_price,
        )

        session = self._session_factory()
        try:
            with session.begin():
                PostgresJobRepository(session).lock_current_execution(fence)
                config_repository = PostgresProviderConfigRepository(session)
                for platform in sorted(used_platforms):
                    provider_config_id = platform_configs[platform]
                    config = config_repository.get(provider_config_id)
                    if config is None:
                        raise ValueError(f"Provider Config 不存在: {provider_config_id}")
                    self._provider_registry.resolve(config=config, platform=platform)

                observed_at = datetime.now(UTC)
                provisioner = PostgresProviderBudgetEnvelopeProvisioner(session)
                for provider_config_id, envelope in envelopes.items():
                    provisioner.ensure_run_envelope(
                        provider_config_id=provider_config_id,
                        run_id=execution.run.id,
                        envelope=envelope,
                        at=observed_at,
                    )
        finally:
            session.close()


def _parse_run_snapshot(snapshot: dict[str, object]) -> tuple[int, dict[str, UUID]]:
    if snapshot.get("schema_version") != "collection-run-config.v1":
        raise ValueError("Collection Run Snapshot schema_version 不受支持")

    request_budget = snapshot.get("request_budget")
    if isinstance(request_budget, bool) or not isinstance(request_budget, int):
        raise ValueError("Collection Run Snapshot request_budget 必须为整数")
    if request_budget < 0:
        raise ValueError("Collection Run Snapshot request_budget 不能为负数")

    raw_platforms = snapshot.get("platforms")
    if not isinstance(raw_platforms, list):
        raise ValueError("Collection Run Snapshot platforms 必须为列表")

    platform_configs: dict[str, UUID] = {}
    for item in raw_platforms:
        if not isinstance(item, dict):
            raise ValueError("Collection Run Snapshot platform item 必须为 object")
        platform = item.get("platform")
        if not isinstance(platform, str) or not platform.strip():
            raise ValueError("Collection Run Snapshot platform 必须为非空字符串")
        normalized_platform = platform.strip()
        if normalized_platform in platform_configs:
            raise ValueError(f"Collection Run Snapshot 平台重复: {normalized_platform}")

        raw_provider_config_id = item.get("provider_config_id")
        try:
            provider_config_id = UUID(str(raw_provider_config_id))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Collection Run Snapshot provider_config_id 无效: {normalized_platform}"
            ) from exc

        config = item.get("config", {})
        if not isinstance(config, dict):
            raise ValueError(f"Collection Run Snapshot config 必须为 object: {normalized_platform}")
        platform_configs[normalized_platform] = provider_config_id

    return request_budget, platform_configs


__all__ = ["PostgresCollectionRunPreparer"]
