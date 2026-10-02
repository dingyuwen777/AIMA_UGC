"""账号采集必须验证真实身份，拒绝搜索歧义和作者串号。"""

import pytest
from aima_ugc.adapters.providers.tikhub.account_identity import (
    AccountIdentityError,
    resolve_profile_identity,
    resolve_search_identity,
)
from aima_ugc.adapters.providers.tikhub.account_runtime import build_account_posts_call


def test_douyin_unique_id_requires_exact_profile_and_stable_sec_uid() -> None:
    identity = resolve_profile_identity(
        platform="douyin",
        id_type="unique_id",
        id_value="handle",
        profile={"unique_id": "handle", "sec_uid": "stable-sec", "uid": "12"},
    )
    assert identity.stable_id == "stable-sec"
    assert identity.author_ids == ("stable-sec", "12")
    assert (
        build_account_posts_call("douyin", identity.stable_id).params["sec_user_id"] == "stable-sec"
    )
    with pytest.raises(AccountIdentityError, match="identity_mismatch"):
        resolve_profile_identity(
            platform="douyin",
            id_type="unique_id",
            id_value="handle",
            profile={"unique_id": "other", "sec_uid": "stable-sec"},
        )


def test_kuaishou_alias_never_silently_falls_back_to_nickname() -> None:
    identity = resolve_search_identity(
        platform="kuaishou",
        id_type="kuaishou_id",
        id_value="handle",
        candidates=[{"user_id": "12", "kwaiId": "handle", "user_name": "官号"}],
    )
    assert identity.stable_id == "12"
    with pytest.raises(AccountIdentityError, match="not_found"):
        resolve_search_identity(
            platform="kuaishou",
            id_type="kuaishou_id",
            id_value="handle",
            candidates=[{"user_id": "13", "kwaiId": "other", "user_name": "handle"}],
        )
    with pytest.raises(AccountIdentityError, match="ambiguous"):
        resolve_search_identity(
            platform="kuaishou",
            id_type="kuaishou_id",
            id_value="handle",
            candidates=[
                {"user_id": "12", "kwaiId": "handle"},
                {"user_id": "13", "kwaiId": "handle"},
            ],
        )


def test_xiaohongshu_red_id_reuses_production_exact_identity_owner() -> None:
    result = resolve_search_identity(
        platform="xiaohongshu",
        id_type="red_id",
        id_value="handle",
        candidates=[{"user_id": "stable-user", "red_id": "handle", "nickname": "官号"}],
    )
    assert result.stable_id == "stable-user"
    assert result.nickname == "官号"
    assert result.matches_author("stable-user", {})
    assert not result.matches_author("another", {})


def test_douyin_author_sec_uid_is_allowed_but_unproven_author_is_rejected() -> None:
    result = resolve_profile_identity(
        platform="douyin",
        id_type="unique_id",
        id_value="handle",
        profile={"unique_id": "handle", "sec_uid": "stable-sec", "uid": "12"},
    )
    assert result.matches_author("12", {"sec_uid": "stable-sec"})
    assert not result.matches_author("13", {"sec_uid": "other-sec"})


def test_kuaishou_profile_requires_requested_alias_and_numeric_user_id() -> None:
    with pytest.raises(AccountIdentityError, match="incomplete"):
        resolve_profile_identity(
            platform="kuaishou",
            id_type="eid",
            id_value="eid-request",
            profile={"user_id": "12", "kwaiId": "handle"},
        )
    with pytest.raises(AccountIdentityError, match="identity_mismatch"):
        resolve_profile_identity(
            platform="kuaishou",
            id_type="user_id",
            id_value="12",
            profile={"user_id": "13", "kwaiId": "handle"},
        )
