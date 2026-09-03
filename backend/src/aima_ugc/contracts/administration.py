"""管理员配置中心、车型目录与 Principal 的 HTTP Contract。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)

from aima_ugc.contracts.base import AimaHttpModel as BaseModel

PrincipalRole = Literal["administrator", "user"]
PrincipalSource = Literal["development", "feishu"]
VehicleModelStatus = Literal["active", "deprecated", "merged"]
AnalysisSchemeVersionStatus = Literal["draft", "published", "retired"]
ProviderKind = Literal["collection", "llm"]

_TAXONOMY_PLACEHOLDER = "{{AIMA_TAXONOMY_JSON}}"


def _trimmed(value: object) -> object:
    """统一清理人工输入的首尾空白。"""

    return value.strip() if isinstance(value, str) else value


def _normalized_identity(value: str) -> str:
    """生成目录内用于冲突判断的大小写不敏感文本身份。"""

    return " ".join(value.split()).casefold()


class CurrentPrincipalResponse(BaseModel):
    """当前请求的 Provider-neutral Principal 投影。"""

    model_config = ConfigDict(extra="forbid")

    principal_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    role: PrincipalRole
    source: PrincipalSource

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_administrator(self) -> bool:
        """返回当前 Principal 是否具备管理员角色。"""

        return self.role == "administrator"


class VehicleModelCreateRequest(BaseModel):
    """创建一个稳定车型及其初始别名。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    display_name: str = Field(min_length=1, max_length=200)
    aliases: tuple[str, ...] = Field(default=(), max_length=100)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        """车型 code 使用去空白后的大写稳定身份。"""

        value = _trimmed(value)
        return value.upper() if isinstance(value, str) else value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        """车型显示名去除无意义首尾空白。"""

        return _trimmed(value)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """车型内别名必须非空且规范化后不重复。"""

        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned):
            raise ValueError("车型别名不能为空")
        identities = tuple(_normalized_identity(item) for item in cleaned)
        if len(identities) != len(set(identities)):
            raise ValueError("同一车型的别名不能重复")
        return cleaned


class VehicleModelUpdateRequest(BaseModel):
    """修改车型显示、别名或启停状态；稳定 code 不允许原地改写。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: tuple[str, ...] | None = Field(default=None, max_length=100)
    status: Literal["active", "deprecated"] | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        """显示名存在时去除首尾空白。"""

        return _trimmed(value)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """复用创建时的别名唯一规则。"""

        if value is None:
            return None
        return VehicleModelCreateRequest.validate_aliases(value)

    @model_validator(mode="after")
    def require_change(self) -> VehicleModelUpdateRequest:
        """拒绝不包含任何修改的空请求。"""

        if self.display_name is None and self.aliases is None and self.status is None:
            raise ValueError("车型更新必须至少包含一个字段")
        return self


class VehicleModelMergeRequest(BaseModel):
    """把错误或重复车型重定向到稳定目标车型。"""

    model_config = ConfigDict(extra="forbid")
    target_vehicle_model_id: UUID


class VehicleModelAliasResponse(BaseModel):
    """车型当前有效别名。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    text: str
    normalized_text: str


class VehicleModelResponse(BaseModel):
    """车型目录中的完整管理投影。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    code: str
    display_name: str
    status: VehicleModelStatus
    version: int = Field(gt=0)
    catalog_version: int = Field(gt=0)
    merged_into_id: UUID | None = None
    aliases: tuple[VehicleModelAliasResponse, ...] = ()
    keyword_pack_ids: tuple[UUID, ...] = ()
    referenced: bool = False
    created_at: datetime
    updated_at: datetime


class VehicleModelListQuery(BaseModel):
    """管理员车型目录的有界 Offset 查询。"""

    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, min_length=1, max_length=200)
    status: VehicleModelStatus | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class VehicleModelListResponse(BaseModel):
    """车型目录页响应。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[VehicleModelResponse, ...]
    total: int = Field(ge=0)
    catalog_version: int = Field(gt=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


class KeywordPackVehicleLinkRequest(BaseModel):
    """替换一个词包当前引用的车型集合。"""

    model_config = ConfigDict(extra="forbid")
    vehicle_model_ids: tuple[UUID, ...] = Field(default=(), max_length=100)

    @field_validator("vehicle_model_ids")
    @classmethod
    def validate_unique_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """词包内车型引用不得重复。"""

        if len(value) != len(set(value)):
            raise ValueError("vehicle_model_ids 不能重复")
        return value


class KeywordPackVehicleLinksResponse(BaseModel):
    """词包当前引用的车型 ID。"""

    model_config = ConfigDict(extra="forbid")
    pack_id: UUID
    vehicle_model_ids: tuple[UUID, ...]


class AnalysisSchemeDefinitionRequest(BaseModel):
    """一个原子 Analysis Scheme 的结构化定义。"""

    model_config = ConfigDict(extra="forbid")

    prompt_template: str = Field(min_length=1, max_length=100_000)
    sentiments: tuple[str, ...] = Field(min_length=1, max_length=50)
    voice_types: tuple[str, ...] = Field(min_length=1, max_length=50)
    labels: dict[str, tuple[str, ...]] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_definition(self) -> AnalysisSchemeDefinitionRequest:
        """校验受控模板、显式未知值和无重复 Taxonomy。"""

        if self.prompt_template.count(_TAXONOMY_PLACEHOLDER) != 1:
            raise ValueError("prompt_template 必须且只能包含一个 Taxonomy 占位符")
        if "无法判断" not in self.sentiments or "无法判断" not in self.voice_types:
            raise ValueError("情感和发声类型都必须显式包含“无法判断”")
        if self.labels.get("无法分类") != ("无法判断",):
            raise ValueError("标签必须显式包含“无法分类 / 无法判断”")
        if len(self.sentiments) != len(set(self.sentiments)):
            raise ValueError("sentiments 不能重复")
        if len(self.voice_types) != len(set(self.voice_types)):
            raise ValueError("voice_types 不能重复")
        secondaries: list[str] = []
        for primary, values in self.labels.items():
            if not primary.strip() or primary != primary.strip() or not values:
                raise ValueError("一级标签必须规范且至少包含一个二级标签")
            if any(not item.strip() or item != item.strip() for item in values):
                raise ValueError("二级标签必须是无首尾空白的非空字符串")
            if len(values) != len(set(values)):
                raise ValueError("同一一级标签下的二级标签不能重复")
            secondaries.extend(values)
        if len(secondaries) != len(set(secondaries)):
            raise ValueError("二级标签不能跨一级标签重复")
        return self


class AnalysisSchemeCreateDraftRequest(BaseModel):
    """基于当前发布版或新定义创建草稿。"""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    definition: AnalysisSchemeDefinitionRequest


class AnalysisSchemeUpdateDraftRequest(BaseModel):
    """以当前草稿版本为并发前提，追加一个新的草稿 Version。"""

    model_config = ConfigDict(extra="forbid")
    description: str = Field(default="", max_length=2000)
    definition: AnalysisSchemeDefinitionRequest
    expected_version: int = Field(gt=0)


class AnalysisSchemePublishRequest(BaseModel):
    """发布或回滚时的乐观锁请求。"""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(gt=0)


class AnalysisSchemeVersionResponse(BaseModel):
    """管理员可见的 Scheme Version；不包含 Secret 或 LLM API 配置。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    scheme_id: UUID
    version: int = Field(gt=0)
    status: AnalysisSchemeVersionStatus
    description: str
    definition: AnalysisSchemeDefinitionRequest
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    taxonomy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime
    published_at: datetime | None = None


class AnalysisSchemeResponse(BaseModel):
    """Scheme 聚合及其版本列表。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: str
    active_version_id: UUID | None = None
    is_active: bool
    versions: tuple[AnalysisSchemeVersionResponse, ...]
    created_at: datetime
    updated_at: datetime


class AnalysisSchemeListResponse(BaseModel):
    """管理员 Scheme 目录响应。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[AnalysisSchemeResponse, ...]


class ProviderConfigCreateRequest(BaseModel):
    """创建管理员可维护 Provider；API Key 仅用于本次写入，不进入响应或数据库。"""

    model_config = ConfigDict(extra="forbid")
    provider_kind: ProviderKind
    provider: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$",
    )
    display_name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, min_length=1, max_length=300)
    api_key: SecretStr
    timeout_seconds: int = Field(default=45, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=20)
    max_concurrency: int = Field(default=5, ge=1, le=500)
    max_rps: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool = True
    is_default: bool = False

    @field_validator("provider", "display_name", "base_url", "model", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        """清理 Provider 管理文本字段。"""

        return _trimmed(value)

    @model_validator(mode="after")
    def validate_provider(self) -> ProviderConfigCreateRequest:
        """校验 Provider Kind 与模型/default 语义。"""

        if not self.api_key.get_secret_value():
            raise ValueError("api_key 不能为空")
        if self.provider_kind == "llm" and not self.model:
            raise ValueError("LLM Provider 必须配置 model")
        if self.provider_kind == "collection" and self.model is not None:
            raise ValueError("采集 Provider 不使用 model")
        if self.provider_kind == "collection" and self.is_default:
            raise ValueError("采集 Provider 由采集计划显式引用，不使用默认标记")
        if self.is_default and not self.enabled:
            raise ValueError("默认 Provider 必须启用")
        return self


class ProviderConfigUpdateRequest(BaseModel):
    """完整替换可变 Provider 字段；省略 api_key 表示不轮换 Secret。"""

    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, min_length=1, max_length=300)
    api_key: SecretStr | None = None
    timeout_seconds: int = Field(default=45, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=20)
    max_concurrency: int = Field(default=5, ge=1, le=500)
    max_rps: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool = True
    is_default: bool = False

    @field_validator("display_name", "base_url", "model", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        """清理 Provider 可变文本字段。"""

        return _trimmed(value)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        """显式空 API Key 不等价于“不轮换”。"""

        if value is not None and not value.get_secret_value():
            raise ValueError("api_key 为空时请省略该字段")
        return value

    @model_validator(mode="after")
    def validate_state(self) -> ProviderConfigUpdateRequest:
        """默认 Provider 必须处于启用状态。"""

        if self.is_default and not self.enabled:
            raise ValueError("默认 Provider 必须启用")
        return self


class ProviderConfigResponse(BaseModel):
    """Provider 管理安全投影；绝不返回 API Key 或内部 secret_ref。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    provider_kind: ProviderKind
    provider: str
    display_name: str
    base_url: str
    model: str | None = None
    timeout_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    max_concurrency: int = Field(gt=0)
    max_rps: int | None = Field(default=None, gt=0)
    enabled: bool
    is_default: bool
    revision: int = Field(gt=0)
    secret_configured: bool


class ProviderConfigListResponse(BaseModel):
    """管理员 Provider 配置目录安全投影。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[ProviderConfigResponse, ...]


class AuditEventListQuery(BaseModel):
    """管理员审计事件稳定 Offset 分页。"""

    model_config = ConfigDict(extra="forbid")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=200)


class AuditEventResponse(BaseModel):
    """安全审计事件投影。"""

    model_config = ConfigDict(extra="forbid")
    id: UUID
    actor_ref: str | None = None
    event_type: str
    object_type: str | None = None
    object_id: str | None = None
    request_id: str | None = None
    safe_detail: dict[str, object]
    created_at: datetime


class AuditEventListResponse(BaseModel):
    """管理员审计事件分页响应。"""

    model_config = ConfigDict(extra="forbid")
    items: tuple[AuditEventResponse, ...]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)


__all__ = [
    "AnalysisSchemeCreateDraftRequest",
    "AnalysisSchemeDefinitionRequest",
    "AnalysisSchemeListResponse",
    "AnalysisSchemePublishRequest",
    "AnalysisSchemeResponse",
    "AnalysisSchemeUpdateDraftRequest",
    "AnalysisSchemeVersionResponse",
    "AuditEventListQuery",
    "AuditEventListResponse",
    "AuditEventResponse",
    "CurrentPrincipalResponse",
    "KeywordPackVehicleLinkRequest",
    "KeywordPackVehicleLinksResponse",
    "PrincipalRole",
    "ProviderConfigCreateRequest",
    "ProviderConfigListResponse",
    "ProviderConfigResponse",
    "ProviderConfigUpdateRequest",
    "ProviderKind",
    "PrincipalSource",
    "VehicleModelAliasResponse",
    "VehicleModelCreateRequest",
    "VehicleModelListQuery",
    "VehicleModelListResponse",
    "VehicleModelMergeRequest",
    "VehicleModelResponse",
    "VehicleModelStatus",
    "VehicleModelUpdateRequest",
]
