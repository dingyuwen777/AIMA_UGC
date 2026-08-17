"""TikHub 同平台 API family 候选与显式备用边界测试。"""

from decimal import Decimal

from aima_ugc.adapters.providers.tikhub.operations.bilibili import (
    build_web_reply_candidate_request,
    build_web_search_candidate_request,
    build_web_video_comments_candidate_request,
    build_web_video_detail_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.operations.douyin import (
    build_video_search_request,
    build_video_search_v1_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.operations.kuaishou import (
    build_comprehensive_search_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.operations.weibo import (
    build_app_search_candidate_request,
    build_web_status_comments_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.operations.xiaohongshu import (
    build_app_v1_comments_candidate_request,
    build_app_v1_detail_candidate_request,
    build_app_v1_search_candidate_request,
    build_app_v1_sub_comments_candidate_request,
    build_web_v3_comments_candidate_request,
    build_web_v3_detail_candidate_request,
    build_web_v3_search_candidate_request,
    build_web_v3_sub_comments_candidate_request,
)
from aima_ugc.adapters.providers.tikhub.pricing import load_tikhub_pricing


def test_douyin_video_search_v1_candidate_reuses_primary_business_filters() -> None:
    primary = build_video_search_request(
        keyword="爱玛",
        cursor=0,
        sort_mode="latest",
        published_within="7d",
        duration="all",
        content_type="video",
    )
    candidate = build_video_search_v1_candidate_request(
        keyword="爱玛",
        cursor=0,
        sort_mode="latest",
        published_within="7d",
        duration="all",
        content_type="video",
    )

    assert primary.path == "/api/v1/douyin/search/fetch_video_search_v2"
    assert candidate.path == "/api/v1/douyin/search/fetch_video_search_v1"
    assert candidate.body == primary.body


def test_weibo_app_search_candidate_matches_realtime_search_mode_without_fake_time_scope() -> None:
    request = build_app_search_candidate_request(keyword="爱玛", page=1, search_mode="latest")

    assert request.path == "/api/v1/weibo/app/fetch_search_all"
    assert request.params == {"query": "爱玛", "page": 1, "search_type": 61}


def test_weibo_web_v2_comment_candidate_is_explicit_and_bounded() -> None:
    request = build_web_status_comments_candidate_request(
        status_id="1234567890", max_id="", count=10
    )

    assert request.path == "/api/v1/weibo/web_v2/fetch_post_comments"
    assert request.params == {"id": "1234567890", "count": 10, "max_id": ""}


def test_bilibili_web_candidates_are_explicit_and_do_not_replace_app_primary() -> None:
    search = build_web_search_candidate_request(
        keyword="爱玛", page=1, page_size=20, sort_mode="latest"
    )
    detail = build_web_video_detail_candidate_request(bv_id="BV1TEST")
    comments = build_web_video_comments_candidate_request(bv_id="BV1TEST", page=1)
    replies = build_web_reply_candidate_request(bv_id="BV1TEST", root="9001", page=1)

    assert search.path == "/api/v1/bilibili/web/fetch_general_search"
    assert search.params == {
        "keyword": "爱玛",
        "order": "pubdate",
        "page": 1,
        "page_size": 20,
    }
    assert detail.path == "/api/v1/bilibili/web/fetch_one_video"
    assert detail.params == {"bv_id": "BV1TEST"}
    assert comments.path == "/api/v1/bilibili/web/fetch_video_comments"
    assert comments.params == {"bv_id": "BV1TEST", "pn": 1}
    assert replies.path == "/api/v1/bilibili/web/fetch_comment_reply"
    assert replies.params == {"bv_id": "BV1TEST", "pn": 1, "rpid": "9001"}


def test_xhs_app_v1_candidates_match_same_business_inputs_without_becoming_primary() -> None:
    search = build_app_v1_search_candidate_request(
        keyword="爱玛",
        page=1,
        sort_type="general",
        note_type="不限",
        time_filter="不限",
    )
    detail = build_app_v1_detail_candidate_request(note_id="note-1")
    comments = build_app_v1_comments_candidate_request(note_id="note-1", start="", sort_strategy=1)
    sub_comments = build_app_v1_sub_comments_candidate_request(
        note_id="note-1", comment_id="comment-1", start=""
    )

    assert search.path == "/api/v1/xiaohongshu/app/search_notes"
    assert search.params == {
        "keyword": "爱玛",
        "page": 1,
        "sort_type": "general",
        "filter_note_type": "不限",
        "filter_note_time": "不限",
    }
    assert detail.path == "/api/v1/xiaohongshu/app/get_note_info"
    assert detail.params == {"note_id": "note-1"}
    assert comments.path == "/api/v1/xiaohongshu/app/get_note_comments"
    assert comments.params == {"note_id": "note-1", "start": "", "sort_strategy": 1}
    assert sub_comments.path == "/api/v1/xiaohongshu/app/get_sub_comments"
    assert sub_comments.params == {
        "note_id": "note-1",
        "comment_id": "comment-1",
        "start": "",
    }


def test_xhs_web_v3_candidates_require_xsec_for_protected_operations() -> None:
    search = build_web_v3_search_candidate_request(
        keyword="爱玛", page=1, sort="general", note_type=0
    )
    detail = build_web_v3_detail_candidate_request(note_id="note-1", xsec_token="xsec-token")
    comments = build_web_v3_comments_candidate_request(
        note_id="note-1", xsec_token="xsec-token", cursor=""
    )
    sub_comments = build_web_v3_sub_comments_candidate_request(
        note_id="note-1",
        root_comment_id="comment-1",
        xsec_token="xsec-token",
        num=10,
        cursor="",
    )

    assert search.path == "/api/v1/xiaohongshu/web_v3/fetch_search_notes"
    assert search.params == {
        "keyword": "爱玛",
        "page": 1,
        "sort": "general",
        "note_type": 0,
    }
    assert detail.path == "/api/v1/xiaohongshu/web_v3/fetch_note_detail"
    assert detail.params == {"note_id": "note-1", "xsec_token": "xsec-token"}
    assert comments.path == "/api/v1/xiaohongshu/web_v3/fetch_note_comments"
    assert comments.params == {
        "note_id": "note-1",
        "xsec_token": "xsec-token",
        "cursor": "",
    }
    assert sub_comments.path == "/api/v1/xiaohongshu/web_v3/fetch_sub_comments"
    assert sub_comments.params == {
        "note_id": "note-1",
        "root_comment_id": "comment-1",
        "xsec_token": "xsec-token",
        "num": 10,
        "cursor": "",
    }


def test_kuaishou_comprehensive_search_is_only_a_candidate_not_a_web_equivalent() -> None:
    request = build_comprehensive_search_candidate_request(
        keyword="爱玛",
        pcursor="",
        sort_mode="latest",
        publish_time="week",
        duration="all",
    )

    assert request.path == "/api/v1/kuaishou/app/search_comprehensive"
    assert request.params == {
        "keyword": "爱玛",
        "pcursor": "",
        "sort_type": "newest",
        "publish_time": "one_week",
        "duration": "all",
    }


def test_kuaishou_app_comment_primary_has_endpoint_level_verified_pricing() -> None:
    catalog = load_tikhub_pricing()

    assert catalog.billing_for_endpoint(
        "/api/v1/kuaishou/app/fetch_video_comment"
    ).unit_price_snapshot == Decimal("0.001000")
    assert catalog.billing_for_endpoint(
        "/api/v1/kuaishou/app/fetch_video_sub_comments"
    ).unit_price_snapshot == Decimal("0.001000")
