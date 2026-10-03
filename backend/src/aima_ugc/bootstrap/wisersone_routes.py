"""WisersOne HTTP 接线；数据库操作留在 Ingestion Service。"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request

from aima_ugc.adapters.persistence.postgres.wisersone import WisersOneConflict
from aima_ugc.contracts.http import (
    HttpErrorResponse,
    WisersOneDownloadCreateRequest,
    WisersOneDownloadListResponse,
    WisersOneDownloadResponse,
)
from aima_ugc.modules.identity import Principal

from .runtime import PlatformRuntime
from .wisersone_http import PostgresWisersOneHttpService

_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HttpErrorResponse} for code in (400, 403, 404, 409, 422, 500, 503)
}


def register_wisersone_routes(
    application: FastAPI,
    runtime: Callable[[], PlatformRuntime | None],
    principal: Callable[[Request], Principal],
) -> None:
    def service() -> PostgresWisersOneHttpService:
        resolved = runtime()
        if resolved is None:
            raise HTTPException(503, "WisersOne 运行依赖不可用")
        return PostgresWisersOneHttpService(resolved)

    @application.post(
        "/api/v1/wisersone-downloads",
        operation_id="createWisersOneDownload",
        response_model=WisersOneDownloadResponse,
        status_code=202,
        tags=["imports"],
        responses=_ERRORS,
    )
    def create(body: WisersOneDownloadCreateRequest, request: Request) -> WisersOneDownloadResponse:
        principal(request).require_administrator()
        try:
            return service().create(
                body, request_id=getattr(request.state, "request_id", str(UUID(int=0)))
            )
        except WisersOneConflict as exc:
            raise HTTPException(409, str(exc)) from None

    @application.get(
        "/api/v1/wisersone-downloads",
        operation_id="listWisersOneDownloads",
        response_model=WisersOneDownloadListResponse,
        tags=["imports"],
        responses=_ERRORS,
    )
    def listing(request: Request) -> WisersOneDownloadListResponse:
        principal(request)
        return service().list()

    @application.get(
        "/api/v1/wisersone-downloads/{download_id}",
        operation_id="getWisersOneDownload",
        response_model=WisersOneDownloadResponse,
        tags=["imports"],
        responses=_ERRORS,
    )
    def get(download_id: UUID, request: Request) -> WisersOneDownloadResponse:
        principal(request)
        try:
            return service().get(download_id)
        except KeyError:
            raise HTTPException(404, "WisersOne 下载不存在") from None

    @application.post(
        "/api/v1/wisersone-downloads/{download_id}/cancel",
        operation_id="cancelWisersOneDownload",
        response_model=WisersOneDownloadResponse,
        tags=["imports"],
        responses=_ERRORS,
    )
    def cancel(download_id: UUID, request: Request) -> WisersOneDownloadResponse:
        principal(request).require_administrator()
        try:
            return service().cancel(download_id)
        except KeyError:
            raise HTTPException(404, "WisersOne 下载不存在") from None

    @application.post(
        "/api/v1/wisersone-downloads/{download_id}/retry",
        operation_id="retryWisersOneDownload",
        response_model=WisersOneDownloadResponse,
        tags=["imports"],
        responses=_ERRORS,
    )
    def retry(download_id: UUID, request: Request) -> WisersOneDownloadResponse:
        principal(request).require_administrator()
        try:
            return service().retry(download_id)
        except KeyError:
            raise HTTPException(404, "WisersOne 下载不存在") from None
        except WisersOneConflict as exc:
            raise HTTPException(409, str(exc)) from None
