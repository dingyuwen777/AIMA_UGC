"""进程 readiness 的稳定内部结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CheckStatus = Literal["ok", "error"]


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """readiness 只暴露组件状态，不携带异常或连接细节。"""

    database: CheckStatus
    artifact_store: CheckStatus
    log_directory: CheckStatus

    @property
    def ready(self) -> bool:
        return self.database == "ok" and self.artifact_store == "ok" and self.log_directory == "ok"
