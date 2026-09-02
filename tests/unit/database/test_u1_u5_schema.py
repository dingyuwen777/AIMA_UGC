"""U1—U5 新表 Owner 与关键约束。"""

from aima_ugc.database_schema import metadata


def test_u1_u5_tables_are_registered_with_single_owner() -> None:
    """新领域表必须进入唯一 MetaData，并声明单一写 Owner。"""

    expected = {
        "vehicle_catalog_versions": "vehicles",
        "vehicle_models": "vehicles",
        "vehicle_model_aliases": "vehicles",
        "keyword_pack_vehicle_models": "vehicles",
        "content_vehicle_evidence": "vehicles",
        "content_vehicle_review_locks": "vehicles",
        "analysis_schemes": "analysis",
        "analysis_scheme_versions": "analysis",
        "analysis_content_manual_overrides": "analysis",
        "content_availability_observations": "content",
        "notification_events": "notification",
        "notification_inbox_items": "notification",
    }

    for table_name, owner in expected.items():
        assert table_name in metadata.tables
        assert metadata.tables[table_name].info["owner"] == owner


def test_vehicle_alias_and_content_evidence_constraints_exist() -> None:
    """别名与内容证据必须由数据库唯一约束承担幂等身份。"""

    alias = metadata.tables["vehicle_model_aliases"]
    evidence = metadata.tables["content_vehicle_evidence"]
    alias_uniques = {constraint.name for constraint in alias.constraints}
    evidence_uniques = {constraint.name for constraint in evidence.constraints}

    assert "uq_vehicle_model_aliases_vehicle_model_id_normalized_text" in alias_uniques
    assert "uq_content_vehicle_evidence_identity" in evidence_uniques


def test_u1_u5_query_indexes_are_registered_in_metadata() -> None:
    """迁移创建的查询索引也必须进入 MetaData，避免 Alembic 误判为待删除。"""

    evidence = metadata.tables["content_vehicle_evidence"]
    inbox = metadata.tables["notification_inbox_items"]

    assert "ix_content_vehicle_evidence_active_vehicle" in {
        index.name for index in evidence.indexes
    }
    assert "ix_notification_inbox_principal_created" in {index.name for index in inbox.indexes}


def test_confirmed_unavailable_requires_linked_provider_evidence_constraint() -> None:
    """数据库必须阻止只有字符串声明、却没有 Attempt/Raw 指针的 confirmed 状态。"""

    availability = metadata.tables["content_availability_observations"]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in availability.constraints
        if hasattr(constraint, "sqltext")
    }
    expression = checks["ck_content_availability_observations_confirmed_evidence"]

    assert "provider_attempt_id is not null" in expression
    assert "raw_artifact_id is not null" in expression

    assert "ck_content_availability_observations_technical_status" in checks
    assert all(len(name) <= 63 for name in checks)
