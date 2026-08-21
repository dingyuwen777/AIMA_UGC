"""Stage 8E Batch → Collection Run 关联 Schema 契约。"""

from aima_ugc.modules.collection.tables import collection_runs_table


def test_collection_run_has_optional_import_batch_parent() -> None:
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
