"""真实账号作品响应中空 since_id 不代表空页。"""

from aima_ugc.adapters.providers.tikhub.account_runtime import advance_weibo_user_posts
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import extract_user_profile
from aima_ugc.adapters.providers.tikhub.runtime import advance_comments


def test_bilibili_app_comment_position_can_decrease_without_stalling() -> None:
    """实测 App mode=2 返回 81 → 61；游标不是递增页号。"""
    result = advance_comments(
        platform="bilibili",
        state={"next_offset": 81},
        body={
            "data": {
                "data": {
                    "cursor": {
                        "next": 61,
                        "is_end": False,
                        "pagination_reply": {"next_offset": "opaque-provider-token"},
                    }
                }
            },
        },
    )
    assert result.should_continue is True
    assert result.next_state == {"next_offset": 61}


def test_weibo_nonempty_page_without_since_id_advances_page_number() -> None:
    body = {"data": {"data": {"list": [{"idstr": "100", "text": "第一条"}], "since_id": ""}}}
    result = advance_weibo_user_posts(state={"page": 1}, body=body)
    assert result.should_continue is True
    assert result.next_state["page"] == 2
    assert result.next_state["since_id"] == ""


def test_weibo_empty_page_is_a_real_exhaustion_signal() -> None:
    result = advance_weibo_user_posts(
        state={"page": 2, "since_id": ""}, body={"data": {"data": {"list": []}}}
    )
    assert result.should_continue is False
    assert result.stop_reason == "empty_page"


def test_kuaishou_profile_never_treats_echoed_request_as_resolved_identity() -> None:
    profile = {"user_id": "98765", "kwaiId": "actual_handle", "user_name": "官号"}
    response = {
        "code": 200,
        "params": {"user_id": "3x-requested-eid"},
        "data": {"userProfile": {"profile": profile}},
    }
    assert extract_user_profile(response) == profile
