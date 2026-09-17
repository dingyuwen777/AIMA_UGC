"""隔离全栈验收使用正式 Worker 与不出网的 TikHub Fixture Transport。"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

from aima_ugc.adapters.providers.tikhub.operations import (
    bilibili,
    douyin,
    kuaishou,
    weibo,
    xiaohongshu,
)
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_reaper,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.entrypoints.worker_main import run_worker_loop
from aima_ugc.modules.collection.providers.transport import (
    ProviderTransportRequest,
    ProviderTransportResponse,
)
from pydantic import SecretStr

_FIXTURES = Path("tests/fixtures/providers/tikhub")


class _CommentFixtureTransport:
    """按生产 Operation 路径提供脱敏响应，未列出的调用立即失败。"""

    def __init__(self) -> None:
        self._routes = {
            xiaohongshu.build_image_detail_request(note_id="fixture").path: (
                "xiaohongshu",
                "detail",
            ),
            xiaohongshu.build_note_comments_request(note_id="fixture").path: (
                "xiaohongshu",
                "comments",
            ),
            xiaohongshu.build_sub_comments_request(note_id="fixture", comment_id="fixture").path: (
                "xiaohongshu",
                "sub_comments",
            ),
            douyin.build_video_detail_request(aweme_id="1").path: ("douyin", "detail"),
            douyin.build_video_comments_request(aweme_id="1").path: ("douyin", "comments"),
            weibo.build_status_detail_request(status_id="1").path: ("weibo", "detail"),
            weibo.build_status_comments_request(status_id="1").path: ("weibo", "comments"),
            bilibili.build_video_detail_request(av_id="1").path: ("bilibili", "detail"),
            bilibili.build_video_comments_request(av_id="1").path: ("bilibili", "comments"),
            kuaishou.build_video_detail_request(photo_id="fixture").path: (
                "kuaishou",
                "detail",
            ),
            kuaishou.build_video_comments_request(photo_id="fixture").path: (
                "kuaishou",
                "comments",
            ),
        }

    def send(self, request: ProviderTransportRequest) -> ProviderTransportResponse:
        try:
            platform, operation = self._routes[request.path]
        except KeyError as exc:
            raise AssertionError("全栈 Fixture 不支持此 TikHub Operation") from exc
        key = {
            "xiaohongshu": "note_id",
            "douyin": "aweme_id",
            "weibo": "status_id",
            "bilibili": "av_id",
            "kuaishou": "photo_id",
        }[platform]
        lookup = str(request.params[key])
        if operation == "detail":
            body = _detail(platform, lookup)
        elif operation == "comments":
            body = _comments(platform, lookup, request.params)
        else:
            body = _xiaohongshu_replies(lookup, request.params)
        return ProviderTransportResponse(status_code=200, body=body)


def _fixture(platform: str, filename: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / platform / filename).read_text(encoding="utf-8"))


def _detail(platform: str, lookup: str) -> dict[str, Any]:
    filename = (
        "image_detail.sanitized.json" if platform == "xiaohongshu" else "detail.sanitized.json"
    )
    body = _fixture(platform, filename)
    title = (
        "爱玛评论补采全栈"
        + {
            "xiaohongshu": "小红书",
            "douyin": "抖音",
            "weibo": "微博",
            "bilibili": "B站",
            "kuaishou": "快手",
        }[platform]
    )
    if platform == "xiaohongshu":
        note = body["data"]["data"][0]["note_list"][0]
        note.update(id=lookup, title=title, comments_count=1)
    elif platform == "douyin":
        video = body["data"]["aweme_detail"]
        video.update(aweme_id=lookup, item_title=title, desc=title)
        video["statistics"]["comment_count"] = 1
    elif platform == "weibo":
        status = body["data"]["detailInfo"]["status"]
        status.update(id=int(lookup), idstr=lookup, text=title, comments_count=1)
    elif platform == "bilibili":
        video = body["data"]["data"]
        video.update(aid=int(lookup), title=title)
        video["stat"].update(aid=int(lookup), reply=1)
    else:
        body["data"]["photos"][0].update(photo_id=lookup, caption=title, comment_count=1)
    return body


def _comments(platform: str, lookup: str, params: dict[str, Any]) -> dict[str, Any]:
    if platform == "kuaishou" and params.get("pcursor"):
        return {"data": {"result": 1, "rootComments": [], "pcursor": ""}}
    body = _fixture(platform, "comments_page1.sanitized.json")
    if platform == "xiaohongshu":
        page = body["data"]["data"]
        page.update(comment_count=1, comment_count_l1=1, has_more=False)
        root = page["comments"][0]
        root.update(note_id=lookup, sub_comment_count=2, sub_comments=[])
    elif platform == "douyin":
        page = body["data"]
        page.update(has_more=0, total=1)
        page["comments"][0].update(aweme_id=lookup, reply_comment_total=0)
    elif platform == "weibo":
        body["data"].pop("moreInfo")
        body["data"]["items"][0]["data"]["total_number"] = 0
    elif platform == "bilibili":
        page = body["data"]["data"]
        page["cursor"]["is_end"] = True
        page["replies"][0].update(oid=int(lookup), rcount=0)
    else:
        root = body["data"]["rootComments"][0]
        root.update(photo_id=lookup, subCommentCount=0)
    return body


def _xiaohongshu_replies(lookup: str, params: dict[str, Any]) -> dict[str, Any]:
    body = _fixture("xiaohongshu", "sub_comments_page1.sanitized.json")
    page = body["data"]["data"]
    reply = page["comments"][0]
    reply["note_id"] = lookup
    if params.get("cursor"):
        reply.update(id="xiaohongshu-comment-reply-page2", content="脱敏第二页回复")
        page.update(cursor="cursor-end", has_more=False)
    else:
        page.update(cursor="cursor-next", has_more=True)
    return body


def main() -> None:
    """仅在隔离全栈环境显式启用，其他环境拒绝启动。"""
    if os.environ.get("AIMA_FULLSTACK_FAKE_TIKHUB") != "1":
        raise RuntimeError("必须显式启用隔离的 Fake TikHub Worker")
    runtime = create_worker_runtime()
    transport = _CommentFixtureTransport()
    registry = create_collection_job_registry(
        runtime=runtime,
        transport_factory=lambda _config: transport,
        secret_resolver=lambda _secret_ref: SecretStr("fixture-secret"),
    )
    worker = create_job_worker(
        runtime=runtime,
        registry=registry,
        worker_id=f"fake-tikhub:{socket.gethostname()}:{os.getpid()}",
        lease_seconds=120,
        retry_delay_seconds=0,
    )
    reaper = create_job_reaper(runtime=runtime, registry=registry, retry_delay_seconds=0)
    try:
        run_worker_loop(worker, reaper)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
