"""Stage 3B Canonical V1 契约测试。"""

from importlib import import_module


def test_canonical_v1_contracts_are_available() -> None:
    canonical = import_module("aima_ugc.contracts.canonical")
    assert canonical.CanonicalContentV1.model_fields["schema_version"].default == "content.v1"
    assert canonical.CanonicalCommentV1.model_fields["schema_version"].default == "comment.v1"
    assert (
        canonical.CanonicalContentAggregateV1.model_fields["schema_version"].default
        == "content.aggregate.v1"
    )
