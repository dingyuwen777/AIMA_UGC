---
schema: rvc-change/v1
id: CHG-20260824-multi-keyword-pack-entrypoints
title: Excel 与 TikHub 手工发现统一多词包选择
level: L2
status: in_progress
owner: aima
branch: feature/multi-keyword-pack-entrypoints
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
affected_areas:
  - ingestion
  - collection
  - frontend
  - contracts
affected_paths:
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/ingestion/import_job.py
  - frontend/src/features/import-batches/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
contracts:
  - HTTP OpenAPI
data_changes: none
---

# 目标

统一主动按关键词处理内容的入口：Excel Import、TikHub Manual Discovery、Collection Plan 均从 Keyword Pack 选择一个或多个词包，按所选词包有效关键词并集去重后执行 OR 匹配/搜索；Batch Supplement 保持针对既有 Batch 内容补采，不引入关键词搜索。

# 成功标准

- [ ] Excel 上传必须选择 1—20 个启用词包，并冻结所选 pack id/version 与 effective_keywords。
- [ ] Excel 过滤继续只检查 Canonical title/text，任一有效关键词命中即可保留。
- [ ] TikHub Manual Discovery 改为选择 1—20 个启用词包，不再手工提交自由关键词，并冻结本次 Run 的有效关键词。
- [ ] Collection Plan 既有多词包语义保持不变。
- [ ] Batch Supplement 不接收词包或关键词。
- [ ] OpenAPI/generated client/前端交互与后端 Contract 一致。

# 范围

- Excel Import multipart Contract、快照、Worker 校验和前端上传弹窗。
- TikHub Manual Discovery Contract、后端词包解析和前端创建抽屉。
- 受影响测试、OpenAPI/generated client、数据入口文档。

# 非目标

- 不改变 Content 去重、Current/Version/Metric、AI Semantic Relevance。
- 不改变 Batch Supplement 的详情/评论补采语义。
- 不改变全局 Relevance 配置或周期 Collection Plan 的既有模型。
- 不新增数据库表或 Migration。

# 必须保持不变

- Content 稳定身份 `(platform, external_content_id)`。
- Rule Relevance 仍为 title/text 任意关键词 OR 匹配。
- PostgreSQL Job Runtime、Artifact、来源追溯与事务边界。
- generated client 必须由 OpenAPI 生成，不手工维护第二套类型。

# 关键决策

1. 不把共享 `RelevanceSnapshotV1` 直接改成多词包，避免扩大 Collection 全局 Relevance 影响面；Excel 使用独立版本化 Import Keyword Pack Snapshot。
2. Manual Discovery 的公共输入改为 `keyword_pack_ids`；后端在创建 Run 时读取并冻结有效关键词，Provider 执行仍消费已有 Run keywords，不改变下游采集执行器。
3. 多词包语义为并集去重 + OR；同一规范化匹配身份只保留一次。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Excel 上传可多选词包并按并集 OR 过滤 | user:2026-08-24-current-request | not_satisfied | 待实现与验证 |
| R2 | TikHub Manual Discovery 从词包选择且支持多选 | user:2026-08-24-current-request | not_satisfied | 待实现与验证 |
| R3 | Batch Supplement 保持不按关键词搜索 | user:2026-08-24-current-request | not_satisfied | 待回归验证 |
| R4 | Collection Plan 既有多词包语义保持 | backend/src/aima_ugc/contracts/http.py | not_satisfied | 待回归验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | 上传弹窗、Manual Discovery 多词包选择与请求结构 |
| Backend/API/PostgreSQL Integration | required | 多词包解析、冻结、Import Job 与 Collection Run 创建 |
| Contract / Generated Client | required | Pydantic → OpenAPI → Orval generated client 一致 |
| Real Full-stack Golden Path | required | 至少验证一次前端请求结构到 API/Job 冻结链路 |
| Real Provider Probe | not_applicable | 本次不改变 TikHub endpoint/响应映射，无需真实收费请求 |
| Docs / Governance / Other | required | 数据入口/采集策略相关文档同步与 Ready Check |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [x] 建立并维护 Validation Matrix
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 目标 API/Unit 测试：Stage 8B Import、Stage 8E Collection Run、相关 Keyword Pack/strategy tests。
- Contract：`python scripts/contracts/generate.py --check`，并检查 Orval generated client。
- Frontend：lint、typecheck、相关 Vitest/Playwright（按仓库现有 CI）。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/appendix/08_数据入口与统一入库实现.md`
- collection/import 模块 README（若当前描述受影响）

# 交付

- Commit：待完成
- PR：待完成
- 发布：不在本次范围
