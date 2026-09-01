"""API 进程装配与健康检查。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.responses import JSONResponse, StreamingResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aima_ugc.bootstrap.analysis_taxonomy_http import (
    ContentAnalysisTaxonomyUnavailable,
    content_analysis_taxonomy_response,
)
from aima_ugc.contracts.administration import (
    AnalysisSchemeCreateDraftRequest,
    AnalysisSchemeListResponse,
    AnalysisSchemePublishRequest,
    AnalysisSchemeResponse,
    AnalysisSchemeUpdateDraftRequest,
    AuditEventListResponse,
    CurrentPrincipalResponse,
    KeywordPackVehicleLinkRequest,
    KeywordPackVehicleLinksResponse,
    VehicleModelCreateRequest,
    VehicleModelListQuery,
    VehicleModelListResponse,
    VehicleModelMergeRequest,
    VehicleModelResponse,
    VehicleModelUpdateRequest,
)
from aima_ugc.contracts.http import (
    AnalysisContentRunCreatedResponse,
    AnalysisContentRunCreateRequest,
    AnalysisContentRunListResponse,
    AnalysisContentRunPreviewRequest,
    AnalysisContentRunPreviewResponse,
    AnalysisContentRunResponse,
    CollectionBatchSupplementEligibilityResponse,
    CollectionCapabilitiesResponse,
    CollectionPlanCreateRequest,
    CollectionPlanListQuery,
    CollectionPlanListResponse,
    CollectionPlanResponse,
    CollectionRunCreatedResponse,
    CollectionRunCreateRequest,
    CollectionRunResponse,
    CollectionRuntimeListQuery,
    CollectionRuntimeListResponse,
    CollectionRuntimeSummaryResponse,
    ContentAnalysisCreatedResponse,
    ContentAnalysisSubmitRequest,
    ContentAnalysisTaxonomyResponse,
    ContentCountRequest,
    ContentDetailResponse,
    ContentListQuery,
    ContentListResponse,
    DataExportCreatedResponse,
    DataExportListResponse,
    DataExportResponse,
    DataExportSubmitRequest,
    GlobalRelevanceConfigRequest,
    GlobalRelevanceConfigResponse,
    HistoricalCampaignConflictListResponse,
    HistoricalCampaignCreatedResponse,
    HistoricalCampaignCreateRequest,
    HistoricalCampaignItemListResponse,
    HistoricalCampaignListResponse,
    HistoricalCampaignResponse,
    HistoricalDirectoryListQuery,
    HistoricalDirectoryListResponse,
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
    KeywordPackListQuery,
    KeywordPackListResponse,
    KeywordPackResponse,
    KeywordPackSummaryResponse,
    LocalDataImportCampaignCreatedResponse,
    LocalDataImportCampaignCreateRequest,
    LocalDataImportFileUploadedResponse,
    ResourceEnabledRequest,
)
from aima_ugc.contracts.product import (
    ContentAnalysisManualReviewRequest,
    ContentAnalysisManualReviewResponse,
    ContentAvailabilityObservationRequest,
    ContentAvailabilityResponse,
    ContentCountResponse,
    ContentVehicleReviewRequest,
    ContentVehicleReviewResponse,
    ExportColumnCatalogResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
)
from aima_ugc.contracts.relevance_review import (
    ContentRelevanceReviewRequest,
    ContentRelevanceReviewResponse,
)
from aima_ugc.modules.administration.http import (
    AdministrationConflict,
    AdministrationHttpService,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.analysis import PromptTaxonomyError, PromptTaxonomyLoader
from aima_ugc.modules.analysis.relevance_review import ContentRelevanceReviewConflict
from aima_ugc.modules.collection.http import (
    CollectionConflict,
    CollectionHttpService,
    CollectionResourceNotFound,
    CollectionRuntimeCursorUnavailable,
    InvalidCollectionRuntimeCursor,
)
from aima_ugc.modules.collection.strategy_http import (
    CollectionStrategyConflict,
    CollectionStrategyHttpService,
    CollectionStrategyInvalid,
    CollectionStrategyResourceNotFound,
)
from aima_ugc.modules.content.http import (
    ContentAnalysisRunConflict,
    ContentAnalysisTargetChanged,
    ContentAnalysisUnavailable,
    ContentCursorUnavailable,
    ContentHttpService,
    ContentResourceNotFound,
    ContentSelectionEmpty,
    InvalidContentCursor,
)
from aima_ugc.modules.identity import (
    AuthorizationDenied,
    DevelopmentIdentityResolver,
    IdentityResolver,
    Principal,
)
from aima_ugc.modules.ingestion.historical_http import (
    HistoricalCampaignNotFound,
    HistoricalCampaignStateConflict,
    HistoricalDirectoryRequestInvalid,
    HistoricalImportHttpService,
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
from aima_ugc.modules.product import ProductHttpService, ProductResourceNotFound
from aima_ugc.modules.reporting.http import (
    DataExportNotReady,
    DataExportResourceNotFound,
    ReportingHttpService,
)
from aima_ugc.platform.health import ReadinessReport
from aima_ugc.platform.logging import log_exception_event

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
    strategy_service: CollectionStrategyHttpService | None = None,
    historical_import_service: HistoricalImportHttpService | None = None,
    administration_service: AdministrationHttpService | None = None,
    product_service: ProductHttpService | None = None,
    identity_resolver: IdentityResolver | None = None,
    analysis_taxonomy_loader: PromptTaxonomyLoader | None = None,
) -> FastAPI:
    """创建 API 应用；默认 runtime 延迟到启动或第一次 readiness 检查。"""
    runtime: PlatformRuntime | None = None
    runtime_failed = False
    resolved_identity = identity_resolver or DevelopmentIdentityResolver()

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

    def current_historical_import_service() -> HistoricalImportHttpService:
        if historical_import_service is not None:
            return historical_import_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Historical Import Service 依赖不可用")
        from aima_ugc.bootstrap.historical_import_http import (
            PostgresHistoricalImportHttpService,
        )

        return PostgresHistoricalImportHttpService(resolved_runtime)

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

    def current_strategy_service() -> CollectionStrategyHttpService:
        if strategy_service is not None:
            return strategy_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Collection Strategy Service 依赖不可用")
        from aima_ugc.bootstrap.collection_strategy_http import (
            PostgresCollectionStrategyHttpService,
        )

        return PostgresCollectionStrategyHttpService(resolved_runtime)

    def current_administration_service() -> AdministrationHttpService:
        """解析管理员配置 Service，不在 Router 内直接访问数据库。"""

        if administration_service is not None:
            return administration_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Administration Service 依赖不可用")
        from aima_ugc.bootstrap.administration_http import (
            PostgresAdministrationHttpService,
        )

        return PostgresAdministrationHttpService(resolved_runtime)

    def current_product_service() -> ProductHttpService:
        if product_service is not None:
            return product_service
        resolved_runtime = get_runtime()
        if resolved_runtime is None:
            raise RuntimeError("Product Service 依赖不可用")
        from aima_ugc.bootstrap.product_http import PostgresProductHttpService

        return PostgresProductHttpService(resolved_runtime)

    def current_principal(request: Request) -> Principal:
        """从唯一 Identity Resolver 取得当前 Principal。"""

        return resolved_identity.resolve(request)

    def current_administrator(request: Request) -> Principal:
        """返回已由后端确认管理员角色的 Principal。"""

        principal = current_principal(request)
        principal.require_administrator()
        return principal

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

    @application.exception_handler(HistoricalCampaignNotFound)
    async def historical_campaign_not_found(
        request: Request,
        _: HistoricalCampaignNotFound,
    ) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="历史迁移不存在",
            detail="请求的 Historical Campaign 不存在。",
            code="historical_campaign_not_found",
        )

    @application.exception_handler(HistoricalCampaignStateConflict)
    async def historical_campaign_conflict(
        request: Request,
        _: HistoricalCampaignStateConflict,
    ) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="历史迁移状态冲突",
            detail="当前 Campaign 状态不允许执行该操作。",
            code="historical_campaign_state_conflict",
        )

    @application.exception_handler(HistoricalDirectoryRequestInvalid)
    async def historical_directory_invalid(
        request: Request,
        _: HistoricalDirectoryRequestInvalid,
    ) -> JSONResponse:
        return _error_response(
            status_code=400,
            request_id=_request_id(request),
            title="历史目录请求不合法",
            detail="路径、游标或扫描选择不在管理员批准的安全边界内。",
            code="historical_directory_invalid",
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

    @application.exception_handler(ProductResourceNotFound)
    async def product_resource_not_found(
        request: Request, _: ProductResourceNotFound
    ) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="资源不存在",
            detail="请求的产品资源不存在。",
            code="product_resource_not_found",
        )

    @application.exception_handler(AuthorizationDenied)
    async def authorization_denied(request: Request, _: AuthorizationDenied) -> JSONResponse:
        """管理员守卫统一返回不泄露资源存在性的 403。"""

        return _error_response(
            status_code=403,
            request_id=_request_id(request),
            title="没有管理员权限",
            detail="当前用户没有执行该管理操作的权限。",
            code="administrator_required",
        )

    @application.exception_handler(AdministrationResourceNotFound)
    async def administration_resource_not_found(
        request: Request,
        _: AdministrationResourceNotFound,
    ) -> JSONResponse:
        """管理员资源不存在时使用稳定错误 Contract。"""

        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="配置资源不存在",
            detail="请求的车型、词包或 Analysis Scheme 不存在。",
            code="administration_resource_not_found",
        )

    @application.exception_handler(AdministrationConflict)
    async def administration_conflict(
        request: Request,
        _: AdministrationConflict,
    ) -> JSONResponse:
        """版本、引用或状态冲突统一返回 409。"""

        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="配置修改冲突",
            detail="配置版本、引用关系或当前状态不允许该操作。",
            code="administration_conflict",
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

    @application.exception_handler(ContentAnalysisUnavailable)
    async def content_analysis_unavailable(
        request: Request, _: ContentAnalysisUnavailable
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            request_id=_request_id(request),
            title="AI 分析配置暂不可用",
            detail="AI 模型或密钥配置不可用，请使用 request_id 联系管理员。",
            code="content_analysis_unavailable",
        )

    @application.exception_handler(ContentAnalysisTaxonomyUnavailable)
    async def content_analysis_taxonomy_unavailable(
        request: Request,
        _: ContentAnalysisTaxonomyUnavailable,
    ) -> JSONResponse:
        return _error_response(
            status_code=503,
            request_id=_request_id(request),
            title="AI 分类配置暂不可用",
            detail="当前 Prompt Taxonomy 无法安全读取或校验。",
            code="content_analysis_taxonomy_unavailable",
            errors=(
                HttpErrorItem(
                    field="taxonomy",
                    code="content_analysis_taxonomy_unavailable",
                    message="请检查服务端 Prompt Taxonomy 配置和日志。",
                ),
            ),
        )

    @application.exception_handler(ContentAnalysisTargetChanged)
    async def content_analysis_target_changed(
        request: Request, _: ContentAnalysisTargetChanged
    ) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="AI 分析目标已经变化",
            detail="预览后的内容集合已经变化，请重新预览并确认。",
            code="content_analysis_target_changed",
            field="body.expected_target_count",
        )

    @application.exception_handler(ContentAnalysisRunConflict)
    async def content_analysis_run_conflict(
        request: Request, _: ContentAnalysisRunConflict
    ) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="AI 分析运行冲突",
            detail="幂等键已经用于不同请求，或运行状态不允许当前操作。",
            code="content_analysis_run_conflict",
        )

    @application.exception_handler(ContentRelevanceReviewConflict)
    async def content_relevance_review_conflict(
        request: Request, _: ContentRelevanceReviewConflict
    ) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="内容无法人工复核",
            detail="所选内容当前相关性状态不允许该人工操作，或内容版本已经变化。",
            code="content_relevance_review_conflict",
            field="body.content_ids",
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

    @application.exception_handler(CollectionStrategyResourceNotFound)
    async def collection_strategy_not_found(
        request: Request, _: CollectionStrategyResourceNotFound
    ) -> JSONResponse:
        return _error_response(
            status_code=404,
            request_id=_request_id(request),
            title="采集策略资源不存在",
            detail="请求的词包、采集计划或 Provider 配置不存在。",
            code="collection_strategy_not_found",
        )

    @application.exception_handler(CollectionStrategyConflict)
    async def collection_strategy_conflict(
        request: Request, _: CollectionStrategyConflict
    ) -> JSONResponse:
        return _error_response(
            status_code=409,
            request_id=_request_id(request),
            title="采集策略无法保存",
            detail="当前词包、全局相关性、Provider 或计划状态不允许该操作。",
            code="collection_strategy_conflict",
        )

    @application.exception_handler(CollectionStrategyInvalid)
    async def collection_strategy_invalid(
        request: Request, _: CollectionStrategyInvalid
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            request_id=_request_id(request),
            title="采集策略不合法",
            detail="采集策略未通过领域规则校验。",
            code="collection_strategy_invalid",
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
        log_exception_event(
            _LOGGER,
            logging.ERROR,
            "api.request_failed",
            "API 请求处理失败",
            exc,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
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

    @application.get(
        "/api/v1/import-batches/{batch_id}/supplement-eligibility",
        operation_id="getCollectionBatchSupplementEligibility",
        response_model=CollectionBatchSupplementEligibilityResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection"],
    )
    def get_collection_batch_supplement_eligibility(
        batch_id: UUID,
    ) -> CollectionBatchSupplementEligibilityResponse:
        return current_collection_service().get_batch_supplement_eligibility(batch_id)

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

    @application.post(
        "/api/v1/contents/count",
        operation_id="countContents",
        response_model=ContentCountResponse,
        responses={422: {"model": HttpErrorResponse}, 500: {"model": HttpErrorResponse}},
        tags=["contents"],
    )
    def count_contents(body: ContentCountRequest) -> ContentCountResponse:
        return current_product_service().count_contents(body)

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

    @application.put(
        "/api/v1/contents/{content_id}/analysis-review",
        operation_id="reviewContentAnalysis",
        response_model=ContentAnalysisManualReviewResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def review_content_analysis(
        content_id: UUID,
        body: ContentAnalysisManualReviewRequest,
        request: Request,
    ) -> ContentAnalysisManualReviewResponse:
        """人工纠正 voice_type、情感与标签，并显式维护维度锁。"""

        return current_content_service().review_analysis(
            content_id,
            body,
            request_id=_request_id(request),
            actor_ref=current_principal(request).principal_id,
        )

    @application.put(
        "/api/v1/contents/{content_id}/vehicles",
        operation_id="reviewContentVehicles",
        response_model=ContentVehicleReviewResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def review_content_vehicles(
        content_id: UUID,
        body: ContentVehicleReviewRequest,
        request: Request,
    ) -> ContentVehicleReviewResponse:
        principal = current_principal(request)
        return current_content_service().review_vehicles(
            content_id,
            body,
            request_id=_request_id(request),
            actor_ref=principal.principal_id,
        )

    @application.post(
        "/api/v1/content-availability-observations",
        operation_id="createContentAvailabilityObservation",
        response_model=ContentAvailabilityResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def create_content_availability_observation(
        body: ContentAvailabilityObservationRequest,
        request: Request,
    ) -> ContentAvailabilityResponse:
        return current_product_service().observe_availability(
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/export-columns",
        operation_id="getExportColumnCatalog",
        response_model=ExportColumnCatalogResponse,
        tags=["exports"],
    )
    def get_export_column_catalog() -> ExportColumnCatalogResponse:
        return current_product_service().get_export_column_catalog()

    @application.get(
        "/api/v1/notifications",
        operation_id="listNotifications",
        response_model=NotificationListResponse,
        tags=["notifications"],
    )
    def list_notifications(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> NotificationListResponse:
        return current_product_service().list_notifications(
            current_principal(request), limit=limit
        )

    @application.put(
        "/api/v1/notifications/read",
        operation_id="markNotificationsRead",
        response_model=NotificationMarkReadResponse,
        tags=["notifications"],
    )
    def mark_notifications_read(
        body: NotificationMarkReadRequest,
        request: Request,
    ) -> NotificationMarkReadResponse:
        return current_product_service().mark_notifications_read(
            current_principal(request), body
        )

    @application.post(
        "/api/v1/content-relevance-reviews",
        operation_id="createContentRelevanceReview",
        response_model=ContentRelevanceReviewResponse,
        responses={
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def create_content_relevance_review(
        body: ContentRelevanceReviewRequest,
        request: Request,
    ) -> ContentRelevanceReviewResponse:
        return current_content_service().review_relevance(
            body,
            request_id=_request_id(request),
        )

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

    @application.post(
        "/api/v1/analysis/content-runs/preview",
        operation_id="previewContentAnalysisRun",
        response_model=AnalysisContentRunPreviewResponse,
        responses={
            422: {"model": HttpErrorResponse},
            503: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def preview_content_analysis_run(
        body: AnalysisContentRunPreviewRequest,
    ) -> AnalysisContentRunPreviewResponse:
        return current_content_service().preview_analysis_run(body)

    @application.post(
        "/api/v1/analysis/content-runs",
        operation_id="createContentAnalysisRun",
        response_model=AnalysisContentRunCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            503: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def create_content_analysis_run(
        body: AnalysisContentRunCreateRequest,
        request: Request,
    ) -> AnalysisContentRunCreatedResponse:
        return current_content_service().create_analysis_run(
            body,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/analysis/content-runs",
        operation_id="listContentAnalysisRuns",
        response_model=AnalysisContentRunListResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["contents"],
    )
    def list_content_analysis_runs() -> AnalysisContentRunListResponse:
        return current_content_service().list_analysis_runs()

    @application.get(
        "/api/v1/analysis/content-runs/{run_id}",
        operation_id="getContentAnalysisRun",
        response_model=AnalysisContentRunResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def get_content_analysis_run(run_id: UUID) -> AnalysisContentRunResponse:
        return current_content_service().get_analysis_run(run_id)

    @application.post(
        "/api/v1/analysis/content-runs/{run_id}/cancel",
        operation_id="cancelContentAnalysisRun",
        response_model=AnalysisContentRunResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["contents"],
    )
    def cancel_content_analysis_run(
        run_id: UUID,
        request: Request,
    ) -> AnalysisContentRunResponse:
        return current_content_service().cancel_analysis_run(
            run_id,
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
            actor_ref=current_principal(request).principal_id,
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

    @application.get(
        "/api/v1/data-import-sources/server/directories",
        operation_id="listDataImportServerDirectories",
        response_model=HistoricalDirectoryListResponse,
        responses={
            400: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.get(
        "/api/v1/historical-import/directories",
        operation_id="listHistoricalImportDirectories",
        response_model=HistoricalDirectoryListResponse,
        responses={
            400: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def list_historical_import_directories(
        query: Annotated[HistoricalDirectoryListQuery, Query()],
    ) -> HistoricalDirectoryListResponse:
        return current_historical_import_service().list_directories(query)

    @application.post(
        "/api/v1/data-import-campaigns/server",
        operation_id="createServerDataImportCampaign",
        response_model=HistoricalCampaignCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            400: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.post(
        "/api/v1/historical-import-campaigns",
        operation_id="createHistoricalImportCampaign",
        response_model=HistoricalCampaignCreatedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            400: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def create_historical_import_campaign(
        body: HistoricalCampaignCreateRequest,
        request: Request,
    ) -> HistoricalCampaignCreatedResponse:
        return current_historical_import_service().create_campaign(
            body,
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/data-import-campaigns/local",
        operation_id="createLocalDataImportCampaign",
        response_model=LocalDataImportCampaignCreatedResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def create_local_data_import_campaign(
        body: LocalDataImportCampaignCreateRequest,
        request: Request,
    ) -> LocalDataImportCampaignCreatedResponse:
        return current_historical_import_service().create_local_campaign(
            body,
            request_id=_request_id(request),
        )

    @application.put(
        "/api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content",
        operation_id="uploadLocalDataImportFile",
        response_model=LocalDataImportFileUploadedResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            413: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    async def upload_local_data_import_file(
        campaign_id: UUID,
        item_id: UUID,
        request: Request,
        file: Annotated[UploadFile, File()],
    ) -> LocalDataImportFileUploadedResponse:
        try:
            return await run_in_threadpool(
                current_historical_import_service().upload_local_file,
                campaign_id,
                item_id,
                filename=file.filename or "",
                content_type=file.content_type,
                source=file.file,
                request_id=_request_id(request),
            )
        finally:
            await file.close()

    @application.post(
        "/api/v1/data-import-campaigns/{campaign_id}/finalize",
        operation_id="finalizeLocalDataImportCampaign",
        response_model=HistoricalCampaignResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def finalize_local_data_import_campaign(
        campaign_id: UUID,
        request: Request,
    ) -> HistoricalCampaignResponse:
        return current_historical_import_service().finalize_local_campaign(
            campaign_id,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/data-import-campaigns",
        operation_id="listDataImportCampaigns",
        response_model=HistoricalCampaignListResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["imports"],
    )
    @application.get(
        "/api/v1/historical-import-campaigns",
        operation_id="listHistoricalImportCampaigns",
        response_model=HistoricalCampaignListResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["imports"],
    )
    def list_historical_import_campaigns() -> HistoricalCampaignListResponse:
        return current_historical_import_service().list_campaigns()

    @application.get(
        "/api/v1/data-import-campaigns/{campaign_id}",
        operation_id="getDataImportCampaign",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.get(
        "/api/v1/historical-import-campaigns/{campaign_id}",
        operation_id="getHistoricalImportCampaign",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def get_historical_import_campaign(campaign_id: UUID) -> HistoricalCampaignResponse:
        return current_historical_import_service().get_campaign(campaign_id)

    @application.get(
        "/api/v1/data-import-campaigns/{campaign_id}/items",
        operation_id="listDataImportCampaignItems",
        response_model=HistoricalCampaignItemListResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.get(
        "/api/v1/historical-import-campaigns/{campaign_id}/items",
        operation_id="listHistoricalImportCampaignItems",
        response_model=HistoricalCampaignItemListResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def list_historical_import_campaign_items(
        campaign_id: UUID,
    ) -> HistoricalCampaignItemListResponse:
        return current_historical_import_service().list_items(campaign_id)

    @application.get(
        "/api/v1/data-import-campaigns/{campaign_id}/conflicts",
        operation_id="listDataImportCampaignConflicts",
        response_model=HistoricalCampaignConflictListResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.get(
        "/api/v1/historical-import-campaigns/{campaign_id}/conflicts",
        operation_id="listHistoricalImportCampaignConflicts",
        response_model=HistoricalCampaignConflictListResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def list_historical_import_campaign_conflicts(
        campaign_id: UUID,
    ) -> HistoricalCampaignConflictListResponse:
        return current_historical_import_service().list_conflicts(campaign_id)

    def campaign_action(
        campaign_id: UUID,
        *,
        action: Literal["start", "cancel", "retry"],
        request: Request,
    ) -> HistoricalCampaignResponse:
        service = current_historical_import_service()
        request_id = _request_id(request)
        if action == "start":
            return service.start_campaign(campaign_id, request_id=request_id)
        if action == "cancel":
            return service.cancel_campaign(campaign_id, request_id=request_id)
        return service.retry_failed(campaign_id, request_id=request_id)

    @application.post(
        "/api/v1/data-import-campaigns/{campaign_id}/start",
        operation_id="startDataImportCampaign",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.post(
        "/api/v1/historical-import-campaigns/{campaign_id}/start",
        operation_id="startHistoricalImportCampaign",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def start_historical_import_campaign(
        campaign_id: UUID,
        request: Request,
    ) -> HistoricalCampaignResponse:
        return campaign_action(campaign_id, action="start", request=request)

    @application.post(
        "/api/v1/data-import-campaigns/{campaign_id}/cancel",
        operation_id="cancelDataImportCampaign",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.post(
        "/api/v1/historical-import-campaigns/{campaign_id}/cancel",
        operation_id="cancelHistoricalImportCampaign",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def cancel_historical_import_campaign(
        campaign_id: UUID,
        request: Request,
    ) -> HistoricalCampaignResponse:
        return campaign_action(campaign_id, action="cancel", request=request)

    @application.post(
        "/api/v1/data-import-campaigns/{campaign_id}/retry-failed",
        operation_id="retryDataImportCampaignFailedItems",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    @application.post(
        "/api/v1/historical-import-campaigns/{campaign_id}/retry-failed",
        operation_id="retryHistoricalImportCampaignFailedItems",
        response_model=HistoricalCampaignResponse,
        responses={
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["imports"],
    )
    def retry_historical_import_campaign_failed_items(
        campaign_id: UUID,
        request: Request,
    ) -> HistoricalCampaignResponse:
        return campaign_action(campaign_id, action="retry", request=request)

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
        keyword_pack_ids: Annotated[tuple[UUID, ...], Form()] = (),
        vehicle_model_ids: Annotated[tuple[UUID, ...], Form()] = (),
    ) -> ImportBatchCreatedResponse:
        form = await request.form()
        items = list(form.multi_items())
        allowed = {"file", "keyword_pack_ids", "vehicle_model_ids"}
        file_items = [value for key, value in items if key == "file"]
        pack_items = [value for key, value in items if key == "keyword_pack_ids"]
        vehicle_items = [value for key, value in items if key == "vehicle_model_ids"]
        if (
            any(key not in allowed for key, _ in items)
            or len(file_items) != 1
            or file_items[0] is not file
            or len(pack_items) != len(keyword_pack_ids)
            or len(vehicle_items) != len(vehicle_model_ids)
            or not keyword_pack_ids
            and not vehicle_model_ids
            or len(keyword_pack_ids) > 20
            or len(vehicle_model_ids) > 100
            or len(keyword_pack_ids) != len(set(keyword_pack_ids))
            or len(vehicle_model_ids) != len(set(vehicle_model_ids))
        ):
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "keyword_pack_ids"),
                        "msg": "multipart 必须包含一个 file，并至少选择词包或车型",
                        "input": None,
                        "ctx": {
                            "error": ValueError(
                                "multipart 必须包含一个 file，并至少选择词包或车型"
                            )
                        },
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
                    keyword_pack_ids=tuple(keyword_pack_ids),
                    vehicle_model_ids=tuple(vehicle_model_ids),
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

    @application.get(
        "/api/v1/content-analysis-taxonomy",
        operation_id="getContentAnalysisTaxonomy",
        response_model=ContentAnalysisTaxonomyResponse,
        responses={503: {"model": HttpErrorResponse}, 500: {"model": HttpErrorResponse}},
        tags=["contents"],
    )
    def get_content_analysis_taxonomy() -> ContentAnalysisTaxonomyResponse:
        """读取数据库 active Analysis Scheme 的分类安全投影。"""

        if analysis_taxonomy_loader is not None:
            try:
                return content_analysis_taxonomy_response(analysis_taxonomy_loader)
            except (PromptTaxonomyError, ValidationError) as exc:
                raise ContentAnalysisTaxonomyUnavailable from exc
        return current_content_service().get_analysis_taxonomy()

    @application.get(
        "/api/v1/principal",
        operation_id="getCurrentPrincipal",
        response_model=CurrentPrincipalResponse,
        responses={500: {"model": HttpErrorResponse}},
        tags=["identity"],
    )
    def get_current_principal(request: Request) -> CurrentPrincipalResponse:
        """返回当前 Provider-neutral Principal 与两角色投影。"""

        principal = current_principal(request)
        return CurrentPrincipalResponse(
            principal_id=principal.principal_id,
            display_name=principal.display_name,
            role=principal.role,
            source=principal.source,
        )

    @application.post(
        "/api/v1/vehicle-models",
        operation_id="createVehicleModel",
        response_model=VehicleModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["vehicles"],
    )
    def create_vehicle_model(
        body: VehicleModelCreateRequest,
        request: Request,
    ) -> VehicleModelResponse:
        """管理员创建车型和初始别名。"""

        return current_administration_service().create_vehicle_model(
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/vehicle-models",
        operation_id="listVehicleModels",
        response_model=VehicleModelListResponse,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["vehicles"],
    )
    def list_vehicle_models(
        query: Annotated[VehicleModelListQuery, Query()],
    ) -> VehicleModelListResponse:
        """读取车型目录供选择器和管理员页面复用。"""

        return current_administration_service().list_vehicle_models(query)

    @application.get(
        "/api/v1/vehicle-models/{vehicle_model_id}",
        operation_id="getVehicleModel",
        response_model=VehicleModelResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["vehicles"],
    )
    def get_vehicle_model(vehicle_model_id: UUID) -> VehicleModelResponse:
        """读取单个车型目录详情。"""

        return current_administration_service().get_vehicle_model(vehicle_model_id)

    @application.put(
        "/api/v1/vehicle-models/{vehicle_model_id}",
        operation_id="updateVehicleModel",
        response_model=VehicleModelResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["vehicles"],
    )
    def update_vehicle_model(
        vehicle_model_id: UUID,
        body: VehicleModelUpdateRequest,
        request: Request,
    ) -> VehicleModelResponse:
        """管理员修改车型显示、别名或启停状态。"""

        return current_administration_service().update_vehicle_model(
            vehicle_model_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.delete(
        "/api/v1/vehicle-models/{vehicle_model_id}",
        operation_id="deleteVehicleModel",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["vehicles"],
    )
    def delete_vehicle_model(vehicle_model_id: UUID, request: Request) -> Response:
        """管理员物理删除未引用车型。"""

        current_administration_service().delete_vehicle_model(
            vehicle_model_id,
            principal=current_principal(request),
            request_id=_request_id(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.post(
        "/api/v1/vehicle-models/{vehicle_model_id}/merge",
        operation_id="mergeVehicleModel",
        response_model=VehicleModelResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["vehicles"],
    )
    def merge_vehicle_model(
        vehicle_model_id: UUID,
        body: VehicleModelMergeRequest,
        request: Request,
    ) -> VehicleModelResponse:
        """管理员把重复车型重定向到稳定目标。"""

        return current_administration_service().merge_vehicle_model(
            vehicle_model_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.put(
        "/api/v1/keyword-packs/{pack_id}/vehicle-models",
        operation_id="replaceKeywordPackVehicleModels",
        response_model=KeywordPackVehicleLinksResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords", "vehicles"],
    )
    def replace_keyword_pack_vehicle_models(
        pack_id: UUID,
        body: KeywordPackVehicleLinkRequest,
        request: Request,
    ) -> KeywordPackVehicleLinksResponse:
        """管理员原子替换一个词包引用的车型。"""

        return current_administration_service().replace_keyword_pack_vehicles(
            pack_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/analysis-schemes",
        operation_id="createAnalysisSchemeDraft",
        response_model=AnalysisSchemeResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["analysis-schemes"],
    )
    def create_analysis_scheme_draft(
        body: AnalysisSchemeCreateDraftRequest,
        request: Request,
    ) -> AnalysisSchemeResponse:
        """管理员创建结构化 Analysis Scheme 草稿。"""

        return current_administration_service().create_analysis_scheme_draft(
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/analysis-schemes",
        operation_id="listAnalysisSchemes",
        response_model=AnalysisSchemeListResponse,
        responses={
            403: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["analysis-schemes"],
    )
    def list_analysis_schemes(request: Request) -> AnalysisSchemeListResponse:
        """管理员读取 Scheme 与版本历史。"""

        current_principal(request).require_administrator()
        return current_administration_service().list_analysis_schemes()

    @application.put(
        "/api/v1/analysis-scheme-versions/{version_id}",
        operation_id="updateAnalysisSchemeDraft",
        response_model=AnalysisSchemeResponse,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["analysis-schemes"],
    )
    def update_analysis_scheme_draft(
        version_id: UUID,
        body: AnalysisSchemeUpdateDraftRequest,
        request: Request,
    ) -> AnalysisSchemeResponse:
        """管理员更新尚未发布的 Scheme Version。"""

        return current_administration_service().update_analysis_scheme_draft(
            version_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/analysis-scheme-versions/{version_id}/publish",
        operation_id="publishAnalysisScheme",
        response_model=AnalysisSchemeResponse,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["analysis-schemes"],
    )
    def publish_analysis_scheme(
        version_id: UUID,
        body: AnalysisSchemePublishRequest,
        request: Request,
    ) -> AnalysisSchemeResponse:
        """管理员原子发布 Scheme Version。"""

        return current_administration_service().publish_analysis_scheme(
            version_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/analysis-scheme-versions/{version_id}/rollback",
        operation_id="rollbackAnalysisScheme",
        response_model=AnalysisSchemeResponse,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["analysis-schemes"],
    )
    def rollback_analysis_scheme(
        version_id: UUID,
        body: AnalysisSchemePublishRequest,
        request: Request,
    ) -> AnalysisSchemeResponse:
        """管理员把历史版本重新激活。"""

        return current_administration_service().rollback_analysis_scheme(
            version_id,
            body,
            principal=current_principal(request),
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/audit-events",
        operation_id="listAuditEvents",
        response_model=AuditEventListResponse,
        responses={
            403: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration"],
    )
    def list_audit_events(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> AuditEventListResponse:
        """管理员读取有界审计历史。"""

        current_principal(request).require_administrator()
        return current_administration_service().list_audit_events(limit=limit)

    @application.post(
        "/api/v1/keyword-packs",
        operation_id="createKeywordPack",
        response_model=KeywordPackResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def create_keyword_pack(
        body: KeywordPackCreateRequest,
        request: Request,
    ) -> KeywordPackResponse:
        principal = current_administrator(request)
        return current_import_service().create_keyword_pack(
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/keyword-packs",
        operation_id="listKeywordPacks",
        response_model=KeywordPackListResponse,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def list_keyword_packs(
        query: Annotated[KeywordPackListQuery, Query()],
    ) -> KeywordPackListResponse:
        return current_strategy_service().list_keyword_packs(query)

    @application.post(
        "/api/v1/keyword-packs/{pack_id}/keywords",
        operation_id="addKeywordToPack",
        response_model=KeywordPackResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def add_keyword(
        pack_id: UUID,
        body: KeywordPackKeywordCreateRequest,
        request: Request,
    ) -> KeywordPackResponse:
        principal = current_administrator(request)
        return current_import_service().add_keyword(
            pack_id,
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )

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
        "/api/v1/keyword-packs/{pack_id}/enabled",
        operation_id="updateKeywordPackEnabled",
        response_model=KeywordPackSummaryResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["keywords"],
    )
    def update_keyword_pack_enabled(
        pack_id: UUID,
        body: ResourceEnabledRequest,
        request: Request,
    ) -> KeywordPackSummaryResponse:
        principal = current_administrator(request)
        return current_strategy_service().set_keyword_pack_enabled(
            pack_id,
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )

    @application.put(
        "/api/v1/relevance-config",
        operation_id="setGlobalRelevanceConfig",
        response_model=GlobalRelevanceConfigResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["relevance"],
    )
    def set_global_relevance(
        body: GlobalRelevanceConfigRequest,
        request: Request,
    ) -> GlobalRelevanceConfigResponse:
        principal = current_administrator(request)
        return current_import_service().set_global_relevance(
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )

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

    @application.post(
        "/api/v1/collection-plans",
        operation_id="createCollectionPlan",
        response_model=CollectionPlanResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def create_collection_plan(
        body: CollectionPlanCreateRequest,
        request: Request,
    ) -> CollectionPlanResponse:
        principal = current_administrator(request)
        return current_strategy_service().create_plan(
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )

    @application.get(
        "/api/v1/collection-plans",
        operation_id="listCollectionPlans",
        response_model=CollectionPlanListResponse,
        responses={
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def list_collection_plans(
        query: Annotated[CollectionPlanListQuery, Query()],
    ) -> CollectionPlanListResponse:
        return current_strategy_service().list_plans(query)

    @application.get(
        "/api/v1/collection-plans/{plan_id}",
        operation_id="getCollectionPlan",
        response_model=CollectionPlanResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def get_collection_plan(plan_id: UUID) -> CollectionPlanResponse:
        return current_strategy_service().get_plan(plan_id)

    @application.put(
        "/api/v1/collection-plans/{plan_id}/enabled",
        operation_id="updateCollectionPlanEnabled",
        response_model=CollectionPlanResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection-strategy"],
    )
    def update_collection_plan_enabled(
        plan_id: UUID,
        body: ResourceEnabledRequest,
        request: Request,
    ) -> CollectionPlanResponse:
        principal = current_administrator(request)
        return current_strategy_service().set_plan_enabled(
            plan_id,
            body,
            actor_ref=principal.principal_id,
            request_id=_request_id(request),
        )

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
