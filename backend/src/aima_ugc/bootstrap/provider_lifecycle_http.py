"""Provider 配置归档、恢复、条件删除与无业务副作用连接测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response, status

from aima_ugc.adapters.persistence.postgres.provider_lifecycle import (
    PostgresProviderConfigLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.system import (
    PostgresAuditRepository,
    PostgresProviderConfigRepository,
)
from aima_ugc.adapters.providers.connectivity import (
    ProviderConnectionTestUnsupported,
    test_provider_connection,
)
from aima_ugc.contracts.http import HttpErrorResponse
from aima_ugc.contracts.resource_lifecycle import (
    ProviderConnectionTestResponse,
    ResourceDeleteEligibilityResponse,
    ResourceLifecycleListResponse,
    ResourceLifecycleResponse,
)
from aima_ugc.modules.administration.http import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.identity import DevelopmentIdentityResolver, IdentityResolver, Principal
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.security import SecretFileError, read_secret_ref
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime, create_platform_runtime


class ProviderLifecycleHttpService(Protocol):
    """扩展路由只依赖业务服务，测试可注入 Fake。"""

    def test_connection(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConnectionTestResponse: ...

    def archive(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ResourceLifecycleResponse: ...

    def restore(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None: ...

    def list_archived(self, *, principal: Principal) -> ResourceLifecycleListResponse: ...

    def delete_eligibility(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
    ) -> ResourceDeleteEligibilityResponse: ...

    def delete(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None: ...


class PostgresProviderLifecycleHttpService:
    """Provider 生命周期写入与审计使用短事务；外部连接测试不占数据库事务。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def test_connection(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConnectionTestResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                config = PostgresProviderConfigRepository(session).get(provider_config_id)
                if config is None:
                    raise AdministrationResourceNotFound
                archived_ids = {
                    item.id for item in PostgresProviderConfigLifecycleRepository(session).list_archived()
                }
                if provider_config_id in archived_ids:
                    raise AdministrationConflict("已归档 Provider 不能执行连接测试")
        finally:
            session.close()

        try:
            credential = read_secret_ref(
                self._runtime.settings.external_secret_root,
                config.secret_ref,
            )
            result = test_provider_connection(config, credential)
        except SecretFileError as exc:
            raise AdministrationConflict("Provider API Key 当前不可读取") from exc
        except ProviderConnectionTestUnsupported as exc:
            raise AdministrationConflict(str(exc)) from exc

        audit_session = self._runtime.database.new_session()
        try:
            with audit_session.begin():
                _audit(
                    audit_session,
                    principal=principal,
                    request_id=request_id,
                    event_type="provider_connection_tested",
                    object_id=str(provider_config_id),
                    detail={"ok": result.ok, "latency_ms": result.latency_ms},
                )
        finally:
            audit_session.close()
        return ProviderConnectionTestResponse(
            ok=result.ok,
            message=result.message,
            latency_ms=result.latency_ms,
        )

    def archive(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> ResourceLifecycleResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigLifecycleRepository(session)
                if repository.get_for_update(provider_config_id) is None:
                    raise AdministrationResourceNotFound
                blockers = repository.archive_blockers(provider_config_id)
                if blockers:
                    raise AdministrationConflict("；".join(blockers))
                archived_at = beijing_now()
                archived = repository.archive(provider_config_id, archived_at=archived_at)
                if archived is None:
                    raise AdministrationConflict("Provider 状态已经变化，请刷新后重试")
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="provider_config_archived",
                    object_id=str(provider_config_id),
                    detail={"revision": archived.revision},
                )
                return ResourceLifecycleResponse(
                    id=provider_config_id,
                    resource_type="provider_config",
                    name=archived.display_name,
                    archived_at=archived_at,
                )
        finally:
            session.close()

    def restore(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                restored = PostgresProviderConfigLifecycleRepository(session).restore(
                    provider_config_id
                )
                if restored is None:
                    raise AdministrationResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="provider_config_restored",
                    object_id=str(provider_config_id),
                    detail={"revision": restored.revision},
                )
        finally:
            session.close()

    def list_archived(self, *, principal: Principal) -> ResourceLifecycleListResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                records = PostgresProviderConfigLifecycleRepository(session).list_archived()
                return ResourceLifecycleListResponse(
                    items=tuple(
                        ResourceLifecycleResponse(
                            id=item.id,
                            resource_type="provider_config",
                            name=item.display_name,
                            archived_at=item.archived_at,
                        )
                        for item in records
                    )
                )
        finally:
            session.close()

    def delete_eligibility(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
    ) -> ResourceDeleteEligibilityResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigLifecycleRepository(session)
                if repository.get_for_update(provider_config_id) is None:
                    raise AdministrationResourceNotFound
                blockers = repository.delete_blockers(provider_config_id)
                return ResourceDeleteEligibilityResponse(
                    id=provider_config_id,
                    eligible=not blockers,
                    blocking_reasons=blockers,
                )
        finally:
            session.close()

    def delete(
        self,
        provider_config_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigLifecycleRepository(session)
                if repository.get_for_update(provider_config_id) is None:
                    raise AdministrationResourceNotFound
                blockers = repository.delete_blockers(provider_config_id)
                if blockers:
                    raise AdministrationConflict("；".join(blockers))
                if not repository.delete_archived(provider_config_id):
                    raise AdministrationResourceNotFound
                _audit(
                    session,
                    principal=principal,
                    request_id=request_id,
                    event_type="provider_config_deleted",
                    object_id=str(provider_config_id),
                    detail={},
                )
        finally:
            session.close()


def install_provider_lifecycle_routes(
    application: FastAPI,
    *,
    service: ProviderLifecycleHttpService | None = None,
    identity_resolver: IdentityResolver | None = None,
) -> None:
    """把 Provider 生命周期扩展装配到最终 API，不复制主路由实现。"""

    resolved_identity = identity_resolver or DevelopmentIdentityResolver()
    runtime: PlatformRuntime | None = None

    def current_service() -> ProviderLifecycleHttpService:
        nonlocal runtime
        if service is not None:
            return service
        if runtime is None:
            runtime = create_platform_runtime("api-provider-lifecycle")
        return PostgresProviderLifecycleHttpService(runtime)

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
        "/api/v1/provider-configs/{provider_config_id}/test-connection",
        operation_id="testProviderConfigConnection",
        response_model=ProviderConnectionTestResponse,
        responses={
            403: {"model": HttpErrorResponse},
            404: {"model": HttpErrorResponse},
            409: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["administration", "provider-configs"],
    )
    def test_provider_config_connection(
        provider_config_id: UUID,
        request: Request,
    ) -> ProviderConnectionTestResponse:
        return current_service().test_connection(
            provider_config_id,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/provider-configs/{provider_config_id}/archive",
        operation_id="archiveProviderConfig",
        response_model=ResourceLifecycleResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}, 409: {"model": HttpErrorResponse}},
        tags=["administration", "provider-configs"],
    )
    def archive_provider_config(
        provider_config_id: UUID,
        request: Request,
    ) -> ResourceLifecycleResponse:
        return current_service().archive(
            provider_config_id,
            principal=principal(request),
            request_id=_request_id(request),
        )

    @application.post(
        "/api/v1/provider-configs/{provider_config_id}/restore",
        operation_id="restoreProviderConfig",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}},
        tags=["administration", "provider-configs"],
    )
    def restore_provider_config(provider_config_id: UUID, request: Request) -> Response:
        current_service().restore(
            provider_config_id,
            principal=principal(request),
            request_id=_request_id(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.get(
        "/api/v1/provider-configs/lifecycle/archived",
        operation_id="listArchivedProviderConfigs",
        response_model=ResourceLifecycleListResponse,
        responses={403: {"model": HttpErrorResponse}},
        tags=["administration", "provider-configs"],
    )
    def list_archived_provider_configs(request: Request) -> ResourceLifecycleListResponse:
        return current_service().list_archived(principal=principal(request))

    @application.get(
        "/api/v1/provider-configs/{provider_config_id}/delete-eligibility",
        operation_id="getProviderConfigDeleteEligibility",
        response_model=ResourceDeleteEligibilityResponse,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}},
        tags=["administration", "provider-configs"],
    )
    def get_provider_config_delete_eligibility(
        provider_config_id: UUID,
        request: Request,
    ) -> ResourceDeleteEligibilityResponse:
        return current_service().delete_eligibility(
            provider_config_id,
            principal=principal(request),
        )

    @application.delete(
        "/api/v1/provider-configs/{provider_config_id}",
        operation_id="deleteProviderConfig",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={403: {"model": HttpErrorResponse}, 404: {"model": HttpErrorResponse}, 409: {"model": HttpErrorResponse}},
        tags=["administration", "provider-configs"],
    )
    def delete_provider_config(provider_config_id: UUID, request: Request) -> Response:
        current_service().delete(
            provider_config_id,
            principal=principal(request),
            request_id=_request_id(request),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            object_type="provider_config",
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
    "PostgresProviderLifecycleHttpService",
    "ProviderLifecycleHttpService",
    "install_provider_lifecycle_routes",
]
