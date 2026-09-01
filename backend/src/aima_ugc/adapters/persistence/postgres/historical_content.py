"""Stage 12 历史 Content 的有界批量填空写入口。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import bindparam, insert, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from aima_ugc.contracts.canonical import CanonicalAuthorV1, CanonicalContentV1
from aima_ugc.modules.content.extended_tables import content_external_ids_table
from aima_ugc.modules.content.ingestion import ContentIngestionService
from aima_ugc.modules.content.tables import accounts_table, content_versions_table, contents_table
from aima_ugc.modules.ingestion.historical_tables import (
    processing_import_batch_identities_table,
    processing_import_batch_item_conflicts_table,
    processing_import_batch_items_table,
)
from aima_ugc.platform.time import beijing_now

from .content_complete import PostgresCompleteContentRepository

_POLICY_VERSION = "historical-fill-only.v1"
_MAX_BATCH_ROWS = 2_000
_CONTENT_FIELDS = {
    "content_type": "content_type",
    "title": "title",
    "text": "text",
    "canonical_url": "canonical_url",
    "share_url": "share_url",
    "published_at": "published_at",
    "source_updated_at": "source_updated_at",
    "status": "status",
}
_AUTHOR_FIELDS = {
    "author.handle": "handle",
    "author.display_name": "display_name",
    "author.profile_url": "profile_url",
    "author.avatar_url": "avatar_url",
    "author.bio": "bio",
    "author.verified": "verified",
    "author.verification_label": "verification_label",
    "author.region": "region",
}
_AUTHOR_METRIC_NAMES = (
    "follower_count",
    "following_count",
    "content_count",
    "total_like_count",
)
_VERSION_COLUMNS = (
    "content_type",
    "title",
    "text",
    "canonical_url",
    "share_url",
    "published_at",
    "source_updated_at",
    "status",
)


@dataclass(frozen=True, slots=True)
class HistoricalBatchRow:
    """一个规范化 Chunk 中的一行；Chunk 自身必须有界。"""

    source_row_ordinal: int
    content: CanonicalContentV1 | None
    preclassified_outcome: Literal["filtered", "invalid"] | None = None
    error_code: str | None = None
    matched_vehicle_aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source_row_ordinal < 1:
            raise ValueError("source_row_ordinal 必须大于等于 1")
        if self.preclassified_outcome is None and self.content is None:
            raise ValueError("待写入历史行必须包含 Canonical Content")
        if self.preclassified_outcome == "filtered" and self.content is None:
            raise ValueError("filtered 行必须保留安全身份所需的 Canonical Content")
        if self.preclassified_outcome == "invalid" and not self.error_code:
            raise ValueError("invalid 行必须包含 error_code")


@dataclass(frozen=True, slots=True)
class HistoricalBatchSummary:
    created: int = 0
    filled: int = 0
    updated: int = 0
    unchanged: int = 0
    conflict: int = 0
    filtered: int = 0
    duplicate: int = 0
    invalid: int = 0
    failed: int = 0
    skipped_terminal: int = 0


@dataclass(slots=True)
class _PlannedRow:
    row: HistoricalBatchRow
    ledger_id: UUID
    identity_hash: str | None
    content_id: UUID | None = None
    content_version: int = 1
    outcome: str = "unchanged"
    filled_fields: list[str] | None = None
    conflicts: list[tuple[str, Any, Any]] | None = None

    def __post_init__(self) -> None:
        self.filled_fields = []
        self.conflicts = []


class PostgresHistoricalContentRepository:
    """Content Owner 的历史批量入口；事务和 Fencing 由上层 Worker 持有。"""

    policy_version = _POLICY_VERSION

    def __init__(self, session: Session) -> None:
        self._session = session

    def ingest_rows(
        self,
        *,
        batch_id: UUID,
        campaign_item_id: UUID,
        chunk_ordinal: int,
        rows: tuple[HistoricalBatchRow, ...],
    ) -> HistoricalBatchSummary:
        """以固定上限处理一个 Chunk；一次事务提交业务变化、行账本和冲突。"""

        if chunk_ordinal < 0:
            raise ValueError("chunk_ordinal 不能为负数")
        if len(rows) > _MAX_BATCH_ROWS:
            raise ValueError(f"单次历史批量不能超过 {_MAX_BATCH_ROWS} 行")
        if not rows:
            return HistoricalBatchSummary()
        ordinals = [item.source_row_ordinal for item in rows]
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("同一调用内 source_row_ordinal 不能重复")

        terminal_ordinals = set(
            self._session.execute(
                select(processing_import_batch_items_table.c.source_row_ordinal).where(
                    processing_import_batch_items_table.c.batch_id == batch_id,
                    processing_import_batch_items_table.c.source_row_ordinal.in_(ordinals),
                )
            ).scalars()
        )
        skipped = len(terminal_ordinals)
        pending = [item for item in rows if item.source_row_ordinal not in terminal_ordinals]
        if not pending:
            return HistoricalBatchSummary(skipped_terminal=skipped)

        preclassified = [
            _PlannedRow(
                row=item,
                ledger_id=uuid4(),
                identity_hash=(
                    _identity_hash(item.content.platform, item.content.external_content_id)
                    if item.content is not None
                    else None
                ),
                outcome=cast(str, item.preclassified_outcome),
            )
            for item in pending
            if item.preclassified_outcome is not None
        ]
        candidates = [item for item in pending if item.preclassified_outcome is None]
        planned = [*preclassified, *self._claim_identities(batch_id=batch_id, rows=candidates)]
        winners = [
            item for item in planned if item.outcome not in {"duplicate", "filtered", "invalid"}
        ]
        self._upsert_authors(winners)
        self._plan_and_write_contents(winners)
        self._write_ledgers(
            batch_id=batch_id,
            campaign_item_id=campaign_item_id,
            chunk_ordinal=chunk_ordinal,
            rows=planned,
        )
        counts: dict[str, int] = {}
        for item in planned:
            counts[item.outcome] = counts.get(item.outcome, 0) + 1
        return HistoricalBatchSummary(
            created=counts.get("created", 0),
            filled=counts.get("filled", 0),
            updated=counts.get("updated", 0),
            unchanged=counts.get("unchanged", 0),
            conflict=counts.get("conflict", 0),
            filtered=counts.get("filtered", 0),
            duplicate=counts.get("duplicate", 0),
            invalid=counts.get("invalid", 0),
            failed=counts.get("failed", 0),
            skipped_terminal=skipped,
        )

    def _claim_identities(
        self,
        *,
        batch_id: UUID,
        rows: list[HistoricalBatchRow],
    ) -> list[_PlannedRow]:
        planned = [
            _PlannedRow(
                row=item,
                ledger_id=uuid4(),
                identity_hash=_identity_hash(
                    cast(CanonicalContentV1, item.content).platform,
                    cast(CanonicalContentV1, item.content).external_content_id,
                ),
            )
            for item in rows
        ]
        claims = [
            {
                "batch_id": batch_id,
                "identity_hash": item.identity_hash,
                "first_row_ordinal": item.row.source_row_ordinal,
            }
            for item in sorted(planned, key=lambda value: value.row.source_row_ordinal)
        ]
        if claims:
            self._session.execute(
                pg_insert(processing_import_batch_identities_table)
                .values(claims)
                .on_conflict_do_nothing(
                    index_elements=[
                        processing_import_batch_identities_table.c.batch_id,
                        processing_import_batch_identities_table.c.identity_hash,
                    ]
                )
            )
        identity_hashes = tuple({cast(str, item.identity_hash) for item in planned})
        first_rows: dict[str, int] = {
            cast(str, row.identity_hash): cast(int, row.first_row_ordinal)
            for row in self._session.execute(
                select(
                    processing_import_batch_identities_table.c.identity_hash,
                    processing_import_batch_identities_table.c.first_row_ordinal,
                ).where(
                    processing_import_batch_identities_table.c.batch_id == batch_id,
                    processing_import_batch_identities_table.c.identity_hash.in_(identity_hashes),
                )
            )
        }
        for item in planned:
            if first_rows[cast(str, item.identity_hash)] != item.row.source_row_ordinal:
                item.outcome = "duplicate"
        return planned

    def _upsert_authors(self, rows: list[_PlannedRow]) -> None:
        authors: dict[tuple[str, str], _PlannedRow] = {}
        for planned in sorted(rows, key=lambda value: value.row.source_row_ordinal):
            content = cast(CanonicalContentV1, planned.row.content)
            author = content.author
            if author is None or author.external_account_id is None:
                continue
            authors.setdefault((content.platform, author.external_account_id), planned)
        if not authors:
            return
        values: list[dict[str, Any]] = []
        for (platform, external_id), planned in authors.items():
            content = cast(CanonicalContentV1, planned.row.content)
            author = cast(CanonicalAuthorV1, content.author)
            candidate = _author_values(author, content.observed_fields)
            values.append(
                {
                    "id": uuid4(),
                    "platform": platform,
                    "external_account_id": external_id,
                    "first_seen_at": content.observed_at,
                    "last_seen_at": content.observed_at,
                    "field_observed_at": {},
                    "updated_at": content.observed_at,
                    **candidate,
                }
            )
        self._session.execute(
            pg_insert(accounts_table)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[accounts_table.c.platform, accounts_table.c.external_account_id]
            )
        )
        keys = tuple(authors)
        existing = {
            (cast(str, row["platform"]), cast(str, row["external_account_id"])): dict(row)
            for row in self._session.execute(
                select(accounts_table)
                .where(
                    tuple_(accounts_table.c.platform, accounts_table.c.external_account_id).in_(
                        keys
                    )
                )
                .with_for_update()
            ).mappings()
        }
        updates: list[dict[str, Any]] = []
        for planned in sorted(rows, key=lambda value: value.row.source_row_ordinal):
            content = cast(CanonicalContentV1, planned.row.content)
            author = content.author
            if author is None or author.external_account_id is None:
                continue
            current = existing[(content.platform, author.external_account_id)]
            changed: dict[str, Any] = {}
            assert planned.filled_fields is not None
            assert planned.conflicts is not None
            for path, column in _AUTHOR_FIELDS.items():
                value = _author_value(author, path)
                if path not in content.observed_fields or _empty(value):
                    continue
                if current[column] is None:
                    changed[column] = value
                    current[column] = value
                    planned.filled_fields.append(path)
                elif _comparable(current[column]) != _comparable(value):
                    _append_conflict(planned.conflicts, path, current[column], value)
            if changed:
                updates.append({"record_id": current["id"], "updated_at": beijing_now(), **changed})
        self._execute_grouped_updates(accounts_table, updates)

    def _plan_and_write_contents(self, rows: list[_PlannedRow]) -> None:
        if not rows:
            return
        identities = tuple(
            (
                cast(CanonicalContentV1, item.row.content).platform,
                cast(CanonicalContentV1, item.row.content).external_content_id,
            )
            for item in rows
        )
        before = {
            (cast(str, row["platform"]), cast(str, row["external_content_id"])): dict(row)
            for row in self._session.execute(
                select(contents_table)
                .where(
                    tuple_(contents_table.c.platform, contents_table.c.external_content_id).in_(
                        identities
                    )
                )
                .with_for_update()
            ).mappings()
        }
        account_ids = self._author_account_ids(rows)
        inserts: list[dict[str, Any]] = []
        inserted_by_identity: dict[tuple[str, str], UUID] = {}
        for planned in rows:
            content = cast(CanonicalContentV1, planned.row.content)
            identity = (content.platform, content.external_content_id)
            if identity in before:
                continue
            content_id = uuid4()
            author_id = _resolved_author_id(content, account_ids)
            values = _new_content_values(content_id, content, author_id)
            inserts.append(values)
            inserted_by_identity[identity] = content_id
        if inserts:
            created_ids = set(
                self._session.execute(
                    pg_insert(contents_table)
                    .values(inserts)
                    .on_conflict_do_nothing(
                        index_elements=[
                            contents_table.c.platform,
                            contents_table.c.external_content_id,
                        ]
                    )
                    .returning(contents_table.c.id)
                ).scalars()
            )
        else:
            created_ids = set()
        current_rows = {
            (cast(str, row["platform"]), cast(str, row["external_content_id"])): dict(row)
            for row in self._session.execute(
                select(contents_table)
                .where(
                    tuple_(contents_table.c.platform, contents_table.c.external_content_id).in_(
                        identities
                    )
                )
                .with_for_update()
            ).mappings()
        }
        current_version_rows = self._current_version_rows(current_rows)
        version_values: list[dict[str, Any]] = []
        external_id_values: list[dict[str, Any]] = []
        content_updates: list[dict[str, Any]] = []
        for planned in rows:
            content = cast(CanonicalContentV1, planned.row.content)
            identity = (content.platform, content.external_content_id)
            current = current_rows[identity]
            content_id = cast(UUID, current["id"])
            planned.content_id = content_id
            planned.content_version = int(current["current_version"])
            created = content_id in created_ids
            author_id = _resolved_author_id(content, account_ids)
            author_snapshot = _historical_author_snapshot(content.author)
            if created:
                planned.outcome = "created"
                version_values.append(
                    _version_values(
                        content_id=content_id,
                        version_no=1,
                        state=current,
                        author_snapshot=author_snapshot,
                        content=content,
                    )
                )
            else:
                old_version = current_version_rows[content_id]
                updates, merged_author = self._fill_existing(
                    planned=planned,
                    current=current,
                    current_author_snapshot=cast(
                        dict[str, Any] | None, old_version["author_snapshot"]
                    ),
                    author_id=author_id,
                    account_ids=account_ids,
                )
                if updates or merged_author != old_version["author_snapshot"]:
                    new_version = int(current["current_version"]) + 1
                    changed_at = beijing_now()
                    content_updates.append(
                        {
                            "record_id": content_id,
                            "current_version": new_version,
                            "updated_at": changed_at,
                            **updates,
                        }
                    )
                    current.update(updates)
                    current["current_version"] = new_version
                    planned.content_version = new_version
                    version_values.append(
                        _version_values(
                            content_id=content_id,
                            version_no=new_version,
                            state=current,
                            author_snapshot=merged_author,
                            content=content,
                        )
                    )
                    planned.outcome = "filled"
                elif planned.conflicts:
                    planned.outcome = "conflict"
                elif planned.filled_fields:
                    planned.outcome = "filled"
                else:
                    planned.outcome = "unchanged"
            if "alternate_ids" in content.observed_fields:
                for id_type, external_id in sorted(content.alternate_ids.items()):
                    external_id_values.append(
                        {
                            "content_id": content_id,
                            "id_type": id_type,
                            "external_id": external_id,
                            "provider_attempt_id": UUID(
                                cast(str, content.source.provider_attempt_id)
                            ),
                            "raw_artifact_id": content.source.raw_artifact_id,
                            "observed_at": content.observed_at,
                        }
                    )
        self._fill_external_ids(rows, external_id_values)
        versioned_ids = {cast(UUID, value["content_id"]) for value in version_values}
        for planned in rows:
            if (
                planned.outcome != "filled"
                or planned.content_id is None
                or planned.content_id in versioned_ids
            ):
                continue
            content = cast(CanonicalContentV1, planned.row.content)
            current = current_rows[(content.platform, content.external_content_id)]
            old_version = current_version_rows[planned.content_id]
            new_version = int(current["current_version"]) + 1
            content_updates.append(
                {
                    "record_id": planned.content_id,
                    "current_version": new_version,
                    "updated_at": beijing_now(),
                }
            )
            current["current_version"] = new_version
            planned.content_version = new_version
            version_values.append(
                _version_values(
                    content_id=planned.content_id,
                    version_no=new_version,
                    state=current,
                    author_snapshot=cast(dict[str, Any] | None, old_version["author_snapshot"]),
                    content=content,
                )
            )
        self._execute_grouped_updates(contents_table, content_updates)
        if version_values:
            self._session.execute(insert(content_versions_table), version_values)

    def _execute_grouped_updates(
        self,
        table: Any,
        rows: list[dict[str, Any]],
    ) -> None:
        """按相同列集合分组为 executemany，数据库往返数不随输入行线性增长。"""

        grouped: dict[frozenset[str], list[dict[str, Any]]] = {}
        for row in rows:
            columns = frozenset(row).difference({"record_id"})
            grouped.setdefault(columns, []).append(row)
        for columns, values in grouped.items():
            statement = (
                update(table)
                .where(table.c.id == bindparam("_historical_record_id"))
                .values({column: bindparam(column) for column in columns})
            )
            params = [
                {
                    "_historical_record_id": value["record_id"],
                    **{column: value[column] for column in columns},
                }
                for value in values
            ]
            self._session.execute(statement, params)

    def _fill_existing(
        self,
        *,
        planned: _PlannedRow,
        current: dict[str, Any],
        current_author_snapshot: dict[str, Any] | None,
        author_id: UUID | None,
        account_ids: dict[tuple[str, str], UUID],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        content = cast(CanonicalContentV1, planned.row.content)
        updates: dict[str, Any] = {}
        assert planned.filled_fields is not None
        assert planned.conflicts is not None
        for path, column in _CONTENT_FIELDS.items():
            if path not in content.observed_fields:
                continue
            value = getattr(content, path)
            if path in {"canonical_url", "share_url"} and value is not None:
                value = str(value)
            _compare_fill(
                path=path,
                current_value=current[column],
                historical_value=value,
                updates=updates,
                column=column,
                filled=planned.filled_fields,
                conflicts=planned.conflicts,
            )
        if "author.external_account_id" in content.observed_fields and author_id is not None:
            _compare_fill(
                path="author.external_account_id",
                current_value=current["author_account_id"],
                historical_value=author_id,
                updates=updates,
                column="author_account_id",
                filled=planned.filled_fields,
                conflicts=planned.conflicts,
            )
        merged_author = dict(current_author_snapshot) if current_author_snapshot else None
        if content.author is not None:
            current_author_id = current["author_account_id"]
            candidate_id = _resolved_author_id(content, account_ids)
            if current_author_id is None or candidate_id == current_author_id:
                if merged_author is None:
                    merged_author = {}
                for path in _AUTHOR_FIELDS:
                    if path not in content.observed_fields:
                        continue
                    key = path.removeprefix("author.")
                    value = _author_value(content.author, path)
                    existing = merged_author.get(key)
                    before_count = len(planned.filled_fields)
                    _compare_fill(
                        path=path,
                        current_value=existing,
                        historical_value=value,
                        updates=merged_author,
                        column=key,
                        filled=planned.filled_fields,
                        conflicts=planned.conflicts,
                    )
                    if len(planned.filled_fields) == before_count and key not in merged_author:
                        merged_author.pop(key, None)
        return updates, merged_author

    def _author_account_ids(self, rows: list[_PlannedRow]) -> dict[tuple[str, str], UUID]:
        key_set: set[tuple[str, str]] = set()
        for item in rows:
            content = cast(CanonicalContentV1, item.row.content)
            author = content.author
            if author is not None and author.external_account_id is not None:
                key_set.add((content.platform, author.external_account_id))
        keys = tuple(key_set)
        if not keys:
            return {}
        return {
            (cast(str, row["platform"]), cast(str, row["external_account_id"])): cast(
                UUID, row["id"]
            )
            for row in self._session.execute(
                select(
                    accounts_table.c.id,
                    accounts_table.c.platform,
                    accounts_table.c.external_account_id,
                ).where(
                    tuple_(accounts_table.c.platform, accounts_table.c.external_account_id).in_(
                        keys
                    )
                )
            ).mappings()
        }

    def _current_version_rows(
        self, current_rows: dict[tuple[str, str], dict[str, Any]]
    ) -> dict[UUID, dict[str, Any]]:
        pairs = tuple(
            (cast(UUID, row["id"]), cast(int, row["current_version"]))
            for row in current_rows.values()
        )
        return {
            cast(UUID, row["content_id"]): dict(row)
            for row in self._session.execute(
                select(content_versions_table).where(
                    tuple_(
                        content_versions_table.c.content_id, content_versions_table.c.version_no
                    ).in_(pairs)
                )
            ).mappings()
        }

    def _fill_external_ids(
        self,
        rows: list[_PlannedRow],
        values: list[dict[str, Any]],
    ) -> None:
        if not values:
            return
        existing = {
            (cast(UUID, row["content_id"]), cast(str, row["id_type"])): cast(
                str, row["external_id"]
            )
            for row in self._session.execute(
                select(content_external_ids_table).where(
                    tuple_(
                        content_external_ids_table.c.content_id,
                        content_external_ids_table.c.id_type,
                    ).in_(tuple((value["content_id"], value["id_type"]) for value in values))
                )
            ).mappings()
        }
        inserts: list[dict[str, Any]] = []
        by_content = {item.content_id: item for item in rows}
        for value in values:
            key = (value["content_id"], value["id_type"])
            current = existing.get(key)
            planned = by_content[cast(UUID, value["content_id"])]
            assert planned.filled_fields is not None
            assert planned.conflicts is not None
            path = f"alternate_ids.{value['id_type']}"
            if current is None:
                inserts.append(value)
                planned.filled_fields.append(path)
                if planned.outcome == "unchanged":
                    planned.outcome = "filled"
            elif current != value["external_id"]:
                planned.conflicts.append((path, current, value["external_id"]))
                if planned.outcome == "unchanged":
                    planned.outcome = "conflict"
        if inserts:
            self._session.execute(
                pg_insert(content_external_ids_table)
                .values(inserts)
                .on_conflict_do_nothing(
                    index_elements=[
                        content_external_ids_table.c.content_id,
                        content_external_ids_table.c.id_type,
                    ]
                )
            )

    def _write_ledgers(
        self,
        *,
        batch_id: UUID,
        campaign_item_id: UUID,
        chunk_ordinal: int,
        rows: list[_PlannedRow],
    ) -> None:
        created_at = beijing_now()
        ledger_values = [
            {
                "id": item.ledger_id,
                "batch_id": batch_id,
                "campaign_item_id": campaign_item_id,
                "source_row_ordinal": item.row.source_row_ordinal,
                "platform": item.row.content.platform if item.row.content is not None else None,
                "external_content_id_hash": (
                    _value_hash(item.row.content.external_content_id)
                    if item.row.content is not None
                    else None
                ),
                "content_id": item.content_id,
                "outcome": item.outcome,
                "error_code": item.row.error_code,
                "filled_count": len(item.filled_fields or ()),
                "conflict_count": len(item.conflicts or ()),
                "committed_chunk_ordinal": chunk_ordinal,
                "created_at": created_at,
            }
            for item in rows
        ]
        self._session.execute(insert(processing_import_batch_items_table), ledger_values)
        conflicts = [
            {
                "id": uuid4(),
                "batch_item_id": item.ledger_id,
                "field_name": path,
                "content_version": item.content_version,
                "current_value_hash": _value_hash(current),
                "historical_value_hash": _value_hash(historical),
                "created_at": created_at,
            }
            for item in rows
            for path, current, historical in (item.conflicts or ())
        ]
        if conflicts:
            self._session.execute(insert(processing_import_batch_item_conflicts_table), conflicts)


class PostgresStandardContentRepository(PostgresHistoricalContentRepository):
    """复用 Campaign 行账本，以既有 Content Owner 执行普通观测语义。"""

    policy_version = "standard-observation.v1"

    def ingest_rows(
        self,
        *,
        batch_id: UUID,
        campaign_item_id: UUID,
        chunk_ordinal: int,
        rows: tuple[HistoricalBatchRow, ...],
    ) -> HistoricalBatchSummary:
        if chunk_ordinal < 0:
            raise ValueError("chunk_ordinal 不能为负数")
        if len(rows) > _MAX_BATCH_ROWS:
            raise ValueError(f"单次标准观测批量不能超过 {_MAX_BATCH_ROWS} 行")
        if not rows:
            return HistoricalBatchSummary()
        ordinals = [item.source_row_ordinal for item in rows]
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("同一调用内 source_row_ordinal 不能重复")
        terminal_ordinals = set(
            self._session.execute(
                select(processing_import_batch_items_table.c.source_row_ordinal).where(
                    processing_import_batch_items_table.c.batch_id == batch_id,
                    processing_import_batch_items_table.c.source_row_ordinal.in_(ordinals),
                )
            ).scalars()
        )
        skipped = len(terminal_ordinals)
        pending = [item for item in rows if item.source_row_ordinal not in terminal_ordinals]
        if not pending:
            return HistoricalBatchSummary(skipped_terminal=skipped)
        planned = [
            _PlannedRow(
                row=item,
                ledger_id=uuid4(),
                identity_hash=(
                    _identity_hash(item.content.platform, item.content.external_content_id)
                    if item.content is not None
                    else None
                ),
                outcome=cast(str, item.preclassified_outcome),
            )
            for item in pending
            if item.preclassified_outcome is not None
        ]
        candidates = [item for item in pending if item.preclassified_outcome is None]
        planned.extend(self._claim_identities(batch_id=batch_id, rows=candidates))
        service = ContentIngestionService(PostgresCompleteContentRepository(self._session))
        for item in planned:
            if item.outcome in {"duplicate", "filtered", "invalid"}:
                continue
            content = cast(CanonicalContentV1, item.row.content)
            result = service.ingest_content(content)
            item.content_id = result.target_id
            item.content_version = result.version_no
            if result.version_created and result.version_no == 1:
                item.outcome = "created"
            elif result.version_created or result.metric_recorded:
                item.outcome = "updated"
            else:
                item.outcome = "unchanged"
        self._write_ledgers(
            batch_id=batch_id,
            campaign_item_id=campaign_item_id,
            chunk_ordinal=chunk_ordinal,
            rows=planned,
        )
        counts: dict[str, int] = {}
        for item in planned:
            counts[item.outcome] = counts.get(item.outcome, 0) + 1
        return HistoricalBatchSummary(
            created=counts.get("created", 0),
            updated=counts.get("updated", 0),
            unchanged=counts.get("unchanged", 0),
            filtered=counts.get("filtered", 0),
            duplicate=counts.get("duplicate", 0),
            invalid=counts.get("invalid", 0),
            failed=counts.get("failed", 0),
            skipped_terminal=skipped,
        )


def _new_content_values(
    content_id: UUID,
    content: CanonicalContentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    """生成列集固定的 Content INSERT 值，未观测字段保持 NULL。"""

    values: dict[str, Any] = {
        **{column: None for column in _CONTENT_FIELDS.values()},
        "id": content_id,
        "platform": content.platform,
        "external_content_id": content.external_content_id,
        "content_type": content.content_type,
        "author_account_id": author_id,
        "first_seen_at": content.observed_at,
        "last_seen_at": content.observed_at,
        "current_version": 1,
        "field_observed_at": {},
        "updated_at": content.observed_at,
    }
    for path, column in _CONTENT_FIELDS.items():
        value = getattr(content, path)
        if path in {"canonical_url", "share_url"} and value is not None:
            value = str(value)
        if path in content.observed_fields and not _empty(value):
            values[column] = value
    return values


def _version_values(
    *,
    content_id: UUID,
    version_no: int,
    state: dict[str, Any],
    author_snapshot: dict[str, Any] | None,
    content: CanonicalContentV1,
) -> dict[str, Any]:
    if content.source.provider_attempt_id is None or content.source.raw_artifact_id is None:
        raise ValueError("历史 Content 来源必须包含 provider_attempt_id 与 raw_artifact_id")
    return {
        "id": uuid4(),
        "content_id": content_id,
        "version_no": version_no,
        **{column: state.get(column) for column in _VERSION_COLUMNS},
        "author_snapshot": author_snapshot,
        "provider_attempt_id": UUID(content.source.provider_attempt_id),
        "raw_artifact_id": content.source.raw_artifact_id,
        "observed_at": content.observed_at,
    }


def _resolved_author_id(
    content: CanonicalContentV1,
    account_ids: dict[tuple[str, str], UUID],
) -> UUID | None:
    if content.author is None or content.author.external_account_id is None:
        return None
    return account_ids[(content.platform, content.author.external_account_id)]


def _author_values(author: CanonicalAuthorV1, observed_fields: list[str]) -> dict[str, Any]:
    """生成列集固定的 Author INSERT 值，保持稀疏字段语义。"""

    values: dict[str, Any] = {column: None for column in _AUTHOR_FIELDS.values()}
    for path, column in _AUTHOR_FIELDS.items():
        value = _author_value(author, path)
        if path in observed_fields and not _empty(value):
            values[column] = value
    return values


def _historical_author_snapshot(author: CanonicalAuthorV1 | None) -> dict[str, Any] | None:
    if author is None:
        return None
    snapshot = author.model_dump(mode="json")
    for name in _AUTHOR_METRIC_NAMES:
        snapshot.pop(name, None)
    return snapshot


def _author_value(author: CanonicalAuthorV1, path: str) -> Any:
    value = getattr(author, path.removeprefix("author."))
    if path in {"author.profile_url", "author.avatar_url"} and value is not None:
        return str(value)
    return value


def _compare_fill(
    *,
    path: str,
    current_value: Any,
    historical_value: Any,
    updates: dict[str, Any],
    column: str,
    filled: list[str],
    conflicts: list[tuple[str, Any, Any]],
) -> None:
    if _empty(historical_value):
        return
    if current_value is None:
        updates[column] = historical_value
        filled.append(path)
    elif _comparable(current_value) != _comparable(historical_value):
        _append_conflict(conflicts, path, current_value, historical_value)


def _append_conflict(
    conflicts: list[tuple[str, Any, Any]],
    path: str,
    current_value: Any,
    historical_value: Any,
) -> None:
    if any(existing_path == path for existing_path, _, _ in conflicts):
        return
    conflicts.append((path, current_value, historical_value))


def _identity_hash(platform: str, external_content_id: str) -> str:
    return _value_hash([platform, external_content_id])


def _value_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _comparable(value: Any) -> Any:
    return str(value) if hasattr(value, "unicode_string") else value


def _empty(value: Any) -> bool:
    return value is None or value == ""


__all__ = [
    "HistoricalBatchRow",
    "HistoricalBatchSummary",
    "PostgresHistoricalContentRepository",
    "PostgresStandardContentRepository",
]
