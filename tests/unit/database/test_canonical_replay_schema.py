from __future__ import annotations

from aima_ugc.database_schema import metadata
from sqlalchemy import BigInteger


def test_canonical_replay_tables_have_owner_constraints_and_bigint_counters() -> None:
    runs = metadata.tables["canonical_replay_runs"]
    inputs = metadata.tables["canonical_replay_run_artifacts"]
    seen = metadata.tables["canonical_replay_seen_content"]

    assert runs.info["owner"] == "ingestion"
    assert inputs.info["owner"] == "ingestion"
    assert seen.info["owner"] == "ingestion"
    assert runs.c.job_id.unique is True
    assert runs.c.client_idempotency_key.unique is True
    assert inputs.primary_key.columns.keys() == ["run_id", "ordinal"]
    assert seen.primary_key.columns.keys() == [
        "run_id",
        "platform",
        "external_content_id",
    ]
    assert isinstance(runs.c.rows_seen.type, BigInteger)
    assert isinstance(runs.c.checkpoint_row_number.type, BigInteger)

    run_checks = {constraint.name for constraint in runs.constraints if constraint.name}
    input_checks = {constraint.name for constraint in inputs.constraints if constraint.name}
    assert "ck_canonical_replay_runs_counters_nonnegative" in run_checks
    assert "ck_canonical_replay_runs_checkpoint_nonnegative" in run_checks
    assert "ck_canonical_replay_run_artifacts_ordinal_nonnegative" in input_checks
