"""Canonical V1 内容原子 Observation。"""

from typing import Literal

from pydantic import AwareDatetime, Field

from .author import CanonicalAuthorV1
from .base import CanonicalObservationModel, Identifier, PlatformName
from .metrics import CanonicalMetricsV1


class CanonicalContentV1(CanonicalObservationModel):
    schema_version: Literal["content.v1"] = "content.v1"
    platform: PlatformName
    external_content_id: Identifier
    alternate_ids: dict[str, Identifier] = Field(default_factory=dict)
    content_type: str
    title: str | None = None
    text: str | None = None
    author: CanonicalAuthorV1 | None = None
    published_at: AwareDatetime | None = None
    source_updated_at: AwareDatetime | None = None
    observed_at: AwareDatetime
    metrics: CanonicalMetricsV1 = Field(default_factory=CanonicalMetricsV1)
