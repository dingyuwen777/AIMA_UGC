"""Provider-neutral 舆情内容 AI 打标结果契约。"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


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
