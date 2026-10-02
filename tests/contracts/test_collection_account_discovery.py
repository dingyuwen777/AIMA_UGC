"""指定账号发现的公共创建入口及身份组合约束。"""

from copy import deepcopy
from uuid import uuid4

import pytest
from aima_ugc.contracts.http import CollectionRunCreateRequest
from pydantic import ValidationError


def account_request() -> dict[str, object]:
    return {
        "mode": "account_discovery",
        "platforms": [{"platform": "xiaohongshu", "provider_config_id": str(uuid4())}],
        "account_selection": {
            "kind": "accounts",
            "published_from": "2026-08-01T00:00:00+08:00",
            "published_to": "2026-08-31T23:59:59+08:00",
            "accounts": [
                {"platform": "xiaohongshu", "account_id_type": "red_id", "account_id": " 12345 "}
            ],
        },
    }


def test_account_discovery_is_a_formal_mode_with_full_comment_defaults() -> None:
    request = CollectionRunCreateRequest.model_validate(account_request())
    assert request.mode == "account_discovery"
    assert request.include_comments is True
    assert request.include_sub_comments is True
    assert request.account_selection is not None
    assert request.account_selection.accounts[0].account_id == "12345"


@pytest.mark.parametrize(
    ("platform", "id_type", "account_id"),
    [
        ("xiaohongshu", "user_id", "abcdef0123456789abcdef01"),
        ("douyin", "unique_id", "my_official_account"),
        ("douyin", "sec_uid", "MS4wLjABAAAA-example"),
        ("weibo", "uid", "12345"),
        ("bilibili", "uid", "12345"),
        ("kuaishou", "user_id", "12345"),
        ("kuaishou", "kuaishou_id", "my_official_account"),
        ("kuaishou", "eid", "3x-example"),
    ],
)
def test_account_id_type_is_explicit_for_each_platform(
    platform: str, id_type: str, account_id: str
) -> None:
    payload = account_request()
    payload["platforms"] = [{"platform": platform, "provider_config_id": str(uuid4())}]
    selection = dict(payload["account_selection"])
    selection["accounts"] = [
        {"platform": platform, "account_id_type": id_type, "account_id": account_id}
    ]
    payload["account_selection"] = selection
    assert CollectionRunCreateRequest.model_validate(payload).mode == "account_discovery"


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "empty",
        "duplicate",
        "wrong_platform",
        "wrong_type",
        "keyword",
        "brand",
        "search",
        "mode",
    ],
)
def test_invalid_account_source_combinations_fail_closed(change: str) -> None:
    payload = deepcopy(account_request())
    selection = payload["account_selection"]
    if change == "missing":
        del payload["account_selection"]
    elif change == "empty":
        selection["accounts"] = []
    elif change == "duplicate":
        selection["accounts"] *= 2
    elif change == "wrong_platform":
        selection["accounts"][0]["platform"] = "douyin"
        selection["accounts"][0]["account_id_type"] = "unique_id"
    elif change == "wrong_type":
        selection["accounts"][0]["account_id_type"] = "uid"
    elif change == "keyword":
        payload["keyword_pack_ids"] = [str(uuid4())]
    elif change == "brand":
        payload["brand_ids"] = [str(uuid4())]
    elif change == "search":
        payload["platforms"][0]["search_config"] = {"sort_mode": "latest"}
    else:
        payload["mode"] = "discovery"
        payload["keyword_pack_ids"] = [str(uuid4())]
    with pytest.raises(ValidationError):
        CollectionRunCreateRequest.model_validate(payload)
