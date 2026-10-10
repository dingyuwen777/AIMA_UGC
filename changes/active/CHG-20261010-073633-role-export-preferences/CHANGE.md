---
schema: coding-change/v1
id: CHG-20261010-073633-role-export-preferences
title: 落实多用户角色权限与个人 Excel 导出配置
level: L3
status: in_progress
owner: Codex
branch: feat/714-role-export-preferences
created: 2026-10-10T07:36:33+08:00
updated: 2026-10-10
completion_gate: required
depends_on: []
affected_areas: [identity, reporting, frontend, workbench, content]
affected_paths: [backend/src/aima_ugc, frontend, migrations, tests, docs]
contracts: [HTTP, ExportColumnCatalogResponse, DataExportRequest, ExportColumnDefault]
data_changes: [reporting_data_exports, reporting_user_export_column_defaults]
---

# 变更摘要

Requirement-Source: #714。管理员负责生产和治理，普通用户查看共享业务结果并导出。最终路由执行显式认证/角色策略，Export 执行归属和列权限，个人字段默认及浏览器状态按 Principal 隔离。

# 背景、现状与问题

## 背景

用户已批准完整实现。decision epoch 2：2026-10-10 最新指令要求完成修改并执行本地验证，先不要合并远程 main；撤销此前本地验证豁免，保留开发分支供验收。

## 当前现状

起点 main `6f9779c56fdb3b4d3a83d8fb0cdd02e4cb9dd79d`。已有两角色、飞书 Session、多企业 Connector、工作台用户布局和 Export Durable Job。最终应用在主工厂后安装扩展路由。

## 问题、根因或约束

路由缺整体授权清单，管理 API 与 UI 边界不一致；Export 只有 JSON 快照创建者，没有查询授权；无个人默认列及可靠浏览器身份隔离。

## 不修改的后果

普通用户可能访问管理数据、产生管理副作用、读取他人文件，账号切换可能继承旧用户状态。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 扩展安装在主工厂之后 | backend/src/aima_ugc/entrypoints/api_main.py | 最终 assembly 后完整授权检查 |
| E2 | Export 快照有 requested_by，读取无 Principal | backend/src/aima_ugc/bootstrap/reporting_http.py | 明确 created_by 与对象授权 |
| E3 | 视频 prepare 可以创建采集 Job | backend/src/aima_ugc/bootstrap/content_playback_service.py | 观看保留，收费刷新管理授权 |
| E4 | 最新用户指令要求本地验证，先不合并远程 main | #714 与用户“修改完本地验证没问题之后，先不要合并到远程主分支” | epoch 2 本地验证 required；不 merge；保留开发分支供验收 |

## 推断与待确认

正式飞书企业授权及生产环境不在本轮执行范围，最终报告明确未验证；当前先完成本地交付，远程 CI 在后续获准的 PR 阶段取得。

# 目标、成功标准与非目标

## 目标

完整实现 #714 的两角色、个人 Export 及会话隔离。

## 成功标准

以 #714 / AC1–AC22 为唯一完成定义；不从本 Change 或测试数量反推需求。

## 范围

Identity、最终 API assembly、Reporting/persistence/Contract/Migration、前端 identity/shell/taskcenter/workbench/voice-plaza、适用回归与正式文档。

## 非目标

不增加角色/RBAC/通用偏好/依赖；不部署、发布或操作生产；不执行付费 Probe，不合并远程 main。

## 必须保持不变

共享业务读取、管理员全部功能、工作台统计身份和刷新、Legacy 标签、导出冻结/重试/七天生命周期、原技术路线与锁定版本。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Parent 根 checkout 单 Writer；前端和测试分别在隔离 worktree 实现后提交整合，独立只读 Review | AGENTS.md、E1 | 避免共享 checkout 写冲突 |
| 接口与契约 | 显式 route policy，Reporting 专用个人默认 API | #714 / AC2、AC16 | Pydantic→OpenAPI→Orval |
| 数据与迁移 | nullable created_by、可靠回填、个人配置无 Identity FK | #714 / AC12、AC15 | Reporting 唯一 Owner |
| 错误与失败语义 | 401/403/私有 Export 404/422/409 | #714 / AC3、AC13、AC16 | 副作用之前拒绝 |
| 兼容性 | 原请求快照保留，字段权限不修改统一 Renderer | #714 / AC12、AC14 | 历史文件下载再次检查列 |
| 部署与回滚 | 增量迁移后整体应用交付，回滚保留新增配置 | #714 / AC19 | 旧漏洞版本必须先访问隔离 |

# 修改方案与决策依据

## 最小充分方案

1. 最终路由清单及 Principal 请求缓存、Cookie 同源检查 → Identity/bootstrap → 每实际路由显式归类，无未知匿名入口 → 本地 API 拒绝与无副作用回归。
2. Export created_by/索引/角色列与默认表/API → Reporting/persistence/Contract/Migration → 所有读取先 owner 过滤，默认 revision 原子并发 → 本地 PostgreSQL、Contract、XLSX 回归。
3. Shell/声音广场/任务源/刷新/会话隔离及导出弹窗 → frontend → 普通用户保留只读与导出，无管理请求，草稿稳定 → 本地 Unit/Browser/真实 Full-stack。
4. 文档、独立 Review、上游 Completion、保留本地提交与开发分支、任务测试资源清理 → 对应交付证据回写；Human Local Acceptance PENDING，不执行 push/PR/merge。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1 | 在最后 assembly 安装 policy，覆盖所有扩展与隐藏路由 |
| D2 | E2 | 明确业务归属用于安全查询和先过滤后分页 |
| D3 | E3 | 在收费/写入分支前拦截，保留普通用户现有媒体读取 |

## 备选方案与取舍

仅修各路由易遗漏未来扩展；数据库动态 RBAC 超出两角色需求。采用固定显式 Route policy + require_administrator + Reporting 对象归属，复用现有 Owner。仅依赖 JSONB requested_by 查询弱约束且不利索引，采用 nullable created_by 增量兼容回填。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 飞书/Session 身份 | #714 / AC1 | not_satisfied | 等待实现与远程回归 |
| R2 | 最终路由完整 policy | #714 / AC2 | not_satisfied | 等待实现与远程回归 |
| R3 | 管理 API 拒绝无副作用 | #714 / AC3 | not_satisfied | 等待实现与远程回归 |
| R4 | 共享只读与旁路 | #714 / AC4 | not_satisfied | 等待实现与远程回归 |
| R5 | 配置/CSRF | #714 / AC5 | not_satisfied | 等待实现与远程回归 |
| R6 | 导航/Route | #714 / AC6 | not_satisfied | 等待实现与远程回归 |
| R7 | 声音广场列表 | #714 / AC7 | not_satisfied | 等待实现与远程回归 |
| R8 | 内容详情 | #714 / AC8 | not_satisfied | 等待实现与远程回归 |
| R9 | 任务中心 | #714 / AC9 | not_satisfied | 等待实现与远程回归 |
| R10 | 共享数据刷新 | #714 / AC10 | not_satisfied | 等待实现与远程回归 |
| R11 | 布局与通知 | #714 / AC11 | not_satisfied | 等待实现与远程回归 |
| R12 | Export 创建者 Schema | #714 / AC12 | not_satisfied | 等待实现与远程回归 |
| R13 | Export 对象授权 | #714 / AC13 | not_satisfied | 等待实现与远程回归 |
| R14 | 列授权 | #714 / AC14 | not_satisfied | 等待实现与远程回归 |
| R15 | 默认字段持久化 | #714 / AC15 | not_satisfied | 等待实现与远程回归 |
| R16 | 默认 API | #714 / AC16 | not_satisfied | 等待实现与远程回归 |
| R17 | 默认弹窗与冻结 | #714 / AC17 | not_satisfied | 等待实现与远程回归 |
| R18 | 会话隔离 | #714 / AC18 | not_satisfied | 等待实现与远程回归 |
| R19 | Migration/Contract/回滚 | #714 / AC19 | not_satisfied | 等待实现与远程回归 |
| R20 | 本地分层验证 | #714 / AC20 | not_satisfied | epoch 2 本地 required；验证进行中 |
| R21 | 独立 Review/文档/兼容 | #714 / AC21 | not_satisfied | 等待实现与远程回归 |
| R22 | 保留分支、不合并与任务清理 | #714 / AC22 | not_satisfied | 交付阶段清理本任务临时资源；保留开发分支 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| backend/src/aima_ugc | Identity/Reporting/Route policy | 服务端权限和个人配置 | R1–R5、R11–R16 |
| frontend | 原有 Feature 角色展示/默认字段/身份隔离 | 用户可见体验与异步安全 | R6–R10、R17–R18 |
| migrations、tests、docs | 增量迁移、真实回归、当前事实同步 | 兼容与可审查交付 | R19–R22 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 权限、默认列、身份换代、任务源；本地 pytest/Vitest |
| 接口 / 契约 | required | OpenAPI/Orval 正式生成及本地漂移检查 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL 归属、revision 并发、Job 无副作用、XLSX 重读 |
| 用户 / 工作流验收 | required | 本地 Playwright 角色/默认字段/会话；人工本地验收 PENDING |
| 跨组件关键路径 | required | 本地真实双角色 API/DB/Worker/Browser 关键链 |
| 外部依赖 / 供应方探测 | not_applicable | 本次不变更飞书远端协议；正式企业/生产验收留待候选环境，不冒充已通过 |
| 构建 / 打包 / 运行 | required | 本地 typecheck/build；远程 CI 在后续 PR 阶段 |
| 文档 / 治理 / 其他 | required | 正式文档、Route 清单、Completion/独立 Review/CI；写入 Contract preflight |

## 验证计划

epoch 2 本地验证 required。复用 `scripts/dev/validate_changed.py --base origin/main` 对应 CI 分类，pytest/PostgreSQL、Vitest/Playwright/fullstack、typecheck/build、Generated Contract/Change Gate。测试失败和修复后结果分别保留，不将自动测试冒充人工验收。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 管理旁路、历史文件、旧异步覆盖 | 逐最终路由、owner/列、identity epoch 回归 |
| 兼容性 | 保留现有合法行为，普通用户权限按任务收紧 | #714 固定角色矩阵 |
| 数据 / Migration | 增量 nullable owner 与专用配置 | 只回填合法字符串，不改 Content/Artifact |
| 部署 / 运行 | 整体版本联动，不在本次部署 | 未授权生产操作 |
| 回滚 / 恢复 | 应用回滚保留列/表/个人配置 | 旧漏洞版本回滚先访问隔离 |

# 文档、依赖、部署与发布影响

同步产品权限、Reporting/API、Schema/部署兼容。无依赖/Runtime 升级。必要显式身份模式沿用现有飞书 Connector/Session。无 Release/Deploy 授权。

# 完成审计

- [ ] upstream_re_read：重读 #714 与适用项目事实。
- [ ] change_coverage：逐 AC 核对施工范围。
- [ ] reverse_audit：API/UI、Schema/Owner、异步/文件/身份边界审计。
- [ ] unresolved_cleared：清零未满足项，依据证据不伪造。

# 完成证据与状态

## 新鲜证据

起点 fetch main 成功；Issue candidate create Contract PASS，平台创建 #714，epoch 2 candidate pre-write PASS、平台更新后 live 重读与 candidate 字节相同。本地后端、前端、PostgreSQL 与迁移验证证据正在收口。

## 未验证内容与剩余风险

本地验证进行中。正式飞书/生产候选环境未执行，不能宣称生产可发布。

## 交付状态

本地任务分支开发中；已提交后端、测试、前端 checkpoint，尚无 push/PR/CI/merge。Human Local Acceptance PENDING；远程 main 合并暂停。

## 备注

顶层 changes 为项目正式 carrier，历史多 schema 由项目 validator 保留；Source CLI 不接受混合 legacy carrier，因此用 canonical template 在项目明确 carrier 建立本 Change，不改历史或创建平行制度。
