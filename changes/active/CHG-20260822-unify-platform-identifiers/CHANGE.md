---
schema: rvc-change/v1
id: CHG-20260822-unify-platform-identifiers
title: 五平台机器标识统一
level: L3
status: ready_for_review
owner: chatgpt
branch: refactor/unify-platform-identifiers
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - contracts
  - collection
  - content
  - ingestion
  - frontend
  - migrations
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/contracts/
  - backend/src/aima_ugc/adapters/providers/tikhub/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/modules/content/
  - backend/src/aima_ugc/modules/system/
  - backend/src/aima_ugc/platform/
  - frontend/src/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - contracts/
  - migrations/versions/
  - tests/
  - .github/workflows/
  - docs/blueprint/
  - docs/appendix/
  - docs/collection/
contracts:
  - CollectionPlatform
  - ProviderPlatformCapabilityV1.platform
  - CanonicalContentV1.platform
  - CanonicalCommentV1.platform
data_changes:
  - platform identifiers xhs -> xiaohongshu
---

# 目标

AIMA_UGC 当前所有**内部平台机器身份**统一为且仅允许：

```text
xiaohongshu
douyin
weibo
bilibili
kuaishou
```

运行时代码、公共 HTTP Contract、generated client、Collection Plan/Run/Scope、Provider Capability/Mapper、Canonical、Content、数据库、Job payload、日志/事件机器上下文、配置、当前源码/测试/Workflow 和正式文档均不得继续把平台简称当内部身份。

外部 Provider Raw/原始 Fixture 保留第三方真实字节；历史 Change、已执行旧 Migration 保留历史事实。Excel 等外部输入可以识别明确的中文平台展示名称，但进入系统后立即归一化到五个正式机器值。

**完整名称大小写兼容只存在于外部输入边界：** HTTP Request/Query、Excel 等外部输入可以接受 `XIAOHONGSHU / Xiaohongshu / xiaohongshu` 这类完整正式名称的大小写和首尾空白差异，并立即归一化为小写正式值；`xhs / red / dy / wb / ks / bili` 等简称/别名仍全部拒绝。数据库、Contract 输出、Job、日志/事件和持久化只保存小写正式值。

**展示层与机器值分离：** Excel 最终展示列继续使用 `小红书 / 抖音 / 微博 / 哔哩哔哩 / 快手`，展示映射的输入只能是五个正式机器值，不接受平台简称或中文展示名反向冒充机器值。

关键词“适用于全部平台”使用 `platform_scope=all`，`all` 不再占用平台身份字段。

# 可观察成功标准

- [x] `PlatformName` / `CollectionPlatform` 只允许 `xiaohongshu / douyin / weibo / bilibili / kuaishou`；
- [x] HTTP Request/Query 与 Excel 等外部输入接受完整正式平台名的大小写差异并立即归一化为小写，仍拒绝 `xhs / red / dy / wb / ks / bili` 等简称/别名；
- [x] Provider Capability、Canonical Content/Comment Mapper 只输出五个正式平台机器值；
- [x] Excel Profile 只把明确中文展示名或正式机器值归一化为五个正式值，不接受 `xhs / red / dy / wb / ks / bili` 等平台简称作为机器输入；
- [x] Excel 最终展示列使用 `小红书 / 抖音 / 微博 / 哔哩哔哩 / 快手`，但内部记录与 Contract 仍保持正式机器值；
- [x] `platform_display_name()` 只接受 `PlatformName`，不维护中文/简称反向兼容映射；
- [x] Collection Plan / Run / Scope / Batch Supplement / Frontend generated client 全部使用五个正式平台机器值；
- [x] 删除运行时平台 alias/双值转换，不保留简称兼容层；
- [x] 当前有效源码路径、类/函数/常量、Job type、schema version、Workflow 名称、日志/事件机器标识、配置、测试与正式文档不继续使用平台简称；
- [x] 第三方 Raw Artifact/Raw Fixture、历史归档 Change、旧 Migration 不因本任务伪造性改写；本 Migration 和 Migration 生命周期测试可以显式引用旧值以完成一次性迁移验证；
- [x] 新 Alembic Migration 一次性迁移当前持久化平台字段中的旧小红书机器值，并为稳定平台身份列增加五值 CHECK；
- [x] Migration 在会造成业务身份唯一键冲突时 fail closed，不静默删除/合并 Content、Account 或历史来源；
- [x] Migration downgrade 只恢复 Schema/字段名，不猜测哪些 `xiaohongshu` 行原先来自旧值；生产级数据回滚依赖升级前 PostgreSQL 备份；
- [x] OpenAPI / generated client 同步且 drift check 通过；
- [x] PostgreSQL 空库升级、Migration downgrade/re-upgrade、目标迁移数据与冲突测试通过；
- [x] Backend Unit / Contract / API / Integration 相关测试通过；
- [x] Frontend lint / TypeScript 7 / Vue typecheck / Unit / build / Mock E2E 通过；
- [x] Stage 8F 真实 Excel Full-stack Acceptance 继续通过；
- [x] Blueprint / Appendix / Collection README / Frontend README 与代码一致；
- [x] 合并前两阶段 Review 无未解决严重/重要问题；
- [ ] PR 合并到 `main` 后 Change 归档。

# 范围

## 修改

1. Pydantic 平台 Contract、OpenAPI、generated client；
2. TikHub Capability、Mapper、Collection Runtime、Content、Frontend 的平台机器值；
3. Excel Import 平台输入归一化规则、HTTP 完整名称大小写归一化与 Excel 中文展示边界；
4. PostgreSQL 稳定平台列、关键词 `platform_scope`、当前固定 JSON 快照；
5. 一次性 Alembic Migration；
6. 当前有效源码/测试/Workflow/日志事件相关命名中的平台简称；
7. Unit / Contract / API / PostgreSQL Integration / Browser E2E / Full-stack 测试；
8. 当前正式文档；
9. 永久平台标识一致性门禁。

## 不修改

- TikHub 等 Provider 返回的第三方 Raw 字节和真实 Provider JSON；
- 第三方 Raw Fixture 内容；
- 外部内容 ID、评论 ID；
- `tikhub`、`imports` 等 provider/source 名称，它们不是 platform；
- AI taxonomy / Prompt；
- Job Runtime、Retry、费用策略；
- Docker / Compose / Internal V1-A；
- 历史 `changes/archive/` 与已发布旧 Migration 文件内容。

# 已确认上游决定

用户明确要求：

> 系统内部不需要平台简称兼容，所有平台字段统一为 `xiaohongshu / douyin / weibo / bilibili / kuaishou`；除 Provider Raw 原始数据外，包括日志等当前系统事实都不要平台简称；系统性修改、避免兼容层，并在验证后合并到主分支。

用户同时明确：

> Excel 导出属于人类展示，平台列应显示中文：`小红书 / 抖音 / 微博 / 哔哩哔哩 / 快手`。

用户后续明确补充：

> 完整平台名称可以保持大小写兼容。

因此本 Change 不设置平台简称/别名兼容窗口；只在外部输入边界允许完整正式名称大小写归一化，内部和持久化始终使用小写正式值，并保留单向的“正式机器值 → 中文展示文案”转换。

# L3 方案比较

## 方案 A：边界长期保留平台简称转换

优点：公共 Contract 变化小。

缺点：永久维护两套平台身份，已经造成 Excel Batch 与 Collection 补采断点；与用户决定冲突。

结论：拒绝。

## 方案 B：全系统五个正式机器值 + 外部完整名称大小写归一化 + 一次性 Migration + 单向中文展示

优点：Contract、Canonical、Collection、Content、Frontend、数据库只剩一套机器身份；外部调用方不受大小写差异影响；Excel/UI 等展示仍可读；后续无需 alias。

代价：公共 HTTP Contract 与 persisted data 均变化，需要 Migration、generated client 和完整回归。

结论：**采用**。

## 方案 C：只改代码，不迁移旧数据库

优点：实现最少。

缺点：旧数据会变成不可见/重复身份，可能继续产生 `(platform, external_content_id)` 双记录。

结论：拒绝。

# 数据兼容与 Migration

## 升级

Migration 从 `20260821_0023` 后新增 `20260822_0024`。

升级前检测会造成唯一身份冲突的历史数据，至少包括：

```text
contents(platform, external_content_id)
accounts(platform, external_account_id)
collection_plan_platforms(plan_id, platform)
collection_scopes(run_id, platform, source_type, source_value, operation_group)
```

发现同一业务身份同时存在旧值和 `xiaohongshu` 时，Migration 明确失败并事务回滚；不得猜测哪条历史应删除，也不得在 Migration 内静默合并 Content Version、Comment、Analysis、Export 或来源链。

无冲突时，一次性把仓库当前正式持久化位置更新为 `xiaohongshu`。JSONB 只迁移当前代码明确拥有的固定快照结构，不对任意 JSON 文本全文替换。

## Downgrade / 数据回滚

平台身份归一化不可从最终数据可靠推断旧来源。因此：

```text
Alembic downgrade
→ 恢复本 Migration 引入的 Schema / 字段名
→ 不把所有 xiaohongshu 数据猜回旧值

生产级数据回滚
→ 停止新进程
→ 恢复升级前 PostgreSQL 备份
→ 恢复旧代码
```

当前项目尚未生产部署；合并前仍必须在隔离 PostgreSQL 验证 upgrade、冲突 fail-closed、downgrade/re-upgrade 与 schema drift。

# 部署顺序

```text
代码 + Migration 同一 Release
→ 停止旧 API/Worker/Scheduler 写入
→ Alembic upgrade head
→ 新 API/Worker/Scheduler 启动
```

不允许新代码连接尚未迁移的旧库，也不允许旧代码继续向升级后的库写旧平台值。

# 风险

- **数据身份冲突**：Migration fail closed，不静默丢历史；
- **Contract 破坏性变化**：同一 PR 同步 OpenAPI/generated/frontend/tests；不提供简称兼容，只允许完整正式名称大小写归一化；
- **遗漏平台简称**：Contract + DB CHECK + 当前仓库静态扫描三层门禁；简称扫描只针对平台身份上下文，避免误伤 `wb` 等非平台技术字符串；
- **展示层误伤**：Excel 保留中文展示，但展示函数输入仍是严格五值；
- **Raw 证据污染**：第三方 Raw/Fixture 不改写；
- **旧历史被改写**：archive Change / 已发布旧 Migration 不修改。

# 实施任务

1. Red：平台一致性 Contract/扫描门禁确认旧平台身份真实失败；
2. 统一 HTTP Contract、Capability、Mapper、Excel Profile、Collection / Content / Frontend 机器值；
3. 删除运行时平台 alias，并为外部完整正式名称增加大小写归一化；
4. 新增 `20260822_0024` 数据 Migration 与 PostgreSQL Integration；
5. 重新生成 OpenAPI / frontend generated client；
6. 收口当前源码路径、符号、Workflow、日志/事件命名中的平台简称；
7. 保留并验证 Excel 五平台中文展示；
8. 更新测试和正式文档；
9. 执行永久 CI；
10. 两阶段 Review，PR Ready 后合并；
11. 归档 Change。

# 验证计划

至少要求：

```text
uv run ruff format --check backend tests scripts migrations
uv run ruff check backend tests scripts migrations
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run pytest tests/integration/database -q
uv run pytest tests/integration/collection -q
uv run pytest tests/integration/content -q
uv run pytest tests/integration/ingestion -q
uv run alembic upgrade head
uv run alembic check
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run test:e2e:fullstack
```

最终以仓库永久 GitHub Actions 的最新 PR HEAD 结果作为合并门禁。

# 文档影响

已检查并按受影响语义同步：

- `docs/blueprint/02-采集系统与数据标准化.md`
- `docs/blueprint/03-数据库与文件存储.md`
- `docs/blueprint/05-日志安全部署与运维.md`（检查后无需制造无关修改）
- `docs/blueprint/07-技术决策与实施门禁.md`
- `docs/blueprint/08-采集策略与平台能力.md`
- `docs/appendix/数据入口与统一入库实现.md`
- `docs/appendix/TikHub五平台真实响应与字段映射.md`
- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/collection/README.md`
- `frontend/README.md`（精确 HTTP 字段由 generated Contract 维护，检查后无需复制第二套平台枚举）

# Git / PR / 验证证据

开始 main：

```text
091fe8b78c118e31a2491b9477705679d6516058
```

分支：

```text
refactor/unify-platform-identifiers
```

PR：`#149 统一五平台机器标识为完整名称`。

## Red / Green 与根因修复

本 Change 先通过平台标识一致性门禁暴露旧平台身份，再系统迁移 Contract、Schema、Runtime、Frontend、测试和正式文档。最终收尾阶段额外定位并修复了以下真实回归：

- 集成测试曾把第三方 `external_content_id / external_comment_id` 跟着内部平台机器值改名；已改为从 Provider Fixture 读取并断言原样持久化，不修改生产 Mapper；
- Stage 8E/8F 测试 seed 仍使用旧 `keyword_pack_items.platform`；已对齐 `platform_scope`；
- Stage 6 根评论测试人工改写第三方 note ID，导致评论找不到父 Content；已改为读取 Fixture `note_id`；
- 新 Contract 门禁对 Python 3.14 PEP 695 type alias 和 SQLAlchemy naming convention 的反射假设错误；已改为验证实际 `TypeAdapter` 行为和物理约束命名；
- Stage 7 Workflow、Frontend Store/Component/E2E Mock 仍有旧字段或旧路径；均已对齐正式 `xiaohongshu` / `platform_scope` Contract。

这些修复没有降低门禁、没有增加平台别名兼容层，也没有修改 Provider Raw Fixture 字节。

## 新鲜 CI

业务实现验证 HEAD：

```text
d0e1782146b7f5b33ad7307a63f0779359d4bb63
```

该 HEAD 的 13 个永久 PR Workflow 全部 `success`：

```text
CI #2049
Stage 4 Job Runtime #883
Stage 5A Provider Raw #1428
Stage 5B Collection Execution #1386
Stage 5C Provider Persistence #1383
Stage 5D Provider Dispatch #1443
Stage 6 Xiaohongshu Vertical Slice #47
Stage 7 Keyword Packs #1659
Stage 7 Provider Config Routing #1772
Stage 7 Plan Occurrence Run Snapshot #1657
Stage 7 Scheduler Runtime #1999
Stage 8F Full-stack Acceptance #176
Stage 1-7 Audit Correctness #941
```

`CI #2049` 内部：

```text
Stage 1            success
Stage 2 Platform   success
Stage 3A Database  success
Windows bootstrap  success
```

Stage 1 实际覆盖并成功：generated Contract/client 漂移检查、Ruff、mypy、Backend Unit/Contract/API、Architecture/Table Owner/Secret/Docs、Wheel、Frontend lint、TypeScript 7 + Vue typecheck、Frontend Unit、production build 和 Mock Playwright E2E。Stage 3A 覆盖空库 Migration、Repository/Import Integration 与 downgrade/re-upgrade。Stage 8F 使用隔离 PostgreSQL、真实 FastAPI、正式 Worker 和生产 Excel Reader/Mapper/Ingestion 完成真实 Browser Acceptance。

Provider Fixture 目录从旧简称路径重命名为正式路径时，JSON/README blob 内容保持不变；外部 Content/Comment ID 回归测试也从真实 Fixture 读取 ID，确认本 Change 没有伪造第三方身份。

本 Change 证据提交后仍必须以 PR 最新 HEAD 重新执行永久 CI，只有最新 HEAD 门禁全绿才允许 Ready/merge。

## 两阶段 Review

### 需求符合性

逐项复核 Change 成功标准、Contract、Migration、generated client、Provider/Canonical/Collection/Content、Excel 输入与中文展示、Frontend、测试和正式文档：

- 内部机器值只有五个正式值；
- 外部正式全名仅做大小写/空白归一化，平台简称仍拒绝；
- `all` 只存在于 `platform_scope`；
- Provider Raw/Fixture 内容、外部 Content/Comment ID、历史归档 Change、旧 Migration 均未被伪造性改写；
- Migration 的冲突检测、不可逆数据回滚边界和停写→upgrade→新代码启动顺序与设计一致；
- 没有进入 AI Prompt、Job Retry/费用策略、Docker/Compose/Internal V1-A 等非目标。

### 代码质量

重点检查正确性、输入边界、Schema/Migration、数据身份、generated Contract、异常/回滚、测试真实性、无关改动和维护成本：

- 未发现尚未解决的严重/重要问题；
- 未新增或升级依赖；
- 未手工维护第二套 generated Client/HTTP Contract；
- 未保留运行时 `xhs/red` alias 转换；
- Migration fail closed，不在冲突时静默删/并历史；
- PR #149 当前无外部 review、inline review thread 或普通 PR 评论。

## 待完成 Git 收尾

- PR #149 转 Ready；
- PR #149 合并到 `main`；
- 从合并后的新 `main` 创建独立归档分支和归档 PR；
- 归档 PR 永久 CI 全绿后合并；
- 最终确认 Active Change 已消失、Archive Change 为 `done`，并记录真实 merge commit。
