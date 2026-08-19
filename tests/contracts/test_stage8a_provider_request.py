"""Stage 8A Provider Request 双父级 Contract 回归测试。"""

from uuid import uuid4

import pytest
from aima_ugc.contracts.provider import ProviderRequestV1
from pydantic import ValidationError


def test_collection_request_constructor_remains_compatible() -> None:
    run_id = uuid4()
    scope_id = uuid4()
    request = ProviderRequestV1.create(
        request_id=uuid4(),
        run_id=run_id,
        scope_id=scope_id,
        provider="tikhub",
        platform="xhs",
        operation="search_notes",
        request_params={"keyword": "爱玛"},
        pagination_input={},
    )

    assert request.run_id == run_id
    assert request.scope_id == scope_id
    assert request.import_batch_id is None


def test_file_import_request_has_real_import_batch_parent() -> None:
    import_batch_id = uuid4()
    request = ProviderRequestV1.create_for_import(
        request_id=uuid4(),
        import_batch_id=import_batch_id,
        provider="imports",
        platform="xhs",
        operation="excel_import",
        request_params={"input_sha256": "a" * 64},
        pagination_input={},
    )

    assert request.run_id is None
    assert request.scope_id is None
    assert request.import_batch_id == import_batch_id


def test_provider_request_rejects_missing_parent() -> None:
    with pytest.raises(ValidationError, match="恰好一个"):
        ProviderRequestV1(
            request_id=uuid4(),
            run_id=None,
            scope_id=None,
            import_batch_id=None,
            provider="imports",
            platform="xhs",
            operation="excel_import",
            request_fingerprint="a" * 64,
            request_params={},
            pagination_input={},
        )


def test_provider_request_rejects_collection_and_import_parents_together() -> None:
    with pytest.raises(ValidationError, match="恰好一个"):
        ProviderRequestV1(
            request_id=uuid4(),
            run_id=uuid4(),
            scope_id=uuid4(),
            import_batch_id=uuid4(),
            provider="imports",
            platform="xhs",
            operation="excel_import",
            request_fingerprint="a" * 64,
            request_params={},
            pagination_input={},
        )
