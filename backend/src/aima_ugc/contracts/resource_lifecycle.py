"""产品配置资源编辑、归档、恢复与条件删除的公共 HTTP Contract。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aima_ugc.contracts.base import AimaHttpModel as BaseModel
from aima_ugc.contracts.http import CollectionPlanPlatformRequest, KeywordPackKeywordCreateRequest
from aima_ugc.contracts.platform import PlatformScope

ResourceLifecycleKind = Literal[
    "keyword_pack",
    "collection_plan",
    "provider_config",
    "analysis_scheme",
]


class ResourceLifecycleResponse(BaseModel):
    """归档资源的最小业务投影，不暴露内部版本/关系实现。"""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    resource_type: ResourceLifecycleKind
    name: str
    archived_at: datetime


class ResourceLifecycleListResponse(BaseModel):
    """一个资源类型的已归档列表。"""

    model_config = ConfigDict(extra="forbid")

    items: tuple[ResourceLifecycleResponse, ...]


class ResourceDeleteEligibilityResponse(BaseModel):
    """物理删除前的只读资格；有历史引用时只允许归档。"""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    eligible: bool
    blocking_reasons: tuple[str, ...] = ()


class ResourceExpectedVersionRequest(BaseModel):
    """所有会覆盖配置内容的写操作都显式携带客户端已见版本。"""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(gt=0)


class KeywordPackUpdateRequest(ResourceExpectedVersionRequest):
    """原子编辑词包；省略 keywords 时兼容仅修改元数据的旧调用。"""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    keywords: tuple[KeywordPackKeywordCreateRequest, ...] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """词包名称统一去除首尾空白。"""

        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("词包名称不能为空")
        return value


class KeywordPackCopyRequest(BaseModel):
    """复制词包时只要求新名称；副本默认停用，避免意外进入运行链。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """复制名称统一去除首尾空白。"""

        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("词包名称不能为空")
        return value


class KeywordPackItemUpdateRequest(ResourceExpectedVersionRequest):
    """修改一个词包成员；共享 Keyword 通过关系替换避免影响其它词包。"""

    text: str = Field(min_length=1, max_length=500)
    source_platform_scope: PlatformScope = "all"
    platform_scope: PlatformScope = "all"
    priority: int = 100
    enabled: bool = True
    note: str = Field(default="", max_length=1000)

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("关键词不能为空")
        return value


class KeywordPackItemRemoveRequest(ResourceExpectedVersionRequest):
    """删除一个词包成员；共享 Keyword 实体本身不会被级联删除。"""

    platform_scope: PlatformScope = "all"


class CollectionPlanUpdateRequest(ResourceExpectedVersionRequest):
    """完整替换一个计划的下一版本配置；历史 Run/Occurrence 继续保留旧版本事实。"""

    name: str = Field(min_length=1, max_length=200)
    schedule_expr: str = Field(min_length=1, max_length=100)
    platforms: tuple[CollectionPlanPlatformRequest, ...] = Field(min_length=1, max_length=5)
    keyword_pack_ids: tuple[UUID, ...] = Field(default=(), max_length=20)
    brand_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    enabled: bool

    @field_validator("name", "schedule_expr", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        """计划名称与调度表达式必须是非空业务文本。"""

        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("计划名称和调度表达式不能为空")
        return value

    @model_validator(mode="after")
    def validate_unique_relations(self) -> CollectionPlanUpdateRequest:
        """保持与创建 Contract 相同的去重和最小执行面约束。"""

        platforms = [item.platform for item in self.platforms]
        if len(platforms) != len(set(platforms)):
            raise ValueError("同一计划的目标平台不得重复")
        if len(self.keyword_pack_ids) != len(set(self.keyword_pack_ids)):
            raise ValueError("同一计划的关键词包不得重复")
        if len(self.brand_ids) != len(set(self.brand_ids)):
            raise ValueError("同一计划的品牌不得重复")
        if not self.keyword_pack_ids:
            raise ValueError("计划必须选择至少一个 Keyword Pack 作为 Search Terms")
        return self


class CollectionPlanCopyRequest(BaseModel):
    """复制计划只要求新名称；副本默认停用并重新进入人工启用流程。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """计划副本名称统一去除首尾空白。"""

        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("计划名称不能为空")
        return value


class ProviderConnectionTestResponse(BaseModel):
    """连接测试只返回业务可理解结果，不返回 Secret、原始响应体或内部请求 ID。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str
    latency_ms: int | None = Field(default=None, ge=0)


class AnalysisSchemeCopyRequest(BaseModel):
    """复制分析方案时创建全新的未发布 Scheme 草稿。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("分析方案名称不能为空")
        return value


__all__ = [
    "AnalysisSchemeCopyRequest",
    "CollectionPlanCopyRequest",
    "CollectionPlanUpdateRequest",
    "KeywordPackCopyRequest",
    "KeywordPackItemRemoveRequest",
    "KeywordPackItemUpdateRequest",
    "KeywordPackUpdateRequest",
    "ProviderConnectionTestResponse",
    "ResourceDeleteEligibilityResponse",
    "ResourceExpectedVersionRequest",
    "ResourceLifecycleKind",
    "ResourceLifecycleListResponse",
    "ResourceLifecycleResponse",
]
