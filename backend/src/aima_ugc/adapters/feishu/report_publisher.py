"""将离线报告发布为飞书原生文档、原始 Word 和可编辑图表 Sheet。"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from aima_ugc.platform.reporting.chart_png import render_chart_png
from aima_ugc.platform.reporting.chart_spec import ChartSpec
from aima_ugc.platform.reporting.feishu_native_document import (
    FeishuNativeBlock,
    FeishuNativeDocument,
    build_feishu_native_document,
)
from aima_ugc.platform.security.secrets import (
    read_secret_file,
    validate_secret_ref,
)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_PENDING_IMPORT_STATUSES = {1, 2}
_RETRIABLE_API_CODES = {99991400, 1061045, 1069923}


class FeishuApiError(RuntimeError):
    """飞书接口未返回可安全消费的成功结果。"""

    def __init__(self, message: str, *, retriable: bool = False) -> None:
        super().__init__(message)
        self.retriable = retriable


@dataclass(frozen=True, slots=True)
class FeishuReportPublisherConfig:
    """一次飞书报告发布所需的最小外部配置。"""

    app_id: str
    app_secret: SecretStr
    folder_token: str
    timeout_seconds: float = 30.0
    poll_interval_seconds: float = 1.0
    max_poll_attempts: int = 120

    def __post_init__(self) -> None:
        if not self.app_id.strip():
            raise ValueError("飞书 app_id 不能为空")
        if not self.app_secret.get_secret_value():
            raise ValueError("飞书 app_secret 不能为空")
        if not self.folder_token.strip():
            raise ValueError("飞书 folder_token 不能为空")
        if self.timeout_seconds <= 0:
            raise ValueError("飞书请求超时必须大于 0")
        if self.poll_interval_seconds < 0:
            raise ValueError("飞书导入轮询间隔不能小于 0")
        if self.max_poll_attempts < 1:
            raise ValueError("飞书导入轮询次数必须大于 0")


@dataclass(frozen=True, slots=True)
class FeishuPublicationSummary:
    """双产物发布后的稳定交付引用。"""

    native_document_token: str
    native_document_url: str
    word_file_token: str
    word_sha256: str
    editable_chart_sheet_token: str | None = None
    editable_chart_sheet_url: str | None = None
    chart_workbook_file_token: str | None = None
    chart_image_block_ids: tuple[str, ...] = ()
    chart_image_sizes: tuple[tuple[int, int], ...] = ()
    import_warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FeishuChartSyncSummary:
    """一次人工同步实际替换的原生文档图片块。"""

    native_document_token: str
    editable_chart_sheet_token: str
    synchronized_chart_count: int
    chart_image_block_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ImportResult:
    token: str
    url: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _DocumentImageBlock:
    """可验证位置的飞书图片块；父节点和索引用于把编辑入口紧贴放在图片下方。"""

    block_id: str
    width: int
    height: int
    parent_id: str
    child_index: int


class FeishuReportPublisher:
    """通过官方 Open API 串行发布报告，避免同目录并发创建。"""

    def __init__(
        self,
        config: FeishuReportPublisherConfig,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._client = client or httpx.Client(
            base_url="https://open.feishu.cn",
            timeout=config.timeout_seconds,
        )
        self._sleep = sleep
        self._tenant_access_token: str | None = None

    def publish(
        self,
        *,
        word_path: Path,
        markdown_path: Path,
        chart_specs: tuple[ChartSpec, ...],
        chart_workbook_path: Path | None,
        title: str,
    ) -> FeishuPublicationSummary:
        """上传原始 Word，直接以原生块重建正文、表格、图片和图表入口。"""

        source_word = _validate_upload_path(word_path, suffix=".docx")
        if not title.strip():
            raise ValueError("飞书报告标题不能为空")
        document = build_feishu_native_document(markdown_path, chart_specs)
        word_bytes = source_word.read_bytes()
        word_sha256 = hashlib.sha256(word_bytes).hexdigest()
        word_file_token = self._upload_file(
            file_name=f"{title}（原始Word下载）.docx",
            content=word_bytes,
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        )
        sheet: _ImportResult | None = None
        chart_file_token: str | None = None
        if chart_workbook_path is not None:
            source_charts = _validate_upload_path(chart_workbook_path, suffix=".xlsx")
            chart_file_token = self._upload_file(
                file_name=f"{title}（可编辑图表源）.xlsx",
                content=source_charts.read_bytes(),
                content_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            )
            sheet = self._import_file(
                file_token=chart_file_token,
                file_extension="xlsx",
                target_type="sheet",
                file_name=f"{title}（可编辑图表）",
            )
            # import_tasks 已完成后，导入源仅是中间件；删除本次精确上传的文件，避免
            # 用户在目标文件夹看到“可编辑图表源.xlsx”，同时保留已创建的原生 Sheet。
            self._delete_file(file_token=chart_file_token)
            chart_file_token = None
        native_document = self._create_document(title=f"{title}（在线编辑）")
        self._write_native_document(
            native_document=native_document,
            document=document,
            sheet_url=None if sheet is None else sheet.url,
            idempotency_source=word_sha256,
        )
        self._append_delivery_links(
            document_token=native_document.token,
            word_file_token=word_file_token,
            sheet_url=None if sheet is None else sheet.url,
            idempotency_source=word_sha256,
        )

        return FeishuPublicationSummary(
            native_document_token=native_document.token,
            native_document_url=native_document.url,
            word_file_token=word_file_token,
            word_sha256=word_sha256,
            editable_chart_sheet_token=None if sheet is None else sheet.token,
            editable_chart_sheet_url=None if sheet is None else sheet.url,
            chart_workbook_file_token=chart_file_token,
            import_warnings=() if sheet is None else sheet.warnings,
        )

    def _create_document(self, *, title: str) -> _ImportResult:
        """创建空白原生文档；正文必须随后使用 block API 写入，不能走 DOCX 导入。"""

        payload = self._request_json(
            "创建飞书原生报告文档",
            "POST",
            "/open-apis/docx/v1/documents",
            json={"folder_token": self._config.folder_token, "title": title},
        )
        document = _nested_mapping(payload, "data", "document")
        if document is None:
            raise FeishuApiError("创建飞书原生报告文档：响应缺少 document")
        token = document.get("document_id")
        if not isinstance(token, str) or not token:
            raise FeishuApiError("创建飞书原生报告文档：响应缺少 document_id")
        url = document.get("url")
        return _ImportResult(
            token=token,
            url=url if isinstance(url, str) and url else f"https://feishu.cn/docx/{token}",
            warnings=(),
        )

    def _write_native_document(
        self,
        *,
        native_document: _ImportResult,
        document: FeishuNativeDocument,
        sheet_url: str | None,
        idempotency_source: str,
    ) -> None:
        """按 Markdown 顺序落块；表格使用 descendant API 保持可编辑单元格结构。"""

        buffered: list[dict[str, Any]] = []
        batch_number = 0

        def flush() -> None:
            nonlocal batch_number
            if not buffered:
                return
            batch_number += 1
            self._append_blocks(
                document_token=native_document.token,
                parent_block_id=native_document.token,
                children=tuple(buffered),
                idempotency_source=f"{idempotency_source}:blocks:{batch_number}",
            )
            buffered.clear()

        for content_index, block in enumerate(document.blocks, start=1):
            if block.kind == "table":
                flush()
                self._append_table(
                    document_token=native_document.token,
                    rows=block.rows,
                    idempotency_source=f"{idempotency_source}:table:{batch_number + 1}",
                )
                continue
            if block.kind in {"image", "chart"}:
                # 飞书不允许在普通 children 请求中直接带图片 token；必须先创建
                # 空图片块，再将素材绑定到那个图片块，最后 PATCH 写入图像信息。
                flush()
                if block.kind == "image":
                    assert block.image_path is not None
                    content = block.image_path.read_bytes()
                    self._append_native_image(
                        document_token=native_document.token,
                        content=content,
                        file_name=block.image_path.name,
                        caption=block.text,
                        idempotency_source=(
                            f"{idempotency_source}:image:{content_index}:"
                            f"{hashlib.sha256(content).hexdigest()}"
                        ),
                    )
                else:
                    assert block.chart_index is not None
                    chart = document.chart_specs[block.chart_index - 1]
                    png, width, height = render_chart_png(chart)
                    self._append_native_image(
                        document_token=native_document.token,
                        content=png,
                        file_name=f"报告图表{block.chart_index:02d}.png",
                        caption=chart.title,
                        width=width,
                        height=height,
                        idempotency_source=(
                            f"{idempotency_source}:chart:{block.chart_index}:"
                            f"{hashlib.sha256(png).hexdigest()}"
                        ),
                    )
                    if sheet_url is not None:
                        buffered.append(
                            _text_block(
                                2,
                                f"编辑图表数据（图表{block.chart_index:02d}）：打开可编辑数据表；"
                                "更新报告时请截图后手动替换本图。",
                                link=sheet_url,
                            )
                        )
                continue
            buffered.extend(
                self._native_block_payloads(
                    block=block,
                )
            )
            if len(buffered) >= 40:
                flush()
        flush()

    def _native_block_payloads(
        self,
        *,
        block: FeishuNativeBlock,
    ) -> tuple[dict[str, Any], ...]:
        if block.kind == "image":
            raise ValueError("飞书图片必须通过专用图片块流程写入")
        if block.kind == "chart":
            raise ValueError("飞书图表必须通过专用图片块流程写入")
        if block.kind == "heading":
            assert block.level is not None
            return (_text_block(block.level + 2, block.text),)
        if block.kind == "paragraph":
            return (_text_block(2, block.text),)
        if block.kind == "bullet":
            return (_text_block(12, block.text),)
        if block.kind == "numbered":
            return (_text_block(13, block.text),)
        if block.kind == "quote":
            return (_text_block(15, block.text),)
        if block.kind == "code":
            return (_text_block(14, block.text),)
        if block.kind == "divider":
            return ({"block_type": 22, "divider": {}},)
        raise ValueError(f"不支持的飞书原生报告块: {block.kind}")

    def _append_native_image(
        self,
        *,
        document_token: str,
        content: bytes,
        file_name: str,
        caption: str,
        width: int | None = None,
        height: int | None = None,
        idempotency_source: str,
    ) -> None:
        actual_width, actual_height = _png_dimensions(content)
        image_block_id = self._create_empty_document_image_block(
            document_token=document_token,
            idempotency_source=f"{idempotency_source}:create",
        )
        image_token = self._upload_document_image(
            parent_node=image_block_id,
            file_name=file_name,
            content=content,
        )
        self._replace_document_image(
            document_token=document_token,
            block_id=image_block_id,
            image_token=image_token,
            width=width or actual_width,
            height=height or actual_height,
            title=caption,
            idempotency_source=f"{idempotency_source}:replace",
        )

    def _create_empty_document_image_block(
        self,
        *,
        document_token: str,
        idempotency_source: str,
    ) -> str:
        """先获取图片 block ID，飞书图片媒体上传必须以它为 parent_node。"""

        payload = self._request_json(
            "创建飞书原生报告图片块",
            "POST",
            f"/open-apis/docx/v1/documents/{document_token}/blocks/{document_token}/children",
            params={
                "document_revision_id": -1,
                "client_token": str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency_source)),
            },
            json={"index": -1, "children": [{"block_type": 27, "image": {}}]},
        )
        children = _nested_list(payload, "data", "children")
        if children is None or len(children) != 1 or not isinstance(children[0], Mapping):
            raise FeishuApiError("创建飞书原生报告图片块：响应缺少图片 block")
        block_id = children[0].get("block_id")
        if not isinstance(block_id, str) or not block_id:
            raise FeishuApiError("创建飞书原生报告图片块：响应缺少图片 block_id")
        return block_id

    def _append_blocks(
        self,
        *,
        document_token: str,
        parent_block_id: str,
        children: tuple[dict[str, Any], ...],
        idempotency_source: str,
    ) -> None:
        for offset in range(0, len(children), 50):
            chunk = children[offset : offset + 50]
            self._request_json(
                "写入飞书原生报告内容块",
                "POST",
                f"/open-apis/docx/v1/documents/{document_token}/blocks/{parent_block_id}/children",
                params={
                    "document_revision_id": -1,
                    "client_token": str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{idempotency_source}:{offset}")
                    ),
                },
                json={"index": -1, "children": list(chunk)},
            )

    def _append_table(
        self,
        *,
        document_token: str,
        rows: tuple[tuple[str, ...], ...],
        idempotency_source: str,
    ) -> None:
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("飞书原生表格行列不一致")
        # descendant API 需要显式提供树中每个 block 的 ID；不能把嵌套对象写进
        # table.children，否则会被飞书按“单元格 ID 数组”校验而拒绝。
        block_namespace = uuid.uuid5(uuid.NAMESPACE_URL, idempotency_source)
        table_id = f"aima_table_{block_namespace.hex}"
        cell_ids: list[str] = []
        descendants: list[dict[str, Any]] = []
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                cell_id = f"aima_cell_{block_namespace.hex}_{row_index}_{column_index}"
                text_id = f"aima_text_{block_namespace.hex}_{row_index}_{column_index}"
                cell_ids.append(cell_id)
                descendants.extend(
                    (
                        {
                            "block_id": cell_id,
                            "block_type": 32,
                            "table_cell": {},
                            "children": [text_id],
                        },
                        {
                            "block_id": text_id,
                            **_text_block(2, value, bold=row_index == 0),
                            "children": [],
                        },
                    )
                )
        descendants.insert(
            0,
            {
                "block_id": table_id,
                "block_type": 31,
                "table": {
                    "property": {
                        "row_size": len(rows),
                        "column_size": len(rows[0]),
                    }
                },
                "children": cell_ids,
            },
        )
        self._request_json(
            "创建飞书原生报告表格",
            "POST",
            f"/open-apis/docx/v1/documents/{document_token}/blocks/{document_token}/descendant",
            params={
                "document_revision_id": -1,
                "client_token": str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency_source)),
            },
            json={
                "index": -1,
                "children_id": [table_id],
                "descendants": descendants,
            },
        )

    def _chart_image_references(
        self,
        *,
        document_token: str,
        expected_image_count: int | None,
        chart_image_positions: tuple[int, ...],
    ) -> tuple[_DocumentImageBlock, ...]:
        """登记原位图表块及其现有尺寸；导入器重排、丢图或失尺寸均拒绝发布。"""

        if expected_image_count is None or expected_image_count < 1:
            raise ValueError("飞书静态图表视图源缺少全部图片数量")

        image_blocks = self._document_image_blocks(document_token)
        if len(image_blocks) != expected_image_count:
            raise FeishuApiError(
                "飞书原生文档导入后的图片数量与静态图表视图源不一致，拒绝创建不可同步报告"
            )
        if max(chart_image_positions) >= len(image_blocks):
            raise FeishuApiError("飞书静态图表位置超出原生文档图片序列")
        chart_blocks = tuple(image_blocks[position] for position in chart_image_positions)
        return chart_blocks

    def _document_image_blocks(self, document_token: str) -> tuple[_DocumentImageBlock, ...]:
        """从根 block 的 children 深度优先遍历，取得实际文档顺序的图片块。"""

        items: list[Any] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token is not None:
                params["page_token"] = page_token
            payload = self._request_json(
                "读取飞书原生文档图片块",
                "GET",
                f"/open-apis/docx/v1/documents/{document_token}/blocks",
                params=params,
            )
            page_items = _nested_list(payload, "data", "items")
            if page_items is None:
                raise FeishuApiError("读取飞书原生文档图片块：响应缺少 items")
            items.extend(page_items)
            data = _nested_mapping(payload, "data")
            if data is None:
                raise FeishuApiError("读取飞书原生文档图片块：响应缺少 data")
            has_more = data.get("has_more", False)
            if has_more is not True:
                break
            next_token = data.get("page_token")
            if not isinstance(next_token, str) or not next_token:
                raise FeishuApiError("读取飞书原生文档图片块：分页缺少 page_token")
            page_token = next_token

        blocks: dict[str, Mapping[str, Any]] = {}
        for item in items:
            if not isinstance(item, Mapping):
                raise FeishuApiError("读取飞书原生文档图片块：items 包含非对象")
            block_id = item.get("block_id")
            if not isinstance(block_id, str) or not block_id or block_id in blocks:
                raise FeishuApiError("读取飞书原生文档图片块：block_id 不合法或重复")
            blocks[block_id] = item
        if document_token not in blocks:
            raise FeishuApiError("读取飞书原生文档图片块：缺少文档根 block")

        visited: set[str] = set()
        image_blocks: list[_DocumentImageBlock] = []

        def visit(block_id: str, *, parent_id: str | None, child_index: int | None) -> None:
            if block_id in visited:
                raise FeishuApiError("飞书原生文档 block 树存在循环或重复引用")
            block = blocks.get(block_id)
            if block is None:
                raise FeishuApiError("飞书原生文档 block 树引用了缺失子节点")
            visited.add(block_id)
            if block.get("block_type") == 27:
                image = block.get("image")
                if not isinstance(image, Mapping):
                    raise FeishuApiError("飞书原生文档图片块缺少 image 属性")
                width = image.get("width")
                height = image.get("height")
                if (
                    isinstance(width, bool)
                    or not isinstance(width, int)
                    or width < 1
                    or isinstance(height, bool)
                    or not isinstance(height, int)
                    or height < 1
                ):
                    raise FeishuApiError("飞书原生文档图片块尺寸不合法，拒绝改变原图位置")
                if parent_id is None or child_index is None:
                    raise FeishuApiError("飞书原生文档图片块不能作为根节点")
                image_blocks.append(
                    _DocumentImageBlock(
                        block_id=block_id,
                        width=width,
                        height=height,
                        parent_id=parent_id,
                        child_index=child_index,
                    )
                )
            children = block.get("children", [])
            if not isinstance(children, list) or any(
                not isinstance(child_id, str) or not child_id for child_id in children
            ):
                raise FeishuApiError("飞书原生文档图片块 children 不合法")
            for index, child_id in enumerate(children):
                visit(child_id, parent_id=block_id, child_index=index)

        visit(document_token, parent_id=None, child_index=None)
        if len(visited) != len(blocks):
            raise FeishuApiError("飞书原生文档 block 树存在未连接节点，拒绝推断图片位置")
        if not image_blocks:
            raise FeishuApiError("飞书原生文档导入后未找到图片块")
        return tuple(image_blocks)

    def sync_chart_images(
        self,
        *,
        native_document_token: str,
        editable_chart_sheet_token: str,
        chart_image_block_ids: tuple[str, ...],
        chart_image_sizes: tuple[tuple[int, int], ...],
        chart_specs: tuple[ChartSpec, ...],
    ) -> FeishuChartSyncSummary:
        """读取固定 Sheet 数据区并替换对应图片，不重建或覆盖原生文档正文。"""

        if not native_document_token.strip() or not editable_chart_sheet_token.strip():
            raise ValueError("飞书图表同步缺少原生文档或电子表格 token")
        if (
            len(chart_image_block_ids) != len(chart_specs)
            or len(chart_image_sizes) != len(chart_specs)
            or not chart_specs
        ):
            raise ValueError("飞书图表同步清单的图片块与图表规格数量不一致")
        if any(not block_id.strip() for block_id in chart_image_block_ids):
            raise ValueError("飞书图表同步清单包含空图片块 ID")

        for index, (block_id, image_size, spec) in enumerate(
            zip(chart_image_block_ids, chart_image_sizes, chart_specs, strict=True), start=1
        ):
            width, height = _valid_image_size(image_size)
            synchronized_spec = self._read_chart_spec_from_sheet(
                spreadsheet_token=editable_chart_sheet_token,
                chart_index=index,
                baseline=spec,
            )
            png, _png_width, _png_height = render_chart_png(synchronized_spec)
            image_token = self._upload_document_image(
                parent_node=block_id,
                file_name=f"同步图表{index:02d}.png",
                content=png,
            )
            self._replace_document_image(
                document_token=native_document_token,
                block_id=block_id,
                image_token=image_token,
                width=width,
                height=height,
                title=synchronized_spec.title,
                idempotency_source=(
                    f"{editable_chart_sheet_token}:{index}:{block_id}:"
                    f"{hashlib.sha256(png).hexdigest()}"
                ),
            )

        return FeishuChartSyncSummary(
            native_document_token=native_document_token,
            editable_chart_sheet_token=editable_chart_sheet_token,
            synchronized_chart_count=len(chart_specs),
            chart_image_block_ids=chart_image_block_ids,
        )

    def _read_chart_spec_from_sheet(
        self,
        *,
        spreadsheet_token: str,
        chart_index: int,
        baseline: ChartSpec,
    ) -> ChartSpec:
        range_name = _chart_sheet_range(chart_index, baseline)
        payload = self._request_json(
            "读取飞书可编辑图表数据",
            "GET",
            (
                f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/"
                f"{quote(range_name, safe='')}"
            ),
        )
        data = _nested_mapping(payload, "data")
        value_range = None if data is None else data.get("valueRange", data.get("value_range"))
        if not isinstance(value_range, Mapping):
            raise FeishuApiError("读取飞书可编辑图表数据：响应缺少 valueRange")
        raw_values = value_range.get("values")
        if not isinstance(raw_values, list):
            raise FeishuApiError("读取飞书可编辑图表数据：响应缺少 values")
        return _chart_spec_from_sheet_values(raw_values, baseline=baseline)

    def _upload_document_image(
        self,
        *,
        parent_node: str,
        file_name: str,
        content: bytes,
    ) -> str:
        if not content or len(content) > _MAX_UPLOAD_BYTES:
            raise ValueError("飞书同步图表 PNG 文件大小不合法")
        payload = self._request_json(
            "上传飞书原生文档图表图片",
            "POST",
            "/open-apis/drive/v1/medias/upload_all",
            data={
                "file_name": file_name,
                "parent_type": "docx_image",
                "parent_node": parent_node,
                "size": str(len(content)),
            },
            files={"file": (file_name, content, "image/png")},
        )
        token = _nested_string(payload, "data", "file_token")
        if token is None:
            raise FeishuApiError("上传飞书原生文档图表图片：响应缺少 file_token")
        return token

    def _replace_document_image(
        self,
        *,
        document_token: str,
        block_id: str,
        image_token: str,
        width: int,
        height: int,
        title: str,
        idempotency_source: str,
    ) -> None:
        self._request_json(
            "替换飞书原生文档图表图片",
            "PATCH",
            f"/open-apis/docx/v1/documents/{document_token}/blocks/{block_id}",
            params={
                "document_revision_id": -1,
                "client_token": str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency_source)),
            },
            json={
                "replace_image": {
                    "token": image_token,
                    "width": width,
                    "height": height,
                    "align": 2,
                    "caption": {"content": title},
                }
            },
        )

    def _access_token(self) -> str:
        if self._tenant_access_token is not None:
            return self._tenant_access_token
        payload = self._request_json(
            "获取 tenant_access_token",
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self._config.app_id,
                "app_secret": self._config.app_secret.get_secret_value(),
            },
            authenticated=False,
        )
        token = payload.get("tenant_access_token")
        if not isinstance(token, str) or not token:
            raise FeishuApiError("获取 tenant_access_token：响应缺少访问令牌")
        self._tenant_access_token = token
        return token

    def _upload_file(self, *, file_name: str, content: bytes, content_type: str) -> str:
        if not content:
            raise ValueError("飞书不允许上传空文件")
        if len(content) > _MAX_UPLOAD_BYTES:
            raise ValueError("飞书单次上传文件不能超过 20 MB")
        payload = self._request_json(
            "上传报告文件",
            "POST",
            "/open-apis/drive/v1/files/upload_all",
            data={
                "file_name": file_name,
                "parent_type": "explorer",
                "parent_node": self._config.folder_token,
                "size": str(len(content)),
            },
            files={"file": (file_name, content, content_type)},
        )
        file_token = _nested_string(payload, "data", "file_token")
        if file_token is None:
            raise FeishuApiError("上传报告文件：响应缺少 file_token")
        return file_token

    def _delete_file(self, *, file_token: str) -> None:
        """删除本次 Sheet 导入专用的精确源文件，不按名称或目录做模糊清理。"""

        if not file_token.strip():
            raise ValueError("飞书待删除文件 token 不能为空")
        self._request_json(
            "清理飞书图表导入源文件",
            "DELETE",
            f"/open-apis/drive/v1/files/{quote(file_token, safe='')}",
            # upload_all 产生的是 Drive 普通文件；删除接口要求显式声明类型。
            params={"type": "file"},
        )

    def _import_file(
        self,
        *,
        file_token: str,
        file_extension: str,
        target_type: str,
        file_name: str,
    ) -> _ImportResult:
        payload = self._request_json(
            "创建飞书原生文档导入任务",
            "POST",
            "/open-apis/drive/v1/import_tasks",
            json={
                "file_extension": file_extension,
                "file_token": file_token,
                "type": target_type,
                "file_name": file_name,
                "point": {"mount_type": 1, "mount_key": self._config.folder_token},
            },
        )
        ticket = _nested_string(payload, "data", "ticket")
        if ticket is None:
            raise FeishuApiError("创建飞书原生文档导入任务：响应缺少 ticket")
        return self._wait_for_import(ticket)

    def _wait_for_import(self, ticket: str) -> _ImportResult:
        for attempt in range(self._config.max_poll_attempts):
            payload = self._request_json(
                "查询飞书原生文档导入结果",
                "GET",
                f"/open-apis/drive/v1/import_tasks/{ticket}",
            )
            result = _nested_mapping(payload, "data", "result")
            if result is None:
                raise FeishuApiError("查询飞书原生文档导入结果：响应缺少 result")
            status = result.get("job_status")
            if status == 0:
                token = result.get("token")
                url = result.get("url")
                if not isinstance(token, str) or not token or not isinstance(url, str) or not url:
                    raise FeishuApiError("查询飞书原生文档导入结果：成功响应缺少 token/url")
                raw_extra = result.get("extra", [])
                warnings = (
                    tuple(str(value) for value in raw_extra) if isinstance(raw_extra, list) else ()
                )
                return _ImportResult(token=token, url=url, warnings=warnings)
            if status not in _PENDING_IMPORT_STATUSES:
                error_message = result.get("job_error_msg", "unknown error")
                raise FeishuApiError(
                    self._redact(f"飞书原生文档导入失败：status={status}, msg={error_message}")
                )
            if attempt + 1 < self._config.max_poll_attempts:
                self._sleep(self._config.poll_interval_seconds)
        raise FeishuApiError("飞书原生文档导入等待超时", retriable=True)

    def _append_delivery_links(
        self,
        *,
        document_token: str,
        word_file_token: str,
        sheet_url: str | None,
        idempotency_source: str,
    ) -> None:
        client_token = str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency_source))
        children: list[dict[str, Any]] = [
            {
                "block_type": 2,
                "text": {
                    "elements": [
                        {
                            "text_run": {
                                "content": "原始 Word 下载：",
                                "text_element_style": {},
                            }
                        },
                        {"mention_doc": {"token": word_file_token, "obj_type": 12}},
                    ],
                    "style": {},
                },
            }
        ]
        if sheet_url is not None:
            children.append(_text_block(2, "可编辑图表数据：打开飞书原生电子表格", link=sheet_url))
        self._request_json(
            "在飞书原生文档中添加报告交付入口",
            "POST",
            (f"/open-apis/docx/v1/documents/{document_token}/blocks/{document_token}/children"),
            params={"document_revision_id": -1, "client_token": client_token},
            json={"index": -1, "children": children},
        )

    def _append_chart_edit_links(
        self,
        *,
        document_token: str,
        sheet_url: str,
        chart_blocks: tuple[_DocumentImageBlock, ...],
        idempotency_source: str,
    ) -> None:
        """在每个原位图表的同级下一行加入对应 Sheet 的编辑入口。"""

        for chart_index, block in reversed(tuple(enumerate(chart_blocks, start=1))):
            client_token = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{idempotency_source}:{block.parent_id}:{block.child_index}",
                )
            )
            self._request_json(
                "在飞书原生文档图表下方添加编辑入口",
                "POST",
                (
                    f"/open-apis/docx/v1/documents/{document_token}"
                    f"/blocks/{block.parent_id}/children"
                ),
                params={"document_revision_id": -1, "client_token": client_token},
                json={
                    "index": block.child_index + 1,
                    "children": [
                        {
                            "block_type": 2,
                            "text": {
                                "elements": [
                                    {
                                        "text_run": {
                                            "content": (
                                                f"编辑此图表（图表{chart_index:02d}）："
                                                "打开可编辑数据表"
                                            ),
                                            "text_element_style": {"link": {"url": sheet_url}},
                                        }
                                    }
                                ],
                                "style": {},
                            },
                        }
                    ],
                },
            )

    def _request_json(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if authenticated:
            headers["Authorization"] = f"Bearer {self._access_token()}"
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise FeishuApiError(
                self._redact(f"{operation}：网络请求失败 ({type(exc).__name__})"),
                retriable=True,
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise FeishuApiError(
                f"{operation}：飞书返回非 JSON 响应，HTTP {response.status_code}",
                retriable=response.status_code == 429 or response.status_code >= 500,
            ) from exc
        if not isinstance(payload, Mapping):
            raise FeishuApiError(f"{operation}：飞书返回的 JSON 不是对象")
        code = payload.get("code")
        if response.is_error or code not in {0, None}:
            message = self._redact(str(payload.get("msg", "unknown error")))
            retriable = (
                response.status_code == 429
                or response.status_code >= 500
                or code in _RETRIABLE_API_CODES
            )
            raise FeishuApiError(
                f"{operation}失败：HTTP {response.status_code}, code={code}, msg={message}",
                retriable=retriable,
            )
        return payload

    def _redact(self, value: str) -> str:
        secret = self._config.app_secret.get_secret_value()
        return value.replace(secret, "[REDACTED]") if secret else value


def load_feishu_report_publisher_config(
    environ: Mapping[str, str],
    *,
    secret_root: Path,
) -> FeishuReportPublisherConfig | None:
    """从显式开关和 Secret 文件加载离线飞书发布配置。"""

    enabled = _parse_bool(environ.get("AIMA_FEISHU_REPORT_ENABLED", "false"))
    if not enabled:
        return None
    app_id = _required_env(environ, "AIMA_FEISHU_APP_ID")
    folder_token = _required_env(environ, "AIMA_FEISHU_FOLDER_TOKEN")
    secret_ref = validate_secret_ref(
        environ.get("AIMA_FEISHU_APP_SECRET_REF", "feishu/report_app_secret")
    )
    root = Path(secret_root)
    app_secret = read_secret_file(root / secret_ref, root=root)
    return FeishuReportPublisherConfig(
        app_id=app_id,
        app_secret=app_secret,
        folder_token=folder_token,
    )


def _validate_upload_path(path: Path, *, suffix: str) -> Path:
    source = Path(path)
    if source.suffix.lower() != suffix:
        raise ValueError(f"飞书上传文件必须是 {suffix}")
    if not source.is_file():
        raise FileNotFoundError(source)
    size = source.stat().st_size
    if size <= 0:
        raise ValueError("飞书不允许上传空文件")
    if size > _MAX_UPLOAD_BYTES:
        raise ValueError("飞书单次上传文件不能超过 20 MB")
    return source


def _chart_sheet_range(chart_index: int, spec: ChartSpec) -> str:
    if chart_index < 1:
        raise ValueError("图表索引必须从 1 开始")
    max_column = len(spec.series) + 1
    max_row = len(spec.categories) + 1
    return f"图表{chart_index:02d}!A1:{_excel_column_name(max_column)}{max_row}"


def _excel_column_name(index: int) -> str:
    if index < 1:
        raise ValueError("Excel 列号必须大于 0")
    parts: list[str] = []
    current = index
    while current:
        current, remainder = divmod(current - 1, 26)
        parts.append(chr(ord("A") + remainder))
    return "".join(reversed(parts))


def _chart_spec_from_sheet_values(raw_values: list[Any], *, baseline: ChartSpec) -> ChartSpec:
    expected_rows = len(baseline.categories) + 1
    expected_columns = len(baseline.series) + 1
    if len(raw_values) < expected_rows:
        raise FeishuApiError("飞书可编辑图表数据行数不足，拒绝覆盖报告图片")
    rows: list[list[Any]] = []
    for raw_row in raw_values[:expected_rows]:
        if not isinstance(raw_row, list) or len(raw_row) < expected_columns:
            raise FeishuApiError("飞书可编辑图表数据列数不足，拒绝覆盖报告图片")
        rows.append(raw_row[:expected_columns])
    categories = tuple(_required_sheet_text(row[0], field="分类") for row in rows[1:])
    series_names = tuple(_required_sheet_text(value, field="系列名称") for value in rows[0][1:])
    series = tuple(
        tuple(_required_sheet_number(row[column], field="图表数值") for row in rows[1:])
        for column in range(1, expected_columns)
    )
    maximum = max((value for values in series for value in values), default=0.0)
    y_max = baseline.y_max
    if y_max is not None and maximum > y_max:
        y_max = max(1.0, maximum + max(1.0, maximum * 0.1))
    return ChartSpec(
        kind=baseline.kind,
        title=baseline.title,
        categories=categories,
        series=series,
        series_names=series_names,
        pie_labels=categories if baseline.kind == "pie" else baseline.pie_labels,
        y_min=baseline.y_min,
        y_max=y_max,
        bar_direction=baseline.bar_direction,
    )


def _required_sheet_text(value: Any, *, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    raise FeishuApiError(f"飞书可编辑图表{field}为空，拒绝覆盖报告图片")


def _required_sheet_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise FeishuApiError(f"飞书可编辑图表{field}不是数值，拒绝覆盖报告图片")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            pass
    raise FeishuApiError(f"飞书可编辑图表{field}不是数值，拒绝覆盖报告图片")


def _valid_image_size(value: tuple[int, int]) -> tuple[int, int]:
    """同步时沿用飞书当前图片块尺寸，不让重渲染图片改变正文排版。"""

    if len(value) != 2:
        raise ValueError("飞书图表同步清单图片尺寸不合法")
    width, height = value
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width < 1
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height < 1
    ):
        raise ValueError("飞书图表同步清单图片尺寸不合法")
    return width, height


def _nested_mapping(payload: Mapping[str, Any], *path: str) -> Mapping[str, Any] | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, Mapping) else None


def _nested_list(payload: Mapping[str, Any], *path: str) -> list[Any] | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, list) else None


def _nested_string(payload: Mapping[str, Any], *path: str) -> str | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, str) and value else None


def _required_env(environ: Mapping[str, str], key: str) -> str:
    value = environ.get(key, "").strip()
    if not value:
        raise ValueError(f"启用飞书报告发布时必须配置 {key}")
    return value


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("AIMA_FEISHU_REPORT_ENABLED 必须是 true/false")


def _text_block(
    block_type: int,
    content: str,
    *,
    link: str | None = None,
    bold: bool = False,
) -> dict[str, Any]:
    """按 block 类型写入飞书要求的专用富文本字段。"""

    style: dict[str, Any] = {}
    if link is not None:
        style["link"] = {"url": link}
    if bold:
        style["bold"] = True
    text_field = {
        2: "text",
        3: "heading1",
        4: "heading2",
        5: "heading3",
        12: "bullet",
        13: "ordered",
        14: "code",
        15: "quote",
    }.get(block_type)
    if text_field is None:
        raise ValueError(f"飞书 block_type={block_type} 不是受支持的文本块")
    return {
        "block_type": block_type,
        text_field: {
            "elements": [{"text_run": {"content": content, "text_element_style": style}}],
            "style": {},
        },
    }


def _png_dimensions(content: bytes) -> tuple[int, int]:
    """PNG 尺寸直接从文件头读取，避免为飞书图片块再引入图像依赖。"""

    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n" or content[12:16] != b"IHDR":
        raise ValueError("飞书原生文档图片必须是有效 PNG")
    width = int.from_bytes(content[16:20], "big")
    height = int.from_bytes(content[20:24], "big")
    if width < 1 or height < 1:
        raise ValueError("飞书原生文档图片尺寸不合法")
    return width, height
