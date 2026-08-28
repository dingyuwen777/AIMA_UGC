"""Provider-neutral 舆情内容 AI 打标结果契约。"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_PATTERN = r"^[0-9a-f]{64}$"

type ContentRelevance = Literal["relevant", "irrelevant"]
type ContentVoiceType = Annotated[str, Field(min_length=1, max_length=128)]


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
    """历史多标签成功结果：一个情感 + 一个或多个一级/二级标签对。"""

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


class ContentLabelAnalysisV3(BaseModel):
    """当前成功分析结果：语义相关性 + 发声类型 + 条件式情感/多标签。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-label-analysis.v3"] = "content-label-analysis.v3"
    relevance: ContentRelevance
    voice_type: ContentVoiceType
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)
    labels: tuple[ContentLabelPairV2, ...] = ()
    prompt_version: str = Field(min_length=1, max_length=256)
    prompt_sha256: str = Field(pattern=_SHA256_PATTERN)
    taxonomy_sha256: str = Field(pattern=_SHA256_PATTERN)
    model_provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    input_hash: str = Field(pattern=_SHA256_PATTERN)
    analyzed_at: AwareDatetime
    analysis_status: Literal["succeeded"] = "succeeded"

    @model_validator(mode="after")
    def validate_relevance_shape(self) -> ContentLabelAnalysisV3:
        keys = [(item.primary_label, item.secondary_label) for item in self.labels]
        if len(keys) != len(set(keys)):
            raise ValueError("labels 不能包含重复一级/二级标签对")
        if self.relevance == "relevant":
            if self.sentiment is None or not self.labels:
                raise ValueError("relevant 内容必须包含情感和至少一个标签对")
        elif self.sentiment is not None or self.labels:
            raise ValueError("irrelevant 内容不得携带情感或业务标签")
        return self

    @property
    def is_relevant(self) -> bool:
        return self.relevance == "relevant"

    @property
    def primary_label(self) -> str | None:
        return self.labels[0].primary_label if self.labels else None

    @property
    def secondary_label(self) -> str | None:
        return self.labels[0].secondary_label if self.labels else None
