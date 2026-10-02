"""账号作品以真实作者和北京时间日期准入；品牌只提供后续证据。"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from aima_ugc.contracts.canonical import CanonicalContentV1


class AccountAuthorIdentity(Protocol):
    """准入只依赖已证明身份的作者校验，不依赖 Provider 响应结构。"""

    def matches_author(self, external_id: str | None, alternate_ids: Mapping[str, str]) -> bool: ...


def account_content_admission(
    content: CanonicalContentV1,
    *,
    identity: AccountAuthorIdentity,
    published_from: datetime,
    published_to: datetime,
) -> str | None:
    """整个结束日均包含在内；缺事实和身份冲突不能伪装成正常过滤。"""
    author = content.author
    if author is None or not identity.matches_author(
        author.external_account_id, author.alternate_ids
    ):
        return "account_author_conflict"
    if content.published_at is None:
        return "publication_unavailable"
    timezone = ZoneInfo("Asia/Shanghai")
    start = datetime.combine(
        published_from.astimezone(timezone).date(), datetime.min.time(), timezone
    )
    end = datetime.combine(
        published_to.astimezone(timezone).date() + timedelta(days=1), datetime.min.time(), timezone
    )
    if not start <= content.published_at < end:
        return "outside_published_date_range"
    return None
