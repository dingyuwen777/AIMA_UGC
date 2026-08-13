"""Canonical V1 互动指标。"""

from typing import Literal

from .base import CanonicalBaseModel, NonNegativeInt


class CanonicalMetricsV1(CanonicalBaseModel):
    """跨平台明确可解释的互动计数；未知与不适用使用 null。"""

    schema_version: Literal["metrics.v1"] = "metrics.v1"
    like_count: NonNegativeInt | None = None
    comment_count: NonNegativeInt | None = None
    share_count: NonNegativeInt | None = None
    repost_count: NonNegativeInt | None = None
    favorite_count: NonNegativeInt | None = None
    view_count: NonNegativeInt | None = None
    play_count: NonNegativeInt | None = None
    danmaku_count: NonNegativeInt | None = None
    coin_count: NonNegativeInt | None = None
    download_count: NonNegativeInt | None = None
    reply_count: NonNegativeInt | None = None
