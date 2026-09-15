---
schema: coding-change/v1
id: CHG-20260915-104114-runtime-script-integration
title: 合并 v3.3.3 运行时与离线脚本配置
level: L3
status: in_progress
owner: Codex
branch: fix/release-archive-evidence
created: 2026-09-15
updated: 2026-09-15
completion_gate: required
depends_on: []
affected_areas:
  - governance
  - imports_test
affected_paths:
  - .agents/runtime/agent-skills.exe
  - backend/src/aima_ugc/adapters/providers/imports_test/comparison_comment_enrichment/enrich_comments.py
  - backend/src/aima_ugc/adapters/providers/imports_test/vehicle_pair_filter/filter_vehicle_pairs.py
  - changes/active/CHG-20260915-104114-runtime-script-integration/CHANGE.md
contracts:
  - 项目内 Agent_Skills Windows Runtime 安装资产
  - imports_test 两阶段人工运行默认输入配置
data_changes:
  - 无 Schema、Migration、业务数据或运行数据变化
---

# 变更摘要

把当前任务分支已提交的 Agent_Skills v3.3.3 Windows Runtime 与工作区两处离线脚本配置分批提交，通过受保护 PR 流程合入当时最新 `main`，并在交付后清理已合并的任务分支。

# 目标、范围与非目标

## 成功标准

- [ ] 项目内提交现有 Agent_Skills v3.3.3 Windows Runtime 资产；按用户决定不追加正式 Release 资产逐字节比对或 Runtime 自测。
- [ ] 车型共现过滤脚本使用用户当前指定的监测 Excel 运行结果路径。
- [ ] 评论补采脚本读取 Stage 2 `output/current/comparison_posts.jsonl`，并在初始化时移除继承的 `SSLKEYLOGFILE`。
- [ ] 两处脚本通过 Ruff、相关离线链路回归和 Change 门禁。
- [ ] PR 通过当前 head required checks 并合入当时最新 `main`；main-fresh CI、Change 归档、Issue 回写和分支清理完成。

## 范围

- 项目内现有 Agent_Skills Windows Runtime 二进制提交。
- `imports_test` 车型共现过滤与评论补采人工运行默认配置。
- 本 Change、PR、CI、合并后验收和任务分支清理。

## 非目标

- 不修改 Agent_Skills canonical 源码，不创建 Tag 或 GitHub Release。
- 不对 v3.3.3 Windows 资产做逐字节比对，不执行 Runtime `status` 或 `self-test`。
- 不调用 TikHub、LLM，不读取、生成或提交本地业务输出数据。
- 不修改正式 API、Contract、Schema、Migration、依赖、部署或 Release workflow。

## 必须保持不变

- 离线脚本继续复用正式 Reader、Mapper、车型匹配、评论 Runtime 和统一 Exporter。
- 本任务验证不得发送真实 Provider 或 LLM 请求。
- 不手工修改 Runtime 二进制内容。
- 不绕过 `main` Ruleset、required checks 或非快进保护。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 直接提交现有 v3.3.3 Windows Runtime，不做资产比对或运行时自测 | #485 / AC1；用户 2026-09-15 明确决定 | satisfied | 独有提交 `652f2877` 只更新 `.agents/runtime/agent-skills.exe`；验证明确排除比对与运行时执行 |
| R2 | 车型共现过滤脚本使用当前指定的监测 Excel 运行结果 | #485 / AC2 | satisfied | `filter_vehicle_pairs.py` 的 `INPUT_JSONL` 指向 `20260914T133339Z` 运行输出 |
| R3 | 评论补采读取 Stage 2 current 并移除继承的 SSLKEYLOGFILE | #485 / AC3 | satisfied | `enrich_comments.py` 使用 `vehicle_pair_filter/output/current/comparison_posts.jsonl` 并在入口导入后清理环境变量 |
| R4 | 两处脚本和 Change 通过本地验证及 PR required CI | #485 / AC4 | not_satisfied | 等待目标 Ruff、相关单元回归、Completion Audit 与 PR CI |
| R5 | 合入最新 main 并完成 main-fresh 验收、Issue 回写和分支清理 | #485 / AC5 | not_satisfied | 等待 PR 合并与合并后验收 |

# 实施与验证计划

1. 保留既有 Runtime 独立提交，另行提交 Change 和两处离线脚本配置。
2. 运行目标 Ruff、相关离线链路单元回归和 Change Completion 检查。
3. 合并最新 `origin/main`，通过 PR required checks 后正常合并。
4. 验证最新 `main`、main-fresh CI 和 Change 归档，回写并关闭 Issue，清理已合并分支。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| Static | required | 两处 Python 脚本 Ruff format/check |
| Unit / Workflow | required | 车型共现过滤、评论补采、离线增量链路回归 |
| Runtime execution / asset comparison | not_applicable | 用户明确要求直接提交现有 v3.3.3 资产，不执行自测或逐字节比对 |
| Contract / API / PostgreSQL | not_applicable | 不修改业务 Contract、API、Schema 或数据 |
| External Provider / LLM | not_applicable | 不修改或调用 TikHub、LLM |
| Docs | not_applicable | 只调整人工脚本当前默认输入实例；既有 README 已说明人工选择输入，未改变产品或正式运维行为 |
| Governance / CI | required | Change Completion、PR current-head required checks、main-fresh CI |

# 风险、兼容、部署与回滚

- 风险：人工路径仅在对应离线输出存在时可直接运行；目标验证只导入和测试生产复用链路，不读取真实输入。
- 风险：清理 `SSLKEYLOGFILE` 会关闭该人工脚本继承的 TLS key log；这是与同目录离线入口一致的安全处理，不改变正式服务环境。
- 兼容：不修改正式产品行为、公共 Contract、依赖、Schema、数据库、启动方式或输出格式。
- 部署：无需数据迁移或应用部署；Runtime 资产随仓库代码交付。
- 回滚：通过后续 PR revert 本次 Runtime 与脚本配置提交；不涉及业务数据回滚。

# Completion Audit

- [ ] upstream_re_read：合并前重读 #485、用户最终决定、当前 diff、目标脚本调用链与 `main` 最新状态。
- [ ] change_coverage：逐项核对 Runtime、两处脚本、验证、PR、main-fresh、Issue 和分支清理。
- [ ] reverse_audit：从脚本入口反查正式 Reader/Mapper/Runtime/Exporter 复用边界，并确认无 Provider/LLM、Contract、Schema、依赖或部署扩张。
- [ ] unresolved_cleared：Ready 前清零 `not_satisfied`，记录当前 head 本地与远程证据。

# 两阶段 Review

## Review A1：上游要求 → Change

待 Ready 前重读 #485 和用户最终决定后填写。

## Review A2：Change → 实现、测试与文档

待本地验证、独立 diff 审查和 PR current-head CI 后填写。
