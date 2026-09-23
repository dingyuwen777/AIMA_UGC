---
schema: coding-change/v1
id: CHG-20260923-165050-vehicle-save-timing
title: 车型编辑保存阶段耗时诊断
level: L2
status: ready_for_review
owner: yuwen.ding
branch: diag/vehicle-save-timing
created: 2026-09-23T16:50:50+08:00
updated: 2026-09-23T17:34:20+08:00
completion_gate: required
depends_on: []
affected_areas:
  - administration
  - vehicles
  - logging
affected_paths:
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/platform/logging/
  - tests/
  - docs/appendix/01_PostgreSQL查询与调试实战.md
contracts: []
data_changes: []
---

# 变更摘要

为管理员编辑车型的现有同步保存链增加低噪声、可关联请求的阶段计时，只帮助后续定位服务器慢点；不在缺少服务器实测时声称已解决性能问题。

# 背景、现状与问题

当前前端只发一次 `PUT /api/v1/vehicle-models/{id}`，保存成功后本地更新车型，不自动重筛。API 已有超过 1 秒的整体 `api.request_slow` 日志，但更新事务内部依次执行连接取得、车型行锁、品牌校验、目录版本推进、车型/别名写入、审计与引用投影，现有日志无法区分这些阶段。服务器实际瓶颈、Migration 状态和并发负载尚未测量；本次只补定位证据。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 作用 |
| --- | --- | --- | --- |
| E1 | 保存只发一次 PUT 且成功后本地更新 | `frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/CatalogConfigurationPanel.vue` | 不增加前端或历史重筛操作 |
| E2 | API 已记录整体慢请求耗时和 request_id | `backend/src/aima_ugc/bootstrap/api.py` | 新阶段事件沿用同一 request_id |
| E3 | 更新在同一事务中锁车型和品牌、推进目录版本并写审计/投影 | `backend/src/aima_ugc/bootstrap/administration_http.py`、`backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py` | 仅围绕现有阶段计时，不改变事务语义 |

# 目标、成功标准与非目标

- 目标：一次慢保存能从同一 request_id 判断连接取得、车型锁、品牌、版本、更新、别名、审计、投影和提交中哪一步耗时。
- 成功标准：正常快速请求不输出 WARNING；慢成功和慢失败均输出稳定安全事件，字段为 ID、变更字段名、结果与阶段毫秒值。
- 非目标：此 Change 不猜测或直接修服务器性能根因，不修改前端行为、HTTP Contract、Schema、Migration、历史重筛，也不部署或执行生产操作。
- 必须保持：现有管理员权限、事务审计、异常映射、别名和车型状态语义、保存不自动重筛；本地 `.codex/config.toml` 不属于交付。

# 约束与意图决策

只补慢保存的定位证据，不把日志当成性能修复；保存仍是同步事务操作，不能自动触发历史重筛。只记录预先确定的安全字段；服务器耗时、数据库锁与连接池状态尚无实测结论。本次不改变 public Contract、Schema、配置或生产数据。

# 修改方案与决策依据

在现有保存调用链直接测量阶段，避免新增独立性能探针或改变写入路径；仅慢请求输出一条结构化日志，既能与 API 请求关联，也不会让正常编辑产生高频告警。阶段计时在失败时保留已发生的等待时间，事务提交成功后才标记成功。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保存日志具有 request_id 与完整阶段耗时 | #583 / AC1 | satisfied | `update_vehicle_model` 与 `update_model` 真实边界计时；单元快/慢/失败回归通过；PostgreSQL 集成回归已写，等待 CI 隔离数据库验证 |
| R2 | 快请求低噪声、慢成功/失败可定位且不泄露业务文本 | #583 / AC2 | satisfied | 默认 1000 毫秒阈值；只记录字段名、ID、结果和毫秒值；无数据库单元 2/2 通过，敏感文本断言通过 |
| R3 | 保存与审计语义不变，文档和回归同步 | #583 / AC3 | satisfied | 更新仍在原事务提交并写审计；新增集成断言成功更新有审计、失败无审计，既有 9 SQL 回归交由 PR CI；PostgreSQL 排障文档已同步；没有自动重筛调用 |
| R4 | 与 #582 独立交付且排除本地工具设置 | #583 / AC4 | satisfied | 独立 `diag/vehicle-save-timing` / PR #584；仅显式添加项目路径，`.codex/config.toml` 保持工作区原样、不提交；合并仍等待两批各自门禁 |

# 计划改动

1. 复用现有结构化日志与单调计时工具，在更新服务和 Repository 的真实阶段边界采样；只让慢请求/慢失败提升到 WARNING。
2. 日志仅包含稳定 ID、字段名称、结果和耗时，不携带品牌/车型文本、别名、Payload、SQL 参数或 Secret。
3. 以针对性测试验证快/慢/失败及事务行为，更新 PostgreSQL 排障文档说明如何把 request_id 与阶段、数据库锁等待关联。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 阶段计时器、快慢阈值、失败与安全字段 |
| 接口 / 契约 | not_applicable | 不修改 HTTP、Pydantic、OpenAPI 或生成 Client |
| 集成 / 持久化 / 运行依赖 | required | 现有 PostgreSQL 管理服务更新回归，确认事务与审计不变 |
| 用户 / 工作流验收 | not_applicable | 页面保存行为不变，诊断事件是运维侧结果 |
| 跨组件关键路径 | not_applicable | 不改 API/前端接线；当前整体慢请求日志已覆盖 API 入口 |
| 外部依赖 / 供应方探测 | not_applicable | 不改 TikHub/LLM/远端接口 |
| 构建 / 打包 / 运行 | required | Python 静态检查与相关正式测试 |
| 文档 / 治理 / 其他 | required | 排障文档、Change Ready、PR CI 与安全字段审查 |

# 风险、兼容性、迁移与回滚

- 主要风险：记录原始文本或正常高频日志；通过字段白名单与慢请求阈值控制。
- 兼容 / Migration / 数据：无公共 Contract 或 Schema 变化；日志增加可通过回退代码撤销。
- 回滚：回退本次代码与文档即可停止新日志；已写入的业务数据和审计不受影响，不执行数据库降级。

# 文档、依赖、部署与发布影响

按 targeted 影响只更新 PostgreSQL 排障说明，解释如何关联 request_id、阶段含义及不能仅凭耗时推断根因。无新依赖、配置、Migration 或部署动作；正式服务器仍需独立部署授权。诊断代码发布后才能收集服务器真实慢请求证据。

# 完成审计

- [x] upstream_re_read：重新读取 #583 的 AC1—AC4 和 `docs/product/02_当前产品能力与用户流程.md` 中保存不自动重筛的正式事实。
- [x] change_coverage：AC1—AC4 均在实现、测试、文档及分批 PR 边界中覆盖；`.codex/config.toml` 未纳入提交范围。
- [x] reverse_audit：从日志字段回查各真实阶段，从更新服务回查慢成功/失败日志、事务提交和既有整体 API 慢请求关联；没有新前端入口或重筛行为。
- [x] unresolved_cleared：所有本 Change 实现项无 `not_satisfied`；PostgreSQL 集成运行与 PR CI/Review/merge 仍是交付门禁，不能因本地单元通过声称已验证服务器性能根因。

# 完成证据与状态

本地证据：`tests/unit/platform/test_vehicle_update_timing.py` 2/2 通过，包含提交失败结果；修改文件 Ruff check/format 与三个生产模块 Mypy 通过；`git diff --check` 和 Change Ready Check 通过。PostgreSQL Secret 文件缺失使本机集成测试无法启动，新增集成及既有 9 SQL 查询回归等待 PR 的隔离数据库 CI。日志旧测试因本机 pytest 临时目录权限失败，非断言失败。Review、CI、PR #584、merge、main-fresh 和 Issue Closure 未完成前禁止合并或声称已交付。
