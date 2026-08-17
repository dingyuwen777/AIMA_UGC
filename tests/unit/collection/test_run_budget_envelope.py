"""Run 总请求预算到 Provider Config 技术包络的领域测试。"""

from decimal import Decimal
from uuid import UUID

from aima_ugc.modules.collection.run_budget import allocate_run_budget_envelopes

_A = UUID("00000000-0000-0000-0000-000000000a01")
_B = UUID("00000000-0000-0000-0000-000000000a02")
_C = UUID("00000000-0000-0000-0000-000000000a03")


def test_weighted_allocation_preserves_exact_run_request_budget() -> None:
    envelopes = allocate_run_budget_envelopes(
        total_request_budget=10,
        provider_scope_weights={_A: 3, _B: 1},
        max_verified_unit_price=Decimal("0.010"),
    )

    assert envelopes[_A].request_limit == 8
    assert envelopes[_B].request_limit == 2
    assert sum(item.request_limit for item in envelopes.values()) == 10
    assert envelopes[_A].monetary_limit == Decimal("0.080")
    assert envelopes[_B].monetary_limit == Decimal("0.020")


def test_remainder_is_deterministic_by_provider_config_id() -> None:
    envelopes = allocate_run_budget_envelopes(
        total_request_budget=5,
        provider_scope_weights={_C: 1, _A: 1, _B: 1},
        max_verified_unit_price=Decimal("0.010"),
    )

    assert envelopes[_A].request_limit == 2
    assert envelopes[_B].request_limit == 2
    assert envelopes[_C].request_limit == 1
    assert sum(item.request_limit for item in envelopes.values()) == 5


def test_zero_total_budget_keeps_all_provider_envelopes_closed() -> None:
    envelopes = allocate_run_budget_envelopes(
        total_request_budget=0,
        provider_scope_weights={_A: 2, _B: 1},
        max_verified_unit_price=Decimal("0.010"),
    )

    assert envelopes[_A].request_limit == 0
    assert envelopes[_B].request_limit == 0
    assert envelopes[_A].monetary_limit == Decimal("0.000")


def test_zero_weight_provider_is_not_allocated_and_invalid_price_is_rejected() -> None:
    envelopes = allocate_run_budget_envelopes(
        total_request_budget=4,
        provider_scope_weights={_A: 1, _B: 0},
        max_verified_unit_price=Decimal("0.010"),
    )
    assert set(envelopes) == {_A}

    try:
        allocate_run_budget_envelopes(
            total_request_budget=1,
            provider_scope_weights={_A: 1},
            max_verified_unit_price=Decimal("0"),
        )
    except ValueError as exc:
        assert "unit price" in str(exc)
    else:
        raise AssertionError("non-positive verified price must fail")
