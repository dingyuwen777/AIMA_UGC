"""真实账号作品响应中空 since_id 不代表空页。"""

from aima_ugc.adapters.providers.tikhub.account_runtime import advance_weibo_user_posts


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
