"""Provider-neutral 内容处理记录。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aima_ugc.contracts.canonical import CanonicalContentV1

from .content_label import ContentLabelAnalysisV1, ContentLabelAnalysisV2

ContentLabelAnalysis = Annotated[
    ContentLabelAnalysisV1 | ContentLabelAnalysisV2,
    Field(discriminator="schema_version"),
]


class UnifiedContentRecordV1(BaseModel):
    """Canonical 内容、命中关键词及可选的已校验分析结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-record.v1"] = "content-record.v1"
    content: CanonicalContentV1
    matched_keywords: list[str] = Field(min_length=1)
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
