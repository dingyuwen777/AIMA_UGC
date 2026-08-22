---
schema: rvc-change/v1
id: CHG-20260822-stage8f-business-closure
title: Stage 8F 真实业务闭环收尾
level: L2
status: done
owner: chatgpt
branch: fix/stage8f-business-closure
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - frontend
  - collection
  - ingestion
  - ci
  - docs
affected_paths:
  - frontend/src/features/import-batches/
  - frontend/src/features/collection-strategy/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_targets.py
  - tests/integration/ingestion/
  - tests/fullstack/
  - .github/workflows/stage8f-fullstack.yml
  - docs/appendix/Stage8F前后端能力矩阵与真实验收.md
  - docs/roadmap/
contracts: []
data_changes: []
---

# 结果

Stage 8F 归档后的真实业务闭环审计缺口已经通过 PR #147 修复并合并到 `main`。

本 Change 没有重新设计 Stage 8，也没有新增公共 HTTP Contract、Schema、Migration、依赖或 Docker/Compose；它只把首版页面的可操作资格、后端业务守卫、失败终态表达与真实 Full-stack Acceptance 收敛到同一套机器事实。

已完成：

- 被 Global Relevance 或启用中的 Collection Plan 引用的 Keyword Pack，前端不再允许无效停用；
- Collection Plan 创建/重新启用前按实时 Pack、Relevance、平台关键词、Provider Config 与 Capability 判断资格；
- Batch Supplement 只提供成功且真实入库的 Batch，并按 Batch Content 与 Provider Capability 收敛平台；
- 修复 Excel 小红书 stored `xiaohongshu` 与 Collection Contract `xhs` 的真实补采断点；
- AI `irrelevant` Content 不会被声音广场默认展示规则错误排除出补采资格；
- Batch A → B → A 切换会重新探测平台资格，不复用错误快照；
- Import `failed/cancelled` 不再伪造所有历史阶段为“等待中”；
- Voice Plaza 空 query/page/selected 不再创建空 Export；
- 用户可见 Job 状态使用业务化中文表达；
- 采集策略继续保持仓库既有默认 `plans` 视图；
- Stage 8F Real Full-stack Acceptance 同时覆盖成功 Excel 链与真实 Worker `invalid_import` 失败链。

# 成功标准

- [x] 被全局 Relevance 或启用中的 Collection Plan 引用的 Keyword Pack，前端和 Store 均拒绝无效停用；
- [x] 已停用 Collection Plan 只有在当前 Relevance、Discovery 词包、目标平台关键词与 Provider Capability 满足正式规则时才允许启用；
- [x] 创建启用 Plan 时，缺失全局 Relevance 或目标平台可用关键词会被前端阻止并解释；
- [x] Batch Supplement 只展示 `succeeded + rows_ingested > 0` 的 Batch；
- [x] Batch Supplement 平台必须真实存在于该 Batch Content，并满足选定 Provider 与评论选项 Capability；
- [x] Excel 小红书 `xiaohongshu` Content 可以被 Collection `xhs` 正确解析为补采目标；
- [x] AI `irrelevant` Content 不会被错误排除出 Batch Supplement 平台资格；
- [x] Batch 切换会重新读取当前 Batch 的平台资格；
- [x] Voice Plaza 当前筛选没有结果时仍可查看历史导出，但不能创建空 Export；
- [x] Import `failed/cancelled` 不再显示无法由 Contract 证明的伪造阶段历史；
- [x] Mock Browser E2E 覆盖资格判断、禁用状态、错误解释与空 Export；
- [x] Real Full-stack Acceptance 覆盖真实成功 Excel 链与真实 Worker 失败链；
- [x] Full-stack 不 Mock `/api/v1/**`，不调用真实付费 TikHub/LLM；
- [x] PostgreSQL Integration 固定验证真实 Excel 入库后的 `xhs` 补采目标；
- [x] Frontend lint、TypeScript 7 + Vue typecheck、Unit、production build、Mock Playwright E2E 全部通过；
- [x] Backend Ruff、mypy、Unit、Contract、API、架构、Table Owner、Secret、Docs、Wheel 全部通过；
- [x] PostgreSQL Migration/drift、repository、Import HTTP/Worker integration 与 downgrade/re-upgrade 全部通过；
- [x] Stage 8F 能力矩阵和 Roadmap 与最终实现同步；
- [x] 两阶段 Review 完成，无严重/重要问题；
- [x] PR #147 已合并到 `main`。

# 保持不变

本 Change 没有修改：

- Pydantic HTTP Contract；
- OpenAPI；
- `frontend/src/generated/api/`；
- PostgreSQL Schema / Alembic Migration；
- Content 持久身份与数据保留语义；
- Job Runtime / Fencing / Retry；
- TikHub Provider 请求实现与费用策略；
- AI taxonomy；
- Python / Node / frontend 依赖及锁定版本；
- Docker/Compose 或公司服务器部署。

因此不存在 Migration、数据回填、依赖升级或部署切换。

# 关键设计决定

1. **不新增资格 API。** 当前已有 Relevance、Collection Plan、Pack detail、Capabilities、Contents API 足以形成前端只读资格快照；后端继续承担最终一致性守卫。
2. **Batch 平台存在性最多做五个平台的 `limit=1` 探测。** 不扫描整批 Content，也不按文件名猜平台。
3. **声音广场展示过滤不等于补采业务过滤。** 默认查询为空时再显式探测 `relevance=irrelevant`，使前端资格与后端 Batch target 语义一致。
4. **`xiaohongshu/xhs` 只在 Collection target reader 边界兼容。** Content stored identity 不改写，Collection 返回统一机器值 `xhs`。
5. **失败阶段历史不伪造。** 当前公开 Contract 没有可审计完整阶段历史，`failed/cancelled` 只展示可靠终态、Job 与错误事实。
6. **普通 CI 不做真实付费 TikHub/LLM 调用。** 真实 Excel、FastAPI、Worker 与 PostgreSQL 进入永久 Full-stack；Provider 付费调用仍由专项 Fixture/Probe 与人工环境负责。

# TDD / 根因证据

## Frontend 有效 Red

HEAD：

```text
9d0443e7e8cb59f8ec26ad8d94ae25dcf392f710
```

CI：

```text
CI #1887
run 32559994733
```

准确证明：

- Global Relevance 引用的 Keyword Pack 仍会发送停用请求；
- failed/empty Import Batch 仍进入补采候选；
- Voice Plaza 空 query 仍创建 Export 请求。

无关 Backend、Contract、Database 门禁保持绿色，因此是有效产品 Red。

## Backend 有效 Red

HEAD：

```text
4fbb4e75efe3f1cd5471db73bc843184e24873c9
```

CI：

```text
CI #1888
run 32560190255
```

真实 Excel Worker 已成功入库一条小红书 Content，但：

```text
PostgresCollectionTargetReader(... platforms=("xhs",))
→ supplement_targets = 0
```

证明 `xiaohongshu` / `xhs` 是真实 Batch Supplement 业务断点，而不是静态推测。

# 最终验证证据

PR #147 最终 HEAD：

```text
b0c231397c3f892dd059c1b67882889bceabe9b8
```

该 HEAD 的永久 Workflow 全部 success：

```text
CI #1946                                      success  run 32563576194
Stage 8F Full-stack Acceptance #73           success  run 32563576208
Stage 6 XHS Vertical Slice #1761             success  run 32563576197
Stage 5D Provider Dispatch #1347              success  run 32563576193
Stage 7 Keyword Packs #1556                  success  run 32563576192
Stage 7 Scheduler Runtime #1896              success  run 32563576196
Stage 7 Plan Occurrence Run Snapshot #1554   success  run 32563576191
Stage 7 Provider Config Routing #1669        success  run 32563576198
Stage 1-7 Audit Correctness #846             success  run 32563576203
```

CI #1946 内部：

```text
Stage 1              success
Stage 2 Platform     success
Stage 3A Database    success
Windows bootstrap    success
```

Stage 1 覆盖：

- locked Python / frontend environment；
- frontend dependency audit；
- local startup smoke；
- generated Contract/client 漂移检查；
- Ruff / mypy；
- Backend Unit / Contract / API；
- Architecture / Table Owner / Secret / Docs；
- Wheel build；
- Frontend lint；
- TypeScript 7 native + Vue typecheck；
- Frontend Unit；
- production build；
- Mock Playwright E2E。

Stage 3A 覆盖：

- Schema / Table Owner；
- 空库 Migration 到 head 与 drift check；
- PostgreSQL repository integration；
- Stage 8B Import HTTP/Worker integration；
- Migration downgrade / re-upgrade。

Stage 8F Full-stack Acceptance #73 固定验证两条不 Mock `/api/v1/**` 的 Browser 链：

```text
合法 Excel
→ Browser file input
→ Vue / generated client
→ FastAPI
→ Import Batch + Job
→ 正式 PostgreSQL Job Worker
→ 生产 Excel Reader / Mapper / Relevance / Ingestion
→ PostgreSQL Content
→ Runtime succeeded
→ 查看入库内容
→ Voice Plaza 显示本批 Content
```

以及：

```text
结构合法但业务字段非法 XLSX
→ Browser upload / HTTP 202
→ Import Batch + Job
→ 正式 Worker
→ failed / invalid_import
→ “查看入库内容” disabled
→ 页面显示可靠失败终态
→ 不渲染伪造 stage-row 历史
```

# 两阶段 Review

## 需求符合性

- 成功标准逐项与代码、Unit、Mock E2E、PostgreSQL Integration、Real Full-stack 和正式文档对应；
- 没有进入 Internal V1-A、Docker/Compose、认证、旧数据迁移等非目标；
- Stage 8F 能力矩阵和 Roadmap 已同步。

## 代码质量

Review 中实际发现并修复：

- AI `irrelevant` Content 会被声音广场默认过滤，可能导致补采资格比后端错误地更严格；
- Batch A → B → A 切换可能复用错误的平台资格；
- 机械写回曾把采集策略默认 Tab 从仓库既有 `plans` 改成 `keywords`，已恢复；
- Vue 模板排版、TypeScript 7 generated 类型边界均按仓库现有质量门禁修正，不降低 lint/typecheck 标准。

最终：

- PR #147 无外部 review；
- 无 inline review thread；
- 无 PR 评论；
- 没有手改 generated client；
- 没有新建第二套 HTTP Contract；
- 没有新增/升级依赖；
- 没有发现尚未解决的严重/重要问题。

# 文档结果

同步：

- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/roadmap/README.md`

`docs/roadmap/内网V1上线实施计划.md` 的 Stage 8F 定义仍然成立；精确资格规则继续由 Stage 8F Appendix 维护，避免 Roadmap 复制第二份实现事实。

# Git / PR

```text
开始 main:
392885def50e7b9783cd743c472f0640d57c8d7d

branch:
fix/stage8f-business-closure

PR:
#147 Stage 8F 真实业务闭环收尾

final head:
b0c231397c3f892dd059c1b67882889bceabe9b8

implementation merge commit:
fe413a423bc55f41f423c3f3f7579d4bc7fd3e96
```

# 后续

本 Change 完成后，不回头重做 Stage 8F。

当前下一最小正式开发单元仍是：

```text
Internal V1-A：最小 Docker / Compose / Config
```

它负责容器化、持久化目录、Secret 挂载、Health/Readiness、空库 Migration 与隔离 Compose Smoke；公司服务器真实部署属于后续 Internal V1-B。