from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
)
from aima_ugc.modules.system.tables import global_relevance_config_table


def test_global_relevance_config_is_a_single_system_owned_keyword_pack_reference() -> None:
    assert global_relevance_config_table.info["owner"] == "system"
    assert set(global_relevance_config_table.c.keys()) == {
        "singleton_key",
        "keyword_pack_id",
        "version",
        "created_at",
        "updated_at",
    }
    assert global_relevance_config_table.c.singleton_key.primary_key is True
    assert global_relevance_config_table.c.keyword_pack_id.nullable is False
    assert {key.target_fullname for key in global_relevance_config_table.foreign_keys} == {
        "keyword_packs.id"
    }


def test_candidate_ingestion_schema_accepts_filtered_without_a_content_target() -> None:
    checks = {
        str(constraint.name): str(constraint.sqltext)
        for constraint in collection_candidate_ingestions_table.constraints
        if hasattr(constraint, "sqltext")
    }
    result_allowed = next(
        value for name, value in checks.items() if name.endswith("result_allowed")
    )
    success_target = next(
        value for name, value in checks.items() if name.endswith("success_target_required")
    )

    assert "filtered" in result_allowed
    assert "filtered" not in success_target
