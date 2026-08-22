---
schema: rvc-change/v1
id: CHG-20260822-stage8f-business-closure
title: Stage 8F 真实业务闭环收尾
level: L2
status: in_progress
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

# 目标

补齐 Stage 8F 归档后审计发现的前端状态与真实后端业务守卫不完全一致问题，使公司内网 V1 进入容器化前，首版页面的可操作状态、异步任务终态和真实业务验收保持一致。

调查过程中进一步由真实 PostgreSQL Integration 证明：Excel Import 的小红书 Content 使用 `xiaohongshu`，Collection Contract 使用 `xhs`，原 Batch Supplement target reader 直接比较二者会导致真实小红书补采目标为空。本 Change 同步修复这个实际业务断点。

本 Change 不重新设计 Stage 8，也不新增公共 API、Schema、Migration 或依赖。

# 可观察成功标准

- [ ] 被全局 Relevance 或启用中的 Collection Plan 引用的 Keyword Pack，前端不再显示为可直接停用；Store 同样拒绝发出无效停用请求。
- [ ] 已停用 Collection Plan 只有在当前 Relevance、Discovery 词包、目标平台关键词与 Provider Capability 均满足后端现行启用条件时，才允许前端执行“启用”。
- [ ] 创建启用 Plan 时，未配置全局 Relevance 或所选词包对目标平台没有可用关键词时，前端阻止提交并解释原因。
- [ ] Batch Supplement 只展示成功且已入库的 Batch；目标平台必须同时满足 Batch 中存在 Content、选定 Provider Config 可执行、所选评论选项对应 Capability 可执行。
- [ ] Excel 小红书 `xiaohongshu` Content 可以被 Collection `xhs` Batch Supplement 正确解析为补采目标。
- [ ] Voice Plaza 当前筛选没有结果时，Export 对话框仍可查看历史导出，但不能创建空 Query/Page/Selected Export。
- [ ] Import Batch `failed/cancelled` 终态不再把所有处理阶段误显示为“等待中”；页面只展示能够由当前 Contract 真实证明的终态与错误导航。
- [ ] Mock Browser E2E 覆盖上述用户交互和禁用状态。
- [ ] Real Full-stack Acceptance 保留成功 Excel 链，并新增真实 Worker 失败终态验收；测试不 Mock `/api/v1/**`。
- [ ] Frontend lint/typecheck/unit/build、Mock E2E、Backend 受影响范围测试与真实 Full-stack Acceptance 全部通过。
- [ ] Stage 8F 能力矩阵和 Roadmap 与最终实现同步。

# 范围

## Frontend

- Collection Strategy：词包停用资格、Plan 创建/重新启用资格。
- Collection Runtime：Batch Supplement 资格与 Import 失败终态表达。
- Voice Plaza：空结果 Export 资格。

## Backend

- 只在 Collection 读取 Batch target 的边界兼容 `xhs` / `xiaohongshu`，不改变 Content 持久身份和公共 Contract。

## Verification

- Unit / Mock Browser E2E：资格判断、禁用状态、错误提示。
- PostgreSQL Integration：真实 Excel 入库后 `platforms=("xhs",)` 必须读取小红书补采目标。
- Real Full-stack：成功 Excel 导入链 + Worker `invalid_import` 失败链。

## Docs

- 更新 Stage 8F 能力矩阵与 Roadmap，最终完成结论以 PR 最终 HEAD 的永久 Workflow 为准。

# 非目标

- 不新增独立 Analysis/Export 页面。
- 不修改 AI taxonomy、TikHub Provider 行为、费用/预算策略。
- 不修改公共 Pydantic HTTP Contract、OpenAPI 或 generated client。
- 不修改 PostgreSQL Schema、Migration、Job Runtime 或数据保留语义。
- 不进入 Docker/Compose、Internal V1-A 或公司服务器部署。

# 必须保持不变

- Vue Feature 只能通过现有 generated client 调正式 API；不手写第二套 HTTP Contract。
- 后端仍是最终业务守卫；前端资格判断只用于交互，不替代服务端校验。
- Batch Supplement 的 Batch/平台事实从现有正式 Content 来源查询获得，不扫描/复制数据库规则。
- Content 的持久化 platform 身份不因 Collection 别名兼容而改写。
- 普通 CI 不调用真实 TikHub 或付费 LLM。
- 不新增或升级依赖。

# 已确认关键决策

1. 本任务采用 L2 最小增量方案，不新增公共资格 API。现有 API 已足以形成可靠资格快照。
2. Keyword Pack 停用资格通过当前 Global Relevance + 全部启用 Collection Plan 的现有 API 快照计算；服务端冲突校验继续保留。
3. Plan 启用资格通过现有 Pack detail、Collection Capabilities 和 Global Relevance 快照计算，并复用后端当前规则的可观察事实；服务端仍最终校验。
4. Batch Supplement 平台资格不枚举整批 Content，而是每个平台调用现有 `/contents` 查询并使用 `limit=1` 做存在性检查，最多五次。
5. `xiaohongshu` / `xhs` 兼容只属于 Collection target reader 边界：Collection 请求 `xhs` 可匹配 stored `xhs` 或 `xiaohongshu`，返回值统一为 `xhs`。
6. Import 失败前最后处理阶段当前 Contract 没有可靠历史事实，因此不伪造“失败发生在哪一阶段”；终态页面准确说明“已失败/已取消 + 错误摘要/Job 状态”，成功与运行中仍展示阶段流水线。

# TDD / 根因证据

## Frontend 有效 Red

测试 HEAD：

```text
9d0443e7e8cb59f8ec26ad8d94ae25dcf392f710
```

CI：

```text
CI #1887
run 32559994733
```

只失败于新增的三条行为：

- Global Relevance 引用的 Keyword Pack 仍发送停用请求；
- failed/empty Import Batch 仍进入补采候选；
- Voice Plaza 空 query 仍创建 Export 请求。

后端、Contract、数据库等无关门禁保持绿色，因此是有效产品 Red。

## Backend 有效 Red

测试 HEAD：

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

# 已实施 Green

- Collection Strategy 集中资格函数读取当前 Pack detail / Relevance / enabled Plans / Provider Capability；按钮和 Store 同时 fail closed，后端继续最终校验。
- Collection Runtime 只把 succeeded + rows_ingested > 0 的 Batch 作为补采候选；按 Batch + 平台 `limit=1` 探测 Content；按选定 Provider 和评论选项收敛 Capability。
- `PostgresCollectionTargetReader` 在 Collection 边界显式兼容 `xhs` 与 stored `xiaohongshu`，并返回 Collection 机器值 `xhs`。
- Voice Plaza 空 query/page/selected 不再创建空 Export；历史 Export 仍可查看/下载。
- Import failed/cancelled 不再渲染伪造的 pending stage timeline，而展示可审计终态。
- Full-stack Acceptance 同时包含真实成功 Excel 和真实 Worker `invalid_import` 失败 fixture。
- Mock Browser E2E 增加词包资格、Batch 平台资格、失败终态和空 Export UI 断言。

# 中间验证事实

一次中间 Full-stack run 已证明失败 fixture 会由生产 Worker 真实落到：

```text
status = failed
error_code = invalid_import
```

该次 run 的产品行为正确，但旧测试选择器把 Drawer 其他区域的“等待中”误判为阶段流水线，故未计为最终通过证据；随后把断言收紧为 `.stage-row` 必须为 0，没有降低业务标准。

最终完成证据仍等待 PR 最终 HEAD 的永久 Workflow 全绿后填写。

# 实施任务

1. [x] Red：Frontend Unit 行为缺口。
2. [x] Red：真实 Excel → Batch Supplement `xhs` 平台断点。
3. [x] Green：前端资格、后端平台边界、失败终态和空 Export。
4. [x] 扩展 Mock Browser E2E 与 Real Full-stack 成功/失败验收。
5. [x] 同步 Stage 8F 能力矩阵与 Roadmap。
6. [ ] 最终 PR HEAD 完整 CI / Full-stack /专项 Workflow 全绿。
7. [ ] 两阶段 Review，无严重/重要问题。
8. [ ] PR Ready、合并、Change 归档。

# 验证计划

```text
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run test:e2e:fullstack

uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
uv run pytest tests/integration/ingestion -q
```

最终以 GitHub PR HEAD 的永久 CI 与 Stage 8F Full-stack Workflow 为准。

# 文档影响

已同步：

- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/roadmap/README.md`

`docs/roadmap/内网V1上线实施计划.md` 现有 Stage 8F 定义仍然成立；精确资格规则与成功/失败自动验收细节统一由 Stage 8F Appendix 维护，避免在 Roadmap 复制第二份实现说明。

# Git / PR

```text
start main: 392885def50e7b9783cd743c472f0640d57c8d7d
branch: fix/stage8f-business-closure
PR: #147 Stage 8F 真实业务闭环收尾
status: Draft / final verification in progress
```
