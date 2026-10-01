"""报告管理员 Router：授权、Contract 与流响应；数据库操作留在 Service。"""

from collections.abc import Callable
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from aima_ugc.adapters.persistence.postgres.report_runs import ReportNotFound
from aima_ugc.contracts.http import HttpErrorItem, HttpErrorResponse
from aima_ugc.contracts.reports import (
    ReportListResponse,
    ReportPreflightResponse,
    ReportResponse,
    ReportSubmitRequest,
)
from aima_ugc.modules.identity import Principal

from .report_runs_http import PostgresReportHttpService, ReportRequestError


def register_report_routes(
    application: FastAPI,
    *,
    service: Callable[[], PostgresReportHttpService],
    administrator: Callable[[Request], Principal],
) -> None:
    """所有入口先确认管理员；测试可以注入同一 Service 边界。"""

    @application.exception_handler(ReportRequestError)
    @application.exception_handler(ReportNotFound)
    async def report_error(request: Request, exc: Exception) -> JSONResponse:
        """使用项目统一问题格式，供生成 Client 的错误解析复用。"""
        status = exc.status if isinstance(exc, ReportRequestError) else 404
        code = exc.code if isinstance(exc, ReportRequestError) else "report_not_found"
        detail = str(exc) if isinstance(exc, ReportRequestError) else "报告不存在"
        request_id = getattr(request.state, "request_id", str(uuid4()))
        error = HttpErrorResponse(
            type=f"https://aima.example/problems/{code}",
            title="报告请求失败",
            status=status,
            detail=detail,
            request_id=request_id,
            errors=(HttpErrorItem(code=code, message=detail),),
        )
        return JSONResponse(status_code=status, content=error.model_dump(mode="json"))

    responses: dict[int | str, dict[str, Any]] = {
        code: {"model": HttpErrorResponse} for code in (403, 404, 409, 410, 422, 500)
    }

    @application.post(
        "/api/v1/reports/preflight",
        operation_id="preflightReport",
        response_model=ReportPreflightResponse,
        responses=responses,
        tags=["reports"],
    )
    def preflight(body: ReportSubmitRequest, request: Request) -> ReportPreflightResponse:
        """实时预检。"""
        administrator(request)
        return service().preflight(body)

    @application.post(
        "/api/v1/reports",
        operation_id="createReport",
        response_model=ReportResponse,
        status_code=202,
        responses=responses,
        tags=["reports"],
    )
    def create(body: ReportSubmitRequest, request: Request) -> ReportResponse:
        """冻结并排队，外部调用由 Worker 完成。"""
        principal = administrator(request)
        return service().create(
            body, actor_ref=principal.principal_id, request_id=request.state.request_id
        )

    @application.get(
        "/api/v1/reports",
        operation_id="listReports",
        response_model=ReportListResponse,
        responses=responses,
        tags=["reports"],
    )
    def list_reports(request: Request) -> ReportListResponse:
        """历史列表。"""
        administrator(request)
        return service().list_recent()

    @application.get(
        "/api/v1/reports/{report_id}",
        operation_id="getReport",
        response_model=ReportResponse,
        responses=responses,
        tags=["reports"],
    )
    def get(report_id: UUID, request: Request) -> ReportResponse:
        """报告详情。"""
        administrator(request)
        return service().get(report_id)

    @application.post(
        "/api/v1/reports/{report_id}/retry",
        operation_id="retryReport",
        response_model=ReportResponse,
        responses=responses,
        tags=["reports"],
    )
    def retry(report_id: UUID, request: Request) -> ReportResponse:
        """恢复失败生成。"""
        administrator(request)
        return service().action(report_id, action="retry", request_id=request.state.request_id)

    @application.post(
        "/api/v1/reports/{report_id}/publish",
        operation_id="publishReport",
        response_model=ReportResponse,
        responses=responses,
        tags=["reports"],
    )
    def publish(report_id: UUID, request: Request) -> ReportResponse:
        """独立发布或恢复失败发布。"""
        administrator(request)
        return service().action(report_id, action="publish", request_id=request.state.request_id)

    @application.post(
        "/api/v1/reports/{report_id}/cancel",
        operation_id="cancelReport",
        response_model=ReportResponse,
        responses=responses,
        tags=["reports"],
    )
    def cancel(report_id: UUID, request: Request) -> ReportResponse:
        """提交生成或发布任务的取消意图。"""
        administrator(request)
        return service().action(report_id, action="cancel", request_id=request.state.request_id)

    @application.get(
        "/api/v1/reports/{report_id}/artifacts/{artifact_id}/download",
        operation_id="downloadReportArtifact",
        response_class=StreamingResponse,
        responses=responses,
        tags=["reports"],
    )
    def download(report_id: UUID, artifact_id: UUID, request: Request) -> StreamingResponse:
        """所属校验与到期校验后流式下载。"""
        administrator(request)
        file = service().download(report_id, artifact_id)
        return StreamingResponse(
            file.chunks,
            media_type=file.content_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.filename)}",
                "Content-Length": str(file.byte_size),
            },
        )
