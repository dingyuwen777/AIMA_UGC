from __future__ import annotations

from aima_ugc.database_schema import metadata
from sqlalchemy import BigInteger


def test_canonical_replay_tables_have_owner_constraints_and_bigint_counters() -> None:
    requests = metadata.tables["canonical_replay_all_requests"]
    runs = metadata.tables["canonical_replay_runs"]
    inputs = metadata.tables["canonical_replay_run_artifacts"]
    seen = metadata.tables["canonical_replay_seen_content"]

    assert requests.info["owner"] == "ingestion"
    assert requests.c.planner_job_id.unique is True
    assert requests.c.accepted_before.nullable is False
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

    request_checks = {constraint.name for constraint in requests.constraints if constraint.name}
    run_checks = {constraint.name for constraint in runs.constraints if constraint.name}
    input_checks = {constraint.name for constraint in inputs.constraints if constraint.name}
    assert "ck_canonical_replay_all_requests_planning_status_allowed" in request_checks
    assert "ck_canonical_replay_runs_counters_nonnegative" in run_checks
    assert "ck_canonical_replay_runs_checkpoint_nonnegative" in run_checks
    assert "ck_canonical_replay_run_artifacts_ordinal_nonnegative" in input_checks
