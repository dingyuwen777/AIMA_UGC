"""PostgreSQL 持久化 Job Runtime Repository。"""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.platform.jobs.models import (
    JobAttemptEvent,
    JobEventType,
    JobIdempotencyConflict,
    JobRecord,
    JobStatus,
    LeaseLostError,
)
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table


class PostgresJobRepository:
    """Job 表的唯一 Platform 写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        job_type: str,
        payload_version: str,
        payload: dict[str, object],
        internal_idempotency_key: str,
        request_id: str | None,
        priority: int,
        max_attempts: int,
        timeout_seconds: int,
        available_at: datetime | None = None,
    ) -> JobRecord:
        """创建内部工作项；相同类型和幂等键只能复用相同 Payload。"""
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        job_id = uuid4()
        values: dict[str, object] = {
            "id": job_id,
            "job_type": job_type,
            "payload_version": payload_version,
            "payload": payload,
            "status": "queued",
            "internal_idempotency_key": internal_idempotency_key,
            "request_id": request_id,
            "priority": priority,
            "attempt": 0,
            "lease_takeover_count": 0,
            "max_attempts": max_attempts,
            "timeout_seconds": timeout_seconds,
            "progress": 0,
            "available_at": available_at if available_at is not None else func.clock_timestamp(),
            "created_at": func.clock_timestamp(),
            "updated_at": func.clock_timestamp(),
        }
        statement = (
            pg_insert(jobs_table)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[jobs_table.c.job_type, jobs_table.c.internal_idempotency_key]
            )
            .returning(*jobs_table.c)
        )
        row = self._session.execute(statement).mappings().one_or_none()
        if row is not None:
            return _row_to_job(row)

        existing = (
            self._session.execute(
                select(jobs_table).where(
                    jobs_table.c.job_type == job_type,
                    jobs_table.c.internal_idempotency_key == internal_idempotency_key,
                )
            )
            .mappings()
            .one()
        )
        job = _row_to_job(existing)
        if job.payload_version != payload_version or job.payload != payload:
            raise JobIdempotencyConflict(
                "internal idempotency key already exists with different payload"
            )
        return job

    def get(self, job_id: UUID) -> JobRecord | None:
        row = (
            self._session.execute(select(jobs_table).where(jobs_table.c.id == job_id))
            .mappings()
            .one_or_none()
        )
        return _row_to_job(row) if row is not None else None

    def list_events(self, job_id: UUID) -> list[JobAttemptEvent]:
        rows = self._session.execute(
            select(job_attempt_events_table)
            .where(job_attempt_events_table.c.job_id == job_id)
            .order_by(job_attempt_events_table.c.event_seq)
        ).mappings()
        return [_row_to_event(row) for row in rows]

    def claim_next(
        self,
        *,
        supported_job_types: tuple[str, ...],
        worker_id: str,
        lease_seconds: int,
    ) -> JobRecord | None:
        """原子认领 queued Job，或接管 Deadline 尚未到达的过期 Lease。"""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if not supported_job_types:
            return None

        new_token = uuid4().hex
        row = (
            self._session.execute(
                text(
                    """
                WITH job_clock AS MATERIALIZED (
                    SELECT clock_timestamp() AS now_at
                ),
                candidate AS (
                    SELECT j.id, j.status AS previous_status
                    FROM jobs AS j, job_clock AS c
                    WHERE j.cancel_requested_at IS NULL
                      AND j.job_type = ANY(CAST(:supported_job_types AS text[]))
                      AND (
                          (
                              j.status = 'queued'
                              AND j.available_at <= c.now_at
                              AND j.attempt < j.max_attempts
                          )
                          OR
                          (
                              j.status = 'running'
                              AND j.lease_expires_at <= c.now_at
                              AND j.attempt_deadline_at > c.now_at
                          )
                      )
                    ORDER BY j.priority DESC, j.created_at, j.id
                    FOR UPDATE OF j SKIP LOCKED
                    LIMIT 1
                ),
                transitioned AS (
                    UPDATE jobs AS j
                    SET
                        status = 'running',
                        attempt = CASE
                            WHEN candidate.previous_status = 'queued' THEN j.attempt + 1
                            ELSE j.attempt
                        END,
                        lease_takeover_count = CASE
                            WHEN candidate.previous_status = 'running'
                                THEN j.lease_takeover_count + 1
                            ELSE j.lease_takeover_count
                        END,
                        attempt_started_at = CASE
                            WHEN candidate.previous_status = 'queued' THEN c.now_at
                            ELSE j.attempt_started_at
                        END,
                        attempt_deadline_at = CASE
                            WHEN candidate.previous_status = 'queued'
                                THEN c.now_at + make_interval(secs => j.timeout_seconds)
                            ELSE j.attempt_deadline_at
                        END,
                        lease_owner = :worker_id,
                        lease_token = :lease_token,
                        lease_expires_at = LEAST(
                            c.now_at + make_interval(secs => :lease_seconds),
                            CASE
                                WHEN candidate.previous_status = 'queued'
                                    THEN c.now_at + make_interval(secs => j.timeout_seconds)
                                ELSE j.attempt_deadline_at
                            END
                        ),
                        heartbeat_at = c.now_at,
                        started_at = COALESCE(j.started_at, c.now_at),
                        error_code = CASE
                            WHEN candidate.previous_status = 'queued' THEN NULL
                            ELSE j.error_code
                        END,
                        updated_at = c.now_at
                    FROM candidate, job_clock AS c
                    WHERE j.id = candidate.id
                    RETURNING j.*, candidate.previous_status
                )
                SELECT * FROM transitioned
                """
                ),
                {
                    "supported_job_types": list(supported_job_types),
                    "worker_id": worker_id,
                    "lease_token": new_token,
                    "lease_seconds": lease_seconds,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None

        job = _row_to_job(row)
        previous_status = cast(str, row["previous_status"])
        event_type: JobEventType = "claimed" if previous_status == "queued" else "lease_taken_over"
        self._append_event(
            job=job,
            event_type=event_type,
            worker_id=worker_id,
            lease_token=new_token,
            reason_code=None,
        )
        return job

    def heartbeat(
        self,
        *,
        job_id: UUID,
        lease_token: str,
        lease_seconds: int,
        progress: int,
    ) -> JobRecord:
        """续租但绝不延长 Attempt Deadline。"""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if not 0 <= progress <= 100:
            raise ValueError("progress must be between 0 and 100")

        row = (
            self._session.execute(
                text(
                    """
                WITH job_clock AS MATERIALIZED (
                    SELECT clock_timestamp() AS now_at
                )
                UPDATE jobs AS j
                SET
                    heartbeat_at = c.now_at,
                    lease_expires_at = LEAST(
                        c.now_at + make_interval(secs => :lease_seconds),
                        j.attempt_deadline_at
                    ),
                    progress = :progress,
                    updated_at = c.now_at
                FROM job_clock AS c
                WHERE j.id = :job_id
                  AND j.status = 'running'
                  AND j.lease_token = :lease_token
                  AND j.cancel_requested_at IS NULL
                  AND j.lease_expires_at > c.now_at
                  AND j.attempt_deadline_at > c.now_at
                RETURNING j.*
                """
                ),
                {
                    "job_id": job_id,
                    "lease_token": lease_token,
                    "lease_seconds": lease_seconds,
                    "progress": progress,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LeaseLostError("job lease is no longer current")
        return _row_to_job(row)

    def cancel_requested(self, *, job_id: UUID, lease_token: str) -> bool:
        """只允许当前、未过期 Lease 读取取消状态。"""
        row = (
            self._session.execute(
                text(
                    """
                WITH job_clock AS MATERIALIZED (
                    SELECT clock_timestamp() AS now_at
                )
                SELECT j.cancel_requested_at
                FROM jobs AS j, job_clock AS c
                WHERE j.id = :job_id
                  AND j.status = 'running'
                  AND j.lease_token = :lease_token
                  AND j.lease_expires_at > c.now_at
                  AND j.attempt_deadline_at > c.now_at
                """
                ),
                {"job_id": job_id, "lease_token": lease_token},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LeaseLostError("job lease is no longer current")
        return row["cancel_requested_at"] is not None

    def succeed(
        self,
        *,
        job_id: UUID,
        lease_token: str,
        result: dict[str, object] | None,
    ) -> JobRecord:
        row = self._live_token_transition(
            job_id=job_id,
            lease_token=lease_token,
            values={
                "status": "succeeded",
                "result": result,
                "progress": 100,
                "finished_at": func.clock_timestamp(),
                "lease_owner": None,
                "lease_token": None,
                "lease_expires_at": None,
                "error_code": None,
                "updated_at": func.clock_timestamp(),
            },
        )
        self._append_event(
            job=row,
            event_type="succeeded",
            worker_id=row.lease_owner,
            lease_token=lease_token,
            reason_code=None,
        )
        return row

    def fail_permanent(
        self,
        *,
        job_id: UUID,
        lease_token: str,
        error_code: str,
    ) -> JobRecord:
        row = self._live_token_transition(
            job_id=job_id,
            lease_token=lease_token,
            values={
                "status": "failed",
                "finished_at": func.clock_timestamp(),
                "lease_owner": None,
                "lease_token": None,
                "lease_expires_at": None,
                "error_code": error_code,
                "updated_at": func.clock_timestamp(),
            },
        )
        self._append_event(
            job=row,
            event_type="failed",
            worker_id=row.lease_owner,
            lease_token=lease_token,
            reason_code=error_code,
        )
        return row

    def retry_transient(
        self,
        *,
        job_id: UUID,
        lease_token: str,
        error_code: str,
        retry_delay_seconds: int,
    ) -> JobRecord:
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be nonnegative")
        row = (
            self._session.execute(
                text(
                    """
                WITH job_clock AS MATERIALIZED (
                    SELECT clock_timestamp() AS now_at
                )
                UPDATE jobs AS j
                SET
                    status = CASE
                        WHEN j.attempt < j.max_attempts THEN 'queued'
                        ELSE 'failed'
                    END,
                    available_at = CASE
                        WHEN j.attempt < j.max_attempts
                            THEN c.now_at + make_interval(
                                secs => :retry_delay_seconds
                                    * power(2, GREATEST(j.attempt - 1, 0))
                            )
                        ELSE j.available_at
                    END,
                    attempt_started_at = CASE
                        WHEN j.attempt < j.max_attempts THEN NULL
                        ELSE j.attempt_started_at
                    END,
                    attempt_deadline_at = CASE
                        WHEN j.attempt < j.max_attempts THEN NULL
                        ELSE j.attempt_deadline_at
                    END,
                    heartbeat_at = CASE
                        WHEN j.attempt < j.max_attempts THEN NULL
                        ELSE j.heartbeat_at
                    END,
                    finished_at = CASE
                        WHEN j.attempt < j.max_attempts THEN NULL
                        ELSE c.now_at
                    END,
                    lease_owner = NULL,
                    lease_token = NULL,
                    lease_expires_at = NULL,
                    progress = CASE WHEN j.attempt < j.max_attempts THEN 0 ELSE j.progress END,
                    error_code = :error_code,
                    updated_at = c.now_at
                FROM job_clock AS c
                WHERE j.id = :job_id
                  AND j.status = 'running'
                  AND j.lease_token = :lease_token
                  AND j.cancel_requested_at IS NULL
                  AND j.lease_expires_at > c.now_at
                  AND j.attempt_deadline_at > c.now_at
                RETURNING j.*
                """
                ),
                {
                    "job_id": job_id,
                    "lease_token": lease_token,
                    "error_code": error_code,
                    "retry_delay_seconds": retry_delay_seconds,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LeaseLostError("job lease is no longer current")
        job = _row_to_job(row)
        event_type: JobEventType = "retry_scheduled" if job.status == "queued" else "failed"
        self._append_event(
            job=job,
            event_type=event_type,
            worker_id=None,
            lease_token=lease_token,
            reason_code=error_code,
        )
        return job

    def mark_cancelled(
        self,
        *,
        job_id: UUID,
        lease_token: str,
    ) -> JobRecord:
        now = func.clock_timestamp()
        statement = (
            update(jobs_table)
            .where(
                jobs_table.c.id == job_id,
                jobs_table.c.status == "running",
                jobs_table.c.lease_token == lease_token,
                jobs_table.c.cancel_requested_at.is_not(None),
                jobs_table.c.lease_expires_at > now,
                jobs_table.c.attempt_deadline_at > now,
            )
            .values(
                status="cancelled",
                finished_at=now,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                updated_at=now,
            )
            .returning(*jobs_table.c)
        )
        row = self._session.execute(statement).mappings().one_or_none()
        if row is None:
            raise LeaseLostError("job lease is no longer current or cancellation is absent")
        job = _row_to_job(row)
        self._append_event(
            job=job,
            event_type="cancelled",
            worker_id=None,
            lease_token=lease_token,
            reason_code="cancel_requested",
        )
        return job

    def request_cancel(self, job_id: UUID) -> JobRecord:
        """queued 立即取消；running 仅记录请求，等待协作或 Reaper 收敛。"""
        row = (
            self._session.execute(
                select(jobs_table).where(jobs_table.c.id == job_id).with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise KeyError(f"job not found: {job_id}")
        job = _row_to_job(row)
        if job.status in {"succeeded", "failed", "cancelled"}:
            return job

        now = func.clock_timestamp()
        if job.status == "queued":
            cancelled_row = (
                self._session.execute(
                    update(jobs_table)
                    .where(jobs_table.c.id == job_id, jobs_table.c.status == "queued")
                    .values(
                        status="cancelled",
                        cancel_requested_at=now,
                        finished_at=now,
                        updated_at=now,
                    )
                    .returning(*jobs_table.c)
                )
                .mappings()
                .one()
            )
            cancelled = _row_to_job(cancelled_row)
            self._append_event(
                job=cancelled,
                event_type="cancelled",
                worker_id=None,
                lease_token=None,
                reason_code="cancel_requested",
            )
            return cancelled

        requested_row = (
            self._session.execute(
                update(jobs_table)
                .where(jobs_table.c.id == job_id, jobs_table.c.status == "running")
                .values(
                    cancel_requested_at=func.coalesce(jobs_table.c.cancel_requested_at, now),
                    updated_at=now,
                )
                .returning(*jobs_table.c)
            )
            .mappings()
            .one()
        )
        return _row_to_job(requested_row)

    def reap_next(
        self,
        *,
        timeout_retry_job_types: tuple[str, ...],
        retry_delay_seconds: int,
    ) -> JobRecord | None:
        """收敛 Deadline 到期和取消状态；过期 Lease 的普通接管留给 Claim。"""
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be nonnegative")

        row = (
            self._session.execute(
                text(
                    """
                WITH job_clock AS MATERIALIZED (
                    SELECT clock_timestamp() AS now_at
                )
                SELECT j.*, c.now_at AS reaper_now
                FROM jobs AS j, job_clock AS c
                WHERE
                    (j.status = 'queued' AND j.cancel_requested_at IS NOT NULL)
                    OR
                    (
                        j.status = 'running'
                        AND (
                            j.attempt_deadline_at <= c.now_at
                            OR (
                                j.cancel_requested_at IS NOT NULL
                                AND j.lease_expires_at <= c.now_at
                            )
                        )
                    )
                ORDER BY j.created_at, j.id
                FOR UPDATE OF j SKIP LOCKED
                LIMIT 1
                """
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None

        job = _row_to_job(row)
        reaper_now = cast(datetime, row["reaper_now"])
        if job.status == "queued":
            return self._reap_cancelled(job=job, now_at=reaper_now)

        if job.cancel_requested_at is not None:
            return self._reap_cancelled(job=job, now_at=reaper_now)

        if job.attempt_deadline_at is None or job.attempt_deadline_at > reaper_now:
            return None
        if job.lease_token is None:
            raise RuntimeError("running job is missing lease token")

        if job.job_type in timeout_retry_job_types and job.attempt < job.max_attempts:
            backoff_seconds = retry_delay_seconds * (2 ** max(job.attempt - 1, 0))
            next_available = reaper_now + timedelta(seconds=backoff_seconds)
            transitioned = (
                self._session.execute(
                    update(jobs_table)
                    .where(
                        jobs_table.c.id == job.id,
                        jobs_table.c.status == "running",
                        jobs_table.c.attempt == job.attempt,
                        jobs_table.c.lease_token == job.lease_token,
                    )
                    .values(
                        status="queued",
                        available_at=next_available,
                        progress=0,
                        attempt_started_at=None,
                        attempt_deadline_at=None,
                        heartbeat_at=None,
                        lease_owner=None,
                        lease_token=None,
                        lease_expires_at=None,
                        error_code="attempt_timeout",
                        updated_at=reaper_now,
                    )
                    .returning(*jobs_table.c)
                )
                .mappings()
                .one()
            )
            retried = _row_to_job(transitioned)
            self._append_event(
                job=retried,
                event_type="retry_scheduled",
                worker_id=job.lease_owner,
                lease_token=job.lease_token,
                reason_code="attempt_timeout",
            )
            return retried

        transitioned = (
            self._session.execute(
                update(jobs_table)
                .where(
                    jobs_table.c.id == job.id,
                    jobs_table.c.status == "running",
                    jobs_table.c.attempt == job.attempt,
                    jobs_table.c.lease_token == job.lease_token,
                )
                .values(
                    status="failed",
                    finished_at=reaper_now,
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                    error_code="attempt_timeout",
                    updated_at=reaper_now,
                )
                .returning(*jobs_table.c)
            )
            .mappings()
            .one()
        )
        failed = _row_to_job(transitioned)
        self._append_event(
            job=failed,
            event_type="timed_out",
            worker_id=job.lease_owner,
            lease_token=job.lease_token,
            reason_code="attempt_timeout",
        )
        return failed

    def _reap_cancelled(self, *, job: JobRecord, now_at: datetime) -> JobRecord:
        conditions = [
            jobs_table.c.id == job.id,
            jobs_table.c.status == job.status,
            jobs_table.c.attempt == job.attempt,
        ]
        if job.status == "running":
            if job.lease_token is None:
                raise RuntimeError("running job is missing lease token")
            conditions.append(jobs_table.c.lease_token == job.lease_token)
        transitioned = (
            self._session.execute(
                update(jobs_table)
                .where(*conditions)
                .values(
                    status="cancelled",
                    finished_at=now_at,
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                    updated_at=now_at,
                )
                .returning(*jobs_table.c)
            )
            .mappings()
            .one()
        )
        cancelled = _row_to_job(transitioned)
        self._append_event(
            job=cancelled,
            event_type="cancelled",
            worker_id=job.lease_owner,
            lease_token=job.lease_token,
            reason_code="cancel_requested",
        )
        return cancelled

    def _live_token_transition(
        self,
        *,
        job_id: UUID,
        lease_token: str,
        values: dict[str, object],
    ) -> JobRecord:
        now = func.clock_timestamp()
        row = (
            self._session.execute(
                update(jobs_table)
                .where(
                    jobs_table.c.id == job_id,
                    jobs_table.c.status == "running",
                    jobs_table.c.lease_token == lease_token,
                    jobs_table.c.cancel_requested_at.is_(None),
                    jobs_table.c.lease_expires_at > now,
                    jobs_table.c.attempt_deadline_at > now,
                )
                .values(**values)
                .returning(*jobs_table.c)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LeaseLostError("job lease is no longer current")
        return _row_to_job(row)

    def _append_event(
        self,
        *,
        job: JobRecord,
        event_type: JobEventType,
        worker_id: str | None,
        lease_token: str | None,
        reason_code: str | None,
    ) -> None:
        fingerprint = sha256(lease_token.encode()).hexdigest() if lease_token is not None else None
        if worker_id is None and fingerprint is not None:
            worker_id = self._session.scalar(
                select(job_attempt_events_table.c.worker_id)
                .where(
                    job_attempt_events_table.c.job_id == job.id,
                    job_attempt_events_table.c.lease_token_fingerprint == fingerprint,
                    job_attempt_events_table.c.worker_id.is_not(None),
                )
                .order_by(job_attempt_events_table.c.event_seq.desc())
                .limit(1)
            )
        next_seq_value = self._session.scalar(
            select(func.coalesce(func.max(job_attempt_events_table.c.event_seq), 0) + 1).where(
                job_attempt_events_table.c.job_id == job.id
            )
        )
        next_seq = cast(int, next_seq_value)
        self._session.execute(
            insert(job_attempt_events_table).values(
                id=uuid4(),
                job_id=job.id,
                event_seq=next_seq,
                attempt=job.attempt,
                lease_takeover_count=job.lease_takeover_count,
                event_type=event_type,
                worker_id=worker_id,
                lease_token_fingerprint=fingerprint,
                reason_code=reason_code,
                safe_detail=None,
                happened_at=func.clock_timestamp(),
            )
        )


def _row_to_job(row: RowMapping) -> JobRecord:
    return JobRecord(
        id=cast(UUID, row["id"]),
        job_type=cast(str, row["job_type"]),
        payload_version=cast(str, row["payload_version"]),
        payload=cast(dict[str, object], row["payload"]),
        result=row["result"],
        status=cast(JobStatus, row["status"]),
        internal_idempotency_key=cast(str, row["internal_idempotency_key"]),
        request_id=cast(str | None, row["request_id"]),
        priority=cast(int, row["priority"]),
        attempt=cast(int, row["attempt"]),
        lease_takeover_count=cast(int, row["lease_takeover_count"]),
        max_attempts=cast(int, row["max_attempts"]),
        timeout_seconds=cast(int, row["timeout_seconds"]),
        attempt_started_at=cast(datetime | None, row["attempt_started_at"]),
        attempt_deadline_at=cast(datetime | None, row["attempt_deadline_at"]),
        progress=cast(int, row["progress"]),
        available_at=cast(datetime, row["available_at"]),
        lease_owner=cast(str | None, row["lease_owner"]),
        lease_token=cast(str | None, row["lease_token"]),
        lease_expires_at=cast(datetime | None, row["lease_expires_at"]),
        heartbeat_at=cast(datetime | None, row["heartbeat_at"]),
        cancel_requested_at=cast(datetime | None, row["cancel_requested_at"]),
        started_at=cast(datetime | None, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
        error_code=cast(str | None, row["error_code"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _row_to_event(row: RowMapping) -> JobAttemptEvent:
    return JobAttemptEvent(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        event_seq=cast(int, row["event_seq"]),
        attempt=cast(int, row["attempt"]),
        lease_takeover_count=cast(int, row["lease_takeover_count"]),
        event_type=cast(JobEventType, row["event_type"]),
        worker_id=cast(str | None, row["worker_id"]),
        lease_token_fingerprint=cast(str | None, row["lease_token_fingerprint"]),
        reason_code=cast(str | None, row["reason_code"]),
        safe_detail=cast(str | None, row["safe_detail"]),
        happened_at=cast(datetime, row["happened_at"]),
    )
