"""Stage 1 品牌/车型过滤 PostgreSQL Schema 不变量。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from sqlalchemy import inspect, text
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import IntegrityError


def _foreign_key_targets(inspector: Inspector, table_name: str) -> dict[tuple[str, ...], str]:
    """把 Inspector 的外键结果压缩为“列 → 目标表”映射，便于断言关键 Schema 边界。"""

    return {
        tuple(item["constrained_columns"]): item["referred_table"]
        for item in inspector.get_foreign_keys(table_name)
    }


def test_brand_vehicle_foundation_schema_matches_stage1_contract() -> None:
    """验证品牌目录、可空车型品牌归属、证据/锁及查询索引均已落到 PostgreSQL。"""

    runtime = DatabaseRuntime(load_settings())
    try:
        inspector = inspect(runtime.engine)
        tables = set(inspector.get_table_names())
        assert {
            "vehicle_brands",
            "vehicle_brand_aliases",
            "content_brand_evidence",
            "content_brand_review_locks",
        } <= tables

        brand_columns = {item["name"]: item for item in inspector.get_columns("vehicle_brands")}
        assert set(brand_columns) == {
            "id",
            "code",
            "display_name",
            "role",
            "status",
            "version",
            "catalog_version",
            "created_at",
            "updated_at",
        }
        brand_checks = {item["name"] for item in inspector.get_check_constraints("vehicle_brands")}
        assert {
            "ck_vehicle_brands_role_allowed",
            "ck_vehicle_brands_status_allowed",
            "ck_vehicle_brands_version_positive",
        } <= brand_checks
        assert _foreign_key_targets(inspector, "vehicle_brands")[("catalog_version",)] == (
            "vehicle_catalog_versions"
        )

        alias_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("vehicle_brand_aliases")
        }
        assert ("brand_id", "normalized_text") in alias_uniques

        model_columns = {item["name"]: item for item in inspector.get_columns("vehicle_models")}
        assert model_columns["brand_id"]["nullable"] is True
        assert _foreign_key_targets(inspector, "vehicle_models")[("brand_id",)] == "vehicle_brands"
        model_indexes = {item["name"]: item for item in inspector.get_indexes("vehicle_models")}
        assert model_indexes["ix_vehicle_models_brand_id_status"]["column_names"] == [
            "brand_id",
            "status",
        ]

        evidence_foreign_keys = _foreign_key_targets(inspector, "content_brand_evidence")
        assert evidence_foreign_keys[("content_id",)] == "contents"
        assert evidence_foreign_keys[("brand_id",)] == "vehicle_brands"
        assert evidence_foreign_keys[("derived_vehicle_model_id",)] == "vehicle_models"
        assert evidence_foreign_keys[("catalog_version",)] == "vehicle_catalog_versions"

        evidence_checks = {
            item["name"] for item in inspector.get_check_constraints("content_brand_evidence")
        }
        assert {
            "ck_content_brand_evidence_source_allowed",
            "ck_content_brand_evidence_derived_vehicle_model_consistent",
            "ck_content_brand_evidence_confidence_range",
        } <= evidence_checks

        evidence_indexes = {
            item["name"]: item for item in inspector.get_indexes("content_brand_evidence")
        }
        assert evidence_indexes["uq_content_brand_evidence_direct_identity"]["unique"] is True
        assert evidence_indexes["uq_content_brand_evidence_vehicle_identity"]["unique"] is True
        assert "ix_content_brand_evidence_active_content" in evidence_indexes
        assert "ix_content_brand_evidence_active_brand" in evidence_indexes

        lock_pk = inspector.get_pk_constraint("content_brand_review_locks")
        assert lock_pk["constrained_columns"] == ["content_id", "content_version"]
        assert _foreign_key_targets(inspector, "content_brand_review_locks")[("content_id",)] == (
            "contents"
        )
    finally:
        runtime.dispose()


def test_brand_alias_and_evidence_identity_use_postgresql_null_semantics() -> None:
    """用真实 PostgreSQL 证明别名局部唯一，以及两类 Evidence 在 NULL 下仍可幂等。"""

    runtime = DatabaseRuntime(load_settings())
    connection = runtime.engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
        brand_id = uuid4()
        other_brand_id = uuid4()
        model_id = uuid4()
        content_id = uuid4()

        for current_brand_id, code, role in (
            (brand_id, f"stage1-owned-{uuid4().hex}", "owned"),
            (other_brand_id, f"stage1-competitor-{uuid4().hex}", "competitor"),
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO vehicle_brands(
                      id, code, display_name, role, status, version,
                      catalog_version, created_at, updated_at
                    ) VALUES (
                      :id, :code, :code, :role, 'active', 1,
                      1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": current_brand_id, "code": code, "role": role},
            )

        normalized_alias = f"共享别名-{uuid4().hex}"
        for current_brand_id in (brand_id, other_brand_id):
            connection.execute(
                text(
                    """
                    INSERT INTO vehicle_brand_aliases(
                      id, brand_id, text, normalized_text, created_at
                    ) VALUES (
                      :id, :brand_id, :alias, :alias, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": uuid4(), "brand_id": current_brand_id, "alias": normalized_alias},
            )

        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    """
                    INSERT INTO vehicle_brand_aliases(
                      id, brand_id, text, normalized_text, created_at
                    ) VALUES (
                      :id, :brand_id, :alias, :alias, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": uuid4(), "brand_id": brand_id, "alias": normalized_alias},
            )

        connection.execute(
            text(
                """
                INSERT INTO vehicle_models(
                  id, code, display_name, brand_id, status, version,
                  catalog_version, created_at, updated_at
                ) VALUES (
                  :id, :code, :code, :brand_id, 'active', 1,
                  1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": model_id,
                "code": f"stage1-model-{uuid4().hex}",
                "brand_id": brand_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO vehicle_models(
                  id, code, display_name, brand_id, status, version,
                  catalog_version, created_at, updated_at
                ) VALUES (
                  :id, :code, :code, NULL, 'active', 1,
                  1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"id": uuid4(), "code": f"stage1-unbranded-{uuid4().hex}"},
        )

        direct_id = uuid4()
        connection.execute(
            text(
                """
                INSERT INTO content_brand_evidence(
                  id, content_id, content_version, brand_id, source,
                  catalog_version, created_at
                ) VALUES (
                  :id, :content_id, 1, :brand_id, 'alias_match',
                  1, CURRENT_TIMESTAMP
                )
                """
            ),
            {"id": direct_id, "content_id": content_id, "brand_id": brand_id},
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    """
                    INSERT INTO content_brand_evidence(
                      id, content_id, content_version, brand_id, source,
                      catalog_version, created_at
                    ) VALUES (
                      :id, :content_id, 1, :brand_id, 'alias_match',
                      1, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": uuid4(), "content_id": content_id, "brand_id": brand_id},
            )

        connection.execute(
            text(
                """
                INSERT INTO content_brand_evidence(
                  id, content_id, content_version, brand_id, source,
                  derived_vehicle_model_id, catalog_version, created_at
                ) VALUES (
                  :id, :content_id, 1, :brand_id, 'vehicle_match',
                  :model_id, 1, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": uuid4(),
                "content_id": content_id,
                "brand_id": brand_id,
                "model_id": model_id,
            },
        )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    """
                    INSERT INTO content_brand_evidence(
                      id, content_id, content_version, brand_id, source,
                      derived_vehicle_model_id, catalog_version, created_at
                    ) VALUES (
                      :id, :content_id, 1, :brand_id, 'vehicle_match',
                      :model_id, 1, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "content_id": content_id,
                    "brand_id": brand_id,
                    "model_id": model_id,
                },
            )

        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text(
                    """
                    INSERT INTO content_brand_evidence(
                      id, content_id, content_version, brand_id, source,
                      derived_vehicle_model_id, catalog_version, created_at
                    ) VALUES (
                      :id, :content_id, 1, :brand_id, 'alias_match',
                      :model_id, 1, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "content_id": uuid4(),
                    "brand_id": brand_id,
                    "model_id": model_id,
                },
            )
    finally:
        transaction.rollback()
        connection.close()
        runtime.dispose()
