"""产品配置资源生命周期 PostgreSQL 集成测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aima_ugc.adapters.persistence.postgres.analysis_scheme_lifecycle import (
    PostgresAnalysisSchemeLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_plan_lifecycle import (
    PostgresCollectionPlanLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.collection_planning import (
    PostgresCollectionPlanningRepository,
)
from aima_ugc.adapters.persistence.postgres.keyword_lifecycle import (
    PostgresKeywordPackLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.provider_lifecycle import (
    PostgresProviderConfigLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.collection.planning import CollectionPlanDefinition, PlanPlatformDefinition
from aima_ugc.modules.system.models import KeywordPack, ProviderConfig
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.time import beijing_now


def _analysis_definition() -> AnalysisSchemeDefinitionRequest:
    return AnalysisSchemeDefinitionRequest(
        prompt_template="分析内容。\n{{AIMA_TAXONOMY_JSON}}\n仅输出 JSON。",
        sentiments=("正面", "负面", "无法判断"),
        voice_types=("用户发声", "营销内容", "无法判断"),
        labels={"产品体验": ("质量",), "无法分类": ("无法判断",)},
    )


def test_keyword_pack_archive_exits_current_catalog_and_restore_stays_disabled() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    pack_id = uuid4()
    try:
        with session.begin():
            catalog = PostgresKeywordCatalogRepository(session)
            catalog.create_pack(
                KeywordPack(
                    id=pack_id,
                    name=f"生命周期词包-{pack_id}",
                    description="",
                    enabled=False,
                    version=1,
                )
            )
            lifecycle = PostgresKeywordPackLifecycleRepository(session)
            archived = lifecycle.archive(pack_id, archived_at=beijing_now())
            assert archived is not None
            assert archived.enabled is False
            assert catalog.get_pack(pack_id) is None
            assert [item.id for item in lifecycle.list_archived()] == [pack_id]

        with session.begin():
            restored = PostgresKeywordPackLifecycleRepository(session).restore(pack_id)
            assert restored is not None
            assert restored.enabled is False
            assert PostgresKeywordCatalogRepository(session).get_pack(pack_id) is not None
    finally:
        with session.begin():
            session.execute(
                __import__("sqlalchemy").delete(
                    __import__(
                        "aima_ugc.modules.system.tables",
                        fromlist=["keyword_packs_table"],
                    ).keyword_packs_table
                ).where(
                    __import__(
                        "aima_ugc.modules.system.tables",
                        fromlist=["keyword_packs_table"],
                    ).keyword_packs_table.c.id
                    == pack_id
                )
            )
        session.close()
        runtime.dispose()


def test_archived_collection_plan_is_not_schedulable_and_restores_disabled() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    provider_id = uuid4()
    plan_id = None
    try:
        with session.begin():
            PostgresProviderConfigRepository(session).create(
                ProviderConfig(
                    id=provider_id,
                    provider="tikhub",
                    display_name=f"生命周期 Provider-{provider_id}",
                    base_url="https://api.tikhub.io",
                    secret_ref=f"providers/{provider_id}/test.key",
                    enabled=True,
                )
            )
            planning = PostgresCollectionPlanningRepository(session)
            created = planning.create_plan(
                CollectionPlanDefinition(
                    name=f"生命周期计划-{provider_id}",
                    enabled=True,
                    schedule_expr="0 * * * *",
                    timezone="Asia/Shanghai",
                    schedule_version=1,
                    misfire_policy="latest_only",
                    max_catch_up_runs=0,
                    detail_policy="on_change",
                    comment_policy="adaptive",
                    created_by=None,
                    platforms=(
                        PlanPlatformDefinition(
                            platform="xiaohongshu",
                            provider_config_id=provider_id,
                            config={},
                        ),
                    ),
                    keyword_pack_ids=(),
                    vehicle_model_ids=(uuid4(),),
                )
            )
            plan_id = created.id
            assert plan_id in planning.list_schedulable_plan_ids(
                now=datetime(2026, 9, 7, tzinfo=UTC)
            )
            assert PostgresCollectionPlanLifecycleRepository(session).archive(
                plan_id,
                archived_at=beijing_now(),
            )
            assert planning.get_plan(plan_id) is None
            assert plan_id not in planning.list_schedulable_plan_ids(
                now=datetime(2026, 9, 7, tzinfo=UTC)
            )

        with session.begin():
            assert PostgresCollectionPlanLifecycleRepository(session).restore(plan_id)
            restored = PostgresCollectionPlanningRepository(session).get_plan(plan_id)
            assert restored is not None
            assert restored.enabled is False
    finally:
        if plan_id is not None:
            from aima_ugc.modules.collection.corrective_tables import (
                collection_plan_decision_policies_table,
            )
            from aima_ugc.modules.collection.tables import (
                collection_plan_platforms_table,
                collection_plan_vehicle_models_table,
                collection_plans_table,
            )
            from sqlalchemy import delete

            with session.begin():
                session.execute(
                    delete(collection_plan_platforms_table).where(
                        collection_plan_platforms_table.c.plan_id == plan_id
                    )
                )
                session.execute(
                    delete(collection_plan_vehicle_models_table).where(
                        collection_plan_vehicle_models_table.c.plan_id == plan_id
                    )
                )
                session.execute(
                    delete(collection_plan_decision_policies_table).where(
                        collection_plan_decision_policies_table.c.plan_id == plan_id
                    )
                )
                session.execute(
                    delete(collection_plans_table).where(collection_plans_table.c.id == plan_id)
                )
                session.execute(
                    __import__("sqlalchemy").delete(
                        __import__(
                            "aima_ugc.modules.system.tables",
                            fromlist=["provider_configs_table"],
                        ).provider_configs_table
                    ).where(
                        __import__(
                            "aima_ugc.modules.system.tables",
                            fromlist=["provider_configs_table"],
                        ).provider_configs_table.c.id
                        == provider_id
                    )
                )
        session.close()
        runtime.dispose()


def test_unused_provider_can_archive_and_delete_but_disappears_from_current_directory() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    provider_id = uuid4()
    try:
        with session.begin():
            current = PostgresProviderConfigRepository(session)
            current.create(
                ProviderConfig(
                    id=provider_id,
                    provider="tikhub",
                    display_name=f"待删除 Provider-{provider_id}",
                    base_url="https://api.tikhub.io",
                    secret_ref=f"providers/{provider_id}/test.key",
                    enabled=False,
                )
            )
            lifecycle = PostgresProviderConfigLifecycleRepository(session)
            archived = lifecycle.archive(provider_id, archived_at=beijing_now())
            assert archived is not None
            assert current.get(provider_id) is None
            assert current.get(provider_id, include_archived=True) is not None
            assert lifecycle.delete_blockers(provider_id) == ()
            assert lifecycle.delete_archived(provider_id) is True
            assert current.get(provider_id, include_archived=True) is None
    finally:
        session.close()
        runtime.dispose()


def test_published_analysis_scheme_can_archive_after_switch_but_cannot_hard_delete() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    first_scheme_id = None
    second_scheme_id = None
    try:
        with session.begin():
            schemes = PostgresAnalysisSchemeRepository(session)
            first = schemes.create_draft(
                name=f"已发布方案-{uuid4()}",
                description="first",
                definition=_analysis_definition(),
                actor_ref="integration-test",
            )
            first_scheme_id = first.scheme_id
            schemes.activate_version(first.id, expected_version=first.version)
            second = schemes.create_draft(
                name=f"替代方案-{uuid4()}",
                description="second",
                definition=_analysis_definition(),
                actor_ref="integration-test",
            )
            second_scheme_id = second.scheme_id
            schemes.activate_version(second.id, expected_version=second.version)

            lifecycle = PostgresAnalysisSchemeLifecycleRepository(session)
            assert lifecycle.archive_blockers(first_scheme_id) == ()
            assert lifecycle.archive(first_scheme_id, archived_at=beijing_now()) is True
            assert all(
                scheme["id"] != first_scheme_id
                for scheme, _ in schemes.list_schemes()
            )
            blockers = lifecycle.delete_blockers(first_scheme_id)
            assert "该分析方案已有发布历史，只允许归档" in blockers
            assert lifecycle.delete_archived(first_scheme_id) is False if not blockers else True
    finally:
        from aima_ugc.modules.analysis.scheme_tables import (
            analysis_scheme_versions_table,
            analysis_schemes_table,
        )
        from sqlalchemy import delete, update

        with session.begin():
            if second_scheme_id is not None:
                session.execute(
                    update(analysis_schemes_table)
                    .where(analysis_schemes_table.c.id == second_scheme_id)
                    .values(active_version_id=None, is_active=False)
                )
            if first_scheme_id is not None:
                session.execute(
                    update(analysis_schemes_table)
                    .where(analysis_schemes_table.c.id == first_scheme_id)
                    .values(active_version_id=None, is_active=False)
                )
            for scheme_id in (first_scheme_id, second_scheme_id):
                if scheme_id is None:
                    continue
                session.execute(
                    delete(analysis_scheme_versions_table).where(
                        analysis_scheme_versions_table.c.scheme_id == scheme_id
                    )
                )
                session.execute(
                    delete(analysis_schemes_table).where(analysis_schemes_table.c.id == scheme_id)
                )
        session.close()
        runtime.dispose()
