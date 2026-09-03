"""管理员车型、词包、Analysis Scheme、Provider 与审计 PostgreSQL Application Service。"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.adapters.persistence.postgres.system import (
    PostgresAuditRepository,
    PostgresProviderConfigRepository,
)
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.contracts.administration import (
    AnalysisSchemeCreateDraftRequest,
    AnalysisSchemeListResponse,
    AnalysisSchemePublishRequest,
    AnalysisSchemeResponse,
    AnalysisSchemeUpdateDraftRequest,
    AnalysisSchemeVersionResponse,
    AuditEventListResponse,
    AuditEventResponse,
    KeywordPackVehicleLinkRequest,
    KeywordPackVehicleLinksResponse,
    ProviderConfigCreateRequest,
    ProviderConfigListResponse,
    ProviderConfigResponse,
    ProviderConfigUpdateRequest,
    ProviderKind,
    VehicleModelAliasResponse,
    VehicleModelCreateRequest,
    VehicleModelListQuery,
    VehicleModelListResponse,
    VehicleModelMergeRequest,
    VehicleModelResponse,
    VehicleModelUpdateRequest,
)
from aima_ugc.modules.administration.http import (
    AdministrationConflict,
    AdministrationResourceNotFound,
)
from aima_ugc.modules.analysis.schemes import AnalysisSchemeVersionRecord
from aima_ugc.modules.identity import Principal
from aima_ugc.modules.system.models import AuditEvent, ProviderConfig
from aima_ugc.modules.system.tables import keyword_packs_table
from aima_ugc.modules.vehicles.models import VehicleModel
from aima_ugc.platform.security import SecretFileError, write_secret_ref
from aima_ugc.platform.time import beijing_now

from .runtime import PlatformRuntime
from .runtime_config import new_secret_ref


class PostgresAdministrationHttpService:
    """管理员配置写入与 audit_events 在同一 PostgreSQL 事务提交。"""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime

    def create_vehicle_model(self, body: VehicleModelCreateRequest, *, principal: Principal, request_id: str) -> VehicleModelResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresVehicleCatalogRepository(session)
                model = repository.create_model(code=body.code, display_name=body.display_name, aliases=body.aliases, actor_ref=principal.principal_id)
                _audit(session, principal=principal, request_id=request_id, event_type="vehicle_model_created", object_type="vehicle_model", object_id=str(model.id), detail={"code": model.code, "catalog_version": model.catalog_version})
                return _vehicle_response(repository, model)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def list_vehicle_models(self, query: VehicleModelListQuery) -> VehicleModelListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresVehicleCatalogRepository(session)
                models, total = repository.list_models(search=query.search, status=query.status, offset=query.offset, limit=query.limit)
                return VehicleModelListResponse(items=tuple(_vehicle_response(repository, model) for model in models), total=total, catalog_version=repository.current_catalog_version(), offset=query.offset, limit=query.limit)
        finally:
            session.close()

    def get_vehicle_model(self, vehicle_model_id: UUID) -> VehicleModelResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresVehicleCatalogRepository(session)
                model = repository.get_model(vehicle_model_id)
                if model is None:
                    raise AdministrationResourceNotFound
                return _vehicle_response(repository, model)
        finally:
            session.close()

    def update_vehicle_model(self, vehicle_model_id: UUID, body: VehicleModelUpdateRequest, *, principal: Principal, request_id: str) -> VehicleModelResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresVehicleCatalogRepository(session)
                try:
                    model = repository.update_model(vehicle_model_id, display_name=body.display_name, aliases=body.aliases, status=body.status, actor_ref=principal.principal_id)
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                _audit(session, principal=principal, request_id=request_id, event_type="vehicle_model_updated", object_type="vehicle_model", object_id=str(model.id), detail={"version": model.version, "catalog_version": model.catalog_version})
                return _vehicle_response(repository, model)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def delete_vehicle_model(self, vehicle_model_id: UUID, *, principal: Principal, request_id: str) -> None:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresVehicleCatalogRepository(session)
                try:
                    deleted = repository.delete_unreferenced_model(vehicle_model_id, actor_ref=principal.principal_id)
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                if not deleted:
                    raise AdministrationResourceNotFound
                _audit(session, principal=principal, request_id=request_id, event_type="vehicle_model_deleted", object_type="vehicle_model", object_id=str(vehicle_model_id), detail={})
        finally:
            session.close()

    def merge_vehicle_model(self, vehicle_model_id: UUID, body: VehicleModelMergeRequest, *, principal: Principal, request_id: str) -> VehicleModelResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresVehicleCatalogRepository(session)
                try:
                    model = repository.merge_model(vehicle_model_id, body.target_vehicle_model_id, actor_ref=principal.principal_id)
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                _audit(session, principal=principal, request_id=request_id, event_type="vehicle_model_merged", object_type="vehicle_model", object_id=str(vehicle_model_id), detail={"target_vehicle_model_id": str(body.target_vehicle_model_id)})
                return _vehicle_response(repository, model)
        finally:
            session.close()

    def replace_keyword_pack_vehicles(self, pack_id: UUID, body: KeywordPackVehicleLinkRequest, *, principal: Principal, request_id: str) -> KeywordPackVehicleLinksResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                if session.scalar(select(keyword_packs_table.c.id).where(keyword_packs_table.c.id == pack_id)) is None:
                    raise AdministrationResourceNotFound
                repository = PostgresVehicleCatalogRepository(session)
                try:
                    result = repository.replace_keyword_pack_models(pack_id, body.vehicle_model_ids, actor_ref=principal.principal_id)
                except LookupError as exc:
                    raise AdministrationResourceNotFound from exc
                _audit(session, principal=principal, request_id=request_id, event_type="keyword_pack_vehicle_links_updated", object_type="keyword_pack", object_id=str(pack_id), detail={"vehicle_model_ids": [str(item) for item in result]})
                return KeywordPackVehicleLinksResponse(pack_id=pack_id, vehicle_model_ids=result)
        finally:
            session.close()

    def create_analysis_scheme_draft(self, body: AnalysisSchemeCreateDraftRequest, *, principal: Principal, request_id: str) -> AnalysisSchemeResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                version = repository.create_draft(name=body.name.strip(), description=body.description.strip(), definition=body.definition, actor_ref=principal.principal_id)
                _audit_scheme(session, principal, request_id, "analysis_scheme_draft_created", version)
                return _scheme_response(repository, version.scheme_id)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def update_analysis_scheme_draft(self, version_id: UUID, body: AnalysisSchemeUpdateDraftRequest, *, principal: Principal, request_id: str) -> AnalysisSchemeResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                try:
                    version = repository.update_draft(version_id, expected_version=body.expected_version, description=body.description.strip(), definition=body.definition, actor_ref=principal.principal_id)
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                _audit_scheme(session, principal, request_id, "analysis_scheme_draft_updated", version)
                return _scheme_response(repository, version.scheme_id)
        finally:
            session.close()

    def publish_analysis_scheme(self, version_id: UUID, body: AnalysisSchemePublishRequest, *, principal: Principal, request_id: str) -> AnalysisSchemeResponse:
        return self._activate_scheme(version_id, body, principal=principal, request_id=request_id, event_type="analysis_scheme_published")

    def rollback_analysis_scheme(self, version_id: UUID, body: AnalysisSchemePublishRequest, *, principal: Principal, request_id: str) -> AnalysisSchemeResponse:
        return self._activate_scheme(version_id, body, principal=principal, request_id=request_id, event_type="analysis_scheme_rolled_back")

    def _activate_scheme(self, version_id: UUID, body: AnalysisSchemePublishRequest, *, principal: Principal, request_id: str, event_type: str) -> AnalysisSchemeResponse:
        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                try:
                    version = repository.activate_version(version_id, expected_version=body.expected_version)
                except RuntimeError as exc:
                    raise AdministrationConflict from exc
                _audit_scheme(session, principal, request_id, event_type, version)
                return _scheme_response(repository, version.scheme_id)
        finally:
            session.close()

    def list_analysis_schemes(self) -> AnalysisSchemeListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAnalysisSchemeRepository(session)
                version, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
                if created:
                    _audit_system_scheme_bootstrap(session, version)
                return AnalysisSchemeListResponse(items=tuple(_scheme_from_rows(scheme, versions) for scheme, versions in repository.list_schemes()))
        finally:
            session.close()

    def list_provider_configs(self, *, provider_kind: ProviderKind | None = None) -> ProviderConfigListResponse:
        """管理员只读 Provider 安全投影，绝不暴露 API Key/secret_ref。"""

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                configs = PostgresProviderConfigRepository(session).list_all(provider_kind=provider_kind)
                return ProviderConfigListResponse(items=tuple(_provider_response(item) for item in configs))
        finally:
            session.close()

    def create_provider_config(self, body: ProviderConfigCreateRequest, *, principal: Principal, request_id: str) -> ProviderConfigResponse:
        """创建 Provider；Secret 以服务端生成的不可变引用写入批准根目录。"""

        principal.require_administrator()
        config_id = uuid4()
        secret_ref = new_secret_ref(config_id, uuid4().hex)
        try:
            candidate = ProviderConfig(
                id=config_id,
                provider=body.provider,
                provider_kind=body.provider_kind,
                display_name=body.display_name,
                base_url=body.base_url,
                model=body.model,
                secret_ref=secret_ref,
                timeout_seconds=body.timeout_seconds,
                max_retries=body.max_retries,
                max_concurrency=body.max_concurrency,
                max_rps=body.max_rps,
                is_default=body.is_default,
                revision=1,
                enabled=body.enabled,
            )
            write_secret_ref(self._runtime.settings.external_secret_root, secret_ref, body.api_key)
        except (ValueError, SecretFileError) as exc:
            raise AdministrationConflict from exc

        session = self._runtime.database.new_session()
        try:
            with session.begin():
                created = PostgresProviderConfigRepository(session).create(candidate)
                _audit_provider(session, principal, request_id, "provider_config_created", created, secret_rotated=True)
                return _provider_response(created)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def update_provider_config(self, provider_config_id: UUID, body: ProviderConfigUpdateRequest, *, principal: Principal, request_id: str) -> ProviderConfigResponse:
        """更新 Provider；API Key 未提供时保持原 Secret 引用，提供时只新增不覆盖。"""

        principal.require_administrator()
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigRepository(session)
                current = repository.get(provider_config_id)
                if current is None:
                    raise AdministrationResourceNotFound
                model = body.model
                if current.provider_kind == "llm" and not model:
                    raise AdministrationConflict("LLM Provider 必须配置 model")
                if current.provider_kind == "collection" and model is not None:
                    raise AdministrationConflict("采集 Provider 不使用 model")
                secret_ref = current.secret_ref
                secret_rotated = body.api_key is not None
                if body.api_key is not None:
                    secret_ref = new_secret_ref(provider_config_id, uuid4().hex)
                    try:
                        write_secret_ref(self._runtime.settings.external_secret_root, secret_ref, body.api_key)
                    except (ValueError, SecretFileError) as exc:
                        raise AdministrationConflict from exc
                try:
                    updated = repository.update_settings(
                        provider_config_id,
                        display_name=body.display_name,
                        base_url=body.base_url,
                        model=model,
                        secret_ref=secret_ref,
                        timeout_seconds=body.timeout_seconds,
                        max_retries=body.max_retries,
                        max_concurrency=body.max_concurrency,
                        max_rps=body.max_rps,
                        enabled=body.enabled,
                        is_default=body.is_default,
                    )
                except (KeyError, ValueError) as exc:
                    raise AdministrationConflict from exc
                _audit_provider(session, principal, request_id, "provider_config_updated", updated, secret_rotated=secret_rotated)
                return _provider_response(updated)
        except IntegrityError as exc:
            raise AdministrationConflict from exc
        finally:
            session.close()

    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                repository = PostgresAuditRepository(session)
                events = repository.list_page(offset=offset, limit=limit)
                return AuditEventListResponse(
                    items=tuple(AuditEventResponse(id=event.id, actor_ref=event.actor_ref, event_type=event.event_type, object_type=event.object_type, object_id=event.object_id, request_id=event.request_id, safe_detail=cast(dict[str, object], event.safe_detail), created_at=event.created_at) for event in events),
                    total=repository.count(), offset=offset, limit=limit,
                )
        finally:
            session.close()


def _vehicle_response(repository: PostgresVehicleCatalogRepository, model: VehicleModel) -> VehicleModelResponse:
    return VehicleModelResponse(
        id=model.id, code=model.code, display_name=model.display_name, status=model.status,
        version=model.version, catalog_version=model.catalog_version, merged_into_id=model.merged_into_id,
        aliases=tuple(VehicleModelAliasResponse(id=alias.id, text=alias.text, normalized_text=alias.normalized_text) for alias in repository.list_aliases(model.id)),
        keyword_pack_ids=repository.list_keyword_pack_ids(model.id), referenced=repository.is_referenced(model.id),
        created_at=model.created_at, updated_at=model.updated_at,
    )


def _provider_response(config: ProviderConfig) -> ProviderConfigResponse:
    return ProviderConfigResponse(
        id=config.id,
        provider_kind=config.provider_kind,
        provider=config.provider,
        display_name=config.display_name,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
        max_concurrency=config.max_concurrency,
        max_rps=config.max_rps,
        enabled=config.enabled,
        is_default=config.is_default,
        revision=config.revision,
        secret_configured=bool(config.secret_ref),
    )


def _scheme_response(repository: PostgresAnalysisSchemeRepository, scheme_id: UUID) -> AnalysisSchemeResponse:
    for scheme, versions in repository.list_schemes():
        if scheme["id"] == scheme_id:
            return _scheme_from_rows(scheme, versions)
    raise AdministrationResourceNotFound


def _scheme_from_rows(scheme: Any, versions: tuple[AnalysisSchemeVersionRecord, ...]) -> AnalysisSchemeResponse:
    return AnalysisSchemeResponse(
        id=cast(UUID, scheme["id"]), name=cast(str, scheme["name"]),
        active_version_id=cast(UUID | None, scheme["active_version_id"]), is_active=cast(bool, scheme["is_active"]),
        versions=tuple(_scheme_version_response(version) for version in versions), created_at=scheme["created_at"], updated_at=scheme["updated_at"],
    )


def _scheme_version_response(version: AnalysisSchemeVersionRecord) -> AnalysisSchemeVersionResponse:
    return AnalysisSchemeVersionResponse(
        id=version.id, scheme_id=version.scheme_id, version=version.version, status=cast(Any, version.status),
        description=version.description, definition=version.definition, prompt_sha256=version.prompt_sha256,
        taxonomy_sha256=version.taxonomy_sha256, created_by=version.created_by, created_at=version.created_at, published_at=version.published_at,
    )


def _audit_provider(session: Any, principal: Principal, request_id: str, event_type: str, config: ProviderConfig, *, secret_rotated: bool) -> None:
    _audit(
        session,
        principal=principal,
        request_id=request_id,
        event_type=event_type,
        object_type="provider_config",
        object_id=str(config.id),
        detail={
            "provider_kind": config.provider_kind,
            "provider": config.provider,
            "revision": config.revision,
            "enabled": config.enabled,
            "is_default": config.is_default,
            "secret_rotated": secret_rotated,
        },
    )


def _audit_scheme(session: Any, principal: Principal, request_id: str, event_type: str, version: AnalysisSchemeVersionRecord) -> None:
    _audit(session, principal=principal, request_id=request_id, event_type=event_type, object_type="analysis_scheme_version", object_id=str(version.id), detail={"scheme_id": str(version.scheme_id), "version": version.version, "prompt_sha256": version.prompt_sha256, "taxonomy_sha256": version.taxonomy_sha256})


def _audit_system_scheme_bootstrap(session: Any, version: AnalysisSchemeVersionRecord) -> None:
    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(), actor_kind="system", actor_ref="system:git-bootstrap", event_type="analysis_scheme_bootstrapped",
            object_type="analysis_scheme_version", object_id=str(version.id), request_id=None,
            safe_detail=cast(Any, {"scheme_id": str(version.scheme_id), "version": version.version, "prompt_sha256": version.prompt_sha256, "taxonomy_sha256": version.taxonomy_sha256}),
            created_at=beijing_now(),
        )
    )


def _audit(session: Any, *, principal: Principal, request_id: str, event_type: str, object_type: str, object_id: str, detail: dict[str, object]) -> None:
    PostgresAuditRepository(session).append(
        AuditEvent(
            id=uuid4(), actor_kind="principal", actor_ref=principal.principal_id, event_type=event_type,
            object_type=object_type, object_id=object_id, request_id=request_id, safe_detail=cast(Any, detail), created_at=beijing_now(),
        )
    )


__all__ = ["PostgresAdministrationHttpService"]
