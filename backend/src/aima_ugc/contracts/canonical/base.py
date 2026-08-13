"""Canonical V1 公共类型和基础约束。"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=512)]
PlatformName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class CanonicalBaseModel(BaseModel):
    """拒绝未声明字段，避免 Provider 私有字段泄漏进公共 Contract。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
