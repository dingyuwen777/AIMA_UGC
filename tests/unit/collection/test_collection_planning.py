from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest
from aima_ugc.modules.collection.planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    DuplicatePlanKeywordPackError,
    DuplicatePlanPlatformError,
    PlanPlatformDefinition,
    UnsafePlanConfigError,
    UnsupportedPlanTimezoneError,
)


class _RecordingPlanningRepository:
    def __init__(self) -> None:
        self.definitions: list[CollectionPlanDefinition] = []

    def create_plan(self, definition: CollectionPlanDefinition):
        self.definitions.append(definition)
        return cast(object, definition)


def _definition(
    *,
    timezone: str = "Asia/Shanghai",
    platforms: tuple[PlanPlatformDefinition, ...] | None = None,
    keyword_pack_ids: tuple[UUID, ...] | None = None,
) -> CollectionPlanDefinition:
    provider_config_id = uuid4()
    return CollectionPlanDefinition(
        name="爱玛舆情默认计划",
        enabled=True,
        schedule_expr="0 */6 * * *",
        timezone=timezone,
        schedule_version=1,
        misfire_policy="explicit-policy-not-yet-executed",
        max_catch_up_runs=0,
        detail_policy="on_change",
        comment_policy="adaptive",
        request_budget=100,
        created_by=None,
        platforms=platforms
        or (
            PlanPlatformDefinition(
                platform="xhs",
                provider_config_id=provider_config_id,
                config={"sort_mode": "latest", "time_filter": "one_day"},
            ),
        ),
        keyword_pack_ids=keyword_pack_ids or (uuid4(),),
    )


def test_service_accepts_only_first_release_timezone_and_preserves_explicit_policy() -> None:
    repository = _RecordingPlanningRepository()
    service = CollectionPlanningService(repository)

    created = service.create_plan(_definition())

    assert created.name == "爱玛舆情默认计划"
    assert repository.definitions[0].timezone == "Asia/Shanghai"
    assert repository.definitions[0].misfire_policy == "explicit-policy-not-yet-executed"

    with pytest.raises(UnsupportedPlanTimezoneError, match="Asia/Shanghai"):
        service.create_plan(_definition(timezone="UTC"))


def test_service_rejects_duplicate_platform_identity() -> None:
    provider_config_id = uuid4()
    duplicate_platforms = (
        PlanPlatformDefinition(platform="xhs", provider_config_id=provider_config_id, config={}),
        PlanPlatformDefinition(platform="xhs", provider_config_id=uuid4(), config={}),
    )

    with pytest.raises(DuplicatePlanPlatformError, match="platform"):
        CollectionPlanningService(_RecordingPlanningRepository()).create_plan(
            _definition(platforms=duplicate_platforms)
        )


def test_service_rejects_duplicate_keyword_pack_identity() -> None:
    pack_id = uuid4()

    with pytest.raises(DuplicatePlanKeywordPackError, match="keyword pack"):
        CollectionPlanningService(_RecordingPlanningRepository()).create_plan(
            _definition(keyword_pack_ids=(pack_id, pack_id))
        )


def test_plan_platform_config_rejects_secret_shaped_keys_recursively() -> None:
    with pytest.raises(UnsafePlanConfigError, match="Secret"):
        PlanPlatformDefinition(
            platform="xhs",
            provider_config_id=uuid4(),
            config={"search": {"access-token": "must-not-be-here"}},
        )


def test_definition_rejects_invalid_stable_numeric_and_text_fields() -> None:
    base = _definition()
    invalid_values = (
        {"name": ""},
        {"schedule_version": 0},
        {"misfire_policy": ""},
        {"max_catch_up_runs": -1},
        {"detail_policy": ""},
        {"comment_policy": ""},
        {"request_budget": -1},
    )

    for overrides in invalid_values:
        values = {
            "name": base.name,
            "enabled": base.enabled,
            "schedule_expr": base.schedule_expr,
            "timezone": base.timezone,
            "schedule_version": base.schedule_version,
            "misfire_policy": base.misfire_policy,
            "max_catch_up_runs": base.max_catch_up_runs,
            "detail_policy": base.detail_policy,
            "comment_policy": base.comment_policy,
            "request_budget": base.request_budget,
            "created_by": base.created_by,
            "platforms": base.platforms,
            "keyword_pack_ids": base.keyword_pack_ids,
        }
        values.update(overrides)
        with pytest.raises(ValueError):
            CollectionPlanDefinition(**values)
