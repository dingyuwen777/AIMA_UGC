"""Stage 6 Content Owner PostgreSQL Current/History 摄取。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date, datetime
from itertools import batched
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, bindparam, insert, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from .content_contributions import ContentContributionSnapshot

from aima_ugc.contracts.canonical import (
    CanonicalAuthorV1,
    CanonicalCommentV1,
    CanonicalContentV1,
)
from aima_ugc.modules.content.account_tables import account_external_ids_table
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_coverage_observations_table,
    comment_metric_observations_table,
    comment_versions_table,
    comments_table,
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)

_BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
_MULTI_VALUES_INSERT_ROWS = 500
_CONTENT_METRICS = (
    "like_count",
    "comment_count",
    "share_count",
    "repost_count",
    "favorite_count",
    "view_count",
    "play_count",
    "danmaku_count",
    "coin_count",
    "download_count",
)
_CONTENT_BUSINESS_COLUMNS = (
    "content_type",
    "title",
    "text",
    "canonical_url",
    "share_url",
    "author_account_id",
    "published_at",
    "source_updated_at",
    "status",
)
_COMMENT_BUSINESS_COLUMNS = (
    "root_comment_id",
    "parent_comment_id",
    "text",
    "published_at",
    "source_updated_at",
    "status",
    "is_by_content_author",
    "author_account_id",
)
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
_ACCOUNT_COLUMNS = tuple(_ACCOUNT_FIELD_COLUMNS.values())
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
    **{f"metrics.{name}": f"current_{name}" for name in _CONTENT_METRICS},
}
_COMMENT_FIELD_COLUMNS = {
    "root_comment_id": "root_comment_id",
    "parent_comment_id": "parent_comment_id",
    "text": "text",
    "published_at": "published_at",
    "source_updated_at": "source_updated_at",
    "status": "status",
    "is_by_content_author": "is_by_content_author",
    "author.external_account_id": "author_account_id",
    "metrics.like_count": "current_like_count",
    "metrics.reply_count": "current_reply_count",
}
_COVERAGE_VALUES = {"complete", "partial", "not_requested", "unavailable"}


@dataclass(frozen=True, slots=True)
class PostgresIngestionResult:
    target_id: UUID
    version_no: int
    version_created: bool
    metric_recorded: bool
    contribution_after: ContentContributionSnapshot | None = dataclass_field(
        default=None, compare=False, repr=False
    )


@dataclass(frozen=True, slots=True)
class PostgresNewContentBatchItem:
    """集合写入中由当前事务真实创建的一条 Content。"""

    observation: CanonicalContentV1
    result: PostgresIngestionResult
    state: dict[str, Any] = dataclass_field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class PostgresExistingContentBatchItem:
    """集合更新一个安全既有 Content 后的结果与已接受 Collection。"""

    observation: CanonicalContentV1
    result: PostgresIngestionResult
    accepted_collection_fields: frozenset[str]


class PostgresContentRepository:
    """Content 模块唯一业务表写入口；事务由调用方持有。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ingest_content(
        self,
        observation: CanonicalContentV1,
        *,
        collection_fields: frozenset[str] = frozenset(),
    ) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        author_id = self._upsert_author(observation)
        content_id = uuid4()
        state = _new_content_state(
            content_id, observation, author_id, collection_fields=collection_fields
        )
        created = self._session.execute(
            pg_insert(contents_table)
            .values(**state)
            .on_conflict_do_nothing(
                index_elements=[
                    contents_table.c.platform,
                    contents_table.c.external_content_id,
                ]
            )
            .returning(contents_table.c.id)
        ).scalar_one_or_none()
        if created is not None:
            self._append_content_version(
                content_id=content_id,
                version_no=1,
                state=state,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            self._append_content_metric(
                content_id=content_id,
                observation=observation,
                reason="initial",
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            return PostgresIngestionResult(content_id, 1, True, True)

        current = dict(
            self._session.execute(
                select(contents_table)
                .where(
                    contents_table.c.platform == observation.platform,
                    contents_table.c.external_content_id == observation.external_content_id,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        content_id = cast(UUID, current["id"])
        metric_changed = _content_metric_changed(current, observation)
        current_updates, field_observed_at = _fresh_updates(
            current=current,
            candidate_updates=_content_updates(observation, author_id),
            observed_fields=observation.observed_fields,
            field_columns=_CONTENT_FIELD_COLUMNS,
            observed_at=observation.observed_at,
        )
        version_no = int(current["current_version"])
        merged = dict(current)
        merged.update(current_updates)
        business_changed = _business_tuple(current, _CONTENT_BUSINESS_COLUMNS) != _business_tuple(
            merged, _CONTENT_BUSINESS_COLUMNS
        )
        version_no += 1 if business_changed else 0
        updates: dict[str, Any] = {
            "first_seen_at": min(current["first_seen_at"], observation.observed_at),
            "last_seen_at": max(current["last_seen_at"], observation.observed_at),
            "updated_at": max(current["updated_at"], observation.observed_at),
            "field_observed_at": field_observed_at,
            "current_version": version_no,
            **current_updates,
        }
        merged.update(updates)
        self._session.execute(
            update(contents_table).where(contents_table.c.id == content_id).values(**updates)
        )
        if business_changed:
            self._append_content_version(
                content_id=content_id,
                version_no=version_no,
                state=merged,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )

        metric_recorded = False
        has_metric_fields = any(
            f"metrics.{name}" in observation.observed_fields for name in _CONTENT_METRICS
        )
        if has_metric_fields and not self._has_content_source_metric(
            content_id, attempt_id, raw_id
        ):
            day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
            if metric_changed:
                reason = "changed"
            elif not self._has_content_metric_on_day(content_id, day):
                reason = "daily_checkpoint"
            else:
                reason = None
            if reason is not None:
                self._append_content_metric(
                    content_id=content_id,
                    observation=observation,
                    reason=reason,
                    attempt_id=attempt_id,
                    raw_id=raw_id,
                )
                metric_recorded = True
        return PostgresIngestionResult(
            content_id,
            version_no,
            business_changed,
            metric_recorded,
        )

    def ingest_new_contents_batch(
        self,
        observations: tuple[CanonicalContentV1, ...],
        *,
        collection_fields: frozenset[str] = frozenset(),
        replay_visibility_owner_id: UUID | None = None,
    ) -> tuple[PostgresNewContentBatchItem, ...]:
        """集合创建 Content，并批量收敛稳定作者；数据库冲突行由调用方回退。"""

        if not observations:
            return ()
        identities = tuple((item.platform, item.external_content_id) for item in observations)
        if len(set(identities)) != len(identities):
            raise ValueError("Content 集合创建不接受重复身份")
        author_ids = self._upsert_content_authors_batch(observations)

        candidates: list[tuple[CanonicalContentV1, UUID, dict[str, Any], UUID, UUID]] = []
        for observation, author_id in zip(observations, author_ids, strict=True):
            attempt_id, raw_id = _source_ids(observation)
            content_id = uuid4()
            state = _new_content_state(
                content_id,
                observation,
                author_id,
                collection_fields=collection_fields,
            )
            # Multi-values INSERT 要求每行拥有相同键；缺失字段与逐行 INSERT 的
            # 数据库 NULL 语义一致，同时在初始写入中直接保存 Replay 可见性归属。
            for column in _CONTENT_BUSINESS_COLUMNS:
                state.setdefault(column, None)
            for metric in _CONTENT_METRICS:
                state.setdefault(f"current_{metric}", None)
            state["replay_visibility_owner_id"] = replay_visibility_owner_id
            candidates.append((observation, content_id, state, attempt_id, raw_id))

        created: dict[tuple[str, str], UUID] = {}
        for candidate_chunk in batched(candidates, _MULTI_VALUES_INSERT_ROWS, strict=False):
            statement = (
                pg_insert(contents_table)
                .on_conflict_do_nothing(
                    index_elements=[
                        contents_table.c.platform,
                        contents_table.c.external_content_id,
                    ]
                )
                .returning(
                    contents_table.c.id,
                    contents_table.c.platform,
                    contents_table.c.external_content_id,
                )
            )
            created_rows = self._session.execute(
                statement,
                [item[2] for item in candidate_chunk],
            )
            created.update(
                {
                    (row.platform, row.external_content_id): cast(UUID, row.id)
                    for row in created_rows
                }
            )
        accepted = [
            item
            for item in candidates
            if created.get((item[0].platform, item[0].external_content_id)) == item[1]
        ]
        if not accepted:
            return ()

        version_values = [
            {
                "id": uuid4(),
                "content_id": content_id,
                "version_no": 1,
                "content_type": state["content_type"],
                "title": state.get("title"),
                "text": state.get("text"),
                "canonical_url": state.get("canonical_url"),
                "share_url": state.get("share_url"),
                "author_snapshot": (
                    observation.author.model_dump(mode="json")
                    if observation.author is not None
                    else None
                ),
                "published_at": state.get("published_at"),
                "source_updated_at": state.get("source_updated_at"),
                "status": state.get("status"),
                "provider_attempt_id": attempt_id,
                "raw_artifact_id": raw_id,
                "observed_at": observation.observed_at,
            }
            for observation, content_id, state, attempt_id, raw_id in accepted
        ]
        for version_chunk in batched(
            version_values,
            _MULTI_VALUES_INSERT_ROWS,
            strict=False,
        ):
            self._session.execute(insert(content_versions_table), list(version_chunk))
        metric_values = [
            {
                "id": uuid4(),
                "content_id": content_id,
                "provider_attempt_id": attempt_id,
                "raw_artifact_id": raw_id,
                "reason": "initial",
                "business_date": observation.observed_at.astimezone(_BUSINESS_TZ).date(),
                "observation_key": _observation_key(observation, "initial"),
                "observed_at": observation.observed_at,
                **{
                    metric: (
                        getattr(observation.metrics, metric)
                        if f"metrics.{metric}" in observation.observed_fields
                        else None
                    )
                    for metric in _CONTENT_METRICS
                },
            }
            for observation, content_id, _state, attempt_id, raw_id in accepted
        ]
        for metric_chunk in batched(
            metric_values,
            _MULTI_VALUES_INSERT_ROWS,
            strict=False,
        ):
            self._session.execute(insert(content_metric_observations_table), list(metric_chunk))
        return tuple(
            PostgresNewContentBatchItem(
                observation=observation,
                result=PostgresIngestionResult(content_id, 1, True, True),
                state=state,
            )
            for observation, content_id, state, _attempt_id, _raw_id in accepted
        )

    def ingest_existing_contents_batch(
        self,
        observations: tuple[CanonicalContentV1, ...],
        *,
        collection_fields: frozenset[str] = frozenset(),
        replay_visibility_owner_id: UUID | None = None,
    ) -> tuple[PostgresExistingContentBatchItem, ...]:
        """集合更新既有 Content，并以批量账号解析保留稳定作者语义。"""

        if not observations:
            return ()
        identities = tuple((item.platform, item.external_content_id) for item in observations)
        if len(set(identities)) != len(identities):
            raise ValueError("既有 Content 集合更新不接受重复身份")
        # 与单行 ingest_content 保持 Account → Content 的锁顺序，避免批量与
        # 兼容路径并发处理同一作者和内容时形成交叉等待。
        author_ids = self._upsert_content_authors_batch(observations)
        current_by_identity = {
            (cast(str, row["platform"]), cast(str, row["external_content_id"])): dict(row)
            for row in self._session.execute(
                select(contents_table)
                .where(
                    tuple_(contents_table.c.platform, contents_table.c.external_content_id).in_(
                        identities
                    )
                )
                .order_by(contents_table.c.id)
                .with_for_update()
            ).mappings()
        }
        if set(current_by_identity) != set(identities):
            raise ValueError("既有 Content 集合更新发现缺失身份")
        if any(
            current_by_identity[identity]["author_account_id"] is not None
            and "author.external_account_id" in observation.observed_fields
            and (observation.author is None or observation.author.external_account_id is None)
            for observation, identity in zip(observations, identities, strict=True)
        ):
            raise ValueError("既有 Content 集合更新不接受清空已绑定稳定作者")

        source_by_identity = {
            (item.platform, item.external_content_id): _source_ids(item) for item in observations
        }
        metric_candidates = tuple(
            (
                cast(UUID, current_by_identity[identity]["id"]),
                *source_by_identity[identity],
                observation.observed_at.astimezone(_BUSINESS_TZ).date(),
            )
            for observation, identity in zip(observations, identities, strict=True)
            if any(f"metrics.{name}" in observation.observed_fields for name in _CONTENT_METRICS)
        )
        source_metric_keys = (
            set(
                self._session.execute(
                    select(
                        content_metric_observations_table.c.content_id,
                        content_metric_observations_table.c.provider_attempt_id,
                        content_metric_observations_table.c.raw_artifact_id,
                    ).where(
                        tuple_(
                            content_metric_observations_table.c.content_id,
                            content_metric_observations_table.c.provider_attempt_id,
                            content_metric_observations_table.c.raw_artifact_id,
                        ).in_(tuple(item[:3] for item in metric_candidates))
                    )
                )
            )
            if metric_candidates
            else set()
        )
        daily_metric_keys = (
            set(
                self._session.execute(
                    select(
                        content_metric_observations_table.c.content_id,
                        content_metric_observations_table.c.business_date,
                    ).where(
                        tuple_(
                            content_metric_observations_table.c.content_id,
                            content_metric_observations_table.c.business_date,
                        ).in_(tuple((item[0], item[3]) for item in metric_candidates))
                    )
                )
            )
            if metric_candidates
            else set()
        )

        update_values: list[dict[str, Any]] = []
        version_values: list[dict[str, Any]] = []
        metric_values: list[dict[str, Any]] = []
        results: list[PostgresExistingContentBatchItem] = []
        for observation, identity, author_id in zip(
            observations,
            identities,
            author_ids,
            strict=True,
        ):
            current = current_by_identity[identity]
            content_id = cast(UUID, current["id"])
            attempt_id, raw_id = source_by_identity[identity]
            candidate_updates = _content_updates(observation, author_id)
            if "author.external_account_id" in observation.observed_fields and (
                observation.author is None or observation.author.external_account_id is None
            ):
                candidate_updates["author_account_id"] = None
            metric_changed = _content_metric_changed(current, observation)
            current_updates, field_observed_at = _fresh_updates(
                current=current,
                candidate_updates=candidate_updates,
                observed_fields=observation.observed_fields,
                field_columns=_CONTENT_FIELD_COLUMNS,
                observed_at=observation.observed_at,
            )
            accepted_collections: set[str] = set()
            for field_name in collection_fields:
                if field_name not in observation.observed_fields:
                    continue
                accepted, field_observed_at = _accept_freshness_map(
                    field_observed_at,
                    field_name,
                    observation.observed_at,
                )
                if accepted:
                    accepted_collections.add(field_name)
            merged = dict(current)
            merged.update(current_updates)
            business_changed = _business_tuple(
                current, _CONTENT_BUSINESS_COLUMNS
            ) != _business_tuple(merged, _CONTENT_BUSINESS_COLUMNS)
            version_no = int(current["current_version"]) + (1 if business_changed else 0)
            values: dict[str, Any] = {
                "record_id": content_id,
                "first_seen_at": min(current["first_seen_at"], observation.observed_at),
                "last_seen_at": max(current["last_seen_at"], observation.observed_at),
                "updated_at": max(current["updated_at"], observation.observed_at),
                "field_observed_at": field_observed_at,
                "current_version": version_no,
                "replay_visibility_owner_id": replay_visibility_owner_id,
                **current_updates,
            }
            merged.update(values)
            update_values.append(values)
            if business_changed:
                version_values.append(
                    {
                        "id": uuid4(),
                        "content_id": content_id,
                        "version_no": version_no,
                        "content_type": merged["content_type"],
                        "title": merged.get("title"),
                        "text": merged.get("text"),
                        "canonical_url": merged.get("canonical_url"),
                        "share_url": merged.get("share_url"),
                        "author_snapshot": (
                            observation.author.model_dump(mode="json")
                            if observation.author is not None
                            else None
                        ),
                        "published_at": merged.get("published_at"),
                        "source_updated_at": merged.get("source_updated_at"),
                        "status": merged.get("status"),
                        "provider_attempt_id": attempt_id,
                        "raw_artifact_id": raw_id,
                        "observed_at": observation.observed_at,
                    }
                )
            metric_recorded = False
            if (
                any(f"metrics.{name}" in observation.observed_fields for name in _CONTENT_METRICS)
                and (content_id, attempt_id, raw_id) not in source_metric_keys
            ):
                day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
                reason = (
                    "changed"
                    if metric_changed
                    else "daily_checkpoint"
                    if (content_id, day) not in daily_metric_keys
                    else None
                )
                if reason is not None:
                    metric_values.append(
                        {
                            "id": uuid4(),
                            "content_id": content_id,
                            "provider_attempt_id": attempt_id,
                            "raw_artifact_id": raw_id,
                            "reason": reason,
                            "business_date": day,
                            "observation_key": _observation_key(observation, reason),
                            "observed_at": observation.observed_at,
                            **{
                                name: (
                                    getattr(observation.metrics, name)
                                    if f"metrics.{name}" in observation.observed_fields
                                    else None
                                )
                                for name in _CONTENT_METRICS
                            },
                        }
                    )
                    metric_recorded = True
            results.append(
                PostgresExistingContentBatchItem(
                    observation=observation,
                    result=PostgresIngestionResult(
                        content_id,
                        version_no,
                        business_changed,
                        metric_recorded,
                    ),
                    accepted_collection_fields=frozenset(accepted_collections),
                )
            )

        self._execute_grouped_content_updates(update_values)
        for version_chunk in batched(version_values, _MULTI_VALUES_INSERT_ROWS, strict=False):
            self._session.execute(insert(content_versions_table).values(list(version_chunk)))
        for metric_chunk in batched(metric_values, _MULTI_VALUES_INSERT_ROWS, strict=False):
            self._session.execute(
                insert(content_metric_observations_table).values(list(metric_chunk))
            )
        return tuple(results)

    def _upsert_content_authors_batch(
        self,
        observations: tuple[CanonicalContentV1, ...],
    ) -> tuple[UUID | None, ...]:
        """按主 ID 与备用稳定 ID 的连通分量批量收敛账号并应用字段新鲜度。"""

        entries = tuple(
            (index, observation, observation.author)
            for index, observation in enumerate(observations)
            if observation.author is not None and observation.author.external_account_id is not None
        )
        if not entries:
            return tuple(None for _ in observations)

        parent: dict[tuple[str, str, str], tuple[str, str, str]] = {}

        def find(token: tuple[str, str, str]) -> tuple[str, str, str]:
            """查找并压缩当前稳定身份的并查集根。"""

            parent.setdefault(token, token)
            root = token
            while parent[root] != root:
                root = parent[root]
            while parent[token] != token:
                following = parent[token]
                parent[token] = root
                token = following
            return root

        def union(left: tuple[str, str, str], right: tuple[str, str, str]) -> None:
            """合并同一 Canonical 作者声明中的主身份和备用身份。"""

            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        primary_tokens: dict[int, tuple[str, str, str]] = {}
        alternate_tokens: set[tuple[str, str, str]] = set()
        for index, observation, raw_author in entries:
            author = raw_author
            primary = (
                "primary",
                observation.platform,
                cast(str, author.external_account_id),
            )
            primary_tokens[index] = primary
            find(primary)
            if "author.alternate_ids" not in observation.observed_fields:
                continue
            for id_type, external_id in sorted(author.alternate_ids.items()):
                alternate = ("alternate", id_type, external_id)
                alternate_tokens.add(alternate)
                union(primary, alternate)

        primary_keys = tuple((token[1], token[2]) for token in set(primary_tokens.values()))
        alternate_keys = tuple((token[1], token[2]) for token in alternate_tokens)

        def load_identity_accounts() -> dict[tuple[str, str, str], tuple[UUID, str]]:
            """集合读取当前主身份和备用身份绑定的账号。"""

            resolved: dict[tuple[str, str, str], tuple[UUID, str]] = {}
            if primary_keys:
                for row in self._session.execute(
                    select(
                        accounts_table.c.id,
                        accounts_table.c.platform,
                        accounts_table.c.external_account_id,
                    ).where(
                        tuple_(
                            accounts_table.c.platform,
                            accounts_table.c.external_account_id,
                        ).in_(primary_keys)
                    )
                ):
                    resolved[("primary", row.platform, row.external_account_id)] = (
                        cast(UUID, row.id),
                        cast(str, row.platform),
                    )
            if alternate_keys:
                for row in self._session.execute(
                    select(
                        account_external_ids_table.c.id_type,
                        account_external_ids_table.c.external_id,
                        accounts_table.c.id,
                        accounts_table.c.platform,
                    )
                    .select_from(
                        account_external_ids_table.join(
                            accounts_table,
                            accounts_table.c.id == account_external_ids_table.c.account_id,
                        )
                    )
                    .where(
                        tuple_(
                            account_external_ids_table.c.id_type,
                            account_external_ids_table.c.external_id,
                        ).in_(alternate_keys)
                    )
                ):
                    resolved[("alternate", row.id_type, row.external_id)] = (
                        cast(UUID, row.id),
                        cast(str, row.platform),
                    )
            return resolved

        def resolve_components(
            identity_accounts: dict[tuple[str, str, str], tuple[UUID, str]],
        ) -> dict[tuple[str, str, str], UUID]:
            """验证组件只命中一个同平台账号，并返回已有绑定。"""

            account_ids: dict[tuple[str, str, str], set[UUID]] = {}
            account_platforms: dict[tuple[str, str, str], set[str]] = {}
            primary_platforms: dict[tuple[str, str, str], set[str]] = {}
            for token in parent:
                root = find(token)
                if token[0] == "primary":
                    primary_platforms.setdefault(root, set()).add(token[1])
                match = identity_accounts.get(token)
                if match is not None:
                    account_ids.setdefault(root, set()).add(match[0])
                    account_platforms.setdefault(root, set()).add(match[1])
            resolved: dict[tuple[str, str, str], UUID] = {}
            for root, platforms in primary_platforms.items():
                ids = account_ids.get(root, set())
                matched_platforms = account_platforms.get(root, set())
                if len(platforms) != 1 or matched_platforms.difference(platforms):
                    raise ValueError("账号备用稳定 ID 指向不同账号或平台")
                if len(ids) > 1:
                    raise ValueError("账号主 ID 与备用稳定 ID 指向不同账号")
                if ids:
                    resolved[root] = next(iter(ids))
            return resolved

        identity_accounts = load_identity_accounts()
        component_accounts = resolve_components(identity_accounts)
        first_entry_by_component: dict[
            tuple[str, str, str], tuple[int, CanonicalContentV1, CanonicalAuthorV1]
        ] = {}
        for index, observation, raw_author in entries:
            root = find(primary_tokens[index])
            first_entry_by_component.setdefault(
                root,
                (index, observation, raw_author),
            )
        inserts: list[dict[str, Any]] = []
        for root, (_index, observation, author) in first_entry_by_component.items():
            if root in component_accounts:
                continue
            inserts.append(
                {
                    "id": uuid4(),
                    "platform": observation.platform,
                    "external_account_id": author.external_account_id,
                    "first_seen_at": observation.observed_at,
                    "last_seen_at": observation.observed_at,
                    "field_observed_at": _initial_freshness(
                        observation.observed_fields,
                        _ACCOUNT_FIELD_COLUMNS,
                        observation.observed_at,
                    ),
                    "updated_at": observation.observed_at,
                    **_account_candidate_updates(author, observation.observed_fields),
                }
            )
        for chunk in batched(inserts, _MULTI_VALUES_INSERT_ROWS, strict=False):
            self._session.execute(
                pg_insert(accounts_table)
                .values(list(chunk))
                .on_conflict_do_nothing(
                    index_elements=[
                        accounts_table.c.platform,
                        accounts_table.c.external_account_id,
                    ]
                )
            )

        identity_accounts = load_identity_accounts()
        component_accounts = resolve_components(identity_accounts)
        unresolved = set(first_entry_by_component).difference(component_accounts)
        if unresolved:
            raise RuntimeError("账号集合写入后无法读取稳定身份")
        locked_accounts = {
            cast(UUID, row["id"]): dict(row)
            for row in self._session.execute(
                select(accounts_table)
                .where(accounts_table.c.id.in_(tuple(set(component_accounts.values()))))
                .order_by(accounts_table.c.id)
                .with_for_update()
            ).mappings()
        }
        for index, observation, raw_author in entries:
            author = raw_author
            account_id = component_accounts[find(primary_tokens[index])]
            current = locked_accounts[account_id]
            fresh_updates, freshness = _fresh_updates(
                current=current,
                candidate_updates=_account_candidate_updates(
                    author,
                    observation.observed_fields,
                ),
                observed_fields=observation.observed_fields,
                field_columns=_ACCOUNT_FIELD_COLUMNS,
                observed_at=observation.observed_at,
            )
            current.update(fresh_updates)
            current["first_seen_at"] = min(current["first_seen_at"], observation.observed_at)
            current["last_seen_at"] = max(current["last_seen_at"], observation.observed_at)
            current["updated_at"] = max(current["updated_at"], observation.observed_at)
            current["field_observed_at"] = freshness

        update_statement = (
            update(accounts_table)
            .where(accounts_table.c.id == bindparam("_batch_account_id"))
            .values(
                first_seen_at=bindparam("first_seen_at"),
                last_seen_at=bindparam("last_seen_at"),
                updated_at=bindparam("updated_at"),
                field_observed_at=bindparam("field_observed_at"),
                **{column: bindparam(column) for column in _ACCOUNT_COLUMNS},
            )
        )
        self._session.execute(
            update_statement,
            [
                {
                    "_batch_account_id": account_id,
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "updated_at": row["updated_at"],
                    "field_observed_at": row["field_observed_at"],
                    **{column: row[column] for column in _ACCOUNT_COLUMNS},
                }
                for account_id, row in locked_accounts.items()
            ],
        )

        desired_alternates: dict[tuple[UUID, str], str] = {}
        for index, observation, raw_author in entries:
            if "author.alternate_ids" not in observation.observed_fields:
                continue
            author = raw_author
            account_id = component_accounts[find(primary_tokens[index])]
            for id_type, external_id in sorted(author.alternate_ids.items()):
                key = (account_id, id_type)
                previous = desired_alternates.setdefault(key, external_id)
                if previous != external_id:
                    raise ValueError(
                        f"账号稳定外部 ID 冲突: account_id={account_id} id_type={id_type}"
                    )
        existing_alternates = {
            (cast(UUID, row.account_id), cast(str, row.id_type)): cast(str, row.external_id)
            for row in self._session.execute(
                select(account_external_ids_table).where(
                    account_external_ids_table.c.account_id.in_(
                        tuple(set(component_accounts.values()))
                    )
                )
            )
        }
        alternate_inserts: list[dict[str, object]] = []
        for key, external_id in desired_alternates.items():
            persisted_external_id = existing_alternates.get(key)
            if persisted_external_id is not None and persisted_external_id != external_id:
                raise ValueError(f"账号稳定外部 ID 冲突: account_id={key[0]} id_type={key[1]}")
            if persisted_external_id is None:
                alternate_inserts.append(
                    {"account_id": key[0], "id_type": key[1], "external_id": external_id}
                )
        for chunk in batched(alternate_inserts, _MULTI_VALUES_INSERT_ROWS, strict=False):
            self._session.execute(
                pg_insert(account_external_ids_table).values(list(chunk)).on_conflict_do_nothing()
            )
        if desired_alternates:
            persisted = {
                (cast(UUID, row.account_id), cast(str, row.id_type)): cast(str, row.external_id)
                for row in self._session.execute(
                    select(account_external_ids_table).where(
                        tuple_(
                            account_external_ids_table.c.account_id,
                            account_external_ids_table.c.id_type,
                        ).in_(tuple(desired_alternates))
                    )
                )
            }
            if persisted != desired_alternates:
                raise ValueError("账号备用稳定 ID 指向不同账号或平台")

        author_ids: list[UUID | None] = [None] * len(observations)
        for index, _observation, _author in entries:
            author_ids[index] = component_accounts[find(primary_tokens[index])]
        return tuple(author_ids)

    def _execute_grouped_content_updates(self, rows: list[dict[str, Any]]) -> None:
        """按列集合分组 executemany，保持不同 observed_fields 的更新语义。"""

        grouped: dict[frozenset[str], list[dict[str, Any]]] = {}
        for row in rows:
            columns = frozenset(row).difference({"record_id"})
            grouped.setdefault(columns, []).append(row)
        for columns, values in grouped.items():
            statement = (
                update(contents_table)
                .where(contents_table.c.id == bindparam("_batch_content_id"))
                .values({column: bindparam(column) for column in columns})
            )
            self._session.execute(
                statement,
                [
                    {
                        "_batch_content_id": value["record_id"],
                        **{column: value[column] for column in columns},
                    }
                    for value in values
                ],
            )

    def ingest_comment(self, observation: CanonicalCommentV1) -> PostgresIngestionResult:
        attempt_id, raw_id = _source_ids(observation)
        content_id = self._session.execute(
            select(contents_table.c.id).where(
                contents_table.c.platform == observation.platform,
                contents_table.c.external_content_id == observation.external_content_id,
            )
        ).scalar_one()
        author_id = self._upsert_comment_author(observation)
        comment_id = uuid4()
        state = _new_comment_state(comment_id, content_id, observation, author_id)
        created = self._session.execute(
            pg_insert(comments_table)
            .values(**state)
            .on_conflict_do_nothing(
                index_elements=[
                    comments_table.c.content_id,
                    comments_table.c.external_comment_id,
                ]
            )
            .returning(comments_table.c.id)
        ).scalar_one_or_none()
        if created is not None:
            self._append_comment_version(
                comment_id=comment_id,
                version_no=1,
                state=state,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            self._append_comment_metric(
                comment_id=comment_id,
                observation=observation,
                reason="initial",
                attempt_id=attempt_id,
                raw_id=raw_id,
            )
            return PostgresIngestionResult(comment_id, 1, True, True)

        current = dict(
            self._session.execute(
                select(comments_table)
                .where(
                    comments_table.c.content_id == content_id,
                    comments_table.c.external_comment_id == observation.external_comment_id,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        comment_id = cast(UUID, current["id"])
        metric_changed = _comment_metric_changed(current, observation)
        current_updates, field_observed_at = _fresh_updates(
            current=current,
            candidate_updates=_comment_updates(observation, author_id),
            observed_fields=observation.observed_fields,
            field_columns=_COMMENT_FIELD_COLUMNS,
            observed_at=observation.observed_at,
        )
        version_no = int(current["current_version"])
        merged = dict(current)
        merged.update(current_updates)
        business_changed = _business_tuple(current, _COMMENT_BUSINESS_COLUMNS) != _business_tuple(
            merged, _COMMENT_BUSINESS_COLUMNS
        )
        version_no += 1 if business_changed else 0
        updates: dict[str, Any] = {
            "first_seen_at": min(current["first_seen_at"], observation.observed_at),
            "last_seen_at": max(current["last_seen_at"], observation.observed_at),
            "updated_at": max(current["updated_at"], observation.observed_at),
            "field_observed_at": field_observed_at,
            "current_version": version_no,
            **current_updates,
        }
        merged.update(updates)
        self._session.execute(
            update(comments_table).where(comments_table.c.id == comment_id).values(**updates)
        )
        if business_changed:
            self._append_comment_version(
                comment_id=comment_id,
                version_no=version_no,
                state=merged,
                observation=observation,
                attempt_id=attempt_id,
                raw_id=raw_id,
            )

        metric_recorded = False
        has_metric_fields = (
            "metrics.like_count" in observation.observed_fields
            or "metrics.reply_count" in observation.observed_fields
        )
        if has_metric_fields and not self._has_comment_source_metric(
            comment_id, attempt_id, raw_id
        ):
            day = observation.observed_at.astimezone(_BUSINESS_TZ).date()
            if metric_changed:
                reason = "changed"
            elif not self._has_comment_metric_on_day(comment_id, day):
                reason = "daily_checkpoint"
            else:
                reason = None
            if reason is not None:
                self._append_comment_metric(
                    comment_id=comment_id,
                    observation=observation,
                    reason=reason,
                    attempt_id=attempt_id,
                    raw_id=raw_id,
                )
                metric_recorded = True
        return PostgresIngestionResult(
            comment_id,
            version_no,
            business_changed,
            metric_recorded,
        )

    def record_comment_coverage(
        self,
        *,
        content_id: UUID,
        provider_attempt_id: UUID,
        raw_artifact_id: UUID,
        coverage: str,
        reported_total: int | None,
        collected_count: int,
        sample_mode: str,
        sort_mode: str,
        target_count: int | None,
        stop_reason: str,
        observed_at: datetime,
    ) -> UUID:
        """按来源幂等保存一次评论 Coverage；0016 前历史行可保留空扩展字段。"""
        if coverage not in _COVERAGE_VALUES:
            raise ValueError("Comment Coverage 状态非法")
        if reported_total is not None and reported_total < 0:
            raise ValueError("Comment Coverage reported_total 不能为负数")
        if collected_count < 0:
            raise ValueError("Comment Coverage collected_count 不能为负数")
        if target_count is not None and target_count < 0:
            raise ValueError("Comment Coverage target_count 不能为负数")
        if observed_at.utcoffset() is None:
            raise ValueError("Comment Coverage observed_at 必须包含时区")
        if not sample_mode.strip() or not sort_mode.strip() or not stop_reason.strip():
            raise ValueError("Comment Coverage 可观测字段不能为空")
        if coverage in {"not_requested", "unavailable"} and collected_count != 0:
            raise ValueError("未请求/不可用 Coverage 不能包含已采集评论")
        if coverage == "complete" and reported_total is not None:
            if collected_count < reported_total:
                raise ValueError("complete Coverage 的采集数不能小于 Provider 报告总数")

        coverage_id = uuid4()
        values = {
            "id": coverage_id,
            "content_id": content_id,
            "provider_attempt_id": provider_attempt_id,
            "raw_artifact_id": raw_artifact_id,
            "coverage": coverage,
            "reported_total": reported_total,
            "collected_count": collected_count,
            "sample_mode": sample_mode.strip(),
            "sort_mode": sort_mode.strip(),
            "target_count": target_count,
            "stop_reason": stop_reason.strip(),
            "observed_at": observed_at,
        }
        row_id = self._session.execute(
            pg_insert(comment_coverage_observations_table)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[
                    comment_coverage_observations_table.c.content_id,
                    comment_coverage_observations_table.c.provider_attempt_id,
                    comment_coverage_observations_table.c.raw_artifact_id,
                ],
                set_={
                    "coverage": values["coverage"],
                    "reported_total": values["reported_total"],
                    "collected_count": values["collected_count"],
                    "sample_mode": values["sample_mode"],
                    "sort_mode": values["sort_mode"],
                    "target_count": values["target_count"],
                    "stop_reason": values["stop_reason"],
                    "observed_at": values["observed_at"],
                },
            )
            .returning(comment_coverage_observations_table.c.id)
        ).scalar_one()
        return cast(UUID, row_id)

    def _upsert_author(self, observation: CanonicalContentV1) -> UUID | None:
        return self._upsert_account(
            observation.platform,
            observation.author,
            observation.observed_fields,
            observation.observed_at,
        )

    def _upsert_comment_author(self, observation: CanonicalCommentV1) -> UUID | None:
        return self._upsert_account(
            observation.platform,
            observation.author,
            observation.observed_fields,
            observation.observed_at,
        )

    def _upsert_account(
        self,
        platform: str,
        author: CanonicalAuthorV1 | None,
        observed_fields: list[str],
        observed_at: datetime,
    ) -> UUID | None:
        if author is None or author.external_account_id is None:
            return None
        candidate_updates = _account_candidate_updates(author, observed_fields)
        alternate_ids = author.alternate_ids if "author.alternate_ids" in observed_fields else {}
        primary_account_id = self._session.scalar(
            select(accounts_table.c.id).where(
                accounts_table.c.platform == platform,
                accounts_table.c.external_account_id == author.external_account_id,
            )
        )
        alternate_account_id = self._account_id_by_alternate_ids(
            platform=platform,
            alternate_ids=alternate_ids,
        )
        if (
            primary_account_id is not None
            and alternate_account_id is not None
            and primary_account_id != alternate_account_id
        ):
            raise ValueError("账号主 ID 与备用稳定 ID 指向不同账号")

        matched_account_id = primary_account_id or alternate_account_id
        account_id = matched_account_id or uuid4()
        created: UUID | None = None
        if matched_account_id is None:
            created = self._session.execute(
                pg_insert(accounts_table)
                .values(
                    id=account_id,
                    platform=platform,
                    external_account_id=author.external_account_id,
                    first_seen_at=observed_at,
                    last_seen_at=observed_at,
                    field_observed_at=_initial_freshness(
                        observed_fields,
                        _ACCOUNT_FIELD_COLUMNS,
                        observed_at,
                    ),
                    updated_at=observed_at,
                    **candidate_updates,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        accounts_table.c.platform,
                        accounts_table.c.external_account_id,
                    ]
                )
                .returning(accounts_table.c.id)
            ).scalar_one_or_none()
        if created is None:
            if matched_account_id is None:
                concurrent_account_id = self._session.scalar(
                    select(accounts_table.c.id).where(
                        accounts_table.c.platform == platform,
                        accounts_table.c.external_account_id == author.external_account_id,
                    )
                )
                if concurrent_account_id is None:
                    raise RuntimeError("账号并发写入后无法读取稳定身份")
                account_id = concurrent_account_id
            row = dict(
                self._session.execute(
                    select(accounts_table)
                    .where(
                        accounts_table.c.id == account_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            account_id = cast(UUID, row["id"])
            fresh_updates, field_observed_at = _fresh_updates(
                current=row,
                candidate_updates=candidate_updates,
                observed_fields=observed_fields,
                field_columns=_ACCOUNT_FIELD_COLUMNS,
                observed_at=observed_at,
            )
            values: dict[str, Any] = {
                "first_seen_at": min(row["first_seen_at"], observed_at),
                "last_seen_at": max(row["last_seen_at"], observed_at),
                "updated_at": max(row["updated_at"], observed_at),
                "field_observed_at": field_observed_at,
                **fresh_updates,
            }
            self._session.execute(
                update(accounts_table).where(accounts_table.c.id == account_id).values(**values)
            )
        if alternate_ids:
            self._upsert_account_external_ids(account_id, alternate_ids)
        return account_id

    def _account_id_by_alternate_ids(
        self,
        *,
        platform: str,
        alternate_ids: dict[str, str],
    ) -> UUID | None:
        """按任一备用稳定 ID 收敛账号，并拒绝跨账号或跨平台的矛盾线索。"""

        if not alternate_ids:
            return None
        predicates = [
            and_(
                account_external_ids_table.c.id_type == id_type,
                account_external_ids_table.c.external_id == external_id,
            )
            for id_type, external_id in sorted(alternate_ids.items())
        ]
        rows = self._session.execute(
            select(accounts_table.c.id, accounts_table.c.platform)
            .select_from(
                account_external_ids_table.join(
                    accounts_table,
                    accounts_table.c.id == account_external_ids_table.c.account_id,
                )
            )
            .where(or_(*predicates))
        ).all()
        account_ids = {cast(UUID, row.id) for row in rows}
        if len(account_ids) > 1 or any(row.platform != platform for row in rows):
            raise ValueError("账号备用稳定 ID 指向不同账号或平台")
        return next(iter(account_ids), None)

    def _upsert_account_external_ids(
        self,
        account_id: UUID,
        alternate_ids: dict[str, str],
    ) -> None:
        for id_type, external_id in sorted(alternate_ids.items()):
            row = (
                self._session.execute(
                    select(account_external_ids_table).where(
                        account_external_ids_table.c.account_id == account_id,
                        account_external_ids_table.c.id_type == id_type,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                self._session.execute(
                    insert(account_external_ids_table).values(
                        account_id=account_id,
                        id_type=id_type,
                        external_id=external_id,
                    )
                )
            elif row["external_id"] != external_id:
                raise ValueError(f"账号稳定外部 ID 冲突: account_id={account_id} id_type={id_type}")

    def _append_content_version(
        self,
        *,
        content_id: UUID,
        version_no: int,
        state: dict[str, Any],
        observation: CanonicalContentV1,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        self._session.execute(
            insert(content_versions_table).values(
                id=uuid4(),
                content_id=content_id,
                version_no=version_no,
                content_type=state["content_type"],
                title=state.get("title"),
                text=state.get("text"),
                canonical_url=state.get("canonical_url"),
                share_url=state.get("share_url"),
                author_snapshot=(
                    observation.author.model_dump(mode="json")
                    if observation.author is not None
                    else None
                ),
                published_at=state.get("published_at"),
                source_updated_at=state.get("source_updated_at"),
                status=state.get("status"),
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                observed_at=observation.observed_at,
            )
        )

    def _append_content_metric(
        self,
        *,
        content_id: UUID,
        observation: CanonicalContentV1,
        reason: str,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        metrics = {
            name: (
                getattr(observation.metrics, name)
                if f"metrics.{name}" in observation.observed_fields
                else None
            )
            for name in _CONTENT_METRICS
        }
        self._session.execute(
            insert(content_metric_observations_table).values(
                id=uuid4(),
                content_id=content_id,
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                reason=reason,
                business_date=observation.observed_at.astimezone(_BUSINESS_TZ).date(),
                observation_key=_observation_key(observation, reason),
                observed_at=observation.observed_at,
                **metrics,
            )
        )

    def _append_comment_version(
        self,
        *,
        comment_id: UUID,
        version_no: int,
        state: dict[str, Any],
        observation: CanonicalCommentV1,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        self._session.execute(
            insert(comment_versions_table).values(
                id=uuid4(),
                comment_id=comment_id,
                version_no=version_no,
                root_comment_id=state.get("root_comment_id"),
                parent_comment_id=state.get("parent_comment_id"),
                text=state.get("text"),
                author_snapshot=(
                    observation.author.model_dump(mode="json")
                    if observation.author is not None
                    else None
                ),
                published_at=state.get("published_at"),
                source_updated_at=state.get("source_updated_at"),
                status=state.get("status"),
                is_by_content_author=state.get("is_by_content_author"),
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                observed_at=observation.observed_at,
            )
        )

    def _append_comment_metric(
        self,
        *,
        comment_id: UUID,
        observation: CanonicalCommentV1,
        reason: str,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> None:
        self._session.execute(
            insert(comment_metric_observations_table).values(
                id=uuid4(),
                comment_id=comment_id,
                provider_attempt_id=attempt_id,
                raw_artifact_id=raw_id,
                reason=reason,
                business_date=observation.observed_at.astimezone(_BUSINESS_TZ).date(),
                observation_key=_observation_key(observation, reason),
                like_count=(
                    observation.metrics.like_count
                    if "metrics.like_count" in observation.observed_fields
                    else None
                ),
                reply_count=(
                    observation.metrics.reply_count
                    if "metrics.reply_count" in observation.observed_fields
                    else None
                ),
                observed_at=observation.observed_at,
            )
        )

    def _has_content_source_metric(
        self,
        content_id: UUID,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> bool:
        return (
            self._session.execute(
                select(content_metric_observations_table.c.id).where(
                    content_metric_observations_table.c.content_id == content_id,
                    content_metric_observations_table.c.provider_attempt_id == attempt_id,
                    content_metric_observations_table.c.raw_artifact_id == raw_id,
                )
            ).first()
            is not None
        )

    def _has_comment_source_metric(
        self,
        comment_id: UUID,
        attempt_id: UUID,
        raw_id: UUID,
    ) -> bool:
        return (
            self._session.execute(
                select(comment_metric_observations_table.c.id).where(
                    comment_metric_observations_table.c.comment_id == comment_id,
                    comment_metric_observations_table.c.provider_attempt_id == attempt_id,
                    comment_metric_observations_table.c.raw_artifact_id == raw_id,
                )
            ).first()
            is not None
        )

    def _has_content_metric_on_day(self, content_id: UUID, day: date) -> bool:
        return (
            self._session.execute(
                select(content_metric_observations_table.c.id).where(
                    content_metric_observations_table.c.content_id == content_id,
                    content_metric_observations_table.c.business_date == day,
                )
            ).first()
            is not None
        )

    def _has_comment_metric_on_day(self, comment_id: UUID, day: date) -> bool:
        return (
            self._session.execute(
                select(comment_metric_observations_table.c.id).where(
                    comment_metric_observations_table.c.comment_id == comment_id,
                    comment_metric_observations_table.c.business_date == day,
                )
            ).first()
            is not None
        )


def _source_ids(
    observation: CanonicalContentV1 | CanonicalCommentV1,
) -> tuple[UUID, UUID]:
    if observation.source.provider_attempt_id is None or observation.source.raw_artifact_id is None:
        raise ValueError("持久化 Canonical 必须包含 provider_attempt_id 与 raw_artifact_id")
    return UUID(observation.source.provider_attempt_id), observation.source.raw_artifact_id


def _account_candidate_updates(
    author: CanonicalAuthorV1,
    observed_fields: list[str],
) -> dict[str, Any]:
    """把 Canonical Author 的已观测字段转换成 Account Current 列。"""

    author_values = {
        "display_name": author.display_name,
        "handle": author.handle,
        "profile_url": str(author.profile_url) if author.profile_url else None,
        "avatar_url": str(author.avatar_url) if author.avatar_url else None,
        "bio": author.bio,
        "verified": author.verified,
        "verification_label": author.verification_label,
        "region": author.region,
        "follower_count": author.follower_count,
        "following_count": author.following_count,
        "content_count": author.content_count,
        "total_like_count": author.total_like_count,
    }
    return {
        _ACCOUNT_FIELD_COLUMNS[path]: author_values[path.removeprefix("author.")]
        for path in _ACCOUNT_FIELD_COLUMNS
        if path in observed_fields
    }


def _new_content_state(
    content_id: UUID,
    observation: CanonicalContentV1,
    author_id: UUID | None,
    *,
    collection_fields: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "id": content_id,
        "platform": observation.platform,
        "external_content_id": observation.external_content_id,
        "content_type": observation.content_type,
        "author_account_id": author_id,
        "first_seen_at": observation.observed_at,
        "last_seen_at": observation.observed_at,
        "current_version": 1,
        "field_observed_at": {
            **_initial_freshness(
                observation.observed_fields,
                _CONTENT_FIELD_COLUMNS,
                observation.observed_at,
            ),
            **{
                field: observation.observed_at.isoformat()
                for field in collection_fields
                if field in observation.observed_fields
            },
        },
        "updated_at": observation.observed_at,
    }
    state.update(_content_updates(observation, author_id))
    return state


def _content_updates(
    observation: CanonicalContentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if "content_type" in observation.observed_fields:
        updates["content_type"] = observation.content_type
    values = {
        "title": observation.title,
        "text": observation.text,
        "canonical_url": (str(observation.canonical_url) if observation.canonical_url else None),
        "share_url": str(observation.share_url) if observation.share_url else None,
        "published_at": observation.published_at,
        "source_updated_at": observation.source_updated_at,
        "status": observation.status,
    }
    for path, value in values.items():
        if path in observation.observed_fields:
            updates[path] = value
    if (
        observation.author is not None
        and author_id is not None
        and "author.external_account_id" in observation.observed_fields
    ):
        updates["author_account_id"] = author_id
    for name in _CONTENT_METRICS:
        if f"metrics.{name}" in observation.observed_fields:
            updates[f"current_{name}"] = getattr(observation.metrics, name)
    return updates


def _new_comment_state(
    comment_id: UUID,
    content_id: UUID,
    observation: CanonicalCommentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "id": comment_id,
        "content_id": content_id,
        "external_comment_id": observation.external_comment_id,
        "root_comment_id": observation.root_comment_id,
        "parent_comment_id": observation.parent_comment_id,
        "author_account_id": author_id,
        "first_seen_at": observation.observed_at,
        "last_seen_at": observation.observed_at,
        "current_version": 1,
        "field_observed_at": _initial_freshness(
            observation.observed_fields,
            _COMMENT_FIELD_COLUMNS,
            observation.observed_at,
        ),
        "updated_at": observation.observed_at,
    }
    state.update(_comment_updates(observation, author_id))
    return state


def _comment_updates(
    observation: CanonicalCommentV1,
    author_id: UUID | None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    values = {
        "root_comment_id": observation.root_comment_id,
        "parent_comment_id": observation.parent_comment_id,
        "text": observation.text,
        "published_at": observation.published_at,
        "source_updated_at": observation.source_updated_at,
        "status": observation.status,
        "is_by_content_author": observation.is_by_content_author,
    }
    for path, value in values.items():
        if path in observation.observed_fields:
            updates[path] = value
    if (
        observation.author is not None
        and author_id is not None
        and "author.external_account_id" in observation.observed_fields
    ):
        updates["author_account_id"] = author_id
    if "metrics.like_count" in observation.observed_fields:
        updates["current_like_count"] = observation.metrics.like_count
    if "metrics.reply_count" in observation.observed_fields:
        updates["current_reply_count"] = observation.metrics.reply_count
    return updates


def _initial_freshness(
    observed_fields: list[str],
    field_columns: dict[str, str],
    observed_at: datetime,
) -> dict[str, str]:
    return {field: observed_at.isoformat() for field in observed_fields if field in field_columns}


def _fresh_updates(
    *,
    current: dict[str, Any],
    candidate_updates: dict[str, Any],
    observed_fields: list[str],
    field_columns: dict[str, str],
    observed_at: datetime,
) -> tuple[dict[str, Any], dict[str, str]]:
    raw_freshness = current.get("field_observed_at") or {}
    if not isinstance(raw_freshness, dict):
        raise ValueError("Current field_observed_at 必须是对象")
    freshness = {str(key): str(value) for key, value in raw_freshness.items()}
    accepted: dict[str, Any] = {}
    for field in observed_fields:
        column = field_columns.get(field)
        if column is None or column not in candidate_updates:
            continue
        previous_raw = freshness.get(field)
        if previous_raw is not None:
            previous_at = datetime.fromisoformat(previous_raw)
            if previous_at.utcoffset() is None:
                raise ValueError("Current field_observed_at 必须包含时区")
            if observed_at < previous_at:
                continue
        accepted[column] = candidate_updates[column]
        freshness[field] = observed_at.isoformat()
    return accepted, freshness


def _accept_freshness_map(
    freshness: dict[str, str],
    field_name: str,
    observed_at: datetime,
) -> tuple[bool, dict[str, str]]:
    """在内存投影上应用与单行 Collection freshness 相同的判定。"""

    updated = dict(freshness)
    previous_raw = updated.get(field_name)
    if previous_raw is not None:
        previous_at = datetime.fromisoformat(previous_raw)
        if previous_at.utcoffset() is None:
            raise ValueError("Current field_observed_at 必须包含时区")
        if observed_at < previous_at:
            return False, updated
    updated[field_name] = observed_at.isoformat()
    return True, updated


def _content_metric_changed(current: dict[str, Any], observation: CanonicalContentV1) -> bool:
    return any(
        f"metrics.{name}" in observation.observed_fields
        and current.get(f"current_{name}") != getattr(observation.metrics, name)
        for name in _CONTENT_METRICS
    )


def _comment_metric_changed(current: dict[str, Any], observation: CanonicalCommentV1) -> bool:
    return (
        "metrics.like_count" in observation.observed_fields
        and current.get("current_like_count") != observation.metrics.like_count
    ) or (
        "metrics.reply_count" in observation.observed_fields
        and current.get("current_reply_count") != observation.metrics.reply_count
    )


def _business_tuple(row: dict[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(name) for name in columns)


def _observation_key(
    observation: CanonicalContentV1 | CanonicalCommentV1,
    reason: str,
) -> str:
    payload = {
        "attempt": observation.source.provider_attempt_id,
        "raw": str(observation.source.raw_artifact_id),
        "locator": observation.source.item_locator,
        "observed_at": observation.observed_at.isoformat(),
        "reason": reason,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
