"""TikHub 抖音 Search V2 真实响应分页结构回归测试。"""

from aima_ugc.adapters.providers.tikhub.operations.douyin import DouyinSearchPagination


def test_real_search_v2_pagination_uses_business_config_next_page() -> None:
    body = {
        "data": {
            "business_config": {
                "backtrace": "backtrace-real-shape",
                "has_more": 1,
                "next_page": {
                    "cursor": 8,
                    "search_id": "search-real-shape",
                },
            },
            "business_data": [
                {"data": {"aweme_info": {"aweme_id": "aweme-1"}}},
                {"data": {"aweme_info": {"aweme_id": "aweme-2"}}},
            ],
        }
    }

    pagination = DouyinSearchPagination.from_response(current_cursor=0, body=body)

    assert pagination.should_continue is True
    assert pagination.next_cursor == 8
    assert pagination.search_id == "search-real-shape"
    assert pagination.backtrace == "backtrace-real-shape"
    assert pagination.item_ids == ("aweme-1", "aweme-2")
