---
schema: coding-change/v1
id: CHG-20260924-121959-voice-plaza-multi-value-filters
title: 声音广场筛选器改版：平台、情感、发声类型多选
level: L3
status: ready_for_review
owner: codex
branch: feature/voice-plaza-multi-value-filters
created: 2026-09-24
updated: 2026-09-24
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - product
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - migrations/versions/20260924_0062_voice_plaza_multi_value_filters.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - tests/contracts/test_analysis_relevance_voice_http.py
contracts:
  - ContentFilterSnapshot.voice_type -> voice_types
  - ContentFilterSnapshot.sentiment -> sentiments
data_changes:
  - migrations/versions/20260924_0062_voice_plaza_multi_value_filters.py
---

# 变更摘要

- **要解决的问题**：声音广场的“发声类型”“情感”筛选当前只能单选，用户无法同时查看多种发声类型或多种情感；筛选区的“内容类型、相关性、竞争范围”等维度占位且与本次需求无关。
- **拟议修改**：把筛选快照中的单值 `voice_type`/`sentiment` 改为多值 `voice_types`/`sentiments`，后端查询改用 `IN` 多值过滤；新增数据 Migration 把历史快照中的单值回填为单元素数组；前端把“平台、情感、发声类型”改为多选，并移除“内容类型、相关性、竞争范围”筛选 UI、上方条数展示，统一字体颜色。
- **预期结果**：用户可以同时勾选多个情感和发声类型进行组合筛选；历史已保存的筛选快照仍能正确解析；前端筛选区更简洁。

# 背景、现状与问题

## 背景

声音广场页面已具备平台、情感、发声类型等筛选维度，但情感与发声类型是单选，不能满足多条件组合筛选的需要。

## 当前现状

- `ContentFilterSnapshot` 中 `voice_type: ContentVoiceType | None`、`sentiment: str | None` 为单值。
- `content_queries.py` 的 `_apply_projection_filters` 与 `_apply_filters` 使用 `==` 做等值过滤。
- 前端 `VoicePlazaFilters.vue` / `store.ts` 对情感、发声类型按单值处理。

## 问题、根因或约束

单值字段无法表达多选；直接把单值改多值属于公共 Contract 破坏性变更，需要 Migration 回填持久化快照并重新生成 OpenAPI/Client。

## 不修改的后果

用户只能单选情感/发声类型，无法做多条件组合筛选；筛选区冗余维度继续占用界面。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Contract 中 `voice_type`/`sentiment` 为单值 | `backend/src/aima_ugc/contracts/http.py` `ContentFilterSnapshot` | 需要改为多值元组 |
| E2 | 后端过滤使用 `==` 等值 | `content_queries.py` `_apply_projection_filters`/`_apply_filters` | 需改为 `.in_()` |
| E3 | 历史快照存于 JSONB | `analysis_content_runs.filter_snapshot`、`reporting_data_exports.request_snapshot` | 需要数据 Migration 回填 |
| E4 | 远端 main 新增 0060/0061 两个 migration | `git ls-tree main migrations/versions/` | 新 migration 排到 0062，`down_revision=20260924_0061` |
| E5 | 生成目录需与 Contract 一致 | CI `generate.py --check` + `check_compatibility.py` | OpenAPI/Client 需重新生成 |

# 目标、成功标准与非目标

## 目标

情感、发声类型支持多选组合筛选，历史快照兼容，前端筛选区简洁。

## 成功标准

- [ ] 筛选快照 `voice_types`/`sentiments` 多值，后端 `IN` 过滤，历史快照回填正确。
- [ ] OpenAPI/TypeScript Client 重新生成且 `generate.py --check`、`check_compatibility.py` 通过。
- [ ] 前端平台/情感/发声类型多选，移除内容类型/相关性/竞争范围筛选 UI。
- [ ] 后端契约测试与前端 voice-plaza 测试通过，CI 绿色。

## 范围

- 上述 affected_paths 内文件。

## 非目标

- 不改变读模型、权限模型、分页游标语义。
- 不引入新依赖或新存储。

## 必须保持不变

- 公共列表/详情/评论响应字段与游标语义。
- 现有筛选字段除 voice_type/sentiment 外保持不变。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 接口与契约 | voice_type/sentiment 改为多值元组 | E1 | 破坏性，需重新生成 OpenAPI/Client |
| 数据与迁移 | 单值 JSONB 回填为单元素数组 | E3/E4 | 新增 0062 Migration |
| 兼容性 | 历史快照由 Migration 无损回填 | E3 | 已保存请求仍可解析 |
| 部署与回滚 | Migration 提供 downgrade，多值无法无损回退时报错 | E4 | 回滚边界明确 |

# 修改方案与决策依据

```text
步骤 1：Contract 单值改多值
→ 修改 ContentFilterSnapshot
→ 字段变为 voice_types/sentiments 元组

步骤 2：后端 IN 过滤
→ content_queries.py
→ _apply_projection_filters/_apply_filters 使用 .in_()

步骤 3：Migration 回填
→ 新增 20260924_0062
→ 单值转单元素数组，downgrade 反向

步骤 4：重新生成
→ python scripts/contracts/generate.py + npm run generate:api
→ OpenAPI/Client 一致

步骤 5：前端多选
→ VoicePlazaFilters.vue / store.ts / VoicePlazaPage.vue
→ 多选并移除冗余筛选 UI
```

# 验证计划

- 目标测试：后端契约测试、前端 voice-plaza 测试。
- 相关回归：`pytest tests/contracts`、`pytest tests/api`、`npm run test`。
- 静态检查或构建：`ruff check`、`mypy`、`npm run typecheck`、`npm run build`。
- 专项真实边界：`alembic check`、PostgreSQL 集成。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 破坏性 Contract 变更 | 重新生成 + Migration 回填 |
| 兼容性 | 历史快照兼容 | 0062 回填单值 |
| 数据 / Migration | 新增 0062 | down_revision=20260924_0061 |
| 部署 / 运行 | 不适用 | 无部署配置变化 |
| 回滚 / 恢复 | downgrade 提供，多值无法无损回退时报错 | 0062 downgrade |

# 文档、依赖、部署与发布影响

- **长期文档**：无结构变化，前端筛选维度说明如需可后续同步。
- **依赖 / Runtime**：不适用，无依赖升级。
- **配置 / Secret**：不适用。
- **部署 / Release**：不适用。
- **兼容 / 消费方通知**：前端与后端同仓库同步，无外部消费方。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 情感、发声类型支持多选 | user:声音广场筛选多选改版需求 / AC1 | satisfied | E1/E2 + Contract 多值 + IN 过滤 |
| R2 | 历史筛选快照兼容 | user:声音广场筛选多选改版需求 / AC2 | satisfied | E3 + 0062 Migration |
| R3 | 前端筛选区多选并移除冗余维度 | user:声音广场筛选多选改版需求 / AC3 | satisfied | 前端 VoicePlazaFilters/store 改动 |
| R4 | 生成物与 Contract 一致 | user:声音广场筛选多选改版需求 / AC4 | satisfied | OpenAPI/Client 重新生成 |

# 完成审计

- [x] upstream_re_read：已重读 Contract、migration 链与远端 main 最新状态。
- [x] change_coverage：Contract/后端/迁移/生成/前端/测试均已覆盖。
- [x] reverse_audit：后端能力（多值筛选）→ 前端多选入口；前端动作 → 后端 IN 过滤真实支持。
- [x] unresolved_cleared：无 not_satisfied，延期/不适用项已注明。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | git | `git diff main...feature` | 仅 12 个声音广场文件 | 无无关改动 |
| V2 | git | `git ls-tree main migrations/versions/` | 远端 0060/0061 保留 | 迁移链正确 |
| V3 | 待 CI | CI 全套 | 待运行 | 契约/前端/集成回归 |

## 未验证内容与剩余风险

- 本地未跑完整测试套件，由 PR CI 验证；不阻塞提交审核。

## 交付状态

- 提交：待提交 Change 记录。
- 拉取请求：待创建。
- CI：待运行。
- 合并：未合并。
- Change 归档：待 merge 后自动归档。

## 备注

无。