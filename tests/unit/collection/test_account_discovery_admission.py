"""按账号日期入库与品牌匹配相互独立。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from aima_ugc.adapters.providers.tikhub.account_identity import ResolvedAccountIdentity
from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1, CanonicalSourceV1
from aima_ugc.modules.collection.account_discovery import account_content_admission

_TZ = ZoneInfo("Asia/Shanghai")


def _content(publication: datetime | None, author_id: str | None = "12") -> CanonicalContentV1:
    return CanonicalContentV1(
        platform="bilibili",
        external_content_id="post",
        content_type="video",
        observed_at=datetime(2026, 10, 3, tzinfo=_TZ),
        published_at=publication,
        author=CanonicalAuthorV1(external_account_id=author_id),
        text="不含品牌的日常笔记",
        observed_fields=["text", "author.external_account_id", "published_at"],
        source=CanonicalSourceV1(
            provider_name="tikhub",
            source_type="account",
            source_value="uid:12",
            observed_at=datetime(2026, 10, 3, tzinfo=_TZ),
        ),
    )


def test_account_date_admission_includes_whole_last_beijing_day() -> None:
    result = account_content_admission(
        _content(datetime(2026, 10, 2, 23, 59, 59, 999999, tzinfo=_TZ)),
        identity=ResolvedAccountIdentity(stable_id="12", author_ids=("12",)),
        published_from=datetime(2026, 10, 1, tzinfo=_TZ),
        published_to=datetime(2026, 10, 2, tzinfo=_TZ),
    )
    assert result is None


def test_account_missing_date_and_author_conflict_have_distinct_partial_reasons() -> None:
    kwargs = dict(
        identity=ResolvedAccountIdentity(stable_id="12", author_ids=("12",)),
        published_from=datetime(2026, 10, 1, tzinfo=_TZ),
        published_to=datetime(2026, 10, 2, tzinfo=_TZ),
    )
    assert account_content_admission(_content(None), **kwargs) == "publication_unavailable"
    assert (
        account_content_admission(_content(datetime(2026, 10, 2, tzinfo=_TZ), "13"), **kwargs)
        == "account_author_conflict"
    )
    assert (
        account_content_admission(_content(datetime(2026, 9, 30, tzinfo=_TZ)), **kwargs)
        == "outside_published_date_range"
    )
