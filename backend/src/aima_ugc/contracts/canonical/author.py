"""Canonical V1 公开作者/评论者结构。"""

from pydantic import AnyHttpUrl

from .base import CanonicalBaseModel, Identifier


class CanonicalAuthorV1(CanonicalBaseModel):
    external_account_id: Identifier | None = None
    alternate_ids: dict[str, Identifier] = {}
    handle: str | None = None
    display_name: str | None = None
    profile_url: AnyHttpUrl | None = None
    avatar_url: AnyHttpUrl | None = None
