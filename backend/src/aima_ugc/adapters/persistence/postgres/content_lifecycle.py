"""Content Owner 的来源撤销重组：按 Delta 回退仍由目标来源独占的 Current 字段。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Table, delete, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.contribution_tables import content_source_contributions_table
from aima_ugc.modules.content.extended_tables import (
    content_external_ids_table,
    content_locations_table,
    content_media_table,
    content_mentions_table,
    content_topics_table,
)
from aima_ugc.modules.content.tables import accounts_table, content_versions_table, contents_table
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
)
from aima_ugc.modules.ingestion.tables import processing_import_batches_table

from .content_contributions import decode_contribution_value

_CONTENT_FIELD_COLUMNS = {
    "content_type": "content_type",
    "title": "title",
    "text": "text",
    "canonical_url": "canonical_url",
    "share_url": "share_url",
    "published_at": "published_at",
    "source_updated_at": "source_updated_at",
    "status": "status",
    "author.external_account_id": "author_account_id",
    "metrics.like_count": "current_like_count",
    "metrics.comment_count": "current_comment_count",
    "metrics.share_count": "current_share_count",
    "metrics.repost_count": "current_repost_count",
    "metrics.favorite_count": "current_favorite_count",
    "metrics.view_count": "current_view_count",
    "metrics.play_count": "current_play_count",
    "metrics.danmaku_count": "current_danmaku_count",
    "metrics.coin_count": "current_coin_count",
    "metrics.download_count": "current_download_count",
}
_ACCOUNT_FIELD_COLUMNS = {
    "author.display_name": "display_name",
    "author.handle": "handle",
    "author.profile_url": "profile_url",
    "author.avatar_url": "avatar_url",
    "author.bio": "bio",
    "author.verified": "verified",
    "author.verification_label": "verification_label",
    "author.region": "region",
    "author.follower_count": "current_follower_count",
    "author.following_count": "current_following_count",
    "author.content_count": "current_content_count",
    "author.total_like_count": "current_total_like_count",
}
_COLLECTION_TABLES = {
    "alternate_ids": content_external_ids_table,
    "media": content_media_table,
    "topics": content_topics_table,
    "mentions": content_mentions_table,
    "locations": content_locations_table,
}


class PostgresContentLifecycleRepository:
    """Content Owner 唯一执行来源撤销后的 Current/Version 重组。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_campaign_contributions(self, campaign_id: UUID) -> tuple[RowMapping, ...]:
        """按实际写入顺序读取 Campaign 文件导入与后续补采的来源 Delta。"""

        contribution = content_source_contributions_table
        attempt = provider_request_attempts_table
        request = provider_requests_table
        batch = processing_import_batches_table
        campaign_item = historical_import_campaign_items_table
        scope = collection_scopes_table
        run = collection_runs_table
        rows = self._session.execute(
            select(contribution)
            .select_from(
                contribution.join(attempt, attempt.c.id == contribution.c.provider_attempt_id)
                .join(request, request.c.id == attempt.c.provider_request_id)
                .outerjoin(batch, batch.c.id == request.c.import_batch_id)
                .outerjoin(
                    campaign_item,
                    campaign_item.c.id == batch.c.historical_campaign_item_id,
                )
                .outerjoin(scope, scope.c.id == request.c.scope_id)
                .outerjoin(run, run.c.id == scope.c.run_id)
            )
            .where(
                (campaign_item.c.campaign_id == campaign_id)
                | (run.c.data_import_campaign_id == campaign_id)
            )
            .order_by(contribution.c.created_at, contribution.c.id)
        ).mappings()
        return tuple(rows)

    def apply_campaign_revocation(
        self,
        campaign_id: UUID,
        *,
        revoked_at: datetime,
    ) -> tuple[tuple[UUID, int], ...]:
        """逆序回退 Campaign Delta，并为每个受影响 Content 追加一个生命周期 Version。"""

        if revoked_at.utcoffset() is None:
            raise ValueError("revoked_at 必须包含时区")
        contributions = self.list_campaign_contributions(campaign_id)
        by_content: dict[UUID, list[RowMapping]] = defaultdict(list)
        for contribution in contributions:
            by_content[cast(UUID, contribution["content_id"])].append(contribution)

        versions: list[tuple[UUID, int]] = []
        for content_id in sorted(by_content, key=str):
            current = dict(
                self._session.execute(
                    select(contents_table)
                    .where(contents_table.c.id == content_id)
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            current_version = cast(int, current["current_version"])
            version_row = (
                self._session.execute(
                    select(content_versions_table).where(
                        content_versions_table.c.content_id == content_id,
                        content_versions_table.c.version_no == current_version,
                    )
                )
                .mappings()
                .one()
            )
            author_snapshot = (
                dict(cast(dict[str, Any], version_row["author_snapshot"]))
                if isinstance(version_row["author_snapshot"], dict)
                else None
            )
            raw_freshness = current.get("field_observed_at") or {}
            if not isinstance(raw_freshness, dict):
                raise ValueError("Content field_observed_at 必须是对象")
            freshness = {str(key): str(value) for key, value in raw_freshness.items()}

            ordered = sorted(
                by_content[content_id],
                key=lambda row: (row["created_at"], str(row["id"])),
                reverse=True,
            )
            for contribution in ordered:
                delta = contribution["delta"]
                if not isinstance(delta, dict) or delta.get("schema_version") != "content-source-contribution.v1":
                    raise ValueError("Content 来源贡献 Delta 版本不受支持")
                author_snapshot = self._apply_delta(
                    content_id=content_id,
                    current=current,
                    freshness=freshness,
                    author_snapshot=author_snapshot,
                    delta=delta,
                )

            version_no = current_version + 1
            source = ordered[0]
            current["current_version"] = version_no
            current["field_observed_at"] = freshness
            current["updated_at"] = revoked_at
            self._session.execute(
                update(contents_table)
                .where(contents_table.c.id == content_id)
                .values(
                    **{
                        column: current[column]
                        for column in set(_CONTENT_FIELD_COLUMNS.values())
                        if column in current
                    },
                    field_observed_at=freshness,
                    current_version=version_no,
                    updated_at=revoked_at,
                )
            )
            self._session.execute(
                insert(content_versions_table).values(
                    id=uuid4(),
                    content_id=content_id,
                    version_no=version_no,
                    content_type=current["content_type"],
                    title=current["title"],
                    text=current["text"],
                    canonical_url=current["canonical_url"],
                    share_url=current["share_url"],
                    author_snapshot=author_snapshot,
                    published_at=current["published_at"],
                    source_updated_at=current["source_updated_at"],
                    status=current["status"],
                    provider_attempt_id=source["provider_attempt_id"],
                    raw_artifact_id=source["raw_artifact_id"],
                    observed_at=revoked_at,
                )
            )
            versions.append((content_id, version_no))
        return tuple(versions)

    def _apply_delta(
        self,
        *,
        content_id: UUID,
        current: dict[str, Any],
        freshness: dict[str, str],
        author_snapshot: dict[str, Any] | None,
        delta: dict[str, Any],
    ) -> dict[str, Any] | None:
        """仅当 Current 仍匹配来源写入后的值/marker 时回退该字段。"""

        content_fields = delta.get("content_fields") or {}
        if not isinstance(content_fields, dict):
            raise ValueError("Contribution content_fields 必须是对象")
        for path, change in content_fields.items():
            if path not in _CONTENT_FIELD_COLUMNS or not isinstance(change, dict):
                raise ValueError("Contribution Content 字段不受支持")
            column = _CONTENT_FIELD_COLUMNS[path]
            after = decode_contribution_value(change.get("after"))
            before = decode_contribution_value(change.get("before"))
            expected_freshness = change.get("after_freshness")
            if current.get(column) != after or freshness.get(path) != expected_freshness:
                continue
            if column == "content_type" and before is None:
                before = "unknown"
            current[column] = before
            _restore_freshness(freshness, path, change.get("before_freshness"))

        author_change = delta.get("author_snapshot")
        if isinstance(author_change, dict):
            after_author = decode_contribution_value(author_change.get("after"))
            if author_snapshot == after_author:
                before_author = decode_contribution_value(author_change.get("before"))
                author_snapshot = (
                    cast(dict[str, Any], before_author)
                    if isinstance(before_author, dict)
                    else None
                )

        collections = delta.get("collections") or {}
        if not isinstance(collections, dict):
            raise ValueError("Contribution collections 必须是对象")
        for field_name, change in collections.items():
            if field_name not in _COLLECTION_TABLES or not isinstance(change, dict):
                raise ValueError("Contribution Collection 字段不受支持")
            expected_freshness = change.get("after_freshness")
            if freshness.get(field_name) != expected_freshness:
                continue
            after_rows = decode_contribution_value(change.get("after"))
            before_rows = decode_contribution_value(change.get("before"))
            if not isinstance(after_rows, list) or not isinstance(before_rows, list):
                raise ValueError("Contribution Collection rows 必须是数组")
            if self._collection_rows(content_id, field_name) != tuple(after_rows):
                continue
            table = _COLLECTION_TABLES[field_name]
            self._session.execute(delete(table).where(table.c.content_id == content_id))
            if before_rows:
                self._session.execute(
                    insert(table),
                    [
                        {"content_id": content_id, **cast(dict[str, object], row)}
                        for row in before_rows
                    ],
                )
            _restore_freshness(freshness, field_name, change.get("before_freshness"))

        account_change = delta.get("account")
        if isinstance(account_change, dict):
            self._apply_account_delta(account_change)
        return author_snapshot

    def _apply_account_delta(self, account_change: dict[str, Any]) -> None:
        """按 Account 自己的 field_observed_at 只回退仍由目标来源独占的账号字段。"""

        account_id_raw = account_change.get("account_id")
        fields = account_change.get("fields") or {}
        if not account_id_raw or not isinstance(fields, dict):
            return
        account_id = UUID(str(account_id_raw))
        row = dict(
            self._session.execute(
                select(accounts_table)
                .where(accounts_table.c.id == account_id)
                .with_for_update()
            )
            .mappings()
            .one()
        )
        raw_freshness = row.get("field_observed_at") or {}
        if not isinstance(raw_freshness, dict):
            raise ValueError("Account field_observed_at 必须是对象")
        freshness = {str(key): str(value) for key, value in raw_freshness.items()}
        updates: dict[str, object] = {}
        for path, change in fields.items():
            if path not in _ACCOUNT_FIELD_COLUMNS or not isinstance(change, dict):
                raise ValueError("Contribution Account 字段不受支持")
            column = _ACCOUNT_FIELD_COLUMNS[path]
            after = decode_contribution_value(change.get("after"))
            if row.get(column) != after or freshness.get(path) != change.get("after_freshness"):
                continue
            updates[column] = decode_contribution_value(change.get("before"))
            _restore_freshness(freshness, path, change.get("before_freshness"))
        if updates:
            self._session.execute(
                update(accounts_table)
                .where(accounts_table.c.id == account_id)
                .values(**updates, field_observed_at=freshness)
            )

    def _collection_rows(
        self,
        content_id: UUID,
        field_name: str,
    ) -> tuple[dict[str, object], ...]:
        """读取当前 Collection，使用与贡献 Snapshot 相同的稳定排序和字段形状。"""

        table = _COLLECTION_TABLES[field_name]
        order_columns = (table.c.id_type,) if field_name == "alternate_ids" else (table.c.position,)
        rows = self._session.execute(
            select(table).where(table.c.content_id == content_id).order_by(*order_columns)
        ).mappings()
        return tuple(
            {
                str(key): value
                for key, value in row.items()
                if key != "content_id"
            }
            for row in rows
        )


def _restore_freshness(
    freshness: dict[str, str],
    path: str,
    previous: object,
) -> None:
    """恢复贡献写入前的 freshness；原先不存在时删除 marker。"""

    if previous is None:
        freshness.pop(path, None)
    else:
        freshness[path] = str(previous)


__all__ = ["PostgresContentLifecycleRepository"]
