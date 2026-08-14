"""Stage 6 小红书已存 Raw 回放 Job 领域入口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from aima_ugc.contracts.provider import RawEnvelopeV1
from aima_ugc.modules.collection.providers import RawArtifactService
from aima_ugc.platform.jobs import JobHandlerResult, JobRegistry
from aima_ugc.platform.jobs.models import JobExecutionContextProtocol
from aima_ugc.platform.storage import ArtifactRecord

XHS_RAW_REPLAY_JOB_TYPE = "collection.xhs.raw-replay.v1"
XHS_RAW_REPLAY_PAYLOAD_VERSION = "collection.xhs.raw-replay.v1"


class XhsRawReplayJobPayload(BaseModel):
    """只保存已存在 Provider Attempt 身份，不携带 Raw 或 Secret。"""

    schema_version: Literal["collection.xhs.raw-replay.v1"] = "collection.xhs.raw-replay.v1"
    provider_attempt_id: UUID


@dataclass(frozen=True, slots=True)
class XhsReplaySource:
    """从数据库受约束来源链解析出的 Raw 回放上下文。"""

    provider_attempt_id: UUID
    provider_request_id: UUID
    provider: str
    platform: str
    operation: str
    source_type: str
    source_value: str
    artifact: ArtifactRecord


@dataclass(frozen=True, slots=True)
class XhsReplaySummary:
    content_count: int = 0
    comment_count: int = 0


class XhsReplaySourceReader(Protocol):
    def load(self, provider_attempt_id: UUID) -> XhsReplaySource: ...


class XhsReplayIngestionWriter(Protocol):
    def ingest(self, source: XhsReplaySource, envelope: RawEnvelopeV1) -> XhsReplaySummary: ...


class XhsRawReplayHandler:
    """只回放已存 Raw；故意不接受 ProviderClient/Transport。"""

    def __init__(
        self,
        *,
        raw_artifacts: RawArtifactService,
        source_reader: XhsReplaySourceReader,
        ingestion_writer: XhsReplayIngestionWriter,
    ) -> None:
        self._raw_artifacts = raw_artifacts
        self._source_reader = source_reader
        self._ingestion_writer = ingestion_writer

    def __call__(
        self,
        payload: BaseModel,
        context: JobExecutionContextProtocol,
    ) -> JobHandlerResult:
        if not isinstance(payload, XhsRawReplayJobPayload):
            raise TypeError("XHS Raw Replay Job Payload 类型错误")
        source = self._source_reader.load(payload.provider_attempt_id)
        envelope = self._raw_artifacts.replay(source.artifact)
        _validate_replay_source(source, envelope)
        if context.cancel_requested():
            return JobHandlerResult.cancelled()
        summary = self._ingestion_writer.ingest(source, envelope)
        context.heartbeat(progress=95)
        return JobHandlerResult.succeeded(
            result={
                "provider_attempt_id": str(source.provider_attempt_id),
                "content_count": summary.content_count,
                "comment_count": summary.comment_count,
            }
        )


def register_xhs_raw_replay_job(registry: JobRegistry, handler: XhsRawReplayHandler) -> None:
    """把 Stage 6 Raw Replay Handler 注册到现有持久化 Job Runtime。"""
    registry.register(
        job_type=XHS_RAW_REPLAY_JOB_TYPE,
        payload_version=XHS_RAW_REPLAY_PAYLOAD_VERSION,
        payload_model=XhsRawReplayJobPayload,
        handler=handler,
        retry_on_timeout=True,
    )


def _validate_replay_source(source: XhsReplaySource, envelope: RawEnvelopeV1) -> None:
    if source.provider != "tikhub" or source.platform != "xhs":
        raise ValueError("XHS Raw Replay 只接受 tikhub/xhs 来源")
    if envelope.provider != source.provider or envelope.platform != source.platform:
        raise ValueError("Raw Envelope Provider/Platform 与数据库来源链不一致")
    if envelope.operation != source.operation:
        raise ValueError("Raw Envelope Operation 与数据库来源链不一致")
    if envelope.request_id != source.provider_request_id:
        raise ValueError("Raw Envelope request_id 与数据库来源链不一致")
    if envelope.attempt_id != source.provider_attempt_id:
        raise ValueError("Raw Envelope attempt_id 与数据库来源链不一致")
