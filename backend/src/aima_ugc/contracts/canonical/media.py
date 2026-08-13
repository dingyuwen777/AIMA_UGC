"""Canonical V1 媒体、话题、提及和公开位置。"""

from typing import Literal

from pydantic import AnyHttpUrl

from .author import CanonicalAuthorV1
from .base import CanonicalBaseModel, Identifier, Latitude, Longitude, NonNegativeInt


class CanonicalMediaV1(CanonicalBaseModel):
    media_type: Literal["image", "video", "live_photo", "audio", "cover", "other"]
    external_media_id: Identifier | None = None
    url: AnyHttpUrl | None = None
    preview_url: AnyHttpUrl | None = None
    width: NonNegativeInt | None = None
    height: NonNegativeInt | None = None
    duration_ms: NonNegativeInt | None = None
    position: NonNegativeInt = 0
    mime_type: str | None = None
    alt_text: str | None = None


class CanonicalTopicV1(CanonicalBaseModel):
    name: str
    external_topic_id: Identifier | None = None
    url: AnyHttpUrl | None = None


class CanonicalMentionV1(CanonicalBaseModel):
    account: CanonicalAuthorV1
    display_text: str | None = None


class CanonicalLocationV1(CanonicalBaseModel):
    location_type: Literal["place", "ip_region"]
    label: str
    country: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
