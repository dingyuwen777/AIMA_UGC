"""Provider-neutral 内容处理记录。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aima_ugc.contracts.canonical import CanonicalContentV1

from .content_label import ContentLabelAnalysisV1, ContentLabelAnalysisV2, ContentLabelAnalysisV3

ContentLabelAnalysis = Annotated[
    ContentLabelAnalysisV1 | ContentLabelAnalysisV2 | ContentLabelAnalysisV3,
    Field(discriminator="schema_version"),
]


class UnifiedContentRecordV1(BaseModel):
    """Canonical 内容、命中关键词及可选的已校验分析结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-record.v1"] = "content-record.v1"
    content: CanonicalContentV1
    matched_keywords: list[str] = Field(default_factory=list)
    matched_vehicle_aliases: list[str] = Field(default_factory=list)
    analysis: ContentLabelAnalysis | None = None

    @field_validator("matched_keywords")
    @classmethod
    def validate_matched_keywords(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("matched_keywords 不能包含重复关键词")
        for keyword in value:
            if not keyword or keyword != keyword.strip():
                raise ValueError("matched_keywords 必须是非空且已清洗的字符串")
        return value

    @field_validator("matched_vehicle_aliases")
    @classmethod
    def validate_matched_vehicle_aliases(cls, value: list[str]) -> list[str]:
        """冻结命中的非空车型别名，并拒绝重复证据。"""

        if len(value) != len(set(value)):
            raise ValueError("matched_vehicle_aliases 不能重复")
        if any(not item or item != item.strip() for item in value):
            raise ValueError("matched_vehicle_aliases 必须是非空且已清洗的字符串")
        return value
