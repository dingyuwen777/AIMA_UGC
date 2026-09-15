---
schema: coding-change/v1
id: CHG-20260915-104114-runtime-script-integration
title: 合并 v3.3.3 运行时与离线脚本配置
level: L3
status: done
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

- [x] 项目内提交现有 Agent_Skills v3.3.3 Windows Runtime 资产；按用户决定不追加正式 Release 资产逐字节比对或 Runtime 自测。
- [x] 车型共现过滤脚本使用用户当前指定的监测 Excel 运行结果路径。
- [x] 评论补采脚本读取 Stage 2 `output/current/comparison_posts.jsonl`，并在初始化时移除继承的 `SSLKEYLOGFILE`。
- [x] 两处脚本通过 Ruff、相关离线链路回归和 Change 门禁。
- [x] 任务分支同步当时最新 `origin/main` 并建立关联 #485 的 PR #486；required CI、合并、main-fresh 验收和清理继续作为正式交付门禁。

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
| R1 | 直接提交现有 v3.3.3 Windows Runtime，不做资产比对或运行时自测 | https://github.com/dingyuwen777/AIMA_UGC/issues/485 / AC1 | satisfied | 独有提交 `652f2877` 只更新 `.agents/runtime/agent-skills.exe`；Issue 已回写用户 2026-09-15 最终决定，验证明确排除比对与运行时执行 |
| R2 | 车型共现过滤脚本使用当前指定的监测 Excel 运行结果 | #485 / AC2 | satisfied | `filter_vehicle_pairs.py` 的 `INPUT_JSONL` 指向 `20260914T133339Z` 运行输出 |
| R3 | 评论补采读取 Stage 2 current 并移除继承的 SSLKEYLOGFILE | #485 / AC3 | satisfied | `enrich_comments.py` 使用 `vehicle_pair_filter/output/current/comparison_posts.jsonl` 并在入口导入后清理环境变量 |
| R4 | 两处脚本和 Change 取得可进入 PR required CI 的本地证据 | #485 / AC4 | satisfied | Ruff format/check 通过；9 个相关测试文件共 29 项通过；Secret、Docs、Docs Facts、Agent Governance 检查通过；配置断言通过 |
| R5 | 同步最新 main 并建立不绕过保护规则的正式 PR 交付路径 | #485 / AC5 | satisfied | 合并 `origin/main` 后 `origin/main...HEAD` 左侧计数为 0；PR #486 关联 #485，后续 CI、合并与 main-fresh 仍由 Issue AC5 约束 |

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

- [x] upstream_re_read：已重读 #485、用户最终决定、当前 diff、目标脚本调用链与 `origin/main` 最新状态。
- [x] change_coverage：已逐项核对 Runtime、两处脚本、验证、PR 和后续 main-fresh、Issue、分支清理门禁。
- [x] reverse_audit：已从脚本入口反查正式 Reader/Mapper/Runtime/Exporter 复用边界，并确认无 Provider/LLM、Contract、Schema、依赖或部署扩张。
- [x] unresolved_cleared：Requirement Traceability 已无 `not_satisfied`；实现侧本地证据齐备，PR current-head 与合并后证据继续由 #485 AC4/AC5 约束。

# 两阶段 Review

## Review A1：上游要求 → Change

独立重读 #485 与用户最终决定后，需求边界为：直接提交现有 v3.3.3 Runtime，不做正式资产比对或 Runtime 自测；保留两处工作区脚本修改；通过受保护 PR 合入最新 `main` 并完成后续清理。R1–R5 覆盖了 Runtime、两个脚本行为、本地可审查证据和正式 PR 交付路径；Tag、Release、Provider、LLM、Contract、Schema、依赖与部署均明确排除。

## Review A2：Change → 实现、测试与文档

Review Target 为 `origin/main...fix/release-archive-evidence`，Review 时任务分支已合并最新 `origin/main`，差异仅含 Runtime 二进制、两个脚本和本 Change。脚本变更只调整人工入口常量与环境变量清理，核心函数继续调用现有生产 Reader/Mapper、车型匹配、TikHub Runtime 抽象和统一 Exporter；`main()` 未在验证中执行，因此没有读取真实输入或发送 Provider/LLM 请求。Ruff format/check、配置导入断言和 9 个相关测试文件 29 项均通过，Secret、Docs、Docs Facts、Agent Governance 检查也通过。范围内未发现确定性 Finding。证据边界：按用户明确决定，Runtime 二进制内容、正式 Release 资产一致性和运行可用性未验证；该已接受边界必须如实保留，不能由脚本测试或后续 CI 扩大解释。
