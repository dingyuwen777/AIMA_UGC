"""小红书指定账号人工采集的账号消歧、日期过滤和公共链复用测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aima_ugc.adapters.providers.tikhub_test import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)
from aima_ugc.adapters.providers.tikhub_test.operations.xiaohongshu_accounts import (
    XiaohongshuAccountResolutionError,
    resolve_account_candidate,
)
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from openpyxl import load_workbook


def _write_env(path: Path) -> None:
    """写入只供 Fake Transport 使用的测试凭据，不接触真实 TikHub。"""
    path.write_text(
        "TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "TIKHUB_API_KEY=fixture-only-secret\n"
        "TIKHUB_TIMEOUT_SECONDS=5\n",
        encoding="utf-8",
    )


def _fake_transport_type(
    responses: list[dict[str, Any]],
    seen_requests: list[ProviderTransportRequest],
) -> type:
    """构造严格按顺序消费响应的 Fake Transport，确保没有隐藏 Provider 请求。"""

    class FakeTransport:
        """只实现账号纵切测试需要的 Transport 上下文协议。"""

        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> FakeTransport:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
            seen_requests.append(request)
            if not responses:
                raise AssertionError("账号采集发出了预期之外的 Provider 请求")
            return ProviderTransportResponse(
                status_code=200,
                external_request_id=f"fixture-{len(seen_requests)}",
                body=responses.pop(0),
            )

    return FakeTransport


def _user_search_response() -> dict[str, Any]:
    """返回一个与配置 red_id 精确匹配的脱敏用户搜索结果。"""
    return {
        "data": {
            "data": {
                "users": [
                    {
                        "user_id": "user-aima",
                        "red_id": "49328786266",
                        "nickname": "爱玛电动车",
                    }
                ],
                "has_more": False,
            },
            "search_id": "search-user-aima",
            "next_page": 2,
        }
    }


def _user_notes_response() -> dict[str, Any]:
    """同页包含一个区间外和一个区间内笔记，验证不会因旧数据提前停页。"""
    return {
        "data": {
            "data": {
                "notes": [
                    {
                        "note_id": "note-july",
                        "cursor": "note-july",
                        "type": "normal",
                        "title": "七月笔记",
                        "timestamp": 1785513599,
                        "comments_count": 0,
                        "user": {
                            "userid": "user-aima",
                            "red_id": "49328786266",
                            "nickname": "爱玛电动车",
                        },
                    },
                    {
                        "note_id": "note-aug",
                        "cursor": "note-aug",
                        "type": "normal",
                        "title": "八月笔记",
                        "timestamp": 1786334400,
                        "comments_count": 2,
                        "user": {
                            "userid": "user-aima",
                            "red_id": "49328786266",
                            "nickname": "爱玛电动车",
                        },
                    },
                ],
                "has_more": False,
            }
        }
    }


def _detail_response() -> dict[str, Any]:
    """详情只声明 1 条评论，用于证明 all 不以计数软目标终止。"""
    return {
        "data": {
            "data": [
                {
                    "note_list": [
                        {
                            "id": "note-aug",
                            "type": "normal",
                            "title": "八月笔记",
                            "desc": "脱敏正文",
                            "time": 1786334400,
                            "comments_count": 1,
                            "user": {
                                "userid": "user-aima",
                                "red_id": "49328786266",
                                "nickname": "爱玛电动车",
                            },
                        }
                    ]
                }
            ]
        }
    }


def _comment_page_one() -> dict[str, Any]:
    """评论第一页只有一条但 Provider 仍有下一页。"""
    return {
        "data": {
            "data": {
                "comments": [
                    {
                        "id": "comment-1",
                        "note_id": "note-aug",
                        "content": "一级评论 1",
                        "sub_comment_count": 0,
                    }
                ],
                "cursor": "comment-cursor-2",
                "index": 1,
                "pageArea": "UNFOLDED",
                "has_more": True,
            }
        }
    }


def _comment_page_two() -> dict[str, Any]:
    """评论第二页返回剩余一条并明确 Provider 已耗尽。"""
    return {
        "data": {
            "data": {
                "comments": [
                    {
                        "id": "comment-2",
                        "note_id": "note-aug",
                        "content": "一级评论 2",
                        "sub_comment_count": 0,
                    }
                ],
                "cursor": "comment-cursor-done",
                "index": 2,
                "pageArea": "UNFOLDED",
                "has_more": False,
            }
        }
    }


def test_red_id_exact_match_wins_and_nickname_only_ambiguity_fails_closed() -> None:
    """账号身份必须由稳定 red_id 消歧；同名候选不能静默选择第一条。"""
    candidates = (
        {"user_id": "user-a", "red_id": "49328786266", "nickname": "已改名"},
        {"user_id": "user-b", "red_id": "other", "nickname": "爱玛电动车"},
    )
    resolved = resolve_account_candidate(
        XiaohongshuAccountTarget(nickname="爱玛电动车", red_id="49328786266"),
        candidates,
    )
    assert resolved.user_id == "user-a"
    assert resolved.red_id == "49328786266"
    assert resolved.nickname == "已改名"
    assert resolved.nickname_matches is False

    with pytest.raises(XiaohongshuAccountResolutionError, match="候选不唯一"):
        resolve_account_candidate(
            XiaohongshuAccountTarget(nickname="同名账号"),
            (
                {"user_id": "user-1", "nickname": "同名账号"},
                {"user_id": "user-2", "nickname": "同名账号"},
            ),
        )


def test_account_run_filters_date_and_all_mode_crosses_soft_comment_target(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """账号 Discovery 只输出日期范围内笔记，all 模式继续翻过普通评论软目标。"""
    env_file = tmp_path / ".env"
    output_root = tmp_path / "output"
    _write_env(env_file)

    responses = [
        _user_search_response(),
        _user_notes_response(),
        _detail_response(),
        _comment_page_one(),
        _comment_page_two(),
    ]
    requests: list[ProviderTransportRequest] = []
    monkeypatch.setattr(
        "aima_ugc.adapters.providers.tikhub_test.operations.runner.TikHubHttpTransport",
        _fake_transport_type(responses, requests),
    )

    result = run_xiaohongshu_accounts(
        accounts=(XiaohongshuAccountTarget(nickname="爱玛电动车", red_id="49328786266"),),
        start_date="2026-08-01",
        end_date="2026-09-02",
        env_file=env_file,
        output_root=output_root,
        run_id="accounts",
        max_account_search_pages=2,
        max_note_pages_per_account=2,
        max_comments_per_content=1,
        max_comment_pages_per_content=3,
        include_comments=True,
        include_replies=False,
        comment_mode="all",
    )

    assert responses == []
    assert result.request_count == 5
    assert result.content_count == 1
    assert result.root_comment_count == 2
    assert result.reply_count == 0
    assert [request.path.rsplit("/", 1)[-1] for request in requests] == [
        "search_users",
        "get_user_posted_notes",
        "get_image_note_detail",
        "get_note_comments",
        "get_note_comments",
    ]

    content_lines = (
        (result.run_dir / "canonical" / "contents.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(content_lines) == 2
    discovery = json.loads(content_lines[0])
    assert discovery["external_content_id"] == "note-aug"
    assert discovery["source"]["source_type"] == "account"
    assert discovery["source"]["source_value"] == "user-aima"
    assert "note-july" not in "\n".join(content_lines)

    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["date_range"] == {
        "start_date": "2026-08-01",
        "end_date": "2026-09-02",
        "timezone": "Asia/Shanghai",
    }
    assert summary["accounts"][0]["configured_red_id"] == "49328786266"
    assert summary["accounts"][0]["resolved_user_id"] == "user-aima"
    assert summary["accounts"][0]["in_range_note_count"] == 1
    assert summary["accounts"][0]["out_of_range_note_count"] == 1

    workbook = load_workbook(result.workbook_path, data_only=False)
    try:
        assert workbook.sheetnames == ["内容", "标签明细", "评论"]
        assert workbook["内容"].max_row == 2
        assert workbook["评论"].max_row == 3
    finally:
        workbook.close()
