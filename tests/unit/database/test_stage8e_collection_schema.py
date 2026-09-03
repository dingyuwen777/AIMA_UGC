"""Stage 8E Batch → Collection Run 关联 Schema 契约。"""

from aima_ugc.modules.collection.tables import collection_runs_table
from sqlalchemy import CheckConstraint


def test_collection_run_has_compatible_batch_and_campaign_parents() -> None:
    assert collection_runs_table.info["owner"] == "collection"
    assert collection_runs_table.c.import_batch_id.nullable is True

    foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in collection_runs_table.c.import_batch_id.foreign_keys
    }
    assert foreign_keys == {"processing_import_batches.id"}

    index = next(
        item
        for item in collection_runs_table.indexes
        if item.name == "ix_collection_runs_import_batch_id_created_at"
    )
    assert tuple(column.name for column in index.columns) == (
        "import_batch_id",
        "created_at",
    )

    assert collection_runs_table.c.data_import_campaign_id.nullable is True
    campaign_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in collection_runs_table.c.data_import_campaign_id.foreign_keys
    }
    assert campaign_foreign_keys == {"historical_import_campaigns.id"}
    campaign_index = next(
        item
        for item in collection_runs_table.indexes
        if item.name == "ix_collection_runs_campaign_id_created_at"
    )
    assert tuple(column.name for column in campaign_index.columns) == (
        "data_import_campaign_id",
        "created_at",
    )
    checks = {
        item.name: str(item.sqltext)
        for item in collection_runs_table.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "ck_collection_runs_import_source_at_most_one" in checks
    assert "data_import_campaign_id" in checks["ck_collection_runs_import_source_at_most_one"]
