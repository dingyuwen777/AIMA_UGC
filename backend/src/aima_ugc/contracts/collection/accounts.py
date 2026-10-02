"""账号身份类型的公共语义；Provider Capability 决定当前开放的子集。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aima_ugc.contracts.platform import PlatformName

type CollectionAccountIdType = Literal[
    "red_id", "user_id", "unique_id", "sec_uid", "uid", "kuaishou_id", "eid"
]

ACCOUNT_ID_TYPES: dict[PlatformName, tuple[CollectionAccountIdType, ...]] = {
    "xiaohongshu": ("red_id", "user_id"),
    "douyin": ("unique_id", "sec_uid"),
    "weibo": ("uid",),
    "bilibili": ("uid",),
    "kuaishou": ("user_id", "kuaishou_id", "eid"),
}


class ProviderAccountCapabilityV1(BaseModel):
    """账号表单与创建校验使用同一 Provider 能力事实。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    supported_id_types: tuple[CollectionAccountIdType, ...] = Field(min_length=1)
    default_id_type: CollectionAccountIdType
    nickname_supported: bool = True

    @model_validator(mode="after")
    def validate_default(self) -> ProviderAccountCapabilityV1:
        if self.default_id_type not in self.supported_id_types:
            raise ValueError("账号默认 ID 类型必须属于已支持类型")
        if len(self.supported_id_types) != len(set(self.supported_id_types)):
            raise ValueError("账号能力的 ID 类型不得重复")
        return self
