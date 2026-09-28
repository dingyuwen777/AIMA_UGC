from __future__ import annotations

import time
from collections.abc import Iterator
from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.feishu_bitable_mirrors import (
    PostgresFeishuBitableMirrorRepository,
)
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.jobs.models import LeaseLostError
from sqlalchemy import text


@pytest.fixture
def database_runtime() -> Iterator[DatabaseRuntime]:
    runtime = DatabaseRuntime(load_settings())
    try:
        yield runtime
    finally:
        runtime.dispose()


def test_mirror_claim_is_atomic_and_stale_worker_cannot_write_back(
    database_runtime: DatabaseRuntime,
) -> None:
    document_token = f"claim-test-{uuid4()}"
    session_a = database_runtime.new_session()
    session_b = database_runtime.new_session()
    mirror_id = None
    try:
        repository_a = PostgresFeishuBitableMirrorRepository(session_a)
        with session_a.begin():
            mirror = repository_a.register(
                publication_job_id=None,
                document_token=document_token,
                document_url="https://feishu.cn/doc/claim-test",
                external_app_token=f"app-{uuid4()}",
                external_table_id="tbl-external",
                embedded_app_token=f"app-{uuid4()}",
                embedded_table_id="tbl-embedded",
            )
            mirror_id = mirror.id

        transaction_a = session_a.begin()
        first = repository_a.claim_due(worker_id="mirror-a", lease_seconds=30)
        assert len(first) == 1
        assert first[0].claim_token is not None
        assert first[0].claim_expires_at is not None
        repository_a.renew_claim(
            first[0].id,
            claim_token=first[0].claim_token,
            lease_seconds=30,
        )

        with session_b.begin():
            assert (
                PostgresFeishuBitableMirrorRepository(session_b).claim_due(
                    worker_id="mirror-b", lease_seconds=30
                )
                == ()
            )
        transaction_a.commit()

        first_token = first[0].claim_token
        assert first_token is not None
        with session_b.begin():
            session_b.execute(
                text(
                    "UPDATE feishu_bitable_mirrors "
                    "SET claim_expires_at = clock_timestamp() - interval '1 second' "
                    "WHERE id = :mirror_id"
                ),
                {"mirror_id": mirror_id},
            )
        with session_b.begin():
            takeover = PostgresFeishuBitableMirrorRepository(session_b).claim_due(
                worker_id="mirror-b", lease_seconds=30
            )
        assert len(takeover) == 1
        assert takeover[0].claim_token != first_token

        with session_a.begin():
            with pytest.raises(LeaseLostError):
                repository_a.renew_claim(
                    mirror_id,
                    claim_token=first_token,
                    lease_seconds=30,
                )
            with pytest.raises(LeaseLostError):
                repository_a.mark_succeeded(
                    mirror_id,
                    known_key_hashes=(),
                    synced_at=takeover[0].next_sync_at,
                    next_sync_at=takeover[0].next_sync_at,
                    claim_token=first_token,
                )
    finally:
        if mirror_id is not None:
            with session_b.begin():
                session_b.execute(
                    text("DELETE FROM feishu_bitable_mirrors WHERE id = :mirror_id"),
                    {"mirror_id": mirror_id},
                )
        session_a.close()
        session_b.close()


def test_renewed_claim_blocks_takeover_after_original_lease_window(
    database_runtime: DatabaseRuntime,
) -> None:
    """可控慢同步跨过原始 Lease 后，续租仍只允许一个 Worker。"""

    document_token = f"slow-claim-test-{uuid4()}"
    session_a = database_runtime.new_session()
    session_b = database_runtime.new_session()
    mirror_id = None
    try:
        repository_a = PostgresFeishuBitableMirrorRepository(session_a)
        with session_a.begin():
            mirror = repository_a.register(
                publication_job_id=None,
                document_token=document_token,
                document_url="https://feishu.cn/doc/slow-claim-test",
                external_app_token=f"app-{uuid4()}",
                external_table_id="tbl-external",
                embedded_app_token=f"app-{uuid4()}",
                embedded_table_id="tbl-embedded",
            )
            mirror_id = mirror.id

        with session_a.begin():
            claimed = repository_a.claim_due(worker_id="slow-worker", lease_seconds=1)
        assert len(claimed) == 1
        token = claimed[0].claim_token
        assert token is not None

        time.sleep(0.7)
        with session_a.begin():
            repository_a.renew_claim(
                claimed[0].id,
                claim_token=token,
                lease_seconds=1,
            )
        time.sleep(0.7)

        with session_b.begin():
            assert (
                PostgresFeishuBitableMirrorRepository(session_b).claim_due(
                    worker_id="takeover-worker",
                    lease_seconds=1,
                )
                == ()
            )
    finally:
        if mirror_id is not None:
            with session_b.begin():
                session_b.execute(
                    text("DELETE FROM feishu_bitable_mirrors WHERE id = :mirror_id"),
                    {"mirror_id": mirror_id},
                )
        session_a.close()
        session_b.close()
