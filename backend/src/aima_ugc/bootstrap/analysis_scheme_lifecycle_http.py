"""Analysis Scheme 复制、归档、恢复与条件删除的扩展 API。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response, status
from sqlalchemy.exc import IntegrityError

from aima_ugc.adapters.persistence.postgres.analysis_scheme_lifecycle import (
    PostgresAnalysisSchemeLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.contracts.administration import (
    AnalysisSchemeResponse,
    AnalysisSchemeVersionResponse,
)
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.contracts.resource_lifecycle import (
    AnalysisSchemeCopyRequest,
    ResourceDeleteEligibilityResponse,
    ResourceLifecycleListResponse,
    ResourceLifecycleResponse,
)
from aima_ugc.modules.administration.http import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.analysis.schemes import AnalysisSchemeVersionRecord
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver, Principal
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime, create_platform_runtime


class AnalysisSchemeLifecycleHttpService(Protocol):
    def copy(
        self,
        scheme_id: UUID,
        body: AnalysisSchemeCopyRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse: ...

    def archive(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ResourceLifecycleResponse: ...

    def restore(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None: ...

    def list_archived(self, *, principal: Principal) -> ResourceLifecycleListResponse: ...

    def delete_eligibility(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
    ) -> ResourceDeleteEligibilityResponse: ...

    def delete(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None: ...


class PostgresAnalysisSchemeLifecycleHttpService:
    """Analysis Scheme 生命周期与审计在同一短事务提交。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def copy(
        self,
        scheme_id: UUID,
        body: AnalysisSchemeCopyRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            try:
                with session.begin():
                    lifecycle = PostgresAnalysisSchemeLifecycleRepository(session)
                    source = lifecycle.get_for_update(scheme_id)
                    if source is None:
                        raise AdministrationResourceNotFound
                    latest_id = lifecycle.latest_version_id(scheme_id)
                    if latest_id is None:
                        raise AdministrationConflict("分析方案缺少可复制版本")
                    schemes = PostgresAnalysisSchemeRepository(session)
                    latest = schemes.get_version(latest_id)
                    if latest is None:  # pragma: no cover - 同事务父版本刚读取存在
                        raise AdministrationConflict("分析方案版本不可读取")
                    copied = schemes.create_draft(
                        name=body.name,
                        description=latest.description,
                        definition=latest.definition,
                        actor_ref=principal.principal_id,
                    )
                    _audit(
                        session,
                        principal=principal,
                        request_id=request_id,
                        event_type="analysis_scheme_copied",
                        object_id=str(copied.scheme_id),
                        detail={
                            "source_scheme_id": str(scheme_id),
                            "source_version": latest.version,
                        },
                    )
                    return _scheme_response(schemes, copied.scheme_id)
            except IntegrityError as exc:
                raise AdministrationConflict("分析方案名称已存在") from exc
            except RuntimeError as exc:
                raise AdministrationConflict(str(exc)) from exc
        finally:
            session.close()

    def archive(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ResourceLifecycleResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeLifecycleRepository(session)
                row = repository.get_for_update(scheme_id)
                if row is None:
                    raise AdministrationResourceNotFound
                blockers = repository.archive_blockers(scheme_id)
                if blockers:
                    raise AdministrationConflict("；".join(blockers))
                archived_at = beijing_now()
                if not repository.archive(scheme_id, archived_at=archived_at):
                    raise AdministrationConflict("分析方案状态已经变化，请刷新后重试")
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="analysis_scheme_archived",
                    object_id=str(scheme_id),
                    detail={},
                )
                return ResourceLifecycleResponse(
                    id=scheme_id,
                    resource_type="analysis_scheme",
                    name=cast(str, row["name"]),
                    archived_at=archived_at,
                )
        finally:
            session.close()

    def restore(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeLifecycleRepository(session)
                if repository.get_for_update(scheme_id) is None:
                    raise AdministrationResourceNotFound
                if not repository.restore(scheme_id):
                    raise AdministrationConflict("分析方案当前不是已归档状态")
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="analysis_scheme_restored",
                    object_id=str(scheme_id),
                    detail={},
                )
        finally:
            session.close()

    def list_archived(self, *, principal: Principal) -> ResourceLifecycleListResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                records = PostgresAnalysisSchemeLifecycleRepository(session).list_archived()
                return ResourceLifecycleListResponse(
                    items=tuple(
                        ResourceLifecycleResponse(
                            id=item.id,
                            resource_type="analysis_scheme",
                            name=item.name,
                            archived_at=item.archived_at,
                        )
                        for item in records
                    )
                )
        finally:
            session.close()

    def delete_eligibility(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
    ) -> ResourceDeleteEligibilityResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeLifecycleRepository(session)
                if repository.get_for_update(scheme_id) is None:
                    raise AdministrationResourceNotFound
                blockers = repository.delete_blockers(scheme_id)
                return ResourceDeleteEligibilityResponse(
                    id=scheme_id,
                    eligible=not blockers,
                    blocking_reasons=blockers,
                )
        finally:
            session.close()

    def delete(
        self,
        scheme_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeLifecycleRepository(session)
                if repository.get_for_update(scheme_id) is None:
                    raise AdministrationResourceNotFound
                blockers = repository.delete_blockers(scheme_id)
                if blockers:
                    raise AdministrationConflict("；".join(blockers))
                if not repository.delete_archived(scheme_id):
                    raise AdministrationResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="analysis_scheme_deleted",
                    object_id=str(scheme_id),
                    detail={},
                )
        finally:
            session.close()


def install_analysis_scheme_lifecycle_routes(
    application: FastAPI,
    *,
    service: AnalysisSchemeLifecycleHttpService | None = None,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """把 Analysis Scheme 生命周期接入最终 API。"""

    resolved_identity = identity_resolver or DevelopmentIdentityResolver()
    runtime: PlatformRuntime | None = None

    def current_service() -> AnalysisSchemeLifecycleHttpService:
        nonlocal runtime
        if service is not None:
            return service
        if runtime is None:
            runtime = create_platform_runtime("api-analysis-scheme-lifecycle")
        return PostgresAnalysisSchemeLifecycleHttpService(runtime)

    if service is None:
        router = cast(Any, application.router)
        original_lifespan = router.lifespan_context

        @asynccontextmanager
        async def lifecycle_lifespan(app: FastAPI) -> AsyncIterator[None]:
            async with original_lifespan(app):
                try:
                    yield
                finally:
                    if runtime is not None:
                        runtime.close()

        router.lifespan_context = lifecycle_lifespan

    def principal(request: Request) -> Principal:
        return resolved_identity.resolve(request)

    @application.post(
        "/api/v1/analysis-schemes/{scheme_id}/copy",
        operation_id="copyAnalysisScheme",
        response_model=AnalysisSchemeResponse,
        status_code=status.HTTP_201_CREATED,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}, 409: {"model": HttpErrorResponse}},
        tags=["analysis-schemes"],
    )
    def copy_analysis_scheme(
        scheme_id: UUID,
        body: AnalysisSchemeCopyRequest,
        request: Request,
    ) -> AnalysisSchemeResponse:
        return current_service().copy(
            scheme_id,
            body,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/analysis-schemes/{scheme_id}/archive",
        operation_id="archiveAnalysisScheme",
        response_model=ResourceLifecycleResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}, 409: {"model": HttpErrorResponse}},
        tags=["analysis-schemes"],
    )
    def archive_analysis_scheme(
        scheme_id: UUID,
        request: Request,
    ) -> ResourceLifecycleResponse:
        return current_service().archive(
            scheme_id,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/analysis-schemes/{scheme_id}/restore",
        operation_id="restoreAnalysisScheme",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}, 409: {"model": HttpErrorResponse}},
        tags=["analysis-schemes"],
    )
    def restore_analysis_scheme(scheme_id: UUID, request: Request) -> Response:
        current_service().restore(
            scheme_id,
            principal=principal(request),
            request_id=_request_id(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.get(
        "/api/v1/analysis-schemes/lifecycle/archived",
        operation_id="listArchivedAnalysisSchemes",
        response_model=ResourceLifecycleListResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["analysis-schemes"],
    )
    def list_archived_analysis_schemes(request: Request) -> ResourceLifecycleListResponse:
        return current_service().list_archived(principal=principal(request))

    @application.get(
        "/api/v1/analysis-schemes/{scheme_id}/delete-eligibility",
        operation_id="getAnalysisSchemeDeleteEligibility",
        response_model=ResourceDeleteEligibilityResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}},
        tags=["analysis-schemes"],
    )
    def get_analysis_scheme_delete_eligibility(
        scheme_id: UUID,
        request: Request,
    ) -> ResourceDeleteEligibilityResponse:
        return current_service().delete_eligibility(
            scheme_id,
            principal=principal(request),
        )

    @application.delete(
        "/api/v1/analysis-schemes/{scheme_id}",
        operation_id="deleteAnalysisScheme",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}, 409: {"model": HttpErrorResponse}},
        tags=["analysis-schemes"],
    )
    def delete_analysis_scheme(scheme_id: UUID, request: Request) -> Response:
        current_service().delete(
            scheme_id,
            principal=principal(request),
            request_id=_request_id(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


def _scheme_response(
    repository: PostgresAnalysisSchemeRepository,
    scheme_id: UUID,
) -> AnalysisSchemeResponse:
    for scheme, versions in repository.list_schemes():
        if scheme["id"] != scheme_id:
            continue
        return AnalysisSchemeResponse(
            id=scheme_id,
            name=cast(str, scheme["name"]),
            active_version_id=cast(UUID | None, scheme["active_version_id"]),
            is_active=cast(bool, scheme["is_active"]),
            versions=tuple(_version_response(item) for item in versions),
            created_at=scheme["created_at"],
            updated_at=scheme["updated_at"],
        )
    raise AdministrationResourceNotFound


def _version_response(version: AnalysisSchemeVersionRecord) -> AnalysisSchemeVersionResponse:
    return AnalysisSchemeVersionResponse(
        id=version.id,
        scheme_id=version.scheme_id,
        version=version.version,
        status=cast(Any, version.status),
        description=version.description,
        definition=version.definition,
        prompt_sha256=version.prompt_sha256,
        taxonomy_sha256=version.taxonomy_sha256,
        created_by=version.created_by,
        created_at=version.created_at,
        published_at=version.published_at,
    )


def _audit(
    session: Any,
    *,
    principal: Principal,
    request_id: str,
    event_type: str,
    object_id: str,
    detail: dict[str, object],
) -> None:
    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(),
            actor_kind="principal",
            actor_ref=principal.principal_id,
            event_type=event_type,
            object_type="analysis_scheme",
            object_id=object_id,
            request_id=request_id,
            safe_detail=cast(Any, detail),
            created_at=beijing_now(),
        )
    )


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return str(value) if value else str(uuid4())


__all__ = [
    "AnalysisSchemeLifecycleHttpService",
    "PostgresAnalysisSchemeLifecycleHttpService",
    "install_analysis_scheme_lifecycle_routes",
]
