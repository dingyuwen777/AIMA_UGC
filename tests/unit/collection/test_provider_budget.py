"""Stage 7 Provider Budget 纯业务要求测试。"""

from decimal import Decimal
from uuid import uuid4

import pytest
from aima_ugc.modules.collection.provider_budget import (
    ProviderBudgetLineageError,
    build_attempt_budget_requirements,
    completed_budget_settlement_amount,
)


def _by_scope_dimension(requirements):
    return {(item.scope_type, item.dimension): (item.unit, item.amount) for item in requirements}


def test_regular_attempt_requires_global_and_run_for_both_dimensions() -> None:
    run_id = uuid4()

    requirements = build_attempt_budget_requirements(
        run_id=run_id,
        content_id=None,
        estimated_cost=Decimal("0.125000"),
        currency="USD",
    )

    assert _by_scope_dimension(requirements) == {
        ("global", "request_count"): ("request", Decimal("1")),
        ("global", "monetary_cost"): ("USD", Decimal("0.125000")),
        ("run", "request_count"): ("request", Decimal("1")),
        ("run", "monetary_cost"): ("USD", Decimal("0.125000")),
    }
    assert {item.run_id for item in requirements if item.scope_type == "run"} == {run_id}
    assert all(item.content_id is None for item in requirements)


def test_comment_attempt_requires_all_four_layers_for_both_dimensions() -> None:
    run_id = uuid4()
    content_id = uuid4()

    requirements = build_attempt_budget_requirements(
        run_id=run_id,
        content_id=content_id,
        estimated_cost=Decimal("0.010000"),
        currency="CNY",
    )

    assert _by_scope_dimension(requirements) == {
        ("global", "request_count"): ("request", Decimal("1")),
        ("global", "monetary_cost"): ("CNY", Decimal("0.010000")),
        ("run", "request_count"): ("request", Decimal("1")),
        ("run", "monetary_cost"): ("CNY", Decimal("0.010000")),
        ("run_comments", "request_count"): ("request", Decimal("1")),
        ("run_comments", "monetary_cost"): ("CNY", Decimal("0.010000")),
        ("content_comments", "request_count"): ("request", Decimal("1")),
        ("content_comments", "monetary_cost"): ("CNY", Decimal("0.010000")),
    }
    assert {item.run_id for item in requirements if item.scope_type in {"run", "run_comments"}} == {
        run_id
    }
    assert {item.content_id for item in requirements if item.scope_type == "content_comments"} == {
        content_id
    }


def test_budget_requirements_reject_invalid_money_inputs() -> None:
    with pytest.raises(ValueError, match="estimated_cost"):
        build_attempt_budget_requirements(
            run_id=uuid4(),
            content_id=None,
            estimated_cost=Decimal("-0.01"),
            currency="USD",
        )

    with pytest.raises(ValueError, match="currency"):
        build_attempt_budget_requirements(
            run_id=uuid4(),
            content_id=None,
            estimated_cost=Decimal("0.01"),
            currency="usd",
        )


def test_completed_estimated_money_settles_reserved_upper_bound_without_fake_actual() -> None:
    settled = completed_budget_settlement_amount(
        dimension="monetary_cost",
        reserved_amount=Decimal("0.010000"),
        billing_status="estimated",
        actual_cost=Decimal("0"),
        billing_currency="USD",
        account_unit="USD",
    )

    assert settled == Decimal("0.010000")


def test_completed_confirmed_money_can_settle_authoritative_actual_cost() -> None:
    settled = completed_budget_settlement_amount(
        dimension="monetary_cost",
        reserved_amount=Decimal("0.010000"),
        billing_status="confirmed",
        actual_cost=Decimal("0.020000"),
        billing_currency="USD",
        account_unit="USD",
    )

    assert settled == Decimal("0.020000")


def test_completed_estimated_money_rejects_nonzero_actual_cost() -> None:
    with pytest.raises(ProviderBudgetLineageError, match="estimated"):
        completed_budget_settlement_amount(
            dimension="monetary_cost",
            reserved_amount=Decimal("0.010000"),
            billing_status="estimated",
            actual_cost=Decimal("0.001000"),
            billing_currency="USD",
            account_unit="USD",
        )
