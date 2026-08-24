from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Runtime: stable Content identity stays unchanged; provider calls use typed alternate ids.
runtime = "backend/src/aima_ugc/adapters/providers/tikhub/runtime.py"
replace_once(
    runtime,
    'def build_detail_call(platform: TikHubPlatform, content: CanonicalContentV1) -> TikHubOperationCall:\n',
    '''def _provider_lookup_identity(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    alternate_ids: dict[str, str] | None = None,\n) -> tuple[str, str]:\n    """选择 TikHub Detail/Comments 实际需要的 typed locator。\n\n    ``external_content_id`` 始终是 Canonical/数据库稳定身份；这里只决定外部 Provider\n    请求参数。Excel/TikHub Mapper 已确认的 typed identity 优先，缺失时兼容旧稳定 ID。\n    """\n    ids = alternate_ids or {}\n    if platform == "xiaohongshu":\n        return "note_id", ids.get("note_id", external_content_id)\n    if platform == "douyin":\n        return "aweme_id", ids.get("aweme_id", external_content_id)\n    if platform == "weibo":\n        return "status_id", ids.get("status_id", external_content_id)\n    if platform == "bilibili":\n        av_id = ids.get("av_id")\n        if av_id:\n            return "av_id", av_id.removeprefix("av").removeprefix("AV")\n        bv_id = ids.get("bv_id")\n        if bv_id:\n            return "bv_id", bv_id\n        if external_content_id.casefold().startswith("bv"):\n            return "bv_id", external_content_id\n        return "av_id", external_content_id.removeprefix("av").removeprefix("AV")\n    return "photo_id", ids.get("photo_id", external_content_id)\n\n\ndef build_detail_call(platform: TikHubPlatform, content: CanonicalContentV1) -> TikHubOperationCall:\n    id_type, lookup_value = _provider_lookup_identity(\n        platform=platform,\n        external_content_id=content.external_content_id,\n        alternate_ids=content.alternate_ids,\n    )\n''',
)
replace_once(runtime, 'note_id=content.external_content_id\n', 'note_id=lookup_value\n')
replace_once(runtime, 'note_id=content.external_content_id\n', 'note_id=lookup_value\n')
replace_once(runtime, 'douyin.build_video_detail_request(aweme_id=content.external_content_id)', 'douyin.build_video_detail_request(aweme_id=lookup_value)')
replace_once(runtime, 'weibo.build_status_detail_request(status_id=content.external_content_id)', 'weibo.build_status_detail_request(status_id=lookup_value)')
replace_once(
    runtime,
    '        bilibili_request = bilibili.build_video_detail_request(av_id=content.external_content_id)\n',
    '        bilibili_request = bilibili.build_video_detail_request(**{id_type: lookup_value})\n',
)
replace_once(runtime, 'kuaishou.build_video_detail_request(photo_id=content.external_content_id)', 'kuaishou.build_video_detail_request(photo_id=lookup_value)')

replace_once(
    runtime,
    '''def build_comments_call(\n    *, platform: TikHubPlatform, external_content_id: str, state: dict[str, object] | None = None\n) -> TikHubOperationCall:\n    paging = state or {}\n''',
    '''def build_comments_call(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    alternate_ids: dict[str, str] | None = None,\n    state: dict[str, object] | None = None,\n) -> TikHubOperationCall:\n    paging = state or {}\n    id_type, lookup_value = _provider_lookup_identity(\n        platform=platform,\n        external_content_id=external_content_id,\n        alternate_ids=alternate_ids,\n    )\n''',
)
replace_once(runtime, '            note_id=external_content_id,\n', '            note_id=lookup_value,\n')
replace_once(runtime, '            aweme_id=external_content_id,\n', '            aweme_id=lookup_value,\n')
replace_once(runtime, '            status_id=external_content_id,\n', '            status_id=lookup_value,\n')
replace_once(
    runtime,
    '        bilibili_request = bilibili.build_video_comments_request(\n            av_id=external_content_id,\n',
    '        bilibili_request = bilibili.build_video_comments_request(\n            **{id_type: lookup_value},\n',
)
replace_once(runtime, '        photo_id=external_content_id,\n', '        photo_id=lookup_value,\n')

replace_once(
    runtime,
    '''def build_sub_comments_call(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    root_comment_id: str,\n    state: dict[str, object] | None = None,\n) -> TikHubOperationCall:\n    """构造当前正式二级回复主 Operation；不做任何 App/Web 自动 fallback。"""\n    paging = state or {}\n''',
    '''def build_sub_comments_call(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    root_comment_id: str,\n    alternate_ids: dict[str, str] | None = None,\n    state: dict[str, object] | None = None,\n) -> TikHubOperationCall:\n    """构造当前正式二级回复主 Operation；不做任何 App/Web 自动 fallback。"""\n    paging = state or {}\n    id_type, lookup_value = _provider_lookup_identity(\n        platform=platform,\n        external_content_id=external_content_id,\n        alternate_ids=alternate_ids,\n    )\n''',
)
replace_once(runtime, '            note_id=external_content_id,\n            comment_id=root_comment_id,', '            note_id=lookup_value,\n            comment_id=root_comment_id,')
replace_once(runtime, '            item_id=external_content_id,\n            comment_id=root_comment_id,', '            item_id=lookup_value,\n            comment_id=root_comment_id,')
replace_once(
    runtime,
    '        bilibili_request = bilibili.build_reply_detail_request(\n            root=root_comment_id,\n            av_id=external_content_id,\n',
    '        bilibili_request = bilibili.build_reply_detail_request(\n            root=root_comment_id,\n            **{id_type: lookup_value},\n',
)
replace_once(runtime, '        photo_id=external_content_id,\n        root_comment_id=root_comment_id,', '        photo_id=lookup_value,\n        root_comment_id=root_comment_id,')

# 2) Batch target: a verified typed lookup no longer needs to equal stable external_content_id.
targets = "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py"
replace_once(
    targets,
    '''    stable_lookup = _legacy_tikhub_lookup(\n        platform=platform,\n        external_content_id=external_content_id,\n    )\n    for id_type in _LOOKUP_ID_PRIORITY[platform]:\n        value = alternate_ids.get(id_type)\n        if value and stable_lookup == (id_type, value):\n            return id_type, value\n    if not has_tikhub_source:\n        return None\n    return stable_lookup\n''',
    '''    for id_type in _LOOKUP_ID_PRIORITY[platform]:\n        value = alternate_ids.get(id_type)\n        if value:\n            return id_type, value\n    if not has_tikhub_source:\n        return None\n    return _legacy_tikhub_lookup(\n        platform=platform,\n        external_content_id=external_content_id,\n    )\n''',
)

# 3) Enrichment carries persisted typed identities into Detail/Comments/SubComments.
scope = "backend/src/aima_ugc/bootstrap/collection_scope.py"
replace_once(
    scope,
    '''            seed = CanonicalContentV1(\n                platform=target.platform,\n                external_content_id=target.external_content_id,\n                content_type=target.content_type,\n                observed_at=self._observed_at(),\n                observed_fields=["content_type"],\n''',
    '''            seed = CanonicalContentV1(\n                platform=target.platform,\n                external_content_id=target.external_content_id,\n                alternate_ids=target.alternate_ids,\n                content_type=target.content_type,\n                observed_at=self._observed_at(),\n                observed_fields=["content_type", "alternate_ids"],\n''',
)
replace_once(
    scope,
    '''            call = build_comments_call(\n                platform=platform,\n                external_content_id=content.external_content_id,\n                state=pagination_state,\n            )\n''',
    '''            call = build_comments_call(\n                platform=platform,\n                external_content_id=content.external_content_id,\n                alternate_ids=content.alternate_ids,\n                state=pagination_state,\n            )\n''',
)
replace_once(
    scope,
    '''                    reply_outcome = self._fetch_sub_comments(\n                        run=run,\n                        scope=scope,\n                        content_id=content_id,\n                        root_comment=comment,\n''',
    '''                    reply_outcome = self._fetch_sub_comments(\n                        run=run,\n                        scope=scope,\n                        content=content,\n                        content_id=content_id,\n                        root_comment=comment,\n''',
)
replace_once(
    scope,
    '''    def _fetch_sub_comments(\n        self,\n        *,\n        run: CollectionRunRecord,\n        scope: CollectionScopeRecord,\n        content_id: UUID,\n''',
    '''    def _fetch_sub_comments(\n        self,\n        *,\n        run: CollectionRunRecord,\n        scope: CollectionScopeRecord,\n        content: CanonicalContentV1,\n        content_id: UUID,\n''',
)
replace_once(
    scope,
    '''            call = build_sub_comments_call(\n                platform=platform,\n                external_content_id=root_comment.external_content_id,\n                root_comment_id=root_comment.external_comment_id,\n                state=pagination_state,\n            )\n''',
    '''            call = build_sub_comments_call(\n                platform=platform,\n                external_content_id=content.external_content_id,\n                root_comment_id=root_comment.external_comment_id,\n                alternate_ids=content.alternate_ids,\n                state=pagination_state,\n            )\n''',
)

# 4) alternate_ids is an identity set: merge by id_type instead of deleting ids from other sources.
complete = "backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py"
replace_once(
    complete,
    '''            self._session.execute(delete(table).where(table.c.content_id == content_id))\n            rows = _content_extension_rows(\n                field_name,\n                content_id,\n                observation,\n                attempt_id=attempt_id,\n                raw_id=raw_id,\n            )\n            if rows:\n                self._session.execute(insert(table).values(rows))\n''',
    '''            rows = _content_extension_rows(\n                field_name,\n                content_id,\n                observation,\n                attempt_id=attempt_id,\n                raw_id=raw_id,\n            )\n            if field_name == "alternate_ids":\n                for row in rows:\n                    statement = pg_insert(table).values(**row)\n                    self._session.execute(\n                        statement.on_conflict_do_update(\n                            index_elements=[table.c.content_id, table.c.id_type],\n                            set_={\n                                "external_id": statement.excluded.external_id,\n                                "provider_attempt_id": statement.excluded.provider_attempt_id,\n                                "raw_artifact_id": statement.excluded.raw_artifact_id,\n                                "observed_at": statement.excluded.observed_at,\n                            },\n                        )\n                    )\n                continue\n            self._session.execute(delete(table).where(table.c.content_id == content_id))\n            if rows:\n                self._session.execute(insert(table).values(rows))\n''',
)

# 5) Existing integration expectation migrates from fail-closed to typed-locator eligibility.
eligibility = "tests/integration/collection/test_collection_supplement_target_eligibility.py"
replace_once(
    eligibility,
    'def test_typed_lookup_that_does_not_match_stable_content_identity_is_not_eligible(\n',
    'def test_typed_lookup_that_does_not_match_stable_content_identity_is_eligible(\n',
)
replace_once(
    eligibility,
    '''    targets = _read_targets(runtime, batch_id=batch_id, identity=_CURRENT_ANALYSIS_IDENTITY)\n\n    assert [target.content_id for target in targets] == [eligible_id]\n\n\ndef test_stale_irrelevant_analysis_does_not_block_supplement_target''',
    '''    targets = _read_targets(runtime, batch_id=batch_id, identity=_CURRENT_ANALYSIS_IDENTITY)\n\n    assert [target.content_id for target in targets] == [eligible_id, mismatched_id]\n    mismatched = next(target for target in targets if target.content_id == mismatched_id)\n    assert mismatched.lookup_id_type == "note_id"\n    assert mismatched.lookup_value == "real-provider-note-id"\n\n\ndef test_stale_irrelevant_analysis_does_not_block_supplement_target''',
)

print("identity alignment patch applied")
