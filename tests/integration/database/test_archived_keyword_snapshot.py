"""归档词包不能重新进入 Import/Scheduler 的冻结关键词输入。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import delete

from aima_ugc.adapters.persistence.postgres.keyword_lifecycle import (
    PostgresKeywordPackLifecycleRepository,
)
from aima_ugc.adapters.persistence.postgres.keywords import PostgresKeywordCatalogRepository
from aima_ugc.adapters.persistence.postgres.scheduled_keywords import (
    MissingScheduledKeywordPackError,
    PostgresScheduledKeywordSnapshotReader,
)
from aima_ugc.modules.system.models import KeywordPack
from aima_ugc.modules.system.tables import keyword_packs_table
from aima_ugc.platform.config import load_settings
from aima_ugc.platform.database import DatabaseRuntime
from aima_ugc.platform.time import beijing_now


def test_archived_keyword_pack_is_missing_from_runtime_snapshot() -> None:
    runtime = DatabaseRuntime(load_settings())
    session = runtime.new_session()
    pack_id = uuid4()
    try:
        with session.begin():
            PostgresKeywordCatalogRepository(session).create_pack(
                KeywordPack(
                    id=pack_id,
                    name=f"归档快照词包-{pack_id}",
                    description="",
                    enabled=False,
                    version=1,
                )
            )
            assert PostgresKeywordPackLifecycleRepository(session).archive(
                pack_id,
                archived_at=beijing_now(),
            ) is not None
            with pytest.raises(MissingScheduledKeywordPackError):
                PostgresScheduledKeywordSnapshotReader(session).read((pack_id,))
    finally:
        with session.begin():
            session.execute(delete(keyword_packs_table).where(keyword_packs_table.c.id == pack_id))
        session.close()
        runtime.dispose()
