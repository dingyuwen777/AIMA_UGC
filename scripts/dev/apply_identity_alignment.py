from __future__ import annotations

from pathlib import Path


def replace_exact(path: str, old: str, new: str, *, expected: int = 1) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} matches, got {count}")
    file_path.write_text(text.replace(old, new, expected), encoding="utf-8")


# 1) Runtime: stable Content identity stays unchanged; provider calls use typed alternate ids.
runtime = "backend/src/aima_ugc/adapters/providers/tikhub/runtime.py"
replace_exact(
    runtime,
    "def build_detail_call(platform: TikHubPlatform, content: CanonicalContentV1) -> TikHubOperationCall:\n",
    '''def _provider_lookup_identity(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    alternate_ids: dict[str, str] | None = None,\n) -> tuple[str, str]:\n    """选择 TikHub Detail/Comments 实际需要的 typed locator。\n\n    ``external_content_id`` 始终是 Canonical/数据库稳定身份；这里只决定外部 Provider\n    请求参数。Excel/TikHub Mapper 已确认的 typed identity 优先，缺失时兼容旧稳定 ID。\n    """\n    ids = alternate_ids or {}\n    if platform == "xiaohongshu":\n        return "note_id", ids.get("note_id", external_content_id)\n    if platform == "douyin":\n        return "aweme_id", ids.get("aweme_id", external_content_id)\n    if platform == "weibo":\n        return "status_id", ids.get("status_id", external_content_id)\n    if platform == "bilibili":\n        av_id = ids.get("av_id")\n        if av_id:\n            return "av_id", av_id[2:] if av_id[:2].casefold() == "av" else av_id\n        bv_id = ids.get("bv_id")\n        if bv_id:\n            return "bv_id", bv_id\n        if external_content_id.casefold().startswith("bv"):\n            return "bv_id", external_content_id\n        return (\n            "av_id",\n            external_content_id[2:]\n            if external_content_id[:2].casefold() == "av"\n            else external_content_id,\n        )\n    return "photo_id", ids.get("photo_id", external_content_id)\n\n\ndef build_detail_call(platform: TikHubPlatform, content: CanonicalContentV1) -> TikHubOperationCall:\n    id_type, lookup_value = _provider_lookup_identity(\n        platform=platform,\n        external_content_id=content.external_content_id,\n        alternate_ids=content.alternate_ids,\n    )\n''',
)
replace_exact(
    runtime,
    "note_id=content.external_content_id\n",
    "note_id=lookup_value\n",
    expected=2,
)
replace_exact(
    runtime,
    "douyin.build_video_detail_request(aweme_id=content.external_content_id)",
    "douyin.build_video_detail_request(aweme_id=lookup_value)",
)
replace_exact(
    runtime,
    "weibo.build_status_detail_request(status_id=content.external_content_id)",
    "weibo.build_status_detail_request(status_id=lookup_value)",
)
replace_exact(
    runtime,
    "        bilibili_request = bilibili.build_video_detail_request(av_id=content.external_content_id)\n",
    "        bilibili_request = bilibili.build_video_detail_request(**{id_type: lookup_value})\n",
)
replace_exact(
    runtime,
    "kuaishou.build_video_detail_request(photo_id=content.external_content_id)",
    "kuaishou.build_video_detail_request(photo_id=lookup_value)",
)

replace_exact(
    runtime,
    '''def build_comments_call(\n    *, platform: TikHubPlatform, external_content_id: str, state: dict[str, object] | None = None\n) -> TikHubOperationCall:\n    paging = state or {}\n''',
    '''def build_comments_call(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    alternate_ids: dict[str, str] | None = None,\n    state: dict[str, object] | None = None,\n) -> TikHubOperationCall:\n    paging = state or {}\n    id_type, lookup_value = _provider_lookup_identity(\n        platform=platform,\n        external_content_id=external_content_id,\n        alternate_ids=alternate_ids,\n    )\n''',
)
replace_exact(
    runtime,
    '''        xiaohongshu_request = xiaohongshu.build_note_comments_request(\n            note_id=external_content_id,\n            cursor=_str_state(paging, "cursor", default=""),\n''',
    '''        xiaohongshu_request = xiaohongshu.build_note_comments_request(\n            note_id=lookup_value,\n            cursor=_str_state(paging, "cursor", default=""),\n''',
)
replace_exact(
    runtime,
    '''        douyin_request = douyin.build_video_comments_request(\n            aweme_id=external_content_id,\n            cursor=_int_state(paging, "cursor", default=0),\n''',
    '''        douyin_request = douyin.build_video_comments_request(\n            aweme_id=lookup_value,\n            cursor=_int_state(paging, "cursor", default=0),\n''',
)
replace_exact(
    runtime,
    '''        weibo_request = weibo.build_status_comments_request(\n            status_id=external_content_id,\n            max_id=_optional_str_state(paging, "max_id"),\n''',
    '''        weibo_request = weibo.build_status_comments_request(\n            status_id=lookup_value,\n            max_id=_optional_str_state(paging, "max_id"),\n''',
)
replace_exact(
    runtime,
    '''        bilibili_request = bilibili.build_video_comments_request(\n            av_id=external_content_id,\n            sort_mode="latest",\n''',
    '''        bilibili_request = bilibili.build_video_comments_request(\n            **{id_type: lookup_value},\n            sort_mode="latest",\n''',
)
replace_exact(
    runtime,
    '''    kuaishou_request = kuaishou.build_video_comments_request(\n        photo_id=external_content_id,\n        pcursor=_str_state(paging, "pcursor", default=""),\n''',
    '''    kuaishou_request = kuaishou.build_video_comments_request(\n        photo_id=lookup_value,\n        pcursor=_str_state(paging, "pcursor", default=""),\n''',
)

replace_exact(
    runtime,
    '''def build_sub_comments_call(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    root_comment_id: str,\n    state: dict[str, object] | None = None,\n) -> TikHubOperationCall:\n    """构造当前正式二级回复主 Operation；不做任何 App/Web 自动 fallback。"""\n    paging = state or {}\n''',
    '''def build_sub_comments_call(\n    *,\n    platform: TikHubPlatform,\n    external_content_id: str,\n    root_comment_id: str,\n    alternate_ids: dict[str, str] | None = None,\n    state: dict[str, object] | None = None,\n) -> TikHubOperationCall:\n    """构造当前正式二级回复主 Operation；不做任何 App/Web 自动 fallback。"""\n    paging = state or {}\n    id_type, lookup_value = _provider_lookup_identity(\n        platform=platform,\n        external_content_id=external_content_id,\n        alternate_ids=alternate_ids,\n    )\n''',
)
replace_exact(
    runtime,
    '''        xiaohongshu_request = xiaohongshu.build_sub_comments_request(\n            note_id=external_content_id,\n            comment_id=root_comment_id,\n''',
    '''        xiaohongshu_request = xiaohongshu.build_sub_comments_request(\n            note_id=lookup_value,\n            comment_id=root_comment_id,\n''',
)
replace_exact(
    runtime,
    '''        douyin_request = douyin.build_video_comment_replies_request(\n            item_id=external_content_id,\n            comment_id=root_comment_id,\n''',
    '''        douyin_request = douyin.build_video_comment_replies_request(\n            item_id=lookup_value,\n            comment_id=root_comment_id,\n''',
)
replace_exact(
    runtime,
    '''        bilibili_request = bilibili.build_reply_detail_request(\n            root=root_comment_id,\n            av_id=external_content_id,\n''',
    '''        bilibili_request = bilibili.build_reply_detail_request(\n            root=root_comment_id,\n            **{id_type: lookup_value},\n''',
)
replace_exact(
    runtime,
    '''    kuaishou_request = kuaishou.build_video_sub_comments_request(\n        photo_id=external_content_id,\n        root_comment_id=root_comment_id,\n''',
    '''    kuaishou_request = kuaishou.build_video_sub_comments_request(\n        photo_id=lookup_value,\n        root_comment_id=root_comment_id,\n''',
)

# 2) Batch target: a verified typed lookup no longer needs to equal stable external_content_id.
targets = "backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py"
replace_exact(
    targets,
    '''    stable_lookup = _legacy_tikhub_lookup(\n        platform=platform,\n        external_content_id=external_content_id,\n    )\n    for id_type in _LOOKUP_ID_PRIORITY[platform]:\n        value = alternate_ids.get(id_type)\n        if value and stable_lookup == (id_type, value):\n            return id_type, value\n    if not has_tikhub_source:\n        return None\n    return stable_lookup\n''',
    '''    for id_type in _LOOKUP_ID_PRIORITY[platform]:\n        value = alternate_ids.get(id_type)\n        if value:\n            return id_type, value\n    if not has_tikhub_source:\n        return None\n    return _legacy_tikhub_lookup(\n        platform=platform,\n        external_content_id=external_content_id,\n    )\n''',
)

# 3) Enrichment carries persisted typed identities into Detail/Comments/SubComments.
scope = "backend/src/aima_ugc/bootstrap/collection_scope.py"
replace_exact(
    scope,
    '''            seed = CanonicalContentV1(\n                platform=target.platform,\n                external_content_id=target.external_content_id,\n                content_type=target.content_type,\n                observed_at=self._observed_at(),\n                observed_fields=["content_type"],\n''',
    '''            seed = CanonicalContentV1(\n                platform=target.platform,\n                external_content_id=target.external_content_id,\n                alternate_ids=target.alternate_ids,\n                content_type=target.content_type,\n                observed_at=self._observed_at(),\n                observed_fields=["content_type", "alternate_ids"],\n''',
)
replace_exact(
    scope,
    '''            call = build_comments_call(\n                platform=platform,\n                external_content_id=content.external_content_id,\n                state=pagination_state,\n            )\n''',
    '''            call = build_comments_call(\n                platform=platform,\n                external_content_id=content.external_content_id,\n                alternate_ids=content.alternate_ids,\n                state=pagination_state,\n            )\n''',
)
replace_exact(
    scope,
    '''                    reply_outcome = self._fetch_sub_comments(\n                        run=run,\n                        scope=scope,\n                        content_id=content_id,\n                        root_comment=comment,\n''',
    '''                    reply_outcome = self._fetch_sub_comments(\n                        run=run,\n                        scope=scope,\n                        content=content,\n                        content_id=content_id,\n                        root_comment=comment,\n''',
)
replace_exact(
    scope,
    '''    def _fetch_sub_comments(\n        self,\n        *,\n        run: CollectionRunRecord,\n        scope: CollectionScopeRecord,\n        content_id: UUID,\n''',
    '''    def _fetch_sub_comments(\n        self,\n        *,\n        run: CollectionRunRecord,\n        scope: CollectionScopeRecord,\n        content: CanonicalContentV1,\n        content_id: UUID,\n''',
)
replace_exact(
    scope,
    '''            call = build_sub_comments_call(\n                platform=platform,\n                external_content_id=root_comment.external_content_id,\n                root_comment_id=root_comment.external_comment_id,\n                state=pagination_state,\n            )\n''',
    '''            call = build_sub_comments_call(\n                platform=platform,\n                external_content_id=content.external_content_id,\n                root_comment_id=root_comment.external_comment_id,\n                alternate_ids=content.alternate_ids,\n                state=pagination_state,\n            )\n''',
)

# 4) alternate_ids is an identity set: merge by id_type; older observations may add a missing id,
#    but may not overwrite a newer value of the same id_type.
complete = "backend/src/aima_ugc/adapters/persistence/postgres/content_complete.py"
replace_exact(
    complete,
    '''            if not _claim_collection_freshness(\n                self._session,\n                parent_table=contents_table,\n                parent_id=content_id,\n                field_name=field_name,\n                observed_at=observation.observed_at,\n            ):\n                continue\n            self._session.execute(delete(table).where(table.c.content_id == content_id))\n            rows = _content_extension_rows(\n                field_name,\n                content_id,\n                observation,\n                attempt_id=attempt_id,\n                raw_id=raw_id,\n            )\n            if rows:\n                self._session.execute(insert(table).values(rows))\n''',
    '''            if field_name == "alternate_ids":\n                # 父级 freshness 只记录最近观察时刻，不阻止较旧来源补充此前缺失的 id_type。\n                _claim_collection_freshness(\n                    self._session,\n                    parent_table=contents_table,\n                    parent_id=content_id,\n                    field_name=field_name,\n                    observed_at=observation.observed_at,\n                )\n                rows = _content_extension_rows(\n                    field_name,\n                    content_id,\n                    observation,\n                    attempt_id=attempt_id,\n                    raw_id=raw_id,\n                )\n                for row in rows:\n                    statement = pg_insert(table).values(**row)\n                    self._session.execute(\n                        statement.on_conflict_do_update(\n                            index_elements=[table.c.content_id, table.c.id_type],\n                            set_={\n                                "external_id": statement.excluded.external_id,\n                                "provider_attempt_id": statement.excluded.provider_attempt_id,\n                                "raw_artifact_id": statement.excluded.raw_artifact_id,\n                                "observed_at": statement.excluded.observed_at,\n                            },\n                            where=table.c.observed_at <= statement.excluded.observed_at,\n                        )\n                    )\n                continue\n            if not _claim_collection_freshness(\n                self._session,\n                parent_table=contents_table,\n                parent_id=content_id,\n                field_name=field_name,\n                observed_at=observation.observed_at,\n            ):\n                continue\n            self._session.execute(delete(table).where(table.c.content_id == content_id))\n            rows = _content_extension_rows(\n                field_name,\n                content_id,\n                observation,\n                attempt_id=attempt_id,\n                raw_id=raw_id,\n            )\n            if rows:\n                self._session.execute(insert(table).values(rows))\n''',
)

# 5) Existing integration expectation migrates from fail-closed to typed-locator eligibility.
eligibility = "tests/integration/collection/test_collection_supplement_target_eligibility.py"
replace_exact(
    eligibility,
    "def test_typed_lookup_that_does_not_match_stable_content_identity_is_not_eligible(\n",
    "def test_typed_lookup_that_does_not_match_stable_content_identity_is_eligible(\n",
)
replace_exact(
    eligibility,
    '''    targets = _read_targets(runtime, batch_id=batch_id, identity=_CURRENT_ANALYSIS_IDENTITY)\n\n    assert [target.content_id for target in targets] == [eligible_id]\n\n\ndef test_stale_irrelevant_analysis_does_not_block_supplement_target''',
    '''    targets = _read_targets(runtime, batch_id=batch_id, identity=_CURRENT_ANALYSIS_IDENTITY)\n\n    assert {target.content_id for target in targets} == {eligible_id, mismatched_id}\n    mismatched = next(target for target in targets if target.content_id == mismatched_id)\n    assert mismatched.lookup_id_type == "note_id"\n    assert mismatched.lookup_value == "real-provider-note-id"\n\n\ndef test_stale_irrelevant_analysis_does_not_block_supplement_target''',
)

# 6) Formal docs: distinguish stable DB identity from provider request locator and state the limit.
docs = "docs/appendix/08_数据入口与统一入库实现.md"
replace_exact(
    docs,
    "# 10. ContentIngestionService 当前怎样处理历史\n",
    '''## 9.3 稳定 Content 身份与 Provider lookup identity\n\nExcel 和 TikHub 统一入库时必须区分两个用途：\n\n```text\n(platform, external_content_id)\n→ PostgreSQL 稳定 Content 身份\n→ 跨批次/跨来源去重、Current/Version/Metric、Comment 归属\n\nCanonicalContentV1.alternate_ids\n→ note_id / aweme_id / status_id / av_id / bv_id / photo_id\n→ TikHub Detail / Comments / SubComments 的 Provider lookup locator\n```\n\n对 Excel 中能够从平台标准原文链接确定性解析 native ID 的内容，`external_content_id` 本身就使用该 native ID，因此后续 TikHub 搜索/详情观察到同一平台 ID 时会直接收敛到同一 Content。\n\n如果某条 Excel 只能用来源文章编号或 URL hash 作为稳定身份，但同时已经获得经过验证的 typed Provider ID，Batch Supplement 可以使用该 typed ID 补详情和评论，同时 Mapper 通过上下文继续把结果挂回原稳定 Content；不会为了发 Provider 请求改写 Content 主身份。\n\n`content_external_ids` 按 `id_type` 合并保留不同来源观察到的可靠身份：较旧 Observation 可以补充此前缺失的 id_type，但不能覆盖同一 id_type 的较新值。\n\n需要注意：typed locator 能让既有 Content 正确补采，并不等于把数据库中已经存在、稳定 `external_content_id` 不同的两条历史 Content 自动合并。历史实体合并需要独立的数据迁移/Identity Registry 设计，本链不会仅凭标题、正文或不确定别名猜测合并。\n\n# 10. ContentIngestionService 当前怎样处理历史\n''',
)

print("identity alignment patch applied")
