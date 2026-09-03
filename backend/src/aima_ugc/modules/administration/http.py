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
    """车型、词包关系、Scheme 与审计的管理边界。"""

    def create_vehicle_model(
        self,
        body: VehicleModelCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleModelResponse:
        """由管理员创建车型。"""

        ...

    def list_vehicle_models(self, query: VehicleModelListQuery) -> VehicleModelListResponse:
        """读取有界车型目录。"""

        ...

    def get_vehicle_model(self, vehicle_model_id: UUID) -> VehicleModelResponse:
        """读取单个车型及引用摘要。"""

        ...

    def update_vehicle_model(
        self,
        vehicle_model_id: UUID,
        body: VehicleModelUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleModelResponse:
        """由管理员更新未合并车型。"""

        ...

    def delete_vehicle_model(
        self,
        vehicle_model_id: UUID,
        *,
        principal: Principal,
        request_id: str,
    ) -> None:
        """物理删除从未引用的车型。"""

        ...

    def merge_vehicle_model(
        self,
        vehicle_model_id: UUID,
        body: VehicleModelMergeRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> VehicleModelResponse:
        """把源车型合并到 active 目标车型。"""

        ...

    def replace_keyword_pack_vehicles(
        self,
        pack_id: UUID,
        body: KeywordPackVehicleLinkRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> KeywordPackVehicleLinksResponse:
        """原子替换词包引用的车型集合。"""

        ...

    def create_analysis_scheme_draft(
        self,
        body: AnalysisSchemeCreateDraftRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse:
        """创建原子 Analysis Scheme 草稿。"""

        ...

    def update_analysis_scheme_draft(
        self,
        version_id: UUID,
        body: AnalysisSchemeUpdateDraftRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse:
        """以旧草稿为并发前提追加一个新草稿版本。"""

        ...

    def publish_analysis_scheme(
        self,
        version_id: UUID,
        body: AnalysisSchemePublishRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse:
        """发布指定 Scheme Version。"""

        ...

    def rollback_analysis_scheme(
        self,
        version_id: UUID,
        body: AnalysisSchemePublishRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> AnalysisSchemeResponse:
        """把历史 Scheme Version 重新激活。"""

        ...

    def list_analysis_schemes(self) -> AnalysisSchemeListResponse:
        """读取 Scheme 与完整版本历史。"""

        ...

    def list_provider_configs(
        self,
        *,
        provider_kind: ProviderKind | None = None,
    ) -> ProviderConfigListResponse:
        """管理员读取 LLM/TikHub Provider 安全投影。"""

        ...

    def create_provider_config(
        self,
        body: ProviderConfigCreateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """管理员创建 Provider 与不可变 Secret 引用。"""

        ...

    def update_provider_config(
        self,
        provider_config_id: UUID,
        body: ProviderConfigUpdateRequest,
        *,
        principal: Principal,
        request_id: str,
    ) -> ProviderConfigResponse:
        """管理员修改 Provider；可选择轮换 Secret。"""

        ...

    def list_audit_events(self, *, offset: int, limit: int) -> AuditEventListResponse:
        """分页读取管理员安全审计摘要。"""

        ...


__all__ = [
    "AdministrationConflict",
    "AdministrationHttpService",
    "AdministrationResourceNotFound",
]
