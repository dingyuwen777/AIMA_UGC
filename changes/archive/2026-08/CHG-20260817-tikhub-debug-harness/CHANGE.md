---
schema: rvc-change/v1
id: CHG-20260817-tikhub-debug-harness
title: TikHub 五平台独立调试与评论增量一致性修复
level: L2
status: done
owner: ChatGPT
branch: agent/tikhub-test-debug
created: 2026-08-17
updated: 2026-08-18
depends_on: []
affected_areas: [collection, provider, content, testing, documentation]
affected_paths: [backend/src/aima_ugc/adapters/providers/tikhub_test/, backend/src/aima_ugc/adapters/providers/tikhub/, backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py, backend/src/aima_ugc/bootstrap/collection_scope.py, backend/src/aima_ugc/modules/collection/decision.py, tests/unit/collection/, tests/integration/collection/, docs/blueprint/, docs/collection/, docs/测试与调试说明.md, README.md, pyproject.toml, uv.lock]
contracts: []
data_changes: []
---

# 完成结论

本 Change 已完成实现、Red→Green、五平台真实 TikHub 验证、两阶段 Review、PR 合并、合并后 `main` 新鲜 CI 与生命周期归档。

它同时完成两件事：

1. 建立小红书、抖音、微博、B站、快手五个平台的无数据库 TikHub 独立测试/调试入口；
2. 修复 Blueprint 08 已批准但 Stage 7 生产执行层未完整闭环的评论增量能力，并用真实 Provider 证据决定哪些平台可以安全按历史 comment ID 提前停止下一页请求。

本 Change **没有进入 Stage 8，没有恢复 Budget/Cost Guard，没有引入 Detail TTL，也没有修改公共 HTTP Contract 或数据库 Schema**。

实现 PR：`#63 实现 TikHub 五平台独立调试并修复评论增量闭环`

```text
开始 main:
e64a9e5956caf08fbbe14321cc0f45b603b3b919

最终 PR head:
970c3c096427251353765aea09fe6bf6b1e37835

PR #63 merge commit / 合并后 main:
fdaf53f18df6ea561a48197caeff9e5e0c6cbd41
```

PR #63 正常 merge，未强推、未跳过 CI、未绕过 PR。最终 PR head 实际取得 `11/11` 正式 PR workflows success；合并后的 `main@fdaf53f18df6ea561a48197caeff9e5e0c6cbd41` 实际触发 10 条适用 push workflow，按 GitHub Actions `status=success` 查询得到 `10/10 success`。

# 最终实现

## 五平台无数据库调试入口

正式目录：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/
```

提供：

```text
run_xiaohongshu()
run_douyin()
run_weibo()
run_bilibili()
run_kuaishou()
```

约束与行为：

- Python 函数入口，无 CLI；
- 不依赖 PostgreSQL、API、Worker 或 Scheduler；
- 复用生产 TikHub Runtime / Operation / Transport / Mapper / Capability / Collection Decision；
- 不复制 endpoint、分页、字段映射或自动 fallback；
- `.env` 只保存 Provider URL/API Key/timeout，真实 `.env` 不提交；关键词是运行时参数；
- 支持 `keyword` 或 `keywords`，多关键词共享 `(platform, external_content_id)` 去重；
- 同一内容被多个关键词命中时只执行一次后续 Detail/Comments/Replies，同时保留全部命中关键词；
- Provider Raw 每次请求先保存，再进入 Mapper；
- 输出 Canonical、`run_summary.json`、跨运行 `state.json` 和原始数据 Excel；
- 调试路径不写数据库。

## 原始数据 Excel

新增并锁定：

```text
openpyxl==3.1.5
types-openpyxl==3.1.5.20260518
```

Excel 是原始采集数据展示，不是分析报告：

- Sheet `内容与评论`；
- 一条内容形成纵向区块，内容公共列纵向合并；
- 一级评论、二级回复各占一行；
- comment/root/parent ID 保留并强制文本；
- URL 可点击；
- 长文本换行；
- 浅色表头、白色主体、无粗黑边框；
- 公式注入防护；
- 多关键词内容显示全部命中关键词。

Blueprint 07/13 已冻结迁移门禁：未来系统级共享原始数据 Excel Exporter 落地后，必须删除 `tikhub_test` 平行 Excel 生成实现并复用共享导出，不能长期维护两套字段、样式和安全规则。

# 生产评论增量闭环

生产 Collection 现在统一拥有 `known_comment_reached` 安全边界：

```text
当前页出现已知历史 comment_id
AND
从第一个已知 comment_id 到页尾全部都是已知历史评论
→ 当前已付费页仍完整 Raw / Mapper / Ingestion
→ stop_reason=known_comment_reached
→ 不再请求下一页
```

如果旧评论后再次出现新评论，不能提前停止，避免置顶/混排导致漏抓。

PostgreSQL state reader 一次查询目标内容已有一级评论 external ID，不做逐评论 SQL；现有 `comments(content_id, external_comment_id)` 唯一身份足够支撑，无需 Migration。正式 `TikHubCollectionScopeExecutor` 与文件态 `tikhub_test` 调用同一个生产边界规则。

Review 还发现并修复了一个生产桥接问题：对于 B站这类 Search 不观察 `comment_count` 的平台，正式 Scope 现在显式设置 `search_missing_required_fields`，先补 Detail 获得最新评论数，再与 previous state 比较并决定是否进入 `fetch_incremental`。

# 五平台最终增量 Capability

| 平台 | `supports_incremental_comment_sort` | 当前证据 |
| --- | --- | --- |
| 小红书 | `true` | App V2 固定 `latest_v2`；官方最新优先语义；当前真实多评论页时间严格非增 |
| B站 | `true` | `mode=2` 为时间排序；首屏必须 `next_offset=0`；真实 20/20 ID 唯一且 20 个时间戳严格非增 |
| 抖音 | `false` | 当前 App V3 评论没有已批准的最新评论排序业务参数 |
| 微博 | `false` | 虽可发 `sort_type=1`，当前真实 20 条有效评论时间顺序不是严格非增 |
| 快手 | `false` | 当前 App 评论没有已批准最新评论参数；真实 94 条一级评论时间顺序不是严格非增 |

因此抖音、微博、快手在 `comment_count` 增加时继续 `refresh_controlled`，不为了省请求而猜测历史边界。

# 真实 Provider 兼容修复

真实 Runner 同时发现并修复：

- 抖音 Search V2 会混入没有稳定 `aweme_info.aweme_id` 的展示/混合卡片；生产 extractor 只把具有稳定视频 ID 的业务卡片送入 Mapper；
- 微博一级评论响应可能混入没有稳定评论 ID 的展示卡片，且当前真实形状可能缺少 `data.moreInfo`；生产 extractor 过滤展示卡片，缺少已证明下一页状态时按 Provider 末页处理，不猜私有游标；
- B站 App 一级评论首屏当前必须显式 `next_offset=0`；生产 Operation/Runtime 已固定首屏语义。

# Red → Green 与 Review 证据

## 调试包初始 Red / Green

- 初始 Red head `19046103682de53a2eb87014053bfe2895409d80`：目标包不存在，pytest 按预期 `ModuleNotFoundError`；前置 Ruff/mypy 已通过。
- Green head `dd34563f1cba09eb70b9c3a570e98b2ec61dee9c`：Python 3.14.7、Ruff、mypy、30 个目标/回归测试和 Secret scan 通过。

## 多关键词 Red / Green

- Red `af0127c81f59fc5121e8302477f7b4096f90a072`：新增用例因 `unexpected keyword argument 'keywords'` 唯一失败；
- Green `64db854e5469f882f9fe6ba7466b31ffa3243727`：多关键词行为、Ruff、mypy 与调试目标测试通过。

## 生产增量与 Review Red / Green

- XHS 增量历史边界已建立 Unit + PostgreSQL/Fake Transport 纵切，证明命中已知历史尾区后不再发送下一页请求，同时保留当前已付费页。
- 两阶段 Review 发现 B站 Search 未观察 comment_count 时没有先补 Detail。新增 `tests/unit/collection/test_collection_scope_decision_bridge.py` 后，Stage 6 Unit 得到有效 Red：`1 failed, 227 passed`，唯一失败为 `detail_calls=[]`。
- 修复后生产 Scope 显式桥接 `search_missing_required_fields`；目标 Bridge/Decision/Capability tests、mypy、Secret scan 和最终正式 CI 全绿。

# 五平台真实 TikHub 验证

所有真实调用都在 GitHub-hosted Runner 执行，Provider 为 `https://api.tikhub.io`，关键词使用“爱玛”。凭据通过一次性 RSA-3072 OAEP-SHA256 交接；明文 TikHub Key 未进入 Git、PR、日志或 Artifact，临时密钥材料与密文占位均已清理。

关键运行：

- `32045460636`：首轮五平台 `run_*()`；XHS 排序证据成立，快手 94 条评论顺序不满足增量；同时暴露抖音/微博真实响应兼容问题。
- `32047972292`：抖音 post-fix；8 个混合 Search 卡片中过滤并映射 7 个稳定 `aweme_id`，Detail/Comments 主链继续可用。
- `32048374466`：微博 post-fix；21 个评论候选中 20 个有效稳定 ID，`sort_type=1` 下 `time_nonincreasing=false`。
- `32049910092`：B站排序验证；Provider 报告 105 条评论的样本用 `mode=2 + next_offset=0` 返回 20 条，20/20 ID 唯一、20 个时间戳严格非增。
- `32051212885`：当前最终五个平台 `tikhub_test` 端到端验证，直接执行 Search → Detail → 一级评论 → 二级回复，并重新打开 Excel。

最终真实端到端结果：

| 平台 | 内容 | 一级评论 | 二级回复 | Provider 请求 | Raw 文件 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 小红书 | 2 | 20 | 2 | 7 | 7 |
| 抖音 | 2 | 35 | 72 | 32 | 32 |
| 微博 | 2 | 39 | 70 | 30 | 30 |
| B站 | 2 | 33 | 4 | 8 | 8 |
| 快手 | 2 | 60 | 273 | 58 | 58 |

五个平台全部满足：

```text
content_nonempty = true
root_comment_nonempty = true
raw_nonempty = true
canonical_contents_exists = true
canonical_comments_exists = true
run_summary_exists = true
workbook_exists = true
workbook_sheet_ok("内容与评论") = true
run_status = completed
failed_platforms = []
```

公开 Artifact 只保存脱敏计数/布尔 summary，不上传完整真实 Raw、Canonical 或 Excel。

# 最终正式验证

PR #63 最终 head：

```text
970c3c096427251353765aea09fe6bf6b1e37835
```

正式 PR workflow：

```text
11 / 11 success
```

包括完整 CI、Stage 1-7 Audit Correctness、Stage 5A/5B/5C/5D、Stage 6 XHS、Stage 7 Provider Config Routing、Keyword Packs、Plan Occurrence Run Snapshot、Scheduler Runtime。

合并后：

```text
main = fdaf53f18df6ea561a48197caeff9e5e0c6cbd41
10 / 10 applicable push workflows success
```

这是 PR 合并后的新鲜 main 证据，不复用 PR 旧结果。

# 两阶段 Review

需求符合性 Review 已逐项对照用户批准要求、Blueprint 07/08/13、五个平台采集说明和最终 diff。正确性/安全/兼容性 Review 检查了生产 Decision、Provider Runtime、PostgreSQL previous-state、Raw/Secret、Excel、依赖、五平台兼容修复、临时文件清理与测试有效性。

Review 发现的唯一阻塞问题是 B站 Search 缺 comment_count 时未先补 Detail；已按 Red→Green 修复。最终 PR 没有未解决 Review、inline thread 或 comment，也没有任务专用临时 workflow、真实 `.env`、TikHub Secret 或真实调试输出进入合并 diff。

# 兼容、迁移、部署与回滚

- 公共 HTTP API / Pydantic HTTP Contract：不变化；
- Canonical Schema：不变化；
- 数据库 Schema / Migration：不变化；
- 业务数据迁移：不需要；
- 依赖：新增并锁定 `openpyxl==3.1.5` 与类型包；未自动升级无关依赖；
- Budget/Cost Guard：继续不存在；
- Provider 自动重试 / App-Web 自动 fallback：未新增；
- 部署形态：不变化，无额外部署迁移步骤；
- Detail 经过固定时长强制刷新 TTL：本 Change 未实现，因其会改变费用/调度语义，需后续独立业务决定；
- 回滚：整体 revert PR #63 即可；由于没有 Schema/Migration，不需要数据库 downgrade 或数据迁移回滚。

# 最终验收

- [x] 五平台独立 `run_*()` 调试入口完成；
- [x] 单关键词/多关键词与跨关键词内容去重完成；
- [x] Raw / Canonical / run summary / state / 原始数据 Excel 完成；
- [x] Excel 术语与 Blueprint 13 未来共享导出门禁完成；
- [x] 生产共享 `known_comment_reached` 增量边界完成；
- [x] PostgreSQL 历史一级评论 ID 一次读取完成；
- [x] XHS/B站增量资格有真实多评论顺序证据；
- [x] 抖音/微博/快手未越权声明增量；
- [x] 抖音/微博/B站真实 Provider 兼容问题修复；
- [x] Review 发现的 B站 Detail 桥接问题完成 Red→Green；
- [x] 五平台最终真实 `tikhub_test` 端到端验证成功；
- [x] Secret 未进入 Git/PR/日志/Artifact；
- [x] 最终 PR head 11/11 workflows success；
- [x] PR #63 正常合并；
- [x] 合并后 main 10/10 applicable push workflows success；
- [x] Change 更新为 `done` 并归档；
- [x] Stage 8 尚未开始。
