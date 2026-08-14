"""版本化 Job Payload 与 Handler 注册表。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from .models import JobExecutionContextProtocol, JobHandlerResult



type JobHandler = Callable[[BaseModel, JobExecutionContextProtocol], JobHandlerResult]


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """单个 Job 类型的生产执行定义。"""

    job_type: str
    payload_version: str
    payload_model: type[BaseModel]
    handler: JobHandler
    retry_on_timeout: bool


class JobRegistry:
    """进程启动时构建的 Job 类型注册表。"""

    def __init__(self) -> None:
        self._definitions: dict[str, JobDefinition] = {}

    def register(
        self,
        *,
        job_type: str,
        payload_version: str,
        payload_model: type[BaseModel],
        handler: JobHandler,
        retry_on_timeout: bool,
    ) -> None:
        if job_type in self._definitions:
            raise ValueError(f"job type already registered: {job_type}")
        self._definitions[job_type] = JobDefinition(
            job_type=job_type,
            payload_version=payload_version,
            payload_model=payload_model,
            handler=handler,
            retry_on_timeout=retry_on_timeout,
        )

    @property
    def supported_types(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    @property
    def timeout_retry_types(self) -> tuple[str, ...]:
        return tuple(
            job_type
            for job_type, definition in self._definitions.items()
            if definition.retry_on_timeout
        )

    def get(self, job_type: str) -> JobDefinition:
        try:
            return self._definitions[job_type]
        except KeyError as exc:
            raise KeyError(f"job type not registered: {job_type}") from exc

    def validate_payload(
        self,
        *,
        job_type: str,
        payload_version: str,
        payload: object,
    ) -> BaseModel:
        definition = self.get(job_type)
        if payload_version != definition.payload_version:
            raise ValueError(
                "payload version mismatch for "
                f"{job_type}: expected {definition.payload_version}, got {payload_version}"
            )
        return definition.payload_model.model_validate(payload)
