"""Canonical V1 来源追溯结构。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from .base import CanonicalBaseModel, Identifier

ProviderName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]


class CanonicalSourceV1(CanonicalBaseModel):
    """描述一条 Canonical Observation 的采集来源。"""

    schema_version: Literal["source.v1"] = "source.v1"
    provider_name: ProviderName
    operation: str | None = None
    provider_request_id: Identifier | None = None
    provider_attempt_id: Identifier | None = None
    raw_artifact_id: UUID | None = None
    source_type: str | None = None
    source_value: str | None = None
    item_locator: str | None = None
    observed_at: AwareDatetime
