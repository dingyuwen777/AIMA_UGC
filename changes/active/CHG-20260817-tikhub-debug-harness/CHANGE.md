---
id: CHG-20260817-tikhub-debug-harness
title: TikHub 五平台独立调试与评论增量一致性修复
level: L2
status: ready_for_review
owner: ChatGPT
branch: agent/tikhub-test-debug
created: 2026-08-17
updated: 2026-08-18
depends_on: []
affected_areas:
  - collection
  - provider
  - content
affected_paths:
  - backend/src/aima_ugc/adapters/providers/tikhub_test
  - backend/src/aima_ugc/adapters/providers/tikhub
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - backend/src/aima_ugc/modules/collection/decision.py
  - tests/unit/collection
  - tests/integration/collection
  - pyproject.toml
  - uv.lock
  - README.md
  - docs/测试与调试说明.md
  - docs/blueprint/07-技术决策与实施门禁.md
  - docs/blueprint/08-采集策略与平台能力.md
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - docs/collection
contracts: []
data_changes: []
---

# TikHub 五平台独立调试与评论增量一致性修复

## 背景

本 Change 最初用于建立小红书、抖音、微博、B站、快手的 TikHub 无数据库独立测试/调试入口。实施期间按用户要求把检查范围扩展到整个采集系统和 Blueprint，确认 Stage 7 已批准的“评论数增长时优先增量抓取、命中安全历史边界后停止下一页”设计没有完整落到生产执行层：

- Blueprint 08 已定义 `fetch_incremental` 与 `known_comment_reached`；
- 生产 Decision 已预留增量 action；
- 但正式 Scope 最初没有读取 PostgreSQL 历史一级评论 ID；
- XHS Operation 已固定 `latest_v2`，Capability 却仍保守关闭增量；
- 五个平台是否能够安全使用历史 comment ID 作为分页停止边界，必须逐平台用官方语义与真实响应重新验证，不能一刀切。

因此本 Change 同时完成独立调试工具和已批准生产设计的一致性修复；`tikhub_test` 只适配无数据库状态，不拥有第二套 endpoint、Mapper、分页或增量判断。

## 目标

1. 提供五个平台可直接调用的 `run_*()` Python 调试入口，不依赖 PostgreSQL、API、Worker 或 Scheduler。
2. 复用生产 TikHub Runtime / Operation / Transport / Mapper / Capability / Collection Decision。
3. 保存 Provider Raw、Canonical、`run_summary.json`、跨运行轻量 `state.json` 和原始数据 Excel。
4. 支持单关键词和多关键词，同一运行共享内容 identity 去重并保留命中关键词。
5. 把 `known_comment_reached` 实现为生产 Collection 共享规则，正式 PostgreSQL Scope 与文件态调试入口共同调用。
6. 逐平台核验最新评论顺序，只对证据充分的平台启用 `supports_incremental_comment_sort`。
7. 使用真实 TikHub 请求验证五平台 Search → Detail → 一级评论 → 二级评论/回复及调试输出闭环。

## 已完成实现

### 1. 五平台独立调试

目录：

```text
backend/src/aima_ugc/adapters/providers/tikhub_test/
```

已提供：

```text
run_xiaohongshu()
run_douyin()
run_weibo()
run_bilibili()
run_kuaishou()
```

边界：

- 无 CLI；
- `.env` 仅保存 `TIKHUB_BASE_URL`、`TIKHUB_API_KEY`、timeout，真实 `.env` 不提交；
- `keyword` 与 `keywords` 二选一，未提供时默认 `爱玛`；
- 多关键词各自 Search，但相同 `(platform, external_content_id)` 只执行一次后续 Detail/Comments/Replies；
- Raw 每次 Provider 响应先落盘再映射；
- Canonical 使用生产 Mapper；
- `run_summary.json` 记录运行、请求、停止原因和关键词命中关系；
- `state.json` 保存跨运行轻量 comment_count / comment ID 状态，可删除重置；
- 输出不写 PostgreSQL。

### 2. 原始数据 Excel

新增并锁定：

```text
openpyxl==3.1.5
types-openpyxl==3.1.5.20260518
```

Excel 是原始采集数据展示，不是分析报告：

- 核心 Sheet：`内容与评论`；
- 一条内容形成纵向区块，公共内容字段跨评论行合并；
- 一级评论、二级回复各占一行；
- comment/root/parent ID 保留并按文本写入；
- URL 可点击；
- 长文本换行；
- 浅色表头、白色主体、无粗黑边框；
- 公式注入防护；
- 多关键词内容显示全部命中关键词。

Blueprint 07/13 已固化迁移门禁：未来正式系统级原始数据 Excel Exporter 落地后，必须删除 `tikhub_test/excel.py` 的平行实现并复用共享导出，避免两套字段/样式/安全规则长期漂移。

### 3. 生产评论增量安全边界

生产 `CollectionDecisionService` 继续负责评论动作。新增共享纯规则：

```text
当前页出现已知历史 comment_id
AND
从第一个已知 comment_id 到当前页末尾全部都是已知历史评论
→ known_comment_reached
→ 当前已付费页仍完整 Raw / Mapper / Ingestion
→ 不再请求下一页
```

如果“已知旧评论后又出现新评论”，不提前停止，避免置顶/混排造成漏抓。

PostgreSQL state reader 一次查询目标内容已有一级评论 external ID 集合，不做逐评论 SQL；现有 `comments(content_id, external_comment_id)` 身份足以支持该能力，不需要 Schema/Migration。

正式 `TikHubCollectionScopeExecutor` 和 `tikhub_test` 调用同一个生产边界规则。

### 4. 五平台当前增量能力

| 平台 | Capability | 当前证据 |
| --- | --- | --- |
| 小红书 | `supports_incremental_comment_sort=true` | App V2 固定 `latest_v2`；官方最新优先语义；真实多评论页时间严格非增 |
| B站 | `true` | App `mode=2` 为时间排序；生产首屏固定 `next_offset=0`；真实 20/20 ID 唯一且 20 个时间戳严格非增 |
| 抖音 | `false` | App V3 评论没有已批准的最新评论排序业务参数 |
| 微博 | `false` | 虽有 `sort_type=1`，真实 20 条有效评论时间顺序不是严格非增 |
| 快手 | `false` | 当前 App 评论无已批准最新评论参数；真实 94 条一级评论时间顺序不是严格非增 |

抖音、微博、快手 `comment_count` 增加时继续 `refresh_controlled`，不为节省请求而猜测安全历史边界。

## 同步修复的真实 Provider 兼容问题

真实 Runner 还发现并修复了两类生产兼容问题：

- 抖音 Search V2 会混入不含稳定 `aweme_info.aweme_id` 的展示/混合卡片；生产 extractor 现在只把具有稳定业务 ID 的条目送入 Mapper。
- 微博一级评论响应可能包含没有稳定评论 ID 的展示卡片，且当前真实形状可能缺少 `data.moreInfo`；生产 extractor 过滤非评论卡片，分页在缺少已证明的下一页状态时按 Provider 末页处理，不猜私有游标。
- B站 App 一级评论当前首屏必须显式 `next_offset=0`；生产 Operation/Runtime 已固定该首屏语义。

## TDD 与自动化证据

### 调试包

- 初始 Red：`19046103682de53a2eb87014053bfe2895409d80`，pytest 因 `aima_ugc.adapters.providers.tikhub_test` 不存在而按预期失败，前置 Ruff/mypy 已通过。
- Green：`dd34563f1cba09eb70b9c3a570e98b2ec61dee9c`，Python 3.14.7、Ruff、mypy 137 个源文件、30 个目标/回归测试、Secret scan 通过。
- 多关键词 Red：`af0127c81f59fc5121e8302477f7b4096f90a072`，仅新增多关键词用例因 `unexpected keyword argument 'keywords'` 失败。
- 多关键词 Green：`64db854e5469f882f9fe6ba7466b31ffa3243727`，Ruff、mypy 和 8 个调试目标测试通过。

### 生产增量与最终化

- XHS 增量边界已建立 Unit + PostgreSQL/Fake Transport 纵切；正式 Stage 6 Unit/PostgreSQL 门禁在修复后取得成功结果。
- Finalizer run `32051045536`：先应用最终生产/文档一致性变更并删除任务专用脚本/workflow，再对最终仓库状态执行 `uv lock --check`、Ruff format/check、mypy、五平台/Decision/Excel 目标 pytest、Architecture、Table Ownership、Secret scan、Docs、`git diff --check`，全部成功后才生成提交 `b65ca8215a06d4b37c0074e1cf41aa6d4a5e0f96`。
- 任务期间产生的一次性 patch/probe/finalizer workflow 均已从正式分支删除；仓库保留原有正式 CI/Stage7 验证机制。

## 五平台真实 TikHub 证据

所有真实验证使用 GitHub-hosted Runner、`https://api.tikhub.io`、关键词“爱玛”。凭据使用一次性 RSA-3072 OAEP-SHA256 交接；明文 Key 未进入 Git、PR、日志或上传 Artifact，Runner 完成后清理临时凭据材料。

### 排序与结构核验

- `32045460636`：首轮五平台 `run_*()` 实际调用；XHS `latest_v2` 评论时间严格非增；快手 94 条唯一一级评论但时间顺序非严格非增；同时暴露抖音/微博真实形状兼容问题。
- `32047972292`：抖音 post-fix 真实验证；8 个混合 Search 卡片中过滤并映射 7 个稳定 `aweme_id`，Detail/Comments 主链继续可用。
- `32048374466`：微博 post-fix 真实验证；21 个评论候选中 20 个有效稳定 ID，`sort_type=1` 下 `time_nonincreasing=false`。
- `32049910092`：B站最终排序验证；Provider 报告 105 条评论的样本使用生产 `mode=2 + next_offset=0` 返回 20 条，20/20 ID 唯一、20 个时间戳严格非增。

### 当前最终代码五平台端到端验证

Run `32051212885` 直接调用当前最终五个平台 `run_*()`，启用 Comments + Replies，并逐平台打开生成的 Excel：

| 平台 | 内容 | 一级评论 | 二级回复 | Provider 请求 | Raw 文件 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 小红书 | 2 | 20 | 2 | 7 | 7 |
| 抖音 | 2 | 35 | 72 | 32 | 32 |
| 微博 | 2 | 39 | 70 | 30 | 30 |
| B站 | 2 | 33 | 4 | 8 | 8 |
| 快手 | 2 | 60 | 273 | 58 | 58 |

五个平台均满足：

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
```

`failed_platforms=[]`。公开 Artifact 只保存上述脱敏 summary，不上传完整真实 Raw/Canonical/Excel。

## 文档事实同步

已同步：

- `README.md`；
- `docs/测试与调试说明.md`；
- Blueprint 07 / 08 / 13 及导航；
- `docs/collection/README.md`；
- 五个平台采集说明；
- `tikhub_test/README.md`。

文档不再保留“小红书是唯一已落地平台”“Stage 7 Budget”“历史 PR #55 尚待合并”等过期事实。

## 非目标与兼容性

- 不新增/修改公共 HTTP API 或公共 Pydantic Contract Schema。
- 不修改数据库 Schema，不新增 Migration，不迁移业务数据。
- 不恢复请求次数/金额 Budget、Budget Account、Reservation Ledger 或发送前 Cost Guard。
- 不增加自动网络重试或自动 App/Web/API family fallback。
- 不把 Provider Raw JSON 变成公共业务结构。
- 不实现分析报告/Report Renderer。
- 不改变生产部署形态；无需部署迁移步骤。
- 本 Change 不引入“按经过时长强制刷新 Detail”的新 TTL 策略；该策略会改变费用与调度语义，需后续独立业务决定。

## 回滚

该 Change 没有 Schema/Migration。若合并后需要回滚，可整体 revert 本 PR：

- 删除 `tikhub_test` 新调试包与 `openpyxl` 新依赖；
- 回退增量 Capability/历史 ID 读取/共享边界逻辑及对应 Provider 兼容修复；
- 不需要数据库 downgrade 或数据迁移回滚。

真实 Raw 调试产物未提交仓库，不参与回滚。

## Git / 集成状态

- 分支：`agent/tikhub-test-debug`。
- PR：#63，Open / Draft；下一步执行两阶段 Review 和正式 CI 后转 Ready。
- 一次性最终真实验证 workflow 已在成功后删除。
- 合并：尚未执行。
- Change：`ready_for_review`；必须在 PR 合并并对 `main` 取得新鲜 CI 后，才可改为 `done` 并移动到 `changes/archive/2026-08/`。
