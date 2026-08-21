"""API 进程装配与健康检查。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.responses import JSONResponse, StreamingResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aima_ugc.contracts.http import (
    CollectionCapabilitiesResponse,
    CollectionRunCreatedResponse,
    CollectionRunCreateRequest,
    CollectionRunResponse,
    CollectionRuntimeListQuery,
    CollectionRuntimeListResponse,
    CollectionRuntimeSummaryResponse,
    ContentAnalysisCreatedResponse,
    ContentAnalysisSubmitRequest,
    ContentDetailResponse,
    ContentListQuery,
    ContentListResponse,
    DataExportCreatedResponse,
    DataExportListResponse,
    DataExportResponse,
    DataExportSubmitRequest,
    GlobalRelevanceConfigRequest,
    GlobalRelevanceConfigResponse,
    HttpErrorItem,
    HttpErrorResponse,
    ImportBatchCreatedResponse,
    ImportBatchListQuery,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportBatchSummaryResponse,
    JobStatusResponse,
    KeywordPackCreateRequest,
    KeywordPackKeywordCreateRequest,
    KeywordPackResponse,
)
from aima_ugc.modules.collection.http import (
    CollectionConflict,
    CollectionHttpService,
    CollectionResourceNotFound,
    CollectionRuntimeCursorUnavailable,
    InvalidCollectionRuntimeCursor,
)
from aima_ugc.modules.content.http import (
    ContentCursorUnavailable,
    ContentHttpService,
    ContentResourceNotFound,
    ContentSelectionEmpty,
    InvalidContentCursor,
)
from aima_ugc.modules.ingestion.http import (
    ImportConflict,
    ImportCursorUnavailable,
    ImportHttpService,
    ImportResourceNotFound,
    ImportUploadTooLarge,
    InvalidImportCursor,
    InvalidImportFile,
    RelevanceConfigurationError,
)
from aima_ugc.modules.ingestion.xlsx_security import MAX_MULTIPART_BODY_BYTES
from aima_ugc.modules.reporting.http import (
    DataExportNotReady,
    DataExportResourceNotFound,
    ReportingHttpService,
)
from aima_ugc.platform.health import ReadinessReport
from aima_ugc.platform.logging import log_event

from .runtime import PlatformRuntime, create_platform_runtime

ReadinessCheck = Callable[[], ReadinessReport]
_LOGGER = logging.getLogger("aima_ugc")


class _RequestBodyTooLarge(RuntimeError):
    pass


class _RequestContextMiddleware:
    """为每个请求建立 request_id，并对 multipart 实际接收字节执行硬上限。"""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        headers = {key.lower(): value for key, value in scope.get("headers", ())}
        is_multipart = headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data")
        declared_length = _parse_content_length(headers.get(b"content-length"))
        if (
            is_multipart
            and declared_length is not None
            and declared_length > MAX_MULTIPART_BODY_BYTES
        ):
            await _send_body_limit_error(scope, receive, send, request_id)
            return

        received = 0
        body_too_large = False

        async def limited_receive() -> Message:
            nonlocal body_too_large, received
            message = await receive()
            if is_multipart and message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_MULTIPART_BODY_BYTES:
                    body_too_large = True
                    raise _RequestBodyTooLarge
            return message

        # Starlette 的 multipart 解析器会把接收流异常转换为 400。multipart 响应体在请求解析完成前
        # 暂存，才能在无 Content-Length 的实际字节超限时稳定改写为统一 413 Contract。
        buffered_messages: list[Message] = []

        async def response_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", ()))
                if not any(key.lower() == b"x-request-id" for key, _ in raw_headers):
                    raw_headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": raw_headers}
            if is_multipart:
                buffered_messages.append(message)
            else:
                await send(message)

        try:
            await self._app(scope, limited_receive, response_send)
        except _RequestBodyTooLarge:
            body_too_large = True
        if body_too_large:
            await _send_body_limit_error(scope, receive, send, request_id)
            return
        for message in buffered_messages:
            await send(message)


def _parse_content_length(value: bytes | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


async def _send_body_limit_error(
    scope: Scope,
    receive: Receive,
    send: Send,
    request_id: str,
) -> None:
    response = _error_response(
        status_code=413,
        request_id=request_id,
        title="上传请求过大",
        detail="multipart 请求体超过 550 MiB 上限。",
        code="multipart_body_too_large",
        field="body",
    )
    response.headers["x-request-id"] = request_id
    await response(scope, receive, send)


class HealthResponse(BaseModel):
    """进程存活检查响应。"""

    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    """readiness 子检查，不包含异常详情。"""

    model_config = ConfigDict(extra="forbid")
    database: Literal["ok", "error"]
    artifact_store: Literal["ok", "error"]
    log_directory: Literal["ok", "error"]


class ReadinessResponse(BaseModel):
    """依赖就绪检查响应。"""

    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "error"]
    checks: ReadinessChecks


def create_app(
    *,
    readiness_check: ReadinessCheck | None = None,
    import_service: ImportHttpService | None = None,
    content_service: ContentHttpService | None = None,
    reporting_service: ReportingHttpService | None = None,
    collection_service: CollectionHttpService | None = None,
) -> FastAPI:
    """创建 API 应用；默认 runtime 延迟到启动或第一次 readiness 检查。"""
    runtime: PlatformRuntime | None = None
    runtime_failed = False

    def get_runtime() -> PlatformRuntime | None:
        nonlocal runtime, runtime_failed
        if runtime is None and not runtime_failed:
            try:
                runtime = create_platform_runtime("api")
            except OSError, ValueError:
                runtime_failed = True
        return runtime

    def current_readiness() -> ReadinessReport:
        if readiness_check is not None:
            return readiness_check()
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            return ReadinessReport(
                database="error",
                artifact_store="error",
                log_directory="error",
            )
        return resolved_runtime.check_readiness()

    def current_import_service() -> ImportHttpService:
        if import_service is not None:
            return import_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Import Service 依赖不可用")
        from aima_ugc.bootstrap.import_http import PostgresImportHttpService

        return PostgresImportHttpService(resolved_runtime)

    def current_content_service() -> ContentHttpService:
        if content_service is not None:
            return content_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Content Service 依赖不可用")
        from aima_ugc.bootstrap.content_http import PostgresContentHttpService

        return PostgresContentHttpService(resolved_runtime)

    def current_reporting_service() -> ReportingHttpService:
        if reporting_service is not None:
            return reporting_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Reporting Service 依赖不可用")
        from aima_ugc.bootstrap.reporting_http import PostgresReportingHttpService

        return PostgresReportingHttpService(resolved_runtime)

    def current_collection_service() -> CollectionHttpService:
        if collection_service is not None:
            return collection_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Collection Service 依赖不可用")
        from aima_ugc.bootstrap.collection_http import PostgresCollectionHttpService

        return PostgresCollectionHttpService(resolved_runtime)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if readiness_check is None:
            get_runtime()
        try:
            yield
        finally:
            if runtime is not None:
                runtime.close()

    application = FastAPI(title="AIMA_UGC API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(_RequestContextMiddleware)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = tuple(
            HttpErrorItem(
                field=".".join(str(item) for item in error["loc"]),
                code=str(error["type"]),
                message="请求字段不合法。",
            )
            for error in exc.errors()
        )
        return _error_response(
            status_code=422,
            request_id=_request_id(request),
            title="请求校验失败",
            detail="请求未通过 Contract 校验。",
            code="request_validation_error",
            errors=errors,
        )

    @application.exception_handler(ImportResourceNotFound)
    async def resource_not_found(request: Request, _: ImportResourceNotFound) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="资源不存在",
            detail="请求的资源不存在。",
            code="resource_not_found",
        )

    @application.exception_handler(ImportConflict)
    async def resource_conflict(request: Request, _: ImportConflict) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="资源冲突",
            detail="同名资源已经存在。",
            code="resource_conflict",
        )

    @application.exception_handler(ImportUploadTooLarge)
    async def upload_too_large(request: Request, _: ImportUploadTooLarge) -> JSONResponse:
        return _error_response(
            status_code=413,
            request_id=_request_id(request),
            title="Excel 资源过大",
            detail="Excel 文件或声明的解压资源超过安全上限。",
            code="xlsx_resource_too_large",
            field="body.file",
        )

    @application.exception_handler(InvalidImportFile)
    async def invalid_import(request: Request, _: InvalidImportFile) -> JSONResponse:
        return _error_response(
            status_code=422,
            request_id=_request_id(request),
            title="Excel 文件不合法",
            detail="文件不是受支持且结构合法的 XLSX。",
            code="invalid_xlsx",
            field="body.file",
        )

    @application.exception_handler(RelevanceConfigurationError)
    async def relevance_unavailable(
        request: Request, _: RelevanceConfigurationError
    ) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="相关性配置不可用",
            detail="全局 Relevance 词包尚未配置或没有有效关键词。",
            code="relevance_config_unavailable",
        )

    @application.exception_handler(InvalidImportCursor)
    async def invalid_import_cursor(request: Request, _: InvalidImportCursor) -> JSONResponse:
        return _error_response(
            status_code=400,
            request_id=_request_id(request),
            title="分页游标不合法",
            detail="分页游标无效、已过期或与当前查询条件不匹配。",
            code="invalid_import_cursor",
            field="query.cursor",
        )

    @application.exception_handler(ImportCursorUnavailable)
    async def import_cursor_unavailable(
        request: Request, _: ImportCursorUnavailable
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            request_id=_request_id(request),
            title="分页服务暂不可用",
            detail="分页服务配置不可用，请使用 request_id 联系管理员。",
            code="import_cursor_unavailable",
        )

    @application.exception_handler(ContentResourceNotFound)
    async def content_resource_not_found(
        request: Request, _: ContentResourceNotFound
    ) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="内容资源不存在",
            detail="请求的内容或任务不存在。",
            code="content_resource_not_found",
        )

    @application.exception_handler(ContentSelectionEmpty)
    async def content_selection_empty(request: Request, _: ContentSelectionEmpty) -> JSONResponse:
        return _error_response(
            status_code=422,
            request_id=_request_id(request),
            title="内容选择为空",
            detail="当前选择条件没有可处理的内容。",
            code="content_selection_empty",
            field="body.targets",
        )

    @application.exception_handler(InvalidContentCursor)
    async def invalid_content_cursor(request: Request, _: InvalidContentCursor) -> JSONResponse:
        return _error_response(
            status_code=400,
            request_id=_request_id(request),
            title="分页游标不合法",
            detail="分页游标无效、已过期或与当前查询条件不匹配。",
            code="invalid_content_cursor",
            field="query.cursor",
        )

    @application.exception_handler(ContentCursorUnavailable)
    async def content_cursor_unavailable(
        request: Request, _: ContentCursorUnavailable
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            request_id=_request_id(request),
            title="分页服务暂不可用",
            detail="声音广场分页服务配置不可用，请使用 request_id 联系管理员。",
            code="content_cursor_unavailable",
        )

    @application.exception_handler(CollectionResourceNotFound)
    async def collection_resource_not_found(
        request: Request, _: CollectionResourceNotFound
    ) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="采集资源不存在",
            detail="请求的采集运行、导入批次、内容或 Provider 配置不存在。",
            code="collection_resource_not_found",
        )

    @application.exception_handler(CollectionConflict)
    async def collection_conflict(request: Request, _: CollectionConflict) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="采集运行无法创建",
            detail="当前配置或资源状态不允许创建采集运行。",
            code="collection_conflict",
        )

    @application.exception_handler(InvalidCollectionRuntimeCursor)
    async def invalid_collection_runtime_cursor(
        request: Request, _: InvalidCollectionRuntimeCursor
    ) -> JSONResponse:
        return _error_response(
            status_code=400,
            request_id=_request_id(request),
            title="分页游标不合法",
            detail="分页游标无效、已过期或与当前查询条件不匹配。",
            code="invalid_collection_runtime_cursor",
            field="query.cursor",
        )

    @application.exception_handler(CollectionRuntimeCursorUnavailable)
    async def collection_runtime_cursor_unavailable(
        request: Request, _: CollectionRuntimeCursorUnavailable
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            request_id=_request_id(request),
            title="分页服务暂不可用",
            detail="采集运行分页服务配置不可用，请使用 request_id 联系管理员。",
            code="collection_runtime_cursor_unavailable",
        )

    @application.exception_handler(DataExportResourceNotFound)
    async def data_export_resource_not_found(
        request: Request, _: DataExportResourceNotFound
    ) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="导出记录不存在",
            detail="请求的导出记录不存在。",
            code="data_export_not_found",
        )

    @application.exception_handler(DataExportNotReady)
    async def data_export_not_ready(request: Request, _: DataExportNotReady) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="导出文件尚未就绪",
            detail="导出任务尚未成功完成，当前不能下载。",
            code="data_export_not_ready",
        )

    @application.exception_handler(StarletteHttpException)
    async def http_error(request: Request, exc: StarletteHttpException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            request_id=_request_id(request),
            title="HTTP 请求失败",
            detail="请求的路径或方法不可用。",
            code="http_error",
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        log_event(
            _LOGGER,
            logging.ERROR,
            "api.request_failed",
            "API 请求处理失败",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
        )
        return _error_response(
            status_code=500,
            request_id=request_id,
            title="服务器内部错误",
            detail="请求处理失败，请使用 request_id 定位日志。",
            code="internal_error",
        )

    @application.get(
        "/health/live",
        operation_id="healthLive",
        response_model=HealthResponse,
        tags=["health"],
    )
    def health_live() -> HealthResponse:
        """返回进程存活状态，不检查外部依赖。"""
        return HealthResponse(status="ok")

    @application.get(
        "/health/ready",
        operation_id="healthReady",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse}},
        tags=["health"],
    )
    def health_ready(response: Response) -> ReadinessResponse:
        """检查 PostgreSQL、Artifact 目录和日志目录，不泄露失败详情。"""
        report = current_readiness()
        response.status_code = (
            status.HTTP_200_OK if report.ready else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return ReadinessResponse(
            status="ok" if report.ready else "error",
            checks=ReadinessChecks(
                database=report.database,
                artifact_store=report.artifact_store,
                log_directory=report.log_directory,
            ),
        )

    @application.get(
        "/api/v1/collection-capabilities",
        operation_id="getCollectionCapabilities",
        response_model=CollectionCapabilitiesResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["collection"],
    )
    def get_collection_capabilities() -> CollectionCapabilitiesResponse:
        return current_collection_service().get_capabilities()

    @application.post(
        "/api/v1/collection-runs",
        operation_id="createCollectionRun",
        response_model=CollectionRunCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection"],
    )
    def create_collection_run(
        body: CollectionRunCreateRequest,
        request: Request,
    ) -> CollectionRunCreatedResponse:
        return current_collection_service().create_run(
            body,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/collection-runs/{run_id}",
        operation_id="getCollectionRun",
        response_model=CollectionRunResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection"],
    )
    def get_collection_run(run_id: UUID) -> CollectionRunResponse:
        return current_collection_service().get_run(run_id)

    @application.get(
        "/api/v1/collection-runtime/runs",
        operation_id="listCollectionRuntimeRuns",
        response_model=CollectionRuntimeListResponse,
        responses={
            400: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            503: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection"],
    )
    def list_collection_runtime_runs(
        query: Annotated[CollectionRuntimeListQuery, Query()],
    ) -> CollectionRuntimeListResponse:
        return current_collection_service().list_runtime_runs(query)

    @application.get(
        "/api/v1/collection-runtime/summary",
        operation_id="getCollectionRuntimeSummary",
        response_model=CollectionRuntimeSummaryResponse,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection"],
    )
    def get_collection_runtime_summary() -> CollectionRuntimeSummaryResponse:
        return current_collection_service().get_runtime_summary()

    @application.get(
        "/api/v1/contents",
        operation_id="listContents",
        response_model=ContentListResponse,
        responses={
            400: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            503: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def list_contents(
        query: Annotated[ContentListQuery, Query()],
    ) -> ContentListResponse:
        return current_content_service().list_contents(query)

    @application.get(
        "/api/v1/contents/{content_id}",
        operation_id="getContent",
        response_model=ContentDetailResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def get_content(content_id: UUID) -> ContentDetailResponse:
        return current_content_service().get_content(content_id)

    @application.post(
        "/api/v1/content-analysis-requests",
        operation_id="createContentAnalysis",
        response_model=ContentAnalysisCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def create_content_analysis(
        body: ContentAnalysisSubmitRequest,
        request: Request,
    ) -> ContentAnalysisCreatedResponse:
        return current_content_service().create_analysis(
            body,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/content-analysis-jobs/{job_id}",
        operation_id="getContentAnalysisJob",
        response_model=JobStatusResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def get_content_analysis_job(job_id: UUID) -> JobStatusResponse:
        return current_content_service().get_analysis_job(job_id)

    @application.post(
        "/api/v1/data-exports",
        operation_id="createDataExport",
        response_model=DataExportCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["exports"],
    )
    def create_data_export(
        body: DataExportSubmitRequest,
        request: Request,
    ) -> DataExportCreatedResponse:
        return current_reporting_service().create_export(
            body,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/data-exports",
        operation_id="listDataExports",
        response_model=DataExportListResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["exports"],
    )
    def list_data_exports() -> DataExportListResponse:
        return current_reporting_service().list_exports()

    @application.get(
        "/api/v1/data-exports/{export_id}",
        operation_id="getDataExport",
        response_model=DataExportResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["exports"],
    )
    def get_data_export(export_id: UUID) -> DataExportResponse:
        return current_reporting_service().get_export(export_id)

    @application.get(
        "/api/v1/data-exports/{export_id}/download",
        operation_id="downloadDataExport",
        response_class=StreamingResponse,
        responses={
            200: {
                "content": {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
                "description": "Excel 导出文件",
            },
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["exports"],
    )
    def download_data_export(export_id: UUID) -> StreamingResponse:
        download = current_reporting_service().download_export(export_id)
        return StreamingResponse(
            download.chunks,
            media_type=download.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{download.filename}"',
                "Content-Length": str(download.byte_size),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @application.post(
        "/api/v1/import-batches",
        operation_id="createImportBatch",
        response_model=ImportBatchCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            409: {"model": HttpErrorResponse},
            413: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    async def create_import_batch(
        request: Request,
        file: Annotated[UploadFile, File()],
    ) -> ImportBatchCreatedResponse:
        form = await request.form()
        items = list(form.multi_items())
        if len(items) != 1 or items[0][0] != "file" or items[0][1] is not file:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body",),
                        "msg": "multipart 只允许一个 file 字段",
                        "input": None,
                        "ctx": {"error": ValueError("multipart 只允许一个 file 字段")},
                    }
                ]
            )
        try:
            return await run_in_threadpool(
                partial(
                    current_import_service().create_import,
                    filename=file.filename or "",
                    content_type=file.content_type,
                    source=file.file,
                    request_id=_request_id(request),
                )
            )
        finally:
            await file.close()

    @application.get(
        "/api/v1/import-batches",
        operation_id="listImportBatches",
        response_model=ImportBatchListResponse,
        responses={
            400: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            503: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def list_import_batches(
        query: Annotated[ImportBatchListQuery, Query()],
    ) -> ImportBatchListResponse:
        return current_import_service().list_import_batches(query)

    @application.get(
        "/api/v1/import-batches/summary",
        operation_id="getImportBatchSummary",
        response_model=ImportBatchSummaryResponse,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def get_import_batch_summary() -> ImportBatchSummaryResponse:
        return current_import_service().get_import_batch_summary()

    @application.get(
        "/api/v1/import-batches/{batch_id}",
        operation_id="getImportBatch",
        response_model=ImportBatchResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def get_import_batch(batch_id: UUID) -> ImportBatchResponse:
        return current_import_service().get_import_batch(batch_id)

    @application.get(
        "/api/v1/jobs/{job_id}",
        operation_id="getJob",
        response_model=JobStatusResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["jobs"],
    )
    def get_job(job_id: UUID) -> JobStatusResponse:
        return current_import_service().get_job(job_id)

    @application.post(
        "/api/v1/keyword-packs",
        operation_id="createKeywordPack",
        response_model=KeywordPackResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def create_keyword_pack(request: KeywordPackCreateRequest) -> KeywordPackResponse:
        return current_import_service().create_keyword_pack(request)

    @application.post(
        "/api/v1/keyword-packs/{pack_id}/keywords",
        operation_id="addKeywordToPack",
        response_model=KeywordPackResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def add_keyword(pack_id: UUID, request: KeywordPackKeywordCreateRequest) -> KeywordPackResponse:
        return current_import_service().add_keyword(pack_id, request)

    @application.get(
        "/api/v1/keyword-packs/{pack_id}",
        operation_id="getKeywordPack",
        response_model=KeywordPackResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def get_keyword_pack(pack_id: UUID) -> KeywordPackResponse:
        return current_import_service().get_keyword_pack(pack_id)

    @application.put(
        "/api/v1/relevance-config",
        operation_id="setGlobalRelevanceConfig",
        response_model=GlobalRelevanceConfigResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["relevance"],
    )
    def set_global_relevance(
        request: GlobalRelevanceConfigRequest,
    ) -> GlobalRelevanceConfigResponse:
        return current_import_service().set_global_relevance(request)

    @application.get(
        "/api/v1/relevance-config",
        operation_id="getGlobalRelevanceConfig",
        response_model=GlobalRelevanceConfigResponse,
        responses={
            409: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["relevance"],
    )
    def get_global_relevance() -> GlobalRelevanceConfigResponse:
        return current_import_service().get_global_relevance()

    return application


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) and value else str(uuid4())


def _error_response(
    *,
    status_code: int,
    request_id: str,
    title: str,
    detail: str,
    code: str,
    field: str | None = None,
    errors: tuple[HttpErrorItem, ...] | None = None,
) -> JSONResponse:
    payload = HttpErrorResponse(
        type=f"https://aima.example/problems/{code}",
        title=title,
        status=status_code,
        detail=detail,
        request_id=request_id,
        errors=errors or (HttpErrorItem(field=field, code=code, message=detail),),
    )
    return JSONResponse(
        status_code=status_code,
        content=json.loads(payload.model_dump_json()),
        headers={"x-request-id": request_id},
    )
