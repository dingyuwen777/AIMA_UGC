"""Canonical V1 公开作者/评论者结构。"""

from pydantic import AnyHttpUrl

from .base import CanonicalBaseModel, Identifier, NonNegativeInt


class CanonicalAuthorV1(CanonicalBaseModel):
    """帖子作者和评论者共用的公开账号信息。"""

    external_account_id: Identifier | None = None
    alternate_ids: dict[str, Identifier] = {}
    handle: str | None = None
    display_name: str | None = None
    profile_url: AnyHttpUrl | None = None
    avatar_url: AnyHttpUrl | None = None
    bio: str | None = None
    verified: bool | None = None
    verification_label: str | None = None
    region: str | None = None
    follower_count: NonNegativeInt | None = None
    following_count: NonNegativeInt | None = None
    content_count: NonNegativeInt | None = None
    total_like_count: NonNegativeInt | None = None
