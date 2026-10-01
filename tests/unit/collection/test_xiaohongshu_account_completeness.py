"""小红书指定账号 all 模式的硬分页边界完整性测试。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from aima_ugc.adapters.providers.tikhub_test import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)


def _write_env(path: Path) -> None:
    path.write_text(
        "TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "TIKHUB_API_KEY=fixture-only-secret\n"
        "TIKHUB_TIMEOUT_SECONDS=5\n",
        encoding="utf-8",
    )


def _fake_transport_type(responses: list[dict[str, Any]]) -> type:
    class FakeTransport:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> FakeTransport:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
            if not responses:
                raise AssertionError(f"出现预期之外的 Provider 请求：{request.path}")
            return ProviderTransportResponse(
                status_code=200,
                external_request_id="fixture-hard-reply-limit",
                body=responses.pop(0),
            )

    return FakeTransport


def _run_reply_case(
    tmp_path: Path,
    monkeypatch: Any,
    *,
    limit: int = 1,
    terminal: bool | None = None,
) -> Any:
    """reply_count 即使低报到已满足，撞到硬页数边界也不能宣称全部回复完整。"""
    env_file = tmp_path / ".env"
    _write_env(env_file)
    responses: list[dict[str, Any]] = [
        {
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
        },
        {
            "data": {
                "data": {
                    "notes": [
                        {
                            "note_id": "note-aug",
                            "cursor": "note-aug",
                            "type": "normal",
                            "title": "八月笔记",
                            "timestamp": 1786334400,
                            "comments_count": 1,
                            "user": {
                                "userid": "user-aima",
                                "red_id": "49328786266",
                                "nickname": "爱玛电动车",
                            },
                        }
                    ],
                    "has_more": False,
                }
            }
        },
        {
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
        },
        {
            "data": {
                "data": {
                    "comments": [
                        {
                            "id": "comment-root",
                            "note_id": "note-aug",
                            "content": "有回复的一级评论",
                            "sub_comment_count": 1,
                        }
                    ],
                    "cursor": "comment-done",
                    "index": 1,
                    "pageArea": "UNFOLDED",
                    "has_more": False,
                }
            }
        },
        {
            "data": {
                "data": {
                    "comments": [
                        {
                            "id": "reply-1",
                            "note_id": "note-aug",
                            "content": "二级回复 1",
                        }
                    ],
                    "cursor": "reply-still-more",
                    "index": 2,
                    "pageArea": "UNFOLDED",
                    "has_more": True,
                }
            }
        },
    ]
    if terminal is not None:
        continuation = copy.deepcopy(responses[-1])
        continuation["data"]["data"].update(
            comments=[] if terminal else continuation["data"]["data"]["comments"],
            cursor="reply-done" if terminal else "reply-still-more",
            has_more=not terminal,
        )
        responses.append(continuation)
    monkeypatch.setattr(
        "aima_ugc.adapters.providers.tikhub_test.operations.runner.TikHubHttpTransport",
        _fake_transport_type(responses),
    )

    result = run_xiaohongshu_accounts(
        accounts=(XiaohongshuAccountTarget(nickname="爱玛电动车", red_id="49328786266"),),
        start_date="2026-08-01",
        end_date="2026-09-02",
        env_file=env_file,
        output_root=tmp_path / "output",
        run_id="hard-reply-limit",
        max_account_search_pages=2,
        max_note_pages_per_account=2,
        max_comment_pages_per_content=2,
        max_reply_pages_per_root=limit,
        include_comments=True,
        include_replies=True,
        comment_mode="all",
    )

    assert responses == []
    assert result.root_comment_count == 1
    assert result.reply_count == 1
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    return summary


def test_all_mode_marks_partial_when_reply_hard_page_limit_is_reached(tmp_path, monkeypatch):
    summary = _run_reply_case(tmp_path, monkeypatch)
    assert summary["status"] == "completed_with_errors"
    assert summary["accounts"][0]["status"] == "partial"
    assert summary["accounts"][0]["warnings"] == [
        {
            "stage": "replies",
            "external_content_id": "note-aug",
            "root_comment_id": "comment-root",
            "observed": 1,
            "expected": 1,
            "reason": "reply_page_limit_boundary",
        }
    ]


@pytest.mark.parametrize("terminal", [False, True])
def test_all_mode_reply_known_count_does_not_hide_cursor_stall(terminal, tmp_path, monkeypatch):
    summary = _run_reply_case(tmp_path, monkeypatch, limit=3, terminal=terminal)
    assert summary["accounts"][0]["status"] == ("completed" if terminal else "partial"), summary
    assert bool(summary["accounts"][0]["warnings"]) == (not terminal), summary
