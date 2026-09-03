"""管理员配置中心 HTTP Application Service Protocol。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aima_ugc.contracts.administration import (
    AnalysisSchemeCreateDraftRequest,
    AnalysisSchemeListResponse,
    AnalysisSchemePublishRequest,
    AnalysisSchemeResponse,
    AnalysisSchemeUpdateDraftRequest,
    AuditEventListResponse,
    KeywordPackVehicleLinkRequest,
    KeywordPackVehicleLinksResponse,
    ProviderConfigCreateRequest,
    ProviderConfigListResponse,
    ProviderConfigResponse,
    ProviderConfigUpdateRequest,
    ProviderKind,
    VehicleModelCreateRequest,
    VehicleModelListQuery,
    VehicleModelListResponse,
    VehicleModelMergeRequest,
    VehicleModelResponse,
    VehicleModelUpdateRequest,
)
from aima_ugc.modules.identity import Principal


class AdministrationResourceNotFound(LookupError):
    """管理员目标资源不存在。"""


class AdministrationConflict(RuntimeError):
    """管理员动作与当前版本、引用或状态冲突。"""


class AdministrationHttpService(Protocol):
    """车型、词包关系、Scheme、Provider 与审计的管理边界。"""

    def create_vehicle_model(
        self,
        body: VehicleModelCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleModelResponse: ...

    def list_vehicle_models(self, query: VehicleModelListQuery) -> VehicleModelListResponse: ...

    def get_vehicle_model(self, vehicle_model_id: UUID) -> VehicleModelResponse: ...

    def update_vehicle_model(
        self,
        vehicle_model_id: UUID,
        body: VehicleModelUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleModelResponse: ...

    def delete_vehicle_model(
        self,
        vehicle_model_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None: ...

    def merge_vehicle_model(
        self,
        vehicle_model_id: UUID,
        body: VehicleModelMergeRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleModelResponse: ...

    def replace_keyword_pack_vehicles(
        self,
        pack_id: UUID,
        body: KeywordPackVehicleLinkRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackVehicleLinksResponse: ...

    def create_analysis_scheme_draft(
        self,
        body: AnalysisSchemeCreateDraftRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse: ...

    def update_analysis_scheme_draft(
        self,
        version_id: UUID,
        body: AnalysisSchemeUpdateDraftRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse: ...

    def publish_analysis_scheme(
        self,
        version_id: UUID,
        body: AnalysisSchemePublishRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse: ...

    def rollback_analysis_scheme(
        self,
        version_id: UUID,
        body: AnalysisSchemePublishRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse: ...

    def list_analysis_schemes(self) -> AnalysisSchemeListResponse: ...

    def list_provider_configs(
        self,
        *,
        provider_kind: ProviderKind | None = None,
    ) -> ProviderConfigListResponse:
        """读取 Provider 安全管理投影。"""

        ...

    def create_provider_config(
        self,
        body: ProviderConfigCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """创建 Provider 并把 API Key 写入不可变 Secret Store。"""

        ...

    def update_provider_config(
        self,
        provider_config_id: UUID,
        body: ProviderConfigUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """更新 Provider；仅在提供 api_key 时创建新的 Secret 引用。"""

        ...

    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse: ...


__all__ = [
    "AdministrationConflict",
    "AdministrationHttpService",
    "AdministrationResourceNotFound",
]