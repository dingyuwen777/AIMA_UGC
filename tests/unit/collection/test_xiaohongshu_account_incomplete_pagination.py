"""小红书指定账号异常分页必须 fail closed / partial 的回归测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.tikhub_test import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)


def _write_env(path: Path) -> None:
    """写入仅供 Fake Transport 使用的隔离配置。"""
    path.write_text(
        "TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "TIKHUB_API_KEY=fixture-only-secret\n"
        "TIKHUB_TIMEOUT_SECONDS=5\n",
        encoding="utf-8",
    )


def _fake_transport_type(
    responses: list[dict[str, Any]],
    seen_paths: list[str],
) -> type:
    """按顺序消费固定响应，并记录是否发生了不应继续的 Provider 请求。"""

    class FakeTransport:
        """实现测试所需的最小 Transport 上下文协议。"""

        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> FakeTransport:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
            seen_paths.append(request.path.rsplit("/", 1)[-1])
            if not responses:
                raise AssertionError(f"出现预期之外的 Provider 请求：{request.path}")
            return ProviderTransportResponse(
                status_code=200,
                external_request_id=f"fixture-{len(seen_paths)}",
                body=responses.pop(0),
            )

    return FakeTransport


def _note(note_id: str) -> dict[str, Any]:
    """构造日期范围内、可由现有 Mapper 映射的用户笔记列表项。"""
    return {
        "note_id": note_id,
        "type": "normal",
        "title": note_id,
        "timestamp": 1786334400,
        "comments_count": 0,
        "user": {"userid": "user-aima", "nickname": "爱玛电动车"},
    }


def _detail(note_id: str) -> dict[str, Any]:
    """构造与用户笔记身份一致的图文详情响应。"""
    return {
        "data": {
            "data": [
                {
                    "note_list": [
                        {
                            "id": note_id,
                            "type": "normal",
                            "title": note_id,
                            "desc": "脱敏正文",
                            "time": 1786334400,
                            "comments_count": 0,
                            "user": {"userid": "user-aima", "nickname": "爱玛电动车"},
                        }
                    ]
                }
            ]
        }
    }


def test_nickname_resolution_fails_closed_when_search_pagination_is_incomplete(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """搜索仍有后续页但缺 search_id 时，不能把第一页唯一昵称候选当成全局唯一。"""
    env_file = tmp_path / ".env"
    _write_env(env_file)
    responses: list[dict[str, Any]] = [
        {
            "data": {
                "data": {
                    "users": [{"user_id": "user-first", "nickname": "同名账号"}],
                    "has_more": True,
                },
                "next_page": 2,
            }
        }
    ]
    seen_paths: list[str] = []
    monkeypatch.setattr(
        "aima_ugc.adapters.providers.tikhub_test.operations.runner.TikHubHttpTransport",
        _fake_transport_type(responses, seen_paths),
    )

    result = run_xiaohongshu_accounts(
        accounts=(XiaohongshuAccountTarget(nickname="同名账号"),),
        start_date="2026-08-01",
        end_date="2026-09-02",
        env_file=env_file,
        output_root=tmp_path / "output",
        run_id="incomplete-user-search",
        include_comments=False,
        include_replies=False,
    )

    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert seen_paths == ["search_users"]
    assert summary["status"] == "failed"
    assert summary["accounts"][0]["status"] == "failed"
    assert summary["accounts"][0]["error_type"] == "XiaohongshuAccountResolutionError"
    assert "无法确认账号唯一性" in summary["accounts"][0]["error_summary"]


def test_user_notes_non_advancing_cursor_marks_account_partial(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Provider 仍有下一页但 cursor 不推进时，已保存当前页也不能宣称账号完整。"""
    env_file = tmp_path / ".env"
    _write_env(env_file)
    responses: list[dict[str, Any]] = [
        {
            "data": {
                "data": {
                    "notes": [_note("note-1")],
                    "cursor": "cursor-stuck",
                    "has_more": True,
                }
            }
        },
        _detail("note-1"),
        {
            "data": {
                "data": {
                    "notes": [_note("note-2")],
                    "cursor": "cursor-stuck",
                    "has_more": True,
                }
            }
        },
        _detail("note-2"),
    ]
    seen_paths: list[str] = []
    monkeypatch.setattr(
        "aima_ugc.adapters.providers.tikhub_test.operations.runner.TikHubHttpTransport",
        _fake_transport_type(responses, seen_paths),
    )

    result = run_xiaohongshu_accounts(
        accounts=(XiaohongshuAccountTarget(user_id="user-aima"),),
        start_date="2026-08-01",
        end_date="2026-09-02",
        env_file=env_file,
        output_root=tmp_path / "output",
        run_id="stalled-user-notes",
        include_comments=False,
        include_replies=False,
        max_note_pages_per_account=5,
    )

    assert responses == []
    assert seen_paths == [
        "get_user_posted_notes",
        "get_image_note_detail",
        "get_user_posted_notes",
        "get_image_note_detail",
    ]
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed_with_errors"
    assert summary["accounts"][0]["status"] == "partial"
    assert summary["accounts"][0]["note_stop_reason"] == "pagination_not_advanced"
    assert summary["accounts"][0]["processed_note_count"] == 2
