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
  - ci
  - docs
affected_paths:
  - frontend/src/features/import-batches/
  - frontend/src/features/collection-strategy/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - tests/fullstack/
  - .github/workflows/stage8f-fullstack.yml
  - docs/appendix/Stage8F前后端能力矩阵与真实验收.md
  - docs/roadmap/
contracts: []
data_changes: []
---

# 目标

补齐 Stage 8F 归档后审计发现的前端状态与真实后端业务守卫不完全一致问题，使公司内网 V1 进入容器化前，首版页面的可操作状态、异步任务终态和真实业务验收保持一致。

本 Change 不重新设计 Stage 8，也不新增公共 API、Schema、Migration 或依赖。

# 可观察成功标准

- [ ] 被全局 Relevance 或启用中的 Collection Plan 引用的 Keyword Pack，前端不再显示为可直接停用；Store 同样拒绝发出无效停用请求。
- [ ] 已停用 Collection Plan 只有在当前 Relevance、Discovery 词包、目标平台关键词与 Provider Capability 均满足后端现行启用条件时，才允许前端执行“启用”。
- [ ] 创建启用 Plan 时，未配置全局 Relevance 或所选词包对目标平台没有可用关键词时，前端阻止提交并解释原因。
- [ ] Batch Supplement 只展示成功且已入库的 Batch；目标平台必须同时满足 Batch 中存在 Content、选定 Provider Config 可执行、所选评论选项对应 Capability 可执行。
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

## Verification

- Unit / Mock Browser E2E：资格判断、禁用状态、错误提示。
- Real Full-stack：成功 Excel 导入链 + Worker 失败链。

## Docs

- 更新 Stage 8F 能力矩阵与 Roadmap，只有最终验收通过后才恢复“严格完成”表述。

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
- 普通 CI 不调用真实 TikHub 或付费 LLM。
- 不新增或升级依赖。

# 已确认关键决策

1. 本任务采用 L2 最小增量方案，不新增公共资格 API。现有 API 已足以形成可靠资格快照。
2. Keyword Pack 停用资格通过当前 Global Relevance + 全部启用 Collection Plan 的现有 API 快照计算；服务端冲突校验继续保留。
3. Plan 启用资格通过现有 Pack detail、Collection Capabilities 和 Global Relevance 快照计算，并复用后端当前规则的可观察事实；服务端仍最终校验。
4. Batch Supplement 平台资格不枚举整批 Content，而是每个平台调用现有 `/contents` 查询并使用 `limit=1` 做存在性检查，最多五次。
5. Import 失败前最后处理阶段当前 Contract 没有可靠历史事实，因此不伪造“失败发生在哪一阶段”；终态页面改为准确说明“已失败/已取消 + 错误摘要/Job 状态”，成功与运行中仍展示阶段流水线。

# 实施任务

1. Red：补 Frontend Unit/Mock E2E，证明当前无效停用/启用/补采/空导出/失败阶段表达会失败。
2. Green：只修改对应 Store/API/Component，使 UI 资格与现有后端守卫一致。
3. 扩展 Full-stack fixture 和 Browser Acceptance，增加真实 Worker 失败终态。
4. 运行 Frontend、Backend 影响范围与 Full-stack 门禁。
5. 两阶段 Review；修正严重/重要问题。
6. 同步 Stage 8F 能力矩阵和 Roadmap。
7. 正常 PR/CI；全部成功后合并并归档 Change。

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

必须更新：

- `docs/appendix/Stage8F前后端能力矩阵与真实验收.md`
- `docs/roadmap/README.md`（只有验收通过后才声明 Stage 8F 严格闭环）
- 必要时同步 `docs/roadmap/内网V1上线实施计划.md`

# Git / PR

```text
start main: 392885def50e7b9783cd743c472f0640d57c8d7d
branch: fix/stage8f-business-closure
PR: pending
status: implementation in progress
```
