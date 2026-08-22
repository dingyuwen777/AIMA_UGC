"""一次性施工脚本：补齐 Batch Supplement eligibility API、前端消费和正式文档。

只在当前 L3 Change 的 GitHub Runner 中执行；所有替换都要求唯一锚点，最终合并前删除本文件。
"""

from __future__ import annotations

from pathlib import Path


def _replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def _append_once(path: str, marker: str, content: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n---\n\n" + content.strip() + "\n", encoding="utf-8")


def _patch_contracts() -> None:
    path = "backend/src/aima_ugc/contracts/http.py"
    old = '''class CollectionCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_configs: tuple[CollectionProviderConfigResponse, ...]
    capabilities: tuple[CollectionCapabilityResponse, ...]


class CollectionRuntimeListQuery(BaseModel):'''
    new = '''class CollectionCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_configs: tuple[CollectionProviderConfigResponse, ...]
    capabilities: tuple[CollectionCapabilityResponse, ...]


class CollectionBatchSupplementTargetResponse(BaseModel):
    """一个平台当前真实可创建 Batch Supplement Scope 的目标数。"""

    model_config = ConfigDict(extra="forbid")

    platform: CollectionPlatform
    target_count: int = Field(gt=0)


class CollectionBatchSupplementEligibilityResponse(BaseModel):
    """前端 Batch Supplement 平台资格；不公开 Provider 私有身份或 AI 结果正文。"""

    model_config = ConfigDict(extra="forbid")

    batch_id: UUID
    targets: tuple[CollectionBatchSupplementTargetResponse, ...] = ()


class CollectionRuntimeListQuery(BaseModel):'''
    _replace_once(path, old, new)
    _replace_once(
        path,
        '    "CollectionCapabilitiesResponse",\n',
        '    "CollectionBatchSupplementEligibilityResponse",\n'
        '    "CollectionBatchSupplementTargetResponse",\n'
        '    "CollectionCapabilitiesResponse",\n',
    )


def _patch_collection_service() -> None:
    path = "backend/src/aima_ugc/bootstrap/collection_http.py"
    _replace_once(
        path,
        '''    CollectionCapabilitiesResponse,
    CollectionCapabilityResponse,''',
        '''    CollectionBatchSupplementEligibilityResponse,
    CollectionBatchSupplementTargetResponse,
    CollectionCapabilitiesResponse,
    CollectionCapabilityResponse,''',
    )
    _replace_once(
        path,
        '''_COLLECTION_JOB_MAX_ATTEMPTS = 2
_SHANGHAI = ZoneInfo("Asia/Shanghai")''',
        '''_COLLECTION_JOB_MAX_ATTEMPTS = 2
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_ALL_COLLECTION_PLATFORMS: tuple[CollectionPlatform, ...] = (
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
    "kuaishou",
)''',
    )
    anchor = '''    def create_run(
        self,
        request: CollectionRunCreateRequest,'''
    method = '''    def get_batch_supplement_eligibility(
        self,
        batch_id: UUID,
    ) -> CollectionBatchSupplementEligibilityResponse:
        session = self._runtime.database.new_session()
        try:
            with session.begin():
                reader = PostgresCollectionTargetReader(
                    session,
                    analysis_identity=current_analysis_identity(self._runtime.settings),
                )
                if not reader.batch_exists(batch_id):
                    raise CollectionResourceNotFound
                targets = reader.list_batch_targets(
                    batch_id=batch_id,
                    platforms=_ALL_COLLECTION_PLATFORMS,
                )
                counts: dict[CollectionPlatform, int] = {}
                for target in targets:
                    counts[target.platform] = counts.get(target.platform, 0) + 1
                return CollectionBatchSupplementEligibilityResponse(
                    batch_id=batch_id,
                    targets=tuple(
                        CollectionBatchSupplementTargetResponse(
                            platform=platform,
                            target_count=counts[platform],
                        )
                        for platform in _ALL_COLLECTION_PLATFORMS
                        if platform in counts
                    ),
                )
        finally:
            session.close()

''' + anchor
    _replace_once(path, anchor, method)


def _patch_api() -> None:
    path = "backend/src/aima_ugc/bootstrap/api.py"
    _replace_once(
        path,
        '''    CollectionCapabilitiesResponse,
    CollectionPlanCreateRequest,''',
        '''    CollectionBatchSupplementEligibilityResponse,
    CollectionCapabilitiesResponse,
    CollectionPlanCreateRequest,''',
    )
    anchor = '''    @application.post(
        "/api/v1/collection-runs",'''
    route = '''    @application.get(
        "/api/v1/import-batches/{batch_id}/supplement-eligibility",
        operation_id="getCollectionBatchSupplementEligibility",
        response_model=CollectionBatchSupplementEligibilityResponse,
        responses={
            404: {"model": HttpErrorResponse},
            422: {"model": HttpErrorResponse},
            500: {"model": HttpErrorResponse},
        },
        tags=["collection"],
    )
    def get_collection_batch_supplement_eligibility(
        batch_id: UUID,
    ) -> CollectionBatchSupplementEligibilityResponse:
        return current_collection_service().get_batch_supplement_eligibility(batch_id)

''' + anchor
    _replace_once(path, anchor, route)


def _patch_frontend() -> None:
    path = "frontend/src/features/import-batches/api.ts"
    _replace_once(
        path,
        '''  getCollectionCapabilities,
  getCollectionRun,''',
        '''  getCollectionBatchSupplementEligibility,
  getCollectionCapabilities,
  getCollectionRun,''',
    )
    _replace_once(path, "  listContents,\n", "")
    old = '''async function batchHasPlatformContent(batchId: string, platform: CollectionPlatform): Promise<boolean> {
  const visible = unwrap(
    await listContents({
      source_identifier: batchId,
      platforms: [platform],
      limit: 1,
    }),
  )
  return visible.items.length > 0
}

export async function fetchBatchContentPlatforms(
  batchId: string,
  platforms: readonly CollectionPlatform[],
): Promise<CollectionPlatform[]> {
  const matches = await Promise.all(
    platforms.map(async (platform) =>
      (await batchHasPlatformContent(batchId, platform)) ? platform : null,
    ),
  )
  return matches.filter((platform): platform is CollectionPlatform => platform !== null)
}
'''
    new = '''export async function fetchBatchContentPlatforms(
  batchId: string,
  platforms: readonly CollectionPlatform[],
): Promise<CollectionPlatform[]> {
  const eligibility = unwrap(await getCollectionBatchSupplementEligibility(batchId))
  const eligible = new Set(eligibility.targets.map((item) => item.platform))
  return platforms.filter((platform) => eligible.has(platform))
}
'''
    _replace_once(path, old, new)


def _patch_api_tests() -> None:
    path = "tests/api/test_stage8e_collection_runs.py"
    _replace_once(
        path,
        '''CONFIG_ID = UUID("33333333-3333-4333-8333-333333333333")''',
        '''CONFIG_ID = UUID("33333333-3333-4333-8333-333333333333")
BATCH_ID = UUID("44444444-4444-4444-8444-444444444444")''',
    )
    anchor = '''    def create_run(self, request, *, request_id):  # type: ignore[no-untyped-def]'''
    method = '''    def get_batch_supplement_eligibility(self, batch_id):  # type: ignore[no-untyped-def]
        assert batch_id == BATCH_ID
        return {
            "batch_id": str(BATCH_ID),
            "targets": [
                {"platform": "xiaohongshu", "target_count": 2},
                {"platform": "weibo", "target_count": 1},
            ],
        }

''' + anchor
    _replace_once(path, anchor, method)
    marker = "def test_create_discovery_collection_run_returns_202() -> None:"
    test = '''def test_batch_supplement_eligibility_is_queryable() -> None:
    client = TestClient(create_app(collection_service=_FakeCollectionService()))

    response = client.get(f"/api/v1/import-batches/{BATCH_ID}/supplement-eligibility")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": str(BATCH_ID),
        "targets": [
            {"platform": "xiaohongshu", "target_count": 2},
            {"platform": "weibo", "target_count": 1},
        ],
    }


''' + marker
    _replace_once(path, marker, test)


def _patch_unit_expectation() -> None:
    path = "tests/unit/collection/test_imports_excel.py"
    _replace_once(
        path,
        "    assert source_fallback.alternate_ids == {}",
        '    assert source_fallback.alternate_ids == {"source_article_id": "SOURCE-002"}',
    )


def _patch_blueprint_02() -> None:
    path = "docs/blueprint/02-采集系统与数据标准化.md"
    old = '''## 12. Content 身份和 Comment 身份

Content：

```text
(platform, external_content_id)
```

Comment：

```text
(content_id, external_comment_id)
```

外部 ID 一律按字符串处理。

为什么不用标题/URL 去重：

- 标题可编辑；
- URL 形式可能变化；
- 同标题可以是不同内容；
- 大整数 ID 在不同语言里可能精度丢失。
'''
    new = '''## 12. Content 稳定身份、Provider Lookup 身份和 Comment 身份

三种身份不能混成一个概念。

Content 稳定业务身份：

```text
(platform, external_content_id)
```

它负责数据库去重和版本收敛。Excel 可以从平台标准 URL 得到原生 ID；如果只能得到来源文章编号或规范化 URL hash，仍允许作为审计 Content 稳定身份，但这不自动代表 Provider 可以拿该值补采。

Provider Lookup 身份：

```text
CanonicalContentV1.alternate_ids
→ content_external_ids(id_type, external_id)
```

当前正式可直接进入 TikHub Batch Supplement 的类型只有：

```text
xiaohongshu → note_id
douyin      → aweme_id
weibo       → status_id
bilibili    → av_id / bv_id
kuaishou    → photo_id
```

Excel 对确定性标准链接只做本地解析，不在 Import 阶段发送付费请求。抖音 `modal_id` 可直接作为 `aweme_id`；微博常见 permalink 的 Base62 BID 本地确定性转换为数字 MID/status_id；B站 AV/BV 保留类型。短链/分享链可以识别并保留，但如果还不能保证 `Detail → 原生 ID → 原 Content` 稳定收敛，就不获得普通付费补采资格，不猜 ID。

Comment 稳定身份：

```text
(content_id, external_comment_id)
```

`external_comment_id/root_comment_id/parent_comment_id` 必须来自 Provider 评论响应；Excel 不生成评论身份。一级评论由 Content lookup identity 发起，二级回复再使用一级评论响应得到的 Comment/Root ID。

所有外部 ID 一律按字符串处理，避免大整数跨语言精度丢失。标题/正文/作者名不参与身份去重；URL 是身份解析证据和来源事实，不作为跨平台内容主键。
'''
    _replace_once(path, old, new)
    _replace_once(
        path,
        '''两者不能共用一个字段/表含义。
''',
        '''两者不能共用一个字段/表含义。

AI Semantic Relevance 的 `irrelevant` 结果属于 Analysis 审计事实：Content/Version/Analysis/来源继续保留；声音广场默认列表隐藏当前 Analysis identity 下明确 irrelevant 的内容，但按 Content UUID 的详情仍可审计读取；普通 Batch Supplement 同样排除当前明确 irrelevant 的 Content，避免继续发生无业务价值的 Provider 费用。旧 Prompt/Taxonomy/Model 结果视为 stale，不永久阻断补采。
''',
    )


def _patch_blueprint_08() -> None:
    _append_once(
        "docs/blueprint/08-采集策略与平台能力.md",
        "# 25. Batch Supplement 的身份与资格边界",
        '''# 25. Batch Supplement 的身份与资格边界

基于 Excel Import Batch 的补采不是“Batch 里有 Content 就能请求 TikHub”。创建 Run 前必须同时满足：

```text
Content 属于目标 Import Batch
+ 当前 AI Analysis identity 未明确判为 irrelevant
+ Content 存在当前正式 Runtime 可消费的 typed Provider lookup identity
+ 所选 Provider Config / Platform Capability 支持本次操作
```

前端通过专用只读资格接口读取每个平台真实 `target_count`，不再用声音广场列表或 `relevance=irrelevant` 二次查询猜资格；后端 `create_run()` 仍重新冻结同一事实作为最终守卫。

当前首次 Batch Supplement 固定执行 Content Detail；一级评论默认可选开启，二级回复依赖一级评论。即：

```text
Detail（固定）
→ Comments（可选）
→ SubComments（可选，依赖 Comments）
```

当前不支持 Comment-only Supplement。以后若要对“详情已成功、评论失败/需刷新”的 Content 单独刷新评论，应建立独立 Change，复用已确认 Provider Content ID，而不是默认重复 Detail。

短链/分享链即使 Provider 提供 URL Detail 接口，也只有在系统能够把解析得到的原生 ID 安全固化并保证仍收敛到原 Content 后，才能成为普通 Batch Supplement 入口；在此之前识别并保留链接，但付费补采关闭失败。''',
    )


def _patch_stage8f() -> None:
    path = "docs/appendix/Stage8F前后端能力矩阵与真实验收.md"
    start = "### 3.2 Batch Supplement 的前端资格"
    end = "### 3.3 小红书 `xiaohongshu` 边界"
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if "GET /api/v1/import-batches/{batch_id}/supplement-eligibility" in text:
        return
    start_index = text.index(start)
    end_index = text.index(end)
    replacement = '''### 3.2 Batch Supplement 的前端资格

“基于已有批次补采”首先要求 Import Batch 已成功入库且存在内容。选择 Batch 后，前端调用正式资格接口：

```text
GET /api/v1/import-batches/{batch_id}/supplement-eligibility
```

后端按来源账本读取 Batch Content，并只统计同时满足以下条件的目标：

```text
当前 AI Analysis identity 未明确 irrelevant
+ 存在当前正式 TikHub Runtime 可直接消费的 typed lookup identity
```

返回的是每个平台真实 `target_count`；前端据此启用平台按钮，再与 Provider Capability 的 `content_detail/comments/sub_comments` 组合判断。前端不再通过 `GET /contents` 或显式查询 `relevance=irrelevant` 猜测补采资格。

来源文章编号、`url_sha256:*`、尚未完成身份收敛的短链/分享链仍可保留为数据库审计 Content，但不因此获得付费补采资格。当前 Analysis identity 下明确 `irrelevant` 的 Content 同样不进入普通 Batch Supplement；旧模型/旧 Prompt 结果为 stale，不永久阻断。

前端资格用于避免用户组成注定失败的任务；`PostgresCollectionHttpService.create_run()` 仍重新解析 Provider、Relevance、Batch target 和 Capability，是最终业务守卫。

'''
    target.write_text(text[:start_index] + replacement + text[end_index:], encoding="utf-8")


def _append_detail_docs() -> None:
    _append_once(
        "docs/appendix/数据入口与统一入库实现.md",
        "## Excel URL 与 Provider Lookup Identity",
        '''## Excel URL 与 Provider Lookup Identity

Excel Import 先保留 Input Artifact，再由生产 Mapper 解析 URL。标准长链接可确定性得到的 Provider ID 会进入 `alternate_ids/content_external_ids`；文章编号或 URL hash 只能保证数据库稳定身份，不自动取得 TikHub 补采资格。

当前本地解析：小红书 `note_id`、抖音 `aweme_id`（含标准 `modal_id`）、微博数字 MID 或 Base62 BID→MID、B站 `av_id/bv_id`、快手 `photo_id`。短链/分享链会识别类型并保留 URL，但在 Detail 返回原生 ID 后尚不能保证原 Content 身份收敛时，普通 Batch Supplement fail closed。

Excel 不生成 Comment ID。一级评论只能在 Content Provider lookup identity 已确认后由 TikHub 获取；评论和二级回复身份继续来自 Provider 响应。''',
    )
    _append_once(
        "docs/appendix/TikHub五平台真实响应与字段映射.md",
        "## Excel 补采 Lookup Identity",
        '''## Excel 补采 Lookup Identity

截至 2026-08-23 当前生产主链：小红书 Detail/Comments 使用 `note_id`；抖音 Detail/Comments 使用 `aweme_id`；微博普通帖子 Detail/Comments 使用数字 `status_id`，`tv/show` 视频链接必须先经视频详情取得真实 `idstr`，不能把 URL 中视频 ID 直接用于评论；B站 App Detail/Comments/Reply 使用 `av_id` 或 `bv_id` 二选一；快手 App Detail/Comments 使用 `photo_id`。

Excel 标准 URL 的 typed identity 必须与这些正式 Operation 参数一致。Comment ID/Root Comment ID 只来自评论响应，不从 Excel URL 推导。真实 Probe 必须复用生产 Operation/Transport/Extractor/Mapper，并限制请求数和费用；删除、私密、失效内容允许跳过候选，但不能把空响应伪装成接口成功。''',
    )
    _append_once(
        "docs/collection/README.md",
        "## Batch Supplement 内容身份门禁",
        '''## Batch Supplement 内容身份门禁

Batch Supplement 只消费 `content_external_ids` 中当前 Runtime 已验证的 typed Provider lookup identity；TikHub 原生历史 Content 可按平台安全解释既有 `external_content_id`。`source_article_id`、`url_sha256:*` 和尚未完成身份收敛的分享链接不直接发送给付费 Provider。

创建 Run 时排除当前 Analysis identity 明确 `irrelevant` 的 Content；执行期不重新改变已冻结 Scope 资格。首次补采固定先 Detail，再按用户选项决定 Comments/SubComments。''',
    )
    _append_once(
        "backend/src/aima_ugc/adapters/providers/imports_test/README.md",
        "## 最终 Excel 的身份列",
        '''## 最终 Excel 的身份列

人工 `imports_test` 最终 Excel 默认保留 `内容ID`；评论视图同时保留 `内容ID/评论ID/根评论ID/父评论ID`。这些列用于审计、去重与后续补采定位，不应因为报告展示简化而从人工数据交付中默认删除。''',
    )


def main() -> None:
    _patch_contracts()
    _patch_collection_service()
    _patch_api()
    _patch_frontend()
    _patch_api_tests()
    _patch_unit_expectation()
    _patch_blueprint_02()
    _patch_blueprint_08()
    _patch_stage8f()
    _append_detail_docs()


if __name__ == "__main__":
    main()
