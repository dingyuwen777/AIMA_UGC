---
schema: rvc-change/v1
id: CHG-20260824-excel-import-submit-state
title: 修复 Excel 导入按钮假忙碌与失败反馈
level: L2
status: in_progress
owner: aima
branch: fix/excel-import-submit-state
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on:
  - CHG-20260824-multi-keyword-pack-entrypoints
affected_areas:
  - frontend
affected_paths:
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportUploadDialog.vue
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/CollectionRuntimePage.vue
  - frontend/src/features/import-batches/store.ts
  - frontend/tests/collection-runtime.spec.ts
  - frontend/e2e/collection-runtime.spec.ts
contracts: []
data_changes: []
---

# 目标

修复采集运行中心 Excel 导入弹窗把“不可提交”错误表现成“系统正在忙”的问题，并让真实上传中的状态与请求失败结果对用户可见且可恢复。

# 成功标准

- [ ] 未选择文件、未选择关键词包、词包加载中或无可用词包时，“开始导入”不可提交，但鼠标不显示忙碌转圈。
- [ ] 只有真实 Excel 创建请求进行中时，按钮才表达 busy 状态并显示“正在创建…”；请求成功或失败后 busy 状态都会复位。
- [ ] Excel 创建请求失败时，错误直接显示在导入弹窗内，用户不需要透过遮罩寻找页面级错误。
- [ ] 现有 Excel multipart、Keyword Pack 多选、Import Job、后端 Contract、Worker 和数据库语义保持不变。

# 范围

- Excel 导入弹窗的提交资格、disabled/busy 视觉语义和可访问状态。
- 页面向弹窗传递现有 Store 错误。
- Store 上传失败后的 busy 复位回归测试。
- Browser Mock Acceptance 覆盖未就绪、真实提交中和失败后的用户可见状态。

# 非目标

- 不修改 Excel 上传 API、OpenAPI/generated client 或 multipart 字段。
- 不修改后端 XLSX 校验、Artifact、Import Job、Worker、数据库或去重/过滤逻辑。
- 不新增上传进度百分比、超时策略或取消上传机制。
- 不修改 TikHub 补采交互。

# 必须保持不变

- `POST /api/v1/import-batches` 继续提交 `file + keyword_pack_ids[]`。
- 多关键词包并集 OR 语义不变。
- Store 继续通过现有 `uploadImportBatch()` 调 generated client，不建立第二套请求实现。
- 不升级 Vue、Pinia、Playwright、Vitest 或其他依赖。

# 关键决策

1. 根因分为“状态语义”和“错误反馈”两层处理：disabled 不再统一使用 `cursor: wait`；只有 `uploading=true` 的真实请求阶段才表达 busy。
2. 提交资格在弹窗内用单一 `canSubmit` 计算，要求文件、至少一个关键词包、词包已加载且当前不在上传中；不把未满足前置条件伪装成运行中。
3. 保留 Store 现有 `try/finally` 作为 busy 状态收尾机制，并用回归测试证明失败路径会恢复 `uploading=false`。
4. 请求错误复用现有 `store.error`，只增加弹窗内展示，不新增错误状态源。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 未实际导入时悬停“开始导入”不能表现为一直转圈 | user:2026-08-24-excel-import-spinner | not_satisfied | 待实现并由 Browser Mock 验证 |
| R2 | 点击开始导入后的 busy 状态必须只对应真实请求，且成功/失败后可恢复 | user:2026-08-24-excel-import-spinner | not_satisfied | 待实现并由 Store/Browser 回归验证 |
| R3 | 前端组件应正确表达 Loading / Error / Empty / Data，而不是让错误被遮罩隐藏 | frontend/README.md | not_satisfied | 待实现弹窗内错误展示并验证 |
| R4 | 不改变 Excel Import HTTP/Job/Worker/数据库业务链 | docs/blueprint/04_后端任务API与前端.md | not_satisfied | 最终 diff/Contract 检查确认无后端与 generated 变更 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | 覆盖未选择文件/词包时 disabled 非 busy、真实 POST 期间 busy、失败后恢复与弹窗内错误 |
| Backend/API/PostgreSQL Integration | not_applicable | 本次不修改服务器规则、数据库、Job/Worker 或持久化行为 |
| Contract / Generated Client | not_applicable | 本次不修改 Pydantic/OpenAPI/generated client；最终 diff 复核确认 |
| Real Full-stack Golden Path | not_applicable | 不改变前后端接线或真实导入链；现有永久 Full-stack CI 只作为额外回归，不作为本次独立风险主证据 |
| Real Provider Probe | not_applicable | 与外部 Provider 无关 |
| Docs / Governance / Other | required | Change、前端 lint/typecheck/build 与仓库永久 CI；正式功能文档语义不变时记录无需同步依据 |

# Completion Audit

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力/边界审计，并复核 Validation Matrix；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [x] 调查当前实现和事实源
- [ ] 建立失败测试并读取 Red 证据
- [x] 建立并维护 Validation Matrix
- [ ] 完成最小实现
- [ ] 同步受影响文档或记录无需同步依据
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- Browser Red/Green：`cd frontend && npx playwright test e2e/collection-runtime.spec.ts`
- Store Red/Green：`cd frontend && npm test -- --run tests/collection-runtime.spec.ts`
- 前端静态检查：`cd frontend && npm run lint && npm run typecheck && npm run build`
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`
- 最终：PR 永久 CI 全绿；若永久 Full-stack workflow 触发，同样要求通过。

## 新鲜证据

- 尚未执行。

# 文档影响

- `frontend/README.md` 与 Blueprint 已明确 Page/Component 负责 Loading/Error/Empty/Data，本次不改变正式功能或接口语义；预计无需修改长期文档。
- 当前 Change 记录根因、行为修复与验证证据。

# 交付

- Commit：待验证后填写。
- PR：待创建。
- 发布：仅合并代码，不执行部署。
