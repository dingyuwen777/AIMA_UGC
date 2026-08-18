"""Stage 7 Collection Decision/Capability 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aima_ugc.contracts.collection import (
    CollectionDecisionRequestV1,
    CollectionDecisionV1,
    ContentObservationV1,
    ProviderOperationCapabilityV1,
    ProviderPlatformCapabilityV1,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]


def test_collection_contracts_are_versioned_and_keep_zero_distinct_from_unknown() -> None:
    assert (
        CollectionDecisionRequestV1.model_fields["schema_version"].default
        == "collection-decision-request.v1"
    )
    assert CollectionDecisionV1.model_fields["schema_version"].default == "collection-decision.v1"
    assert (
        ProviderPlatformCapabilityV1.model_fields["schema_version"].default
        == "provider-operations-capability.v1"
    )

    assert ContentObservationV1(comment_count=0).comment_count == 0
    assert ContentObservationV1(comment_count=None).comment_count is None
    with pytest.raises(ValidationError):
        ContentObservationV1(comment_count=-1)


def test_capability_rejects_provider_technical_state_as_extra_contract_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderOperationCapabilityV1(
            business_operation="keyword_search",
            provider_operations=("search_notes",),
            cursor="forbidden",
        )


def test_platform_capability_rejects_duplicate_business_operations() -> None:
    operation = ProviderOperationCapabilityV1(
        business_operation="keyword_search",
        provider_operations=("search_notes",),
    )
    with pytest.raises(ValidationError, match="重复"):
        ProviderPlatformCapabilityV1(
            provider="tikhub",
            platform="xhs",
            operations=(operation, operation),
        )


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("decision-request.v1.schema.json", CollectionDecisionRequestV1),
        ("decision.v1.schema.json", CollectionDecisionV1),
        ("provider-operations-capability.v1.schema.json", ProviderPlatformCapabilityV1),
    ],
)
def test_fixed_collection_schemas_match_pydantic_contract(filename: str, model: type) -> None:
    target = ROOT / "contracts" / "collection" / filename

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == model.model_json_schema()
