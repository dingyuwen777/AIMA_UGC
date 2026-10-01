"""正式发布保持安全模式，并在每次外部发送前复核任务。"""

import json
from pathlib import Path

import httpx
import pytest
from aima_ugc.adapters.feishu import FeishuReportPublisher, FeishuReportPublisherConfig
from aima_ugc.bootstrap.feishu_report_publication import (
    FeishuReportPublicationConfigurationError,
    publish_prepared_report_to_feishu,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.jobs import LeaseLostError
from aima_ugc.platform.reporting import ChartSpec
from openpyxl import Workbook
from pydantic import SecretStr


def test_publisher_stops_before_next_http_write_after_fence_loss() -> None:
    """已发送请求可有远端结果，失效后不继续发新请求。"""
    sent = []
    lost = False

    def guard() -> None:
        if lost:
            raise LeaseLostError("stale publication")

    def send(request: httpx.Request) -> httpx.Response:
        nonlocal lost
        sent.append(request)
        lost = True
        return httpx.Response(200, json={"code": 0, "data": {}})

    with httpx.Client(
        base_url="https://open.feishu.cn", transport=httpx.MockTransport(send)
    ) as client:
        publisher = FeishuReportPublisher(
            FeishuReportPublisherConfig(
                app_id="app", app_secret=SecretStr("test"), folder_token="folder"
            ),
            client=client,
            before_request=guard,
        )
        publisher._tenant_access_token = "test-token"
        publisher._request_json("first", "POST", "/test")
        with pytest.raises(LeaseLostError):
            publisher._request_json("second", "POST", "/test")
    assert len(sent) == 1


def test_prepared_publication_rejects_dry_run_before_any_file_or_http_access(
    tmp_path: Path,
) -> None:
    """安全模式判定发生在配置、产物和网络之前，不伪造 published。"""
    settings = load_settings().model_copy(update={"feishu_dry_run": True})
    with pytest.raises(FeishuReportPublicationConfigurationError):
        publish_prepared_report_to_feishu(
            report=None,
            rows=(),
            settings=settings,
            environ={},
            checkpoint=None,
            idempotency_key="report-test",
            progress=lambda _: pytest.fail("不能报告发布成功"),
        )  # type: ignore[arg-type]


def test_data_attachment_is_uploaded_once_and_kept_on_publication_retry(tmp_path: Path) -> None:
    """原始Word和数据Excel均可下载，重试复用上传断点，不删除附件。"""
    word = tmp_path / "report.docx"
    word.write_bytes(b"original-word")
    markdown = tmp_path / "report.md"
    markdown.write_text(
        "# 报告\n\n数据库报告正文。\n\n```mermaid\nxychart-beta\n```\n", encoding="utf-8"
    )
    data = tmp_path / "report-data.xlsx"
    book = Workbook()
    book.active.append(["内容", "本期数据"])
    book.save(data)
    book.close()
    sent = []

    class Checkpoint:
        def __init__(self):  # type: ignore[no-untyped-def]
            self.values = {}

        def get(self, key):  # type: ignore[no-untyped-def]
            return self.values.get(key)

        def set(self, key, value):  # type: ignore[no-untyped-def]
            self.values[key] = value

    checkpoint = Checkpoint()

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        path = request.url.path
        if path.endswith("tenant_access_token/internal"):
            return httpx.Response(200, json={"code": 0, "tenant_access_token": "token"})
        if path.endswith("files/upload_all"):
            token = "word" if b"original-word" in request.content else "data"
            if token == "data":
                assert data.read_bytes() in request.content
            return httpx.Response(200, json={"code": 0, "data": {"file_token": token}})
        if path.endswith("/documents"):
            return httpx.Response(
                200, json={"code": 0, "data": {"document": {"document_id": "doc"}}}
            )
        if path.endswith("/children"):
            if json.loads(request.content)["children"] == [{"block_type": 27, "image": {}}]:
                return httpx.Response(
                    200, json={"code": 0, "data": {"children": [{"block_id": "image"}]}}
                )
            return httpx.Response(200, json={"code": 0, "data": {}})
        if path.endswith("medias/upload_all"):
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "image"}})
        if path.endswith("/blocks/image") and request.method == "PATCH":
            return httpx.Response(200, json={"code": 0, "data": {}})
        pytest.fail(f"不允许额外外部请求：{request.method} {path}")

    with httpx.Client(
        base_url="https://open.feishu.cn", transport=httpx.MockTransport(respond)
    ) as client:
        publisher = FeishuReportPublisher(
            FeishuReportPublisherConfig(
                app_id="app", app_secret=SecretStr("test"), folder_token="folder"
            ),
            client=client,
        )
        for _ in range(2):
            publisher.publish(
                word_path=word,
                markdown_path=markdown,
                chart_specs=(
                    ChartSpec(
                        kind="bar",
                        title="声量",
                        categories=("抖音",),
                        series=((1.0,),),
                        series_names=("内容",),
                    ),
                ),
                chart_workbook_path=None,
                data_workbook_path=data,
                title="报告",
                checkpoint=checkpoint,
                idempotency_key="report-attachment",
            )
    assert len([request for request in sent if request.url.path.endswith("files/upload_all")]) == 2
    assert not any(request.method == "DELETE" for request in sent)
    assert checkpoint.get("data_file_token") == "data"
    links = [
        json.loads(request.content) for request in sent if request.url.path.endswith("/children")
    ]
    assert sum("报告 Excel 下载：" in json.dumps(body, ensure_ascii=False) for body in links) == 1


@pytest.mark.parametrize(
    "cancel_after_token,missing_readback", [(False, False), (True, False), (False, True)]
)
def test_representative_publication_uses_guard_for_both_real_table_upserts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancel_after_token: bool,
    missing_readback: bool,
) -> None:
    """生产发布装配外表和文档镜像表，取消后不继续发送外部写入。"""
    from aima_ugc.adapters.feishu import FeishuBitableClient
    from aima_ugc.bootstrap import representative_selection_publication as module

    from tests.unit.platform.test_feishu_bitable import _MirrorAPI

    root = tmp_path / "secrets"
    root.mkdir()
    (root / "feishu_app_secret").write_text("test-only", encoding="utf-8")
    settings = load_settings().model_copy(
        update={
            "secret_dir": root,
            "external_secret_dir": root,
            "feishu_app_id": "app",
            "feishu_app_token": "external",
            "feishu_table_id": "template",
            "feishu_max_retries": 0,
        }
    )
    values = {
        "external_table": {"table_id": "tbl-external", "name": "外表", "app_token": "external"},
        "embedded_table": {"table_id": "tbl-embedded", "name": "镜像", "app_token": "embedded"},
    }

    class Checkpoint:
        def get(self, key):  # type: ignore[no-untyped-def]
            return values.get(key)

        def set(self, key, value):  # type: ignore[no-untyped-def]
            values[key] = value

    api = _MirrorAPI(external=[], embedded=[])
    sent = []
    guards = []
    clients = []

    def guard() -> None:
        guards.append(True)
        if cancel_after_token and sent:
            raise LeaseLostError("cancelled")

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if missing_readback and api.mutations and request.url.path.endswith("/records"):
            return httpx.Response(200, json={"code": 0, "data": {"items": [], "has_more": False}})
        return api(request)

    def factory(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["before_request"] is guard
        client = httpx.Client(
            base_url="https://open.feishu.cn", transport=httpx.MockTransport(respond)
        )
        clients.append(client)
        return FeishuBitableClient(**kwargs, client=client)

    monkeypatch.setattr(module, "FeishuBitableClient", factory)
    try:

        def publish():  # type: ignore[no-untyped-def]
            return module.publish_representative_rows_to_feishu(
                rows=(
                    {
                        "声音内容/连接": "https://example.test/report",
                        "处理进展": "待处理",
                        "一级标签": "产品体验",
                    },
                ),
                output_dir=tmp_path / "sync",
                settings=settings,
                target_bitable_block_token="embedded_tbl-embedded",
                checkpoint=Checkpoint(),
                before_request=guard,
            )

        if cancel_after_token:
            with pytest.raises(LeaseLostError):
                publish()
            assert api.mutations == []
            assert len(sent) == 1
        elif missing_readback:
            from aima_ugc.adapters.feishu import FeishuAPIError

            with pytest.raises(FeishuAPIError) as failure:
                publish()
            assert failure.value.retryable
            assert not api.records["embedded"]
        else:
            result = publish()
            assert result.mirror_table_id == "tbl-embedded"
            assert len(api.records["external"]) == len(api.records["embedded"]) == 1
            assert len(clients) == 3
            assert len(guards) >= len(sent)
    finally:
        for client in clients:
            client.close()
