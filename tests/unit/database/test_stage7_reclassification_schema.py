from aima_ugc.modules.vehicles.tables import content_reclassification_runs_table


def test_content_reclassification_run_keeps_frozen_scope_and_checkpoint() -> None:
    assert content_reclassification_runs_table.info["owner"] == "vehicles"
    assert set(content_reclassification_runs_table.c.keys()) == {
        "id",
        "job_id",
        "catalog_snapshot",
        "shard_index",
        "shard_count",
        "start_after_content_id",
        "end_at_content_id",
        "checkpoint_content_id",
        "batch_size",
        "max_contents",
        "processed_count",
        "matched_count",
        "unmatched_count",
        "brand_evidence_count",
        "vehicle_evidence_count",
        "conflict_count",
        "brand_locked_count",
        "vehicle_locked_count",
        "created_by",
        "created_at",
        "updated_at",
    }
    assert content_reclassification_runs_table.c.job_id.unique is True
    assert content_reclassification_runs_table.c.catalog_snapshot.nullable is False
    targets = {key.target_fullname for key in content_reclassification_runs_table.foreign_keys}
    assert targets == {"jobs.id"}
