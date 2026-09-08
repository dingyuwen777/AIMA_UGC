---
schema: coding-change/v1
id: CHG-20260909-074535-frontend-security-patches
title: 修复前端工具链已知安全漏洞
level: L3
status: in_progress
owner: codex
branch: fix/frontend-security-patches-20260909
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - frontend-toolchain
affected_paths:
  - frontend/package.json
  - frontend/package-lock.json
contracts: []
data_changes: []
---

# 背景与目标

上游为 Issue #397 和用户明确批准的独立安全修复。main 基线 28d3c1c601c94e9e9d38522c828b3cbd0e37ddb5；管理员 PR #396 的 7149c4d7 提交在 CI 34288968567 的前端安全审计失败，两个漏洞分别是 js-yaml 的 GHSA-2883-xcg3-v3hh 与 Vitest 的 GHSA-82fw-gwwq-j7x9。保留现状会持续阻塞受保护合并并保留已知漏洞。

只更新 Vitest 4.1.10 → 4.1.11 家族、Orval 下的 js-yaml 4.3.1 → 4.3.2；Orval 保持 8.24.0，使用父依赖限定的 npm override。隔离候选 npm 解析已通过、392 包审计为 0 漏洞，正式安装与回归仍需执行。验收以 Issue AC1–AC4 为准，不由本 Change 创造第二套完成标准。

不改变 Node 24.19.0、npm 11.17.0、其他依赖、框架、公共 Contract、Schema、数据、业务功能、Figma、生产部署或安全阈值。管理员实现仍在原分支；本分支从 main 开始，不混入用户已有工作流指南修改。

# 方案与兼容边界

采用用户批准的两个补丁。仅修高危 js-yaml 可消除 high 阈值阻塞但遗留中危 Vitest，因此不采用。npm audit fix --force 建议的 Orval 7.11.2 降级存在破坏性，不采用。当前没有更低风险且能够同时满足两个安全修复的已验证方案。

主要风险为 YAML 解析及测试工具行为变化。通过锁定安装、依赖树、审计、既有 Unit、Orval 正式生成和漂移检查、lint/typecheck/build/Browser、适用 Full-stack 与完整 CI 验证。无数据迁移、API 或部署顺序变化；补丁失败时保留结果调查，恢复旧版本会重新引入漏洞，不作为安全修复完成。正式文档不复制 patch 版本表，Docs Impact 为 not_applicable，精确版本仍由 manifest/lock 维护。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 仅两个补丁家族、锁定安装及其他版本保持 | https://github.com/dingyuwen777/AIMA_UGC/issues/397 / AC1 | not_satisfied | 正式分支实施和 npm ci 后核验 |
| R2 | 安全审计及安全门禁保持 | https://github.com/dingyuwen777/AIMA_UGC/issues/397 / AC2 | not_satisfied | 原 CI 审计失败为 Red；候选审计通过不代替正式安装验证 |
| R3 | 前端完整回归与 Client 一致 | https://github.com/dingyuwen777/AIMA_UGC/issues/397 / AC3 | not_satisfied | 正式安装后执行既有测试及生成漂移检查 |
| R4 | 独立两阶段审查及完成定义核对 | https://github.com/dingyuwen777/AIMA_UGC/issues/397 / AC4 | not_satisfied | 实现和本地验证后执行 |
| R5 | 当前提交正式 CI | https://github.com/dingyuwen777/AIMA_UGC/issues/397 / AC3 | explicitly_deferred | 仅按项目提交→push→CI时序后置，合并前必须成功，不豁免 |
| R6 | main 验证、归档、需求关闭、清理及管理员分支消费 | https://github.com/dingyuwen777/AIMA_UGC/issues/397 / AC4 | explicitly_deferred | 用户已批准完整交付；依赖安全修复合并后执行，最终交付前必须完成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Component | required | 全部前端 Unit 验证新 Vitest 下既有行为 |
| Contract / Generated Client | required | 运行正式 Orval，生成 Client 与当前 OpenAPI 无漂移 |
| Backend/API/PostgreSQL Integration | not_applicable | 仅前端 devDependencies，无后端/数据库代码或依赖变化；正式 CI 若按包边界选择此层仍执行 |
| Browser Mock Acceptance | required | 全部既有浏览器测试验证构建工具链兼容 |
| Real Full-stack Golden Path | required | 正式 CI 的 package 影响闭包及真实应用接线 |
| External Provider Probe | not_applicable | 未改 Provider 协议，不执行付费调用；安全通告与 npm 官方元数据已核验 |
| Build / Package / Runtime | required | npm ci、依赖树、audit、lint/typecheck/build，正式 CI 的 package/运行验证 |
| Docs / Governance | required | Change、Issue、差异/Secret、两阶段 Review 与 CI；长期文档无需复制版本 |

# 实施计划

1. Issue / 本地分支 / Change → 建立可审查的独立安全修复范围 → 最小治理提交、首次 push、早期普通 PR（逻辑未就绪）。
2. frontend/package.json 与 package-lock.json → 应用两个补丁候选 → npm ci、依赖树、audit 和结构化锁文件差异核验。
3. 前端既有生成/测试/构建入口 → 验证工具链兼容与真实接线 → lint、Unit、generate:api、build、Browser 及正式 CI 的完整适用层；纯配置使用实际审计 Red/Green，不新增版本号测试。
4. Change / PR / Issue → 独立审查与当前 head CI 后合并 → main 新鲜 CI、自动归档、管理员分支正常合入 main、需求关闭与分支清理。

# Completion Audit

- [ ] upstream_re_read：Ready 前重读 Issue #397 的 AC1–AC4、用户批准及项目版本门禁。
- [ ] change_coverage：检查两个修复、版本保持、安装/审计/生成/测试及完整交付覆盖。
- [ ] reverse_audit：manifest → lock → npm ci → 实际依赖树 → 生成与测试/构建消费者；不新增业务入口。
- [ ] unresolved_cleared：本地实现与审查全部完成后核对，CI/main 继续单独阻止提前完成。

# 当前证据

- 原 CI 34288968567 安全审计退出 1：2 moderate、2 high 依赖条目，对应两个上游漏洞。
- 隔离候选在 Node 24.19.0 / npm 11.17.0 下解析：392 包、0 漏洞，退出 0；锁文件只变动 9 个包版本，没有增删包。
- 独立分支已从已同步 main 创建，生产依赖尚未修改，本记录不表示 Ready 或可合并。
