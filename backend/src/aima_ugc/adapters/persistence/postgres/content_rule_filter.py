"""Content Owner 对全历史重筛规则结果的集合发布。"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Uuid, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from .voice_plaza_projection import defer_voice_plaza_projection

_RULE_VISIBILITY_REFRESH_BATCH_SIZE = 1000


class PostgresContentRuleFilterRepository:
    """只改 Content 规则可见性，并在同一事务结清派生投影。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def publish(
        self,
        *,
        request_id: UUID | None,
        accepted_before: datetime | None,
    ) -> tuple[int, int]:
        """只更新可见性发生变化的行；`None` 表示解除规则快照门禁。"""

        if (request_id is None) != (accepted_before is None):
            raise ValueError("规则快照请求与受理时间必须同时存在或同时为空")
        self._session.execute(text("DROP TABLE IF EXISTS pg_temp.replay_rule_visibility_changed"))
        if request_id is None:
            self._session.execute(
                text(
                    """
                    CREATE TEMP TABLE replay_rule_visibility_changed
                    ON COMMIT DROP AS
                    SELECT content.id AS content_id, true AS target_visible
                    FROM contents AS content
                    LEFT JOIN (
                        SELECT DISTINCT change.content_id
                        FROM canonical_replay_content_changes AS change
                        JOIN canonical_replay_all_requests AS replay
                          ON replay.id = change.all_request_id
                        WHERE change.version_before IS NULL
                          AND change.reverted_at IS NULL
                          AND replay.reconciliation_status = 'pending'
                          AND replay.lifecycle_status IN (
                              'active', 'cancelling', 'reverting'
                          )
                    ) AS pending_new ON pending_new.content_id = content.id
                    WHERE content.rule_filter_visible IS DISTINCT FROM true
                      AND pending_new.content_id IS NULL
                    """
                )
            )
        else:
            self._session.execute(
                text(
                    """
                    CREATE TEMP TABLE replay_rule_visibility_changed
                    ON COMMIT DROP AS
                    SELECT content.id AS content_id,
                           (
                               matched.content_id IS NOT NULL
                               OR COALESCE(
                                   content.latest_normal_filter_match_at > :accepted_before,
                                   false
                               )
                           ) AS target_visible
                    FROM contents AS content
                    LEFT JOIN (
                        SELECT DISTINCT change.content_id
                        FROM canonical_replay_content_changes AS change
                        WHERE change.all_request_id = :request_id
                          AND change.reverted_at IS NULL
                          AND COALESCE(change.delta ->> 'resolver_outcome', 'matched')
                              <> 'unmatched'
                    ) AS matched ON matched.content_id = content.id
                    WHERE content.rule_filter_visible IS DISTINCT FROM (
                        matched.content_id IS NOT NULL
                        OR COALESCE(
                            content.latest_normal_filter_match_at > :accepted_before,
                            false
                        )
                    )
                    """
                ),
                {"request_id": request_id, "accepted_before": accepted_before},
            )
        self._session.execute(
            text(
                "CREATE UNIQUE INDEX replay_rule_visibility_changed_id "
                "ON replay_rule_visibility_changed(content_id)"
            )
        )
        defer_voice_plaza_projection(self._session)
        self._session.execute(
            text(
                """
                UPDATE contents AS content
                SET rule_filter_visible = changed.target_visible
                FROM replay_rule_visibility_changed AS changed
                WHERE content.id = changed.content_id
                """
            )
        )
        counts = self._session.execute(
            text(
                """
                SELECT count(*) FILTER (WHERE NOT target_visible) AS hidden,
                       count(*) FILTER (WHERE target_visible) AS restored
                FROM replay_rule_visibility_changed
                """
            )
        ).one()
        refresh = text(
            "SELECT refresh_voice_plaza_content_projection_batch(:content_ids)"
        ).bindparams(bindparam("content_ids", type_=ARRAY(Uuid())))
        after_content_id: UUID | None = None
        while True:
            statement = text(
                """
                SELECT content_id
                FROM replay_rule_visibility_changed
                WHERE (:after_content_id IS NULL OR content_id > :after_content_id)
                ORDER BY content_id
                LIMIT :limit
                """
            ).bindparams(bindparam("after_content_id", type_=Uuid()))
            content_ids = tuple(
                self._session.scalars(
                    statement,
                    {
                        "after_content_id": after_content_id,
                        "limit": _RULE_VISIBILITY_REFRESH_BATCH_SIZE,
                    },
                )
            )
            if not content_ids:
                break
            self._session.execute(refresh, {"content_ids": list(content_ids)}).all()
            after_content_id = cast(UUID, content_ids[-1])
        self._session.execute(text("SELECT set_config('aima.defer_voice_plaza', 'off', true)"))
        return cast(int, counts.hidden), cast(int, counts.restored)


__all__ = ["PostgresContentRuleFilterRepository"]
