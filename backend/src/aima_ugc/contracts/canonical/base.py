"""Canonical V1 公共类型和基础约束。"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Identifier = Annotated[str, Field(min_length=1, max_length=512)]
PlatformName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
ObservedFieldPath = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=r"^[a-z][a-z0-9_.-]*$"),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class CanonicalBaseModel(BaseModel):
    """拒绝未声明字段，避免 Provider 私有字段泄漏进公共 Contract。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CanonicalObservationModel(CanonicalBaseModel):
    """一次原子 Observation 必须声明本次真实观察到的字段。"""

    observed_fields: list[ObservedFieldPath]

    @field_validator("observed_fields")
    @classmethod
    def observed_fields_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("observed_fields 不能包含重复字段")
        return value
