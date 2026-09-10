from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
)


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
