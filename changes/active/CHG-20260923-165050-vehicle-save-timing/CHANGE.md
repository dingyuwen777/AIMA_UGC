---
schema: coding-change/v1
id: CHG-20260923-165050-vehicle-save-timing
title: 车型编辑保存阶段耗时诊断
level: L2
status: in_progress
owner: yuwen.ding
branch: diag/vehicle-save-timing
created: 2026-09-23T16:50:50+08:00
updated: 2026-09-23T16:50:50+08:00
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

# 修改方案与决策依据

1. 复用现有结构化日志与单调计时工具，在更新服务和 Repository 的真实阶段边界采样；只让慢请求/慢失败提升到 WARNING。
2. 日志仅包含稳定 ID、字段名称、结果和耗时，不携带品牌/车型文本、别名、Payload、SQL 参数或 Secret。
3. 以针对性测试验证快/慢/失败及事务行为，更新 PostgreSQL 排障文档说明如何把 request_id 与阶段、数据库锁等待关联。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保存日志具有 request_id 与完整阶段耗时 | #583 / AC1 | not_satisfied | 实现及测试后补充 |
| R2 | 快请求低噪声、慢成功/失败可定位且不泄露业务文本 | #583 / AC2 | not_satisfied | 实现及测试后补充 |
| R3 | 保存与审计语义不变，文档和回归同步 | #583 / AC3 | not_satisfied | 实现及测试后补充 |
| R4 | 与 #582 独立交付且排除本地工具设置 | #583 / AC4 | not_satisfied | PR diff 与 Git 状态后补充 |

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

# 完成审计

- [ ] upstream_re_read：重新读取 #583 的 AC1—AC4 和保存不自动重筛的正式产品事实。
- [ ] change_coverage：确认本 Change 未遗漏上游要求，也未纳入 .codex/config.toml。
- [ ] reverse_audit：从日志字段回查真实阶段，从更新服务回查日志可定位性，并核对验证矩阵。
- [ ] unresolved_cleared：所有 not_satisfied 清零；未验证服务器性能根因仍如实保留。

# 风险与交付

- 主要风险：记录原始文本或正常高频日志；通过字段白名单与慢请求阈值控制。
- 兼容 / Migration / 数据：无公共 Contract 或 Schema 变化；日志增加可通过回退代码撤销。
- 验证、Review、CI、PR、merge、main-fresh 和 Issue Closure：施工中，待真实证据更新。
