"""TikHub 调试主链复用生产 Runtime 的无数据库纵切回归。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.tikhub_test import run_xiaohongshu
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from openpyxl import load_workbook

_FIXTURE_ROOT = Path("tests/fixtures/providers/tikhub/xhs")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _fake_transport_type(
    responses: list[dict[str, Any]],
    seen_requests: list[ProviderTransportRequest],
) -> type:
    class FakeTransport:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> FakeTransport:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
            seen_requests.append(request)
            if not responses:
                raise AssertionError("调试主链发出了预期之外的 Provider 请求")
            return ProviderTransportResponse(
                status_code=200,
                external_request_id=f"fixture-{len(seen_requests)}",
                body=responses.pop(0),
            )

    return FakeTransport


def _matching_detail() -> dict[str, Any]:
    return {
        "data": {
            "data": [
                {
                    "note_list": [
                        {
                            "id": "note-fixture-1",
                            "title": "脱敏标题 A",
                            "desc": "脱敏正文 A",
                            "type": "normal",
                            "time": 1720000000,
                            "liked_count": 10,
                            "comments_count": 1,
                            "collected_count": 2,
                            "shared_count": 1,
                            "user": {
                                "userid": "user-fixture-1",
                                "nickname": "脱敏用户 A",
                            },
                        }
                    ]
                }
            ]
        }
    }


def _matching_comments() -> dict[str, Any]:
    body = _fixture("comments_page1.sanitized.json")
    root = body["data"]["data"]["comments"][0]
    root["note_id"] = "note-fixture-1"
    return body


def _matching_replies() -> dict[str, Any]:
    body = _fixture("sub_comments_page1.sanitized.json")
    reply = body["data"]["data"]["comments"][0]
    reply["note_id"] = "note-fixture-1"
    return body


def _write_env(path: Path) -> None:
    path.write_text(
        "TIKHUB_BASE_URL=https://api.tikhub.io\n"
        "TIKHUB_API_KEY=fixture-only-secret\n"
        "TIKHUB_TIMEOUT_SECONDS=5\n",
        encoding="utf-8",
    )


def test_xhs_debug_runtime_reuses_production_flow_and_skips_unchanged_refresh(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    env_file = tmp_path / ".env"
    output_root = tmp_path / "output"
    _write_env(env_file)

    first_responses = [
        _fixture("search_notes_page1.sanitized.json"),
        _matching_detail(),
        _matching_comments(),
        _matching_replies(),
    ]
    first_requests: list[ProviderTransportRequest] = []
    monkeypatch.setattr(
        "aima_ugc.adapters.providers.tikhub_test.runner.TikHubHttpTransport",
        _fake_transport_type(first_responses, first_requests),
    )

    first = run_xiaohongshu(
        keyword="爱玛",
        env_file=env_file,
        output_root=output_root,
        run_id="first",
        max_search_pages=1,
        max_contents=1,
        max_comments_per_content=1,
        max_comment_pages_per_content=1,
        max_replies_per_root=1,
        max_reply_pages_per_root=1,
    )

    assert first_responses == []
    assert first.request_count == 4
    assert first.content_count == 1
    assert first.root_comment_count == 1
    assert first.reply_count == 1
    assert len(list((first.run_dir / "raw").glob("*.json"))) == 4

    content_lines = (
        (first.run_dir / "canonical" / "contents.jsonl").read_text(encoding="utf-8").splitlines()
    )
    comment_lines = (
        (first.run_dir / "canonical" / "comments.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(content_lines) == 2
    assert len(comment_lines) == 2
    assert {json.loads(line)["external_content_id"] for line in comment_lines} == {"note-fixture-1"}
    assert json.loads(first.manifest_path.read_text(encoding="utf-8"))["status"] == "completed"

    workbook = load_workbook(first.workbook_path, data_only=False)
    try:
        sheet = workbook["内容与评论"]
        assert sheet.max_row == 3
        assert sheet["P2"].value == "xhs-comment-root-1"
        assert sheet["P3"].value == "xhs-comment-reply-2"
    finally:
        workbook.close()

    second_responses = [_fixture("search_notes_page1.sanitized.json")]
    second_requests: list[ProviderTransportRequest] = []
    monkeypatch.setattr(
        "aima_ugc.adapters.providers.tikhub_test.runner.TikHubHttpTransport",
        _fake_transport_type(second_responses, second_requests),
    )

    second = run_xiaohongshu(
        keyword="爱玛",
        env_file=env_file,
        output_root=output_root,
        run_id="second",
        max_search_pages=1,
        max_contents=1,
        max_comments_per_content=1,
        max_comment_pages_per_content=1,
        max_replies_per_root=1,
        max_reply_pages_per_root=1,
    )

    assert second_responses == []
    assert second.request_count == 1
    assert second.content_count == 1
    assert second.root_comment_count == 0
    assert second.reply_count == 0
    assert len(first_requests) == 4
    assert len(second_requests) == 1
