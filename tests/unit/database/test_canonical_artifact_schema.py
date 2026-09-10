from aima_ugc.platform.storage.tables import canonical_artifact_links_table


def test_canonical_artifact_link_schema_has_one_owner_and_strong_parent_constraints() -> None:
    assert canonical_artifact_links_table.info["owner"] == "platform"
    assert canonical_artifact_links_table.primary_key.columns.keys() == ["artifact_id"]

    foreign_keys = {
        column.name: foreign_key.target_fullname
        for column in canonical_artifact_links_table.columns
        for foreign_key in column.foreign_keys
    }
    assert foreign_keys == {
        "artifact_id": "artifacts.id",
        "processing_import_batch_id": "processing_import_batches.id",
        "historical_import_campaign_item_id": "historical_import_campaign_items.id",
        "collection_scope_id": "collection_scopes.id",
        "provider_attempt_id": "provider_request_attempts.id",
    }
    check_sql = " ".join(
        str(constraint.sqltext)
        for constraint in canonical_artifact_links_table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "num_nonnulls" in check_sql
    assert "= 1" in check_sql
    indexes = {index.name: index for index in canonical_artifact_links_table.indexes}
    assert set(indexes) == {
        "ix_canonical_artifact_links_processing_import_batch_id",
        "ix_canonical_artifact_links_historical_import_campaign_item_id",
        "ix_canonical_artifact_links_collection_scope_id",
        "ix_canonical_artifact_links_provider_attempt_id",
        "uq_canonical_artifact_links_processing_import_batch_id",
        "uq_canonical_artifact_links_historical_import_campaign_item_id",
    }
    assert indexes["uq_canonical_artifact_links_processing_import_batch_id"].unique is True
    assert indexes["uq_canonical_artifact_links_historical_import_campaign_item_id"].unique is True
