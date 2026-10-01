"""新版重筛 Owner 在写入前稳定 Current/Account 的真实贡献基线。"""

from datetime import timedelta

import pytest
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.adapters.persistence.postgres.content_contributions import (
    build_content_contribution_delta,
    capture_content_contribution_snapshots_batch,
)
from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1
from aima_ugc.modules.content.tables import accounts_table, contents_table
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.time import beijing_now
from sqlalchemy import func, select

from tests.integration.content.test_content_audit_regressions import (
    _source,
)
from tests.integration.content.test_content_audit_regressions import (
    database_runtime as database_runtime,
)


def _observation(database: DatabaseRuntime, title: str, *, suffix: str) -> CanonicalContentV1:
    now = beijing_now()
    return CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="replay-owner-baseline",
        content_type="note",
        title=title,
        observed_at=now,
        source=_source(database, observed_at=now, suffix=suffix),
        observed_fields=["content_type", "title"],
    )


@pytest.mark.parametrize("protected", [False, True])
def test_replay_account_preparation_keeps_new_author_delta_and_protected_row_unchanged(
    database_runtime: DatabaseRuntime,
    protected: bool,
) -> None:
    initial = _observation(database_runtime, "初始正文", suffix="owner-initial")
    update = _observation(database_runtime, "候选新正文", suffix="owner-update").model_copy(
        update={
            "author": CanonicalAuthorV1(
                external_account_id="new-replay-author", display_name="候选作者"
            ),
            "observed_fields": [
                "content_type",
                "title",
                "author.external_account_id",
                "author.display_name",
            ],
        }
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        owner.ingest_content(initial)
        before = capture_content_contribution_snapshots_batch(session, ((update, None),))[0]
        cutoff = beijing_now() + timedelta(seconds=-1 if protected else 1)
        item = owner.ingest_contents_with_before_snapshots_batch(
            ((update, before),), replay_accepted_before=cutoff
        )[0]
        assert item.protected_by_later_write is protected
        if protected:
            assert session.scalar(select(func.count()).select_from(accounts_table)) == 0
            current = session.execute(select(contents_table)).mappings().one()
            assert current["title"] == "初始正文"
            assert current["current_version"] == 1
            assert current["author_account_id"] is None
        else:
            delta = build_content_contribution_delta(update, item.before, item.contribution_after)
            assert item.before.account_fields["author.display_name"] is None
            assert delta["account"]["fields"]["author.display_name"]["before"] is None
            assert delta["account"]["fields"]["author.display_name"]["after"] == "候选作者"
            assert session.scalar(select(accounts_table.c.display_name)) == "候选作者"


def test_replay_replaces_stale_before_snapshot_with_locked_current_baseline(
    database_runtime: DatabaseRuntime,
) -> None:
    initial = _observation(database_runtime, "初始正文", suffix="baseline-initial")
    normal = _observation(database_runtime, "外部新正文", suffix="baseline-normal")
    replay = _observation(database_runtime, "本次正文", suffix="baseline-replay")
    with database_runtime.new_session() as session, session.begin():
        PostgresCompleteContentRepository(session).ingest_content(initial)
        stale = capture_content_contribution_snapshots_batch(session, ((replay, None),))[0]
    with database_runtime.new_session() as session, session.begin():
        PostgresCompleteContentRepository(session).ingest_content(normal)
    with database_runtime.new_session() as session, session.begin():
        item = PostgresCompleteContentRepository(
            session
        ).ingest_contents_with_before_snapshots_batch(
            ((replay, stale),),
            replay_accepted_before=beijing_now() + timedelta(seconds=1),
        )[0]
        assert item.before.version_no == 2
        assert item.before.content_fields["title"] == "外部新正文"
        delta = build_content_contribution_delta(replay, item.before, item.contribution_after)
        assert delta["content_fields"]["title"]["before"] == "外部新正文"
        assert delta["content_fields"]["title"]["after"] == "本次正文"
