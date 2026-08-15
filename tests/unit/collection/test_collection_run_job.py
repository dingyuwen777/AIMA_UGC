"""正式 Collection Run Job Payload 契约测试。"""

import pytest
from aima_ugc.modules.collection.collection_run_job import CollectionRunJobPayload
from pydantic import ValidationError


def test_collection_run_job_payload_contains_only_stable_schema_identity() -> None:
    payload = CollectionRunJobPayload()

    assert payload.model_dump(mode="json") == {"schema_version": "collection.run.v1"}


def test_collection_run_job_payload_rejects_unconstrained_run_or_secret_fields() -> None:
    with pytest.raises(ValidationError):
        CollectionRunJobPayload.model_validate(
            {
                "schema_version": "collection.run.v1",
                "run_id": "019c0000-0000-7000-8000-000000000001",
            }
        )

    with pytest.raises(ValidationError):
        CollectionRunJobPayload.model_validate(
            {
                "schema_version": "collection.run.v1",
                "token": "must-not-be-here",
            }
        )
