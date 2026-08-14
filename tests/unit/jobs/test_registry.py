from typing import Literal

import pytest
from pydantic import BaseModel

from aima_ugc.platform.jobs.registry import JobRegistry


class EchoPayloadV1(BaseModel):
    schema_version: Literal["echo.v1"] = "echo.v1"
    value: str


def _handler(payload: BaseModel, context: object) -> object:
    return payload, context


def test_registry_validates_versioned_payload_and_exposes_supported_types() -> None:
    registry = JobRegistry()
    registry.register(
        job_type="test.echo.v1",
        payload_version="echo.v1",
        payload_model=EchoPayloadV1,
        handler=_handler,
        retry_on_timeout=True,
    )

    payload = registry.validate_payload(
        job_type="test.echo.v1",
        payload_version="echo.v1",
        payload={"schema_version": "echo.v1", "value": "ok"},
    )

    assert isinstance(payload, EchoPayloadV1)
    assert payload.value == "ok"
    assert registry.supported_types == ("test.echo.v1",)


def test_registry_rejects_duplicate_job_type() -> None:
    registry = JobRegistry()
    registry.register(
        job_type="test.echo.v1",
        payload_version="echo.v1",
        payload_model=EchoPayloadV1,
        handler=_handler,
        retry_on_timeout=True,
    )

    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            job_type="test.echo.v1",
            payload_version="echo.v1",
            payload_model=EchoPayloadV1,
            handler=_handler,
            retry_on_timeout=True,
        )


def test_registry_rejects_unknown_type_and_payload_version_mismatch() -> None:
    registry = JobRegistry()
    registry.register(
        job_type="test.echo.v1",
        payload_version="echo.v1",
        payload_model=EchoPayloadV1,
        handler=_handler,
        retry_on_timeout=True,
    )

    with pytest.raises(KeyError, match="not registered"):
        registry.validate_payload(
            job_type="test.unknown.v1",
            payload_version="unknown.v1",
            payload={},
        )

    with pytest.raises(ValueError, match="payload version"):
        registry.validate_payload(
            job_type="test.echo.v1",
            payload_version="echo.v2",
            payload={"schema_version": "echo.v1", "value": "ok"},
        )
