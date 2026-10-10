---
schema: coding-change/v1
id: CHG-20261010-073633-role-export-preferences
title: 落实多用户角色权限与个人 Excel 导出配置
level: L3
status: ready_for_review
owner: Codex
branch: feat/714-role-export-preferences
created: 2026-10-10T07:36:33+08:00
updated: 2026-10-10
completion_gate: required
depends_on: []
affected_areas:
  - identity
  - reporting
  - frontend
  - workbench
  - content
affected_paths:
  - backend/src/aima_ugc
  - frontend
  - migrations
  - tests
  - docs
contracts:
  - HTTP
  - ExportColumnCatalogResponse
  - DataExportRequest
  - ExportColumnDefault
data_changes:
  - reporting_data_exports
  - reporting_user_export_column_defaults
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
| R1 | 飞书/Session 身份 | #714 / AC1 | satisfied | `tests/unit/identity/`、platform 身份映射/Session/单多 Connector 本地回归；沿用稳定组 ID/管理员优先/八小时会话，真实企业 OAuth 候选验收见 R20 边界 |
| R2 | 最终路由完整 policy | #714 / AC2 | satisfied | [最终 175 项实际 Method+Path 清单](evidence/route-authorization-inventory.md)、`tests/api/test_route_authorization.py`：未知/重复/未受保护路由启动拒绝、隐藏与扩展均覆盖、每请求 Principal 复用 |
| R3 | 管理 API 拒绝无副作用 | #714 / AC3 | satisfied | `test_route_authorization.py` 逐最终管理路由执行前拒绝和服务探针；`test_role_exports_and_defaults.py` 真实 Session/DB/Job/Artifact 事实不变；统一 401/403/422/409 错误 |
| R4 | 共享只读与旁路 | #714 / AC4 | satisfied | `test_role_export_columns_and_csrf.py`、Content/Workbench 集成和 Full-stack；普通用户播放仅读取既有结果，通用 Job 管理授权，媒体恢复 F3 定向回归 |
| R5 | 配置/CSRF | #714 / AC5 | satisfied | `test_feishu_auth_http.py`、`test_role_export_columns_and_csrf.py`；显式 feishu/development、Compose 正式默认失败关闭、Cookie 同源写校验、合法 OAuth 回调/配置来源通过 |
| R6 | 导航/Route | #714 / AC6 | satisfied | `app-shell.spec.ts`、`identity-auth-guard.spec.ts`、`identity-store.spec.ts` 和真实角色 Full-stack：两/五菜单、管理深链拒绝、无管理请求/菜单闪现/403 登录循环 |
| R7 | 声音广场列表 | #714 / AC7 | satisfied | VoicePlazaPage/Table 显式能力、Store 写入口保护；`voice-plaza.spec.ts` Unit/Browser 与 Full-stack 保留选择/AI 结果/筛选/导出，隐藏分析/补采/复核管理动作 |
| R8 | 内容详情 | #714 / AC8 | satisfied | Detail/Comment/Media 显式权限 props；detail/media/comment 组件回归、普通用户详情 Browser；正文、评论回复、有效人工摘要/证据保留，编辑器和恢复写入口关闭 |
| R9 | 任务中心 | #714 / AC9 | satisfied | `task-center.spec.ts`、Full-stack 请求监测：普通用户真实请求源仅自己 Export；角色换代清旧缓存与在途结果，管理员原管理任务/取消回归 |
| R10 | 共享数据刷新 | #714 / AC10 | satisfied | opaque 只读 content-revision、首次追赶/慢请求 Red→Green、Workbench 既有 3 秒/小时刷新与深链 Browser；真实 Full-stack 管理员复核后普通用户已打开页面自动更新且无 Analysis Run 请求 |
| R11 | 布局与通知 | #714 / AC11 | satisfied | Workbench layout 的 principal/revision 集成及 Browser；`test_u1_u5_identity_product.py` 当前用户通知/已读、product service 普通用户管理通知过滤；Identity Store 安全深链与换号旧通知回归 |
| R12 | Export 创建者 Schema | #714 / AC12 | satisfied | `20261010_0087_export_ownership_defaults.py`、`test_export_ownership_migration.py` 与 Reporting PG：仅可靠非空字符串回填、未知 owner 管理员可见、新建 Session owner、用户时间索引 |
| R13 | Export 对象授权 | #714 / AC13 | satisfied | `test_role_exports_and_defaults.py` 先 owner 过滤再 LIMIT、A/B/admin 详情/下载、Job/Artifact/到期；真实双用户 Full-stack 跨用户详情与下载 404 |
| R14 | 列授权 | #714 / AC14 | satisfied | Catalog v3 单一 EXPORT_COLUMNS、API 伪造字段拒绝、降权配置/历史 v2 文件下载拒绝；Worker XLSX 全工作表无受限字段，管理员与离线 Renderer 既有回归 |
| R15 | 默认字段持久化 | #714 / AC15 | satisfied | Reporting 专表/Repository CAS、`test_role_exports_and_defaults.py`：每用户一条、有序有效列、NULL 恢复 revision 单调、开发 Principal 无 Identity FK |
| R16 | 默认 API | #714 / AC16 | satisfied | `test_role_export_columns_and_csrf.py` 与 Reporting PG：当前 Session、0/null、revision/catalog 409、非法 422、读取过滤且原始记录不重写；OpenAPI/Orval 生成一致 |
| R17 | 默认弹窗与冻结 | #714 / AC17 | satisfied | 延迟默认、409、恢复失败 Browser 和 Full-stack 跨浏览器恢复；显式保存/恢复、草稿保护、临时导出不改默认；PG 生成并重读 XLSX 验证冻结字段和顺序 |
| R18 | 会话隔离 | #714 / AC18 | satisfied | `principal-scope.spec.ts`、`identity-store.spec.ts`、旧异步 Unit、sessionStorage/Legacy Browser、真实多标签页 Cookie 换号：同用户恢复、历史无归属清除、换号清 Pinia/默认/在途结果 |
| R19 | Migration/Contract/回滚 | #714 / AC19 | satisfied | 新增 0087，不改旧 Migration/Content/Artifact；Migration PG/历史兼容 14 项、Generated Contract/兼容检查通过；正式部署文档说明整体联动与保留配置回滚/旧漏洞访问隔离 |
| R20 | 本地分层验证 | #714 / AC20 | satisfied | [本地验证记录](evidence/local-validation.md)：2611 pytest、361 Vitest、218 Browser、真实 Session Full-stack 原 20+修后 1、972 唯一 PG、XLSX 重读、迁移/Contract/类型/构建；首次采集五项未复现风险保留，原模块/原序 96 PASS；企业候选/远程 CI 明确未执行 |
| R21 | 独立 Review/文档/兼容 | #714 / AC21 | satisfied | [独立 Review 与修复](evidence/review-repair.md)：首轮三项 P2 全部由原 Reviewer CLOSED；最终直接日志 addendum 判定本地可验收/无 blocking Acceptance gap；正式产品/Reporting/Schema/部署文档与管理员原流程回归同步 |
| R22 | 保留分支、不合并与任务清理 | #714 / AC22 | satisfied | [本地交付与清理](evidence/local-delivery.md)：两个临时分支/worktree、测试服务、两个专属 PG 容器/匿名卷、任务 Source/temp/Secret/数据及前端生成产物均已清理；根开发分支保留，无 push/PR/CI/merge/发布/部署 |

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

- [x] upstream_re_read：2026-10-10 再次 live 读取 #714（updated_at `2026-10-10T00:19:28Z`，epoch 2 未变），核对 AGENTS、技术决策与生产路线；以用户最新本地验证/暂停合并指令为交付边界。
- [x] change_coverage：按 #714 AC1–22 逐条核对，R1–22 均有当前实现/直接测试/独立复核/实际清理证据；未来企业候选、远程 CI 和人工验收按上游既定交付边界列未执行，未用 Change 自证需求全集。
- [x] reverse_audit：最终 API→UI、UI→生成 Client→Owner、Schema/迁移→查询归属、Job→冻结文件→下载列权限，以及 Principal→会话/草稿/旧异步反向检查；普通用户选择/AI 结果/媒体/评论保留，管理侧原入口回归已覆盖。
- [x] unresolved_cleared：原 Reviewer 确认 F1/F2/F3 全部 CLOSED、无 blocking 本地 Acceptance gap；所有本地验证和临时资源清理完成。首次采集异常当前原序未复现、根因未知作为已披露风险，未伪造修复或环境归因。Human PENDING/无远程交付符合用户当前边界。

# 完成证据与状态

## 新鲜证据

起点 fetch main 成功；Issue candidate create Contract PASS，平台创建 #714，epoch 2 candidate pre-write PASS、平台更新后 live 重读与 candidate 字节相同。当前代码 `513c79804f3fe14121ba0b0422865e16a2ac8d61`；完整 changed-scope preflight 退出 0（2611 pytest、361 Vitest、218 Browser、类型/构建/Contract 等）；真实 Session Full-stack 原 20 项及新增 1 项均通过。详见 [本地验证记录](evidence/local-validation.md) 与 [Review 修复记录](evidence/review-repair.md)。

## 未验证内容与剩余风险

正式飞书/多企业真实 Connector、最终 HTTPS/Origin/Cookie、Linux 专属进程回收、专用报告浏览器候选装配、Release/离线回放与远程 required CI 未执行，不能宣称生产可发布。首次采集五项失败未能恢复具体异常，原模块/原序重跑 96 项全部通过、258 唯一覆盖齐全；保留未复现风险，不伪造已修复或基础设施归因。

## 交付状态

本地实现、自动验证、独立复核与临时资源清理已完成；`check_change_completion.py --root . --require-active-ready` 通过，Change 为本地 ready_for_review。后端、测试、前端与交付证据形成可审查的本地提交，尚无 push/PR/CI/merge。Human Local Acceptance PENDING；保留根开发分支，远程 main 合并暂停。此状态不代表 PR Ready、可合并或生产候选就绪。

## 备注

顶层 changes 为项目正式 carrier，历史多 schema 由项目 validator 保留；Source CLI 不接受混合 legacy carrier，因此用 canonical template 在项目明确 carrier 建立本 Change，不改历史或创建平行制度。
