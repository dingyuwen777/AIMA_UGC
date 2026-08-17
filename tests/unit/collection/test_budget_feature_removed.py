"""预算功能已从当前系统实现撤回，仅允许未来重新设计后接入。"""

from __future__ import annotations

import importlib.util
from dataclasses import fields

import aima_ugc.database_schema  # noqa: F401
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanRecord,
)
from aima_ugc.modules.collection.tables import collection_plans_table
from aima_ugc.platform.database.metadata import metadata


def test_collection_plan_no_longer_exposes_request_budget() -> None:
    definition_fields = {field.name for field in fields(CollectionPlanDefinition)}
    record_fields = {field.name for field in fields(CollectionPlanRecord)}

    assert "request_budget" not in definition_fields
    assert "request_budget" not in record_fields
    assert "request_budget" not in collection_plans_table.c


def test_runtime_schema_no_longer_registers_budget_ledger_tables() -> None:
    assert "provider_budget_accounts" not in metadata.tables
    assert "provider_budget_reservations" not in metadata.tables


def test_budget_runtime_modules_are_removed_instead_of_left_dormant() -> None:
    assert importlib.util.find_spec("aima_ugc.modules.collection.provider_budget") is None
    assert importlib.util.find_spec("aima_ugc.modules.collection.run_budget") is None
    assert (
        importlib.util.find_spec("aima_ugc.adapters.persistence.postgres.provider_budget") is None
    )
    assert (
        importlib.util.find_spec("aima_ugc.adapters.persistence.postgres.provider_budget_envelope")
        is None
    )
    assert (
        importlib.util.find_spec(
            "aima_ugc.adapters.persistence.postgres.collection_run_preparation"
        )
        is None
    )
