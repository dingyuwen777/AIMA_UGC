"""正式 Worker 的有界 HTTP 健康反馈聚合。"""

from __future__ import annotations

from bisect import insort
from datetime import datetime
from threading import Lock

from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.adapters.persistence.postgres.analysis_recovery import TransportObservation
from aima_ugc.modules.analysis.recovery import RECOVERY_MODE


class AnalysisRecoveryFeedback:
    """HTTP 线程只聚合时间；调度线程在现有短事务合并持久窗口。"""

    def __init__(self, *, mode: str = "recovery.v1") -> None:
        """失败时刻最多 4096 段，溢出合并最旧半窗；不缓存响应或请求身份。"""

        self._lock = Lock()
        self._mode = mode
        self._success: datetime | None = None
        self._failures: list[tuple[datetime, datetime]] = []

    def audit(self, audit: LLMHTTPRequestAudit) -> None:
        """v2 的任意 HTTP 响应证明网络可达，输出合法性仍由 Item Validator 判断。"""

        with self._lock:
            at = audit.completed_at
            if audit.status_code is not None and (
                self._mode == RECOVERY_MODE or 200 <= audit.status_code < 300
            ):
                if self._success is None or at > self._success:
                    self._success = at
                self._failures = [
                    (max(first, self._success), last)
                    for first, last in self._failures
                    if last > self._success
                ]
            elif (
                audit.error_code in {"timeout", "network_error"} and audit.timeout_phase != "pool"
                if self._mode == RECOVERY_MODE
                else (
                    audit.error_code in {"timeout", "network_error"}
                    or audit.status_code in {408, 429}
                    or (audit.status_code is not None and 500 <= audit.status_code < 600)
                )
            ):
                if self._success is None or at > self._success:
                    insort(self._failures, (at, at))
                    if len(self._failures) > 4096:
                        merged = (
                            self._failures[0][0],
                            max(last for _, last in self._failures[:2048]),
                        )
                        self._failures[:2048] = [merged]

    def take(self) -> TransportObservation:
        """转移当前聚合；事务失败由调用方停止执行，已持久 Item 仍可接管。"""

        with self._lock:
            value = TransportObservation(
                success_at=self._success, failure_spans=tuple(self._failures)
            )
            self._success = None
            self._failures.clear()
            return value
