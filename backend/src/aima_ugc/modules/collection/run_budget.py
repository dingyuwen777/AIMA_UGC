"""Run 总请求预算到 Provider Config 技术包络的确定性分配。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RunProviderBudgetEnvelope:
    """一个 Provider Config 在当前 Run 内的最坏请求/金额上界。"""

    provider_config_id: UUID
    request_limit: int
    monetary_limit: Decimal


def allocate_run_budget_envelopes(
    *,
    total_request_budget: int,
    provider_scope_weights: dict[UUID, int],
    max_verified_unit_price: Decimal,
) -> dict[UUID, RunProviderBudgetEnvelope]:
    """按冻结 Scope 权重分配总请求预算，余数按 Provider Config ID 稳定分配。"""
    if total_request_budget < 0:
        raise ValueError("total request budget 不能为负数")
    if max_verified_unit_price <= 0:
        raise ValueError("max verified unit price 必须大于 0")

    active = {
        provider_config_id: weight
        for provider_config_id, weight in provider_scope_weights.items()
        if weight > 0
    }
    if not active:
        return {}

    total_weight = sum(active.values())
    base_allocations: dict[UUID, int] = {
        provider_config_id: (total_request_budget * weight) // total_weight
        for provider_config_id, weight in active.items()
    }
    remaining = total_request_budget - sum(base_allocations.values())
    ordered = sorted(active, key=str)
    for provider_config_id in ordered[:remaining]:
        base_allocations[provider_config_id] += 1

    return {
        provider_config_id: RunProviderBudgetEnvelope(
            provider_config_id=provider_config_id,
            request_limit=request_limit,
            monetary_limit=max_verified_unit_price * request_limit,
        )
        for provider_config_id, request_limit in base_allocations.items()
    }


__all__ = ["RunProviderBudgetEnvelope", "allocate_run_budget_envelopes"]
