"""正式 Collection Run Job 的版本化 Payload Contract。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

COLLECTION_RUN_JOB_TYPE = "collection.run.v1"
COLLECTION_RUN_PAYLOAD_VERSION = "collection.run.v1"


class CollectionRunJobPayload(BaseModel):
    """Worker 通过当前 Job ID 反查 Run；Payload 不复制 Run ID、Plan 或 Secret。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["collection.run.v1"] = "collection.run.v1"


__all__ = [
    "COLLECTION_RUN_JOB_TYPE",
    "COLLECTION_RUN_PAYLOAD_VERSION",
    "CollectionRunJobPayload",
]
