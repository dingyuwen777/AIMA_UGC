"""运行时冻结的全局 Relevance 关键词快照。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RelevanceSnapshotV1(BaseModel):
    """Import Job / Collection Run 创建时冻结的完整相关性执行输入。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["relevance-snapshot.v1"] = "relevance-snapshot.v1"
    keyword_pack_id: UUID
    keyword_pack_version: int = Field(gt=0)
    config_version: int = Field(gt=0)
    effective_keywords: tuple[str, ...] = Field(min_length=1)


__all__ = ["RelevanceSnapshotV1"]
