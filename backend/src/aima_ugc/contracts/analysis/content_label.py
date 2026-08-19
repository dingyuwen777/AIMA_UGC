"""Provider-neutral 舆情内容 AI 打标结果契约。"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ContentLabelPairV2(BaseModel):
    """一个经过 Taxonomy 校验的一级/二级标签父子对。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)


class ContentLabelAnalysisV1(BaseModel):
    """通过 PromptTaxonomy 与本地 Validator 校验后的单标签分析结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-label-analysis.v1"] = "content-label-analysis.v1"
    sentiment: str = Field(min_length=1, max_length=128)
    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)
    prompt_version: str = Field(min_length=1, max_length=256)
    prompt_sha256: str = Field(pattern=_SHA256_PATTERN)
    taxonomy_sha256: str = Field(pattern=_SHA256_PATTERN)
    model_provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    input_hash: str = Field(pattern=_SHA256_PATTERN)
    analyzed_at: AwareDatetime
    analysis_status: Literal["succeeded"] = "succeeded"


class ContentLabelAnalysisV2(BaseModel):
    """当前多标签成功分析结果：一个情感 + 一个或多个一级/二级标签对。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-label-analysis.v2"] = "content-label-analysis.v2"
    sentiment: str = Field(min_length=1, max_length=128)
    labels: tuple[ContentLabelPairV2, ...] = Field(min_length=1)
    prompt_version: str = Field(min_length=1, max_length=256)
    prompt_sha256: str = Field(pattern=_SHA256_PATTERN)
    taxonomy_sha256: str = Field(pattern=_SHA256_PATTERN)
    model_provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    input_hash: str = Field(pattern=_SHA256_PATTERN)
    analyzed_at: AwareDatetime
    analysis_status: Literal["succeeded"] = "succeeded"

    @field_validator("labels")
    @classmethod
    def validate_unique_labels(
        cls, value: tuple[ContentLabelPairV2, ...]
    ) -> tuple[ContentLabelPairV2, ...]:
        keys = [(item.primary_label, item.secondary_label) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("labels 不能包含重复一级/二级标签对")
        return value

    @property
    def primary_label(self) -> str:
        """兼容旧只读调用：返回按重要性排序后的第一个一级标签。"""

        return self.labels[0].primary_label

    @property
    def secondary_label(self) -> str:
        """兼容旧只读调用：返回按重要性排序后的第一个二级标签。"""

        return self.labels[0].secondary_label
