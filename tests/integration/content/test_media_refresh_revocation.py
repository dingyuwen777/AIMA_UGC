"""真实 URL 发布后的旧来源撤销只能清除该来源仍独占的属性。"""

from copy import deepcopy
from datetime import timedelta

import pytest
from aima_ugc.adapters.persistence.postgres import content_contributions
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.content_lifecycle import (
    PostgresContentLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.content_playback import (
    PostgresContentPlaybackRepository,
)
from aima_ugc.adapters.providers.fake import FakeProviderTransport
from aima_ugc.contracts.content_playback import ContentMediaPlaybackPrepareRequest
from aima_ugc.modules.collection.providers import ProviderTransportResponse
from aima_ugc.modules.collection.tables import collection_runs_table
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.content.extended_tables import content_media_table
from aima_ugc.modules.content.media_playback_tables import (
    content_media_playback_states_table as states,
)
from aima_ugc.platform.jobs import JobWorker
from aima_ugc.platform.jobs.tables import jobs_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import select, update

from tests.integration.collection.test_collection_scope_runtime import _fixture
from tests.integration.content.test_content_audit_regressions import _source
from tests.integration.content.test_content_playback import (
    VIEWER,
    _executor,
    _prepare,
    _registry,
    _seed,
)
from tests.integration.content.test_content_playback import database_runtime as database_runtime


def _refresh(runtime, seed, tmp_path):
    """由正式 Worker 完成第一次刷新，使后续准备面对真实终态 Job/Run。"""
    prepared = _prepare(seed)
    with runtime.new_session() as session, session.begin():
        session.execute(
            update(jobs_table).where(jobs_table.c.id == prepared.job_id).values(priority=50)
        )
    transport = FakeProviderTransport(
        (
            ProviderTransportResponse(
                status_code=200, body=_fixture("video_detail_20261009.sanitized.json")
            ),
        )
    )
    worker = JobWorker(
        session_factory=runtime.new_session,
        registry=_registry(runtime, _executor(runtime, tmp_path, transport)),
        worker_id="media-revocation",
        lease_seconds=120,
        retry_delay_seconds=0,
        minimum_priority=50,
    )
    assert worker.run_once() and transport.call_count == 1
    with runtime.new_session() as session, session.begin():
        assert (
            session.scalar(select(jobs_table.c.status).where(jobs_table.c.id == prepared.job_id))
            == "succeeded"
        )
    return prepared


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("batch", [False, True])
def test_url_refresh_keeps_new_stream_while_revoking_old_cover_and_duration(
    database_runtime, tmp_path, monkeypatch, legacy, batch
):
    build = content_contributions._build_delta

    def legacy_delta(*args, **kwargs):
        """创建时的完整旧行只去除当时不存在的媒体元数据，不修改落盘 Delta。"""
        delta = build(*args, **kwargs)
        delta["schema_version"] = "content-source-contribution.v1"
        for side in ("before", "after"):
            for media in delta["collections"]["media"][side]:
                media.pop("observation_metadata", None)
        return delta

    with monkeypatch.context() as patch:
        if legacy:
            patch.setattr(content_contributions, "_build_delta", legacy_delta)
        seed = _seed(database_runtime, legacy=legacy)
    with database_runtime.new_session() as session, session.begin():
        contributions = tuple(
            session.execute(select(content_source_contributions_table)).mappings()
        )
        assert len(contributions) == 1
        immutable = deepcopy(contributions[0]["delta"])
    prepared = _refresh(database_runtime, seed, tmp_path)
    with database_runtime.new_session() as session, session.begin():
        refreshed = session.execute(select(content_media_table)).mappings().one()
        new_url = refreshed["url"]
        state_before = dict(session.execute(select(states)).mappings().one())
        lifecycle = PostgresContentLifecycleRepository(session)
        if batch:
            lifecycle.apply_contributions_batch(contributions, revoked_at=beijing_now())
        else:
            lifecycle.apply_contributions(contributions, revoked_at=beijing_now())
        media = session.execute(select(content_media_table)).mappings().one()
        assert media["url"] == new_url and media["media_type"] == "video"
        assert media["preview_url"] is None and media["duration_ms"] is None
        assert session.execute(select(states)).mappings().one_or_none() == state_before
        assert session.scalar(select(content_source_contributions_table.c.delta)) == immutable
        owner = PostgresContentPlaybackRepository(session)
        source = owner.get_source(seed.content_id, 0, lock=True)
        owner.record_stream_failure(source, code="cdn_forbidden", now=beijing_now())
    body = ContentMediaPlaybackPrepareRequest(failed_source_revision=source.source_revision)
    assert (
        seed.service.prepare(
            seed.content_id, 0, body, principal=VIEWER, request_id="cooldown"
        ).status
        == "cooldown"
    )
    monkeypatch.setattr(
        "aima_ugc.bootstrap.content_playback_service.beijing_now",
        lambda: beijing_now() + timedelta(minutes=6),
    )
    next_prepare = seed.service.prepare(
        seed.content_id, 0, body, principal=VIEWER, request_id="next"
    )
    assert next_prepare.status == "preparing" and next_prepare.generation == prepared.generation + 1
    assert next_prepare.job_id != prepared.job_id
    assert (
        seed.service.prepare(seed.content_id, 0, body, principal=VIEWER, request_id="same").job_id
        == next_prepare.job_id
    )
    with database_runtime.new_session() as session, session.begin():
        assert (
            len(
                tuple(
                    session.execute(
                        select(collection_runs_table).where(
                            collection_runs_table.c.config_snapshot["mode"].astext
                            == "media_refresh"
                        )
                    )
                )
            )
            == 2
        )


@pytest.mark.parametrize("batch", [False, True])
def test_deleted_media_restored_with_same_identity_starts_new_job_lifecycle(
    database_runtime, tmp_path, batch
):
    """真正删除可清理状态；撤销删除恢复相同身份时不能碰撞旧终态任务。"""
    seed = _seed(database_runtime)
    prepared = _refresh(database_runtime, seed, tmp_path)
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresContentPlaybackRepository(session)
        original = owner.get_source(seed.content_id, 0)
    later = _source(database_runtime, observed_at=beijing_now(), suffix="media-delete")
    with database_runtime.new_session() as session, session.begin():
        PostgresCompleteContentRepository(session).ingest_content(
            seed.observation.model_copy(
                update={
                    "source": later,
                    "observed_at": later.observed_at,
                    "observed_fields": ["media"],
                    "media_collection_mode": "complete",
                    "media": [],
                }
            )
        )
        assert session.scalar(select(states.c.generation)) is None
        contributions = tuple(
            session.execute(
                select(content_source_contributions_table).where(
                    content_source_contributions_table.c.provider_attempt_id
                    == later.provider_attempt_id
                )
            ).mappings()
        )
        assert len(contributions) == 1
        lifecycle = PostgresContentLifecycleRepository(session)
        if batch:
            lifecycle.apply_contributions_batch(contributions, revoked_at=beijing_now())
        else:
            lifecycle.apply_contributions(contributions, revoked_at=beijing_now())
        owner = PostgresContentPlaybackRepository(session)
        restored = owner.get_source(seed.content_id, 0, lock=True)
        assert restored.identity_token == original.identity_token
        assert restored.generation == 0
        owner.record_stream_failure(restored, code="cdn_forbidden", now=beijing_now())
    body = ContentMediaPlaybackPrepareRequest(failed_source_revision=restored.source_revision)
    next_prepare = seed.service.prepare(
        seed.content_id, 0, body, principal=VIEWER, request_id="restored"
    )
    assert next_prepare.status == "preparing" and next_prepare.job_id != prepared.job_id
    assert (
        seed.service.prepare(
            seed.content_id, 0, body, principal=VIEWER, request_id="restored-again"
        ).job_id
        == next_prepare.job_id
    )
    with database_runtime.new_session() as session, session.begin():
        assert (
            len(
                tuple(
                    session.execute(
                        select(collection_runs_table).where(
                            collection_runs_table.c.config_snapshot["mode"].astext
                            == "media_refresh"
                        )
                    )
                )
            )
            == 2
        )
