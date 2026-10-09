"""补采和集合导入的冻结作者输入与字段新鲜度回归。"""

from datetime import timedelta

import pytest
from aima_ugc.adapters.persistence.postgres.content_complete import (
    PostgresCompleteContentRepository,
)
from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1
from aima_ugc.modules.content.tables import content_versions_table, contents_table
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.time import beijing_now
from sqlalchemy import select

from tests.integration.content.test_content_current_concurrency import _source
from tests.integration.content.test_content_current_concurrency import (
    database_runtime as database_runtime,
)


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("stable_author", [False, True])
def test_sparse_author_preserves_frozen_input_and_author_only_change_versions(
    database_runtime: DatabaseRuntime, batch: bool, stable_author: bool
) -> None:
    """相同生产 Owner 的单条和集合路径都不得让作者输入在同版下漂移。"""
    now = beijing_now()
    author = CanonicalAuthorV1(
        external_account_id="snapshot-author" if stable_author else None,
        display_name="原作者",
        bio="原简介",
        verification_label="认证作者",
    )
    original = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="snapshot-content",
        content_type="note",
        title="爱玛帖子",
        author=author,
        observed_at=now,
        observed_fields=[
            "content_type",
            "title",
            "author.display_name",
            "author.bio",
            "author.verification_label",
        ]
        + (["author.external_account_id"] if stable_author else []),
        source=_source(database_runtime, observed_at=now, suffix="snapshot-initial"),
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        result = (
            owner.ingest_contents_batch((original,))[0] if batch else owner.ingest_content(original)
        )
    later = now + timedelta(seconds=2)
    sparse = original.model_copy(
        update={
            "title": None,
            "share_url": "https://example.com/supplement",
            "author": None,
            "observed_at": later,
            "observed_fields": ["share_url"],
            "source": _source(database_runtime, observed_at=later, suffix="snapshot-sparse"),
        }
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        if batch:
            owner.ingest_contents_batch((sparse,))
        else:
            owner.ingest_content(sparse)
        version = (
            session.execute(
                select(content_versions_table).where(
                    content_versions_table.c.content_id == result.target_id,
                    content_versions_table.c.version_no == 2,
                )
            )
            .mappings()
            .one()
        )
        assert version["title"] == "爱玛帖子"
        assert version["author_snapshot"]["display_name"] == "原作者"
        assert version["author_snapshot"]["bio"] == "原简介"
        assert version["author_snapshot"]["verification_label"] == "认证作者"
    changed = original.model_copy(
        update={
            "author": CanonicalAuthorV1(
                external_account_id=author.external_account_id, bio="新简介"
            ),
            "observed_at": later + timedelta(seconds=1),
            "observed_fields": ["author.bio"],
            "source": _source(
                database_runtime, observed_at=later + timedelta(seconds=1), suffix="snapshot-bio"
            ),
        }
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        if batch:
            owner.ingest_contents_batch((changed,))
        else:
            owner.ingest_content(changed)
        current = session.execute(select(contents_table)).mappings().one()
        assert current["current_version"] == 3
        rows = (
            session.execute(
                select(content_versions_table).order_by(content_versions_table.c.version_no)
            )
            .mappings()
            .all()
        )
        assert rows[0]["author_snapshot"]["bio"] == "原简介"
        assert rows[1]["author_snapshot"]["bio"] == "原简介"
        assert rows[2]["author_snapshot"]["display_name"] == "原作者"
        assert rows[2]["author_snapshot"]["bio"] == "新简介"
    older = changed.model_copy(
        update={
            "author": author,
            "observed_at": now,
            "observed_fields": ["author.bio"],
            "source": _source(database_runtime, observed_at=now, suffix="snapshot-older"),
        }
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        if batch:
            owner.ingest_contents_batch((older,))
        else:
            owner.ingest_content(older)
        assert session.scalar(select(contents_table.c.current_version)) == 3
        assert (
            session.scalar(
                select(content_versions_table.c.author_snapshot).where(
                    content_versions_table.c.version_no == 3
                )
            )["bio"]
            == "新简介"
        )


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("clear_bio", [False, True])
def test_detaching_stable_account_preserves_unobserved_author_input(
    database_runtime: DatabaseRuntime, batch: bool, clear_bio: bool
) -> None:
    """解绑账号不是证明作者文本消失；仅明确观察到的文本空值才清除冻结输入。"""
    now = beijing_now()
    original = CanonicalContentV1(
        platform="xiaohongshu",
        external_content_id="detach-author-content",
        content_type="note",
        title="爱玛 作者解绑",
        author=CanonicalAuthorV1(
            external_account_id="stable-detached",
            display_name="原作者",
            bio="原简介",
            verification_label="原认证",
        ),
        observed_at=now,
        observed_fields=[
            "content_type",
            "title",
            "author.external_account_id",
            "author.display_name",
            "author.bio",
            "author.verification_label",
        ],
        source=_source(database_runtime, observed_at=now, suffix="detach-initial"),
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        initial = (
            owner.ingest_contents_batch((original,))[0] if batch else owner.ingest_content(original)
        )
        old = session.scalar(
            select(content_versions_table.c.author_snapshot).where(
                content_versions_table.c.content_id == initial.target_id
            )
        )
    later = now + timedelta(seconds=1)
    detached = original.model_copy(
        update={
            "author": None,
            "observed_at": later,
            "observed_fields": ["author.external_account_id"]
            + (["author.bio"] if clear_bio else []),
            "source": _source(database_runtime, observed_at=later, suffix="detach-second"),
        }
    )
    with database_runtime.new_session() as session, session.begin():
        owner = PostgresCompleteContentRepository(session)
        result = (
            owner.ingest_contents_batch((detached,))[0] if batch else owner.ingest_content(detached)
        )
        assert result.version_no == 2
        current = session.execute(select(contents_table)).mappings().one()
        assert current["author_account_id"] is None
        snapshot = session.scalar(
            select(content_versions_table.c.author_snapshot).where(
                content_versions_table.c.content_id == initial.target_id,
                content_versions_table.c.version_no == 2,
            )
        )
        assert snapshot["display_name"] == "原作者"
        assert snapshot["verification_label"] == "原认证"
        assert snapshot["bio"] == (None if clear_bio else "原简介")
        assert (
            session.scalar(
                select(content_versions_table.c.author_snapshot).where(
                    content_versions_table.c.content_id == initial.target_id,
                    content_versions_table.c.version_no == 1,
                )
            )
            == old
        )
        from aima_ugc.adapters.persistence.postgres.analysis import (
            canonical_analysis_content_from_row,
        )
        from aima_ugc.adapters.persistence.postgres.analysis_reuse import (
            PostgresAnalysisReuseRepository,
        )
        from aima_ugc.modules.analysis.content_labeling import content_labeling_input_hash

        inputs = PostgresAnalysisReuseRepository(session)._version_inputs((initial.target_id,))
        previous_hash = content_labeling_input_hash(
            canonical_analysis_content_from_row(inputs[(initial.target_id, 1)])
        )
        current_hash = content_labeling_input_hash(
            canonical_analysis_content_from_row(inputs[(initial.target_id, 2)])
        )
        assert (current_hash == previous_hash) is (not clear_bio)
