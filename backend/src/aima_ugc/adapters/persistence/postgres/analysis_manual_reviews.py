"""内容 voice_type、情感与标签人工纠正的 PostgreSQL Owner。"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.analysis.manual_override_tables import (
    analysis_content_manual_overrides_table,
)
from aima_ugc.platform.time import beijing_now


class PostgresAnalysisManualReviewRepository:
    """维护每个内容版本的人工锁定当前态；审计历史由调用方负责。"""

    def __init__(self, session: Session) -> None:
        """绑定调用方事务中的 PostgreSQL Session。"""

        self._session = session

    def review(
        self,
        *,
        content_id: UUID,
        content_version: int,
        voice_type: str | None,
        sentiment: str | None,
        labels: tuple[tuple[str, str], ...] | None,
        unlock_dimensions: tuple[str, ...],
        actor_ref: str,
    ) -> RowMapping:
        """按维度保存或解锁人工当前态，并拒绝无确认的覆盖。"""

        current = (
            self._session.execute(
                select(analysis_content_manual_overrides_table)
                .where(
                    analysis_content_manual_overrides_table.c.content_id == content_id,
                    analysis_content_manual_overrides_table.c.content_version == content_version,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        requested = {
            "voice_type": voice_type is not None,
            "sentiment": sentiment is not None,
            "labels": labels is not None,
        }
        for dimension, has_value in requested.items():
            if (
                has_value
                and current is not None
                and bool(current[f"{dimension}_locked"])
                and dimension not in unlock_dimensions
            ):
                raise RuntimeError(f"{dimension} 已人工锁定，修改前必须显式解锁")

        values: dict[str, object] = {
            "voice_type": cast(str | None, current["voice_type"]) if current else None,
            "sentiment": cast(str | None, current["sentiment"]) if current else None,
            "labels": cast(list[dict[str, str]], current["labels"]) if current else [],
            "voice_type_locked": bool(current["voice_type_locked"]) if current else False,
            "sentiment_locked": bool(current["sentiment_locked"]) if current else False,
            "labels_locked": bool(current["labels_locked"]) if current else False,
        }
        for dimension in unlock_dimensions:
            values[dimension] = [] if dimension == "labels" else None
            values[f"{dimension}_locked"] = False
        if voice_type is not None:
            values["voice_type"] = voice_type
            values["voice_type_locked"] = True
        if sentiment is not None:
            values["sentiment"] = sentiment
            values["sentiment_locked"] = True
        if labels is not None:
            values["labels"] = [
                {"primary_label": primary, "secondary_label": secondary}
                for primary, secondary in labels
            ]
            values["labels_locked"] = True
        now = beijing_now()
        return (
            self._session.execute(
                pg_insert(analysis_content_manual_overrides_table)
                .values(
                    content_id=content_id,
                    content_version=content_version,
                    actor_ref=actor_ref,
                    updated_at=now,
                    **values,
                )
                .on_conflict_do_update(
                    index_elements=[
                        analysis_content_manual_overrides_table.c.content_id,
                        analysis_content_manual_overrides_table.c.content_version,
                    ],
                    set_={**values, "actor_ref": actor_ref, "updated_at": now},
                )
                .returning(analysis_content_manual_overrides_table)
            )
            .mappings()
            .one()
        )


__all__ = ["PostgresAnalysisManualReviewRepository"]
