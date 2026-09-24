---
schema: coding-change/v1
id: CHG-20260923-115743-report-strategy-feishu-publication
title: 报告策略页面与飞书发布 Job 前后端接通
level: L3
status: ready_for_review
owner: chatgpt
branch: feature/merge-BOLL2-main
created: 2026-09-20
updated: 2026-09-24
completion_gate: required
depends_on:
  - CHG-20260917-180708-representative-selection-feishu-sync
affected_areas:
  - administration
  - frontend
  - jobs
  - artifact
  - external-provider
  - database
  - runtime
  - migration
  - dependencies
  - contracts
  - documentation
affected_paths:
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/feishu_publication_http.py
  - backend/src/aima_ugc/bootstrap/feishu_publication_worker.py
  - backend/src/aima_ugc/bootstrap/feishu_report_publication.py
  - backend/src/aima_ugc/modules/administration/feishu_publication_jobs.py
  - backend/src/aima_ugc/contracts/feishu_publication.py
  - frontend/src/features/admin-configuration/
  - frontend/src/generated/api/client.ts
  - contracts/openapi/openapi.json
  - tests/unit/platform/
  - frontend/e2e/admin-configuration-release2.spec.ts
  - migrations/versions/20260924_0062_feishu_mirror_claims.py
  - docs/
contracts:
  - FeishuPublicationCreatedResponse
  - FeishuPublicationJobResponse
  - FeishuReportPublicationResult
data_changes:
  - 复用通用 jobs 表保存报告发布 Job
  - 复用 ArtifactStore 保存上传的本期/上期 XLSX
  - 显式关闭 Dry Run 后才产生飞书文档/多维表外部写入
  - Job Payload 追加跨 Attempt 外部资源 checkpoint（不含 Secret）
  - `feishu_bitable_mirrors` 追加 claim/lease/fencing 状态
---

# 变更摘要

把管理员配置的“报告策略”页面接入真实双 XLSX 上传、持久 Job、Worker 和结果轮询。报告 Job 在 Worker 内执行与 `generate_report.py --publish-all` 等价的完整编排：代表性内容筛选、行动建议、报告生成、代表性多维表同步和飞书报告发布。开发环境默认 Dry Run，执行报告/LLM 流程但不调用飞书写入，也不生成伪造链接。

# 背景、现状与问题

此前页面只有本地文件/日期校验，后端没有可调用的报告发布 API；直接把浏览器本地路径交给后端也不成立。用户确认使用本期/上期两个 Excel、必填日期范围，并先采用 Fake/Dry Run 配置。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 | 支撑约束 |
| --- | --- | --- | --- |
| E1 | 页面文件来自浏览器，后端必须接收 multipart 并保存受控 Artifact | `frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/ReportStrategyPanel.vue`、`feishu_publication_http.py` | 不传本地路径，不把字节写入 Job Payload |
| E2 | 项目已有 PostgreSQL Durable Job Runtime 和 Worker Registry | `platform/jobs/`、`bootstrap/worker.py` | 不新增第二套队列或同步 HTTP 长任务 |
| E3 | `generate_report.py --publish-all` 已有代表性筛选、报告和飞书发布事实源 | `adapters/providers/imports_test/generate_report.py`、`bootstrap/feishu_report_publication.py` | Worker 复用同一编排，不复制报告统计/筛选业务 |
| E4 | Dry Run 必须不调用飞书写入，真实链接不能伪造 | `platform/config/settings.py`、`test_feishu_report_publication.py` | 默认 `AIMA_FEISHU_DRY_RUN=true`，结果 URL 为空 |
| E5 | 页面需要异步状态、成功摘要和失败反馈 | `ReportStrategyPanel.vue`、`admin-configuration-release2.spec.ts` | POST 返回 Job，页面轮询 GET 直至终态 |
| E6 | 外部发布会跨多个飞书资源产生副作用，重试必须复用已确认身份并按稳定 token 幂等 | `report_publisher.py`、Job Payload checkpoint | 不从头创建 Word/XLSX/Sheet/Docx/Bitable |
| E7 | 常驻镜像可能多实例并发运行，普通 due 扫描不能保证单消费者 | `feishu_bitable_mirrors.py`、0062 migration | claim/lease/fencing 与旧 Worker 写回保护 |

# 目标、成功标准与非目标

## 目标

- [x] 报告策略页面上传本期/上期 `.xlsx` 和日期范围，调用真实管理员 API。
- [x] 上传文件经过 XLSX 安全校验并保存为 Artifact，Job Payload 只保存稳定 Artifact ID、文件名、日期和 Dry Run 开关。
- [x] 报告 Job 注册到现有 Worker Registry，并在 Worker 内执行 `--publish-all` 等价流程。
- [x] 页面展示排队、生成、成功、失败和 Dry Run 结果；成功时只展示真实飞书链接。
- [x] OpenAPI 与 generated client 同步，管理员权限由后端校验。

## 非目标

- 不新增独立 Report 数据库表、报告中心页面或第二套任务队列。
- 不修改报告统计口径、代表性筛选规则、飞书字段映射和现有 Renderer。
- 不在普通测试中调用真实飞书或真实付费 LLM；真实租户写入仍需人工显式关闭 Dry Run。
- 不把浏览器本地路径、Secret、完整内部路径或第三方响应正文返回给前端。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与执行 | 复用现有报告编排、Durable Job Runtime 与 Worker Registry | E2、E3 | 不新增平行队列或复制报告业务 |
| 文件与数据 | XLSX 存入受控 Artifact，Job Payload 只保存稳定 ID 与参数 | E1、E2 | 不暴露本地路径或文件字节 |
| 外部写入 | Dry Run 默认阻断飞书写入，真实发布需显式关闭 | E4 | 不生成伪造链接或静默写入 |
| 外部副作用恢复 | Job Payload 每个 checkpoint 立即 fenced 持久化，Feishu API 使用稳定 client_token/request_id，Bitable Upsert 复用稳定键 | E6 | Attempt 重试从已确认身份继续，避免重复创建 |
| 镜像并发 | PostgreSQL `FOR UPDATE SKIP LOCKED` claim + expires_at + token CAS | E7 | 多实例只允许一个有效消费者，过期后旧实例不能写回 |
| 接口与权限 | 使用专用管理员 multipart API 与 Job 查询入口 | E1、E5 | 权限由后端校验，前端不执行长任务 |
| 兼容与回滚 | 保持现有报告口径和 Renderer；代码可回滚 | E3、E4 | 不改变历史报告语义 |

# 修改方案与决策依据

1. API 采用两个专用 multipart 管理员入口和一个 Job 查询入口，拒绝通用 shell 执行器。
2. 上传先保存受控 Artifact，再入队通用 Job；Worker 从 Artifact 读入临时目录并校验 SHA-256。
3. 报告路径复用 `prepare_representative_report()` 与统一报告 Renderer；Dry Run 在发布器之前返回，不调用任何飞书写入。
4. 前端只通过 generated client 的 Feature API 调用 HTTP，使用 3 秒轮询并在组件卸载时停止轮询；POST 成功后先保存 job_id，首个 GET 失败仍继续轮询。
5. 报告外部副作用使用跨 Attempt durable checkpoint；镜像同步在 PostgreSQL 中 claim 后才访问飞书。

## 备选方案与取舍

不采用同步 HTTP 长任务、独立报告表或第二套队列：上传和报告生成需要受控 Artifact、持久 Job 与现有 Worker Registry 承载。也不在每次重试时重新创建飞书资源；使用稳定操作键、跨 Attempt checkpoint 和镜像 claim/lease/fencing，使已确认的外部资源可恢复且并发执行者不能越权写回。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 报告策略上传两份 XLSX、填写合法日期范围并创建异步 Job | user:confirmed-report-strategy / AC1 | satisfied | `feishu_publication_http.py`、`api.py`、前端 API 封装与报告 E2E |
| R2 | 上传文件经过安全校验并以 Artifact ID 进入 Job，不传浏览器本地路径 | user:confirmed-report-strategy / AC2 | satisfied | `validate_xlsx_stream()`、`ArtifactService.store_stream()`、Worker 完整性校验测试 |
| R3 | Worker 执行与 `generate_report.py --publish-all` 等价的报告/代表性内容全流程 | user:confirmed-report-strategy / AC3 | satisfied | `publish_all_report_to_feishu()`、Job executor、报告发布单元测试 |
| R4 | Fake/Dry Run 默认执行本地报告/LLM流程，不调用飞书写入且不生成假链接 | user:confirmed-report-strategy / AC4 | satisfied | `AIMA_FEISHU_DRY_RUN=true`、Dry Run 单元测试和页面结果断言 |
| R5 | 页面按真实 Job 状态轮询并展示成功摘要、失败错误和可用飞书链接 | user:confirmed-report-strategy / AC5 | satisfied | `ReportStrategyPanel.vue`、`admin-configuration-release2.spec.ts` |
| R6 | 只有管理员可创建/查询发布 Job，Secret 不进入 Contract、Payload 或结果 | user:confirmed-report-strategy / AC6 | satisfied | `current_administrator()`、Contract 模型、HTTP/Worker 安全结果测试 |
| R7 | OpenAPI/generated client、当前产品文档和 API 导航与实现一致 | user:confirmed-report-strategy / AC7 | satisfied | `contracts/openapi/openapi.json`、generated client、产品/Blueprint/Guide/Appendix 更新 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 |
| --- | --- | --- |
| Administration / API / frontend | 接通报告策略、上传、Job 查询和配置界面 | 提供管理员可观察的异步操作路径 |
| Reporting / Artifact / Worker | 复用报告流程并通过受控 Artifact 执行 | 保持文件与任务边界清晰 |
| Contracts / docs / tests | 同步 API、产品说明和回归覆盖 | 保持实现、契约和验证证据一致 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| Contract / OpenAPI | required | OpenAPI 生成、generated client 类型和 Contract 检查 |
| Behavior / Unit | required | 报告编排、Dry Run、Job Payload/Handler、Artifact、飞书发布回归 |
| User / Workflow Acceptance | required | 管理员报告策略 Browser E2E：上传、日期校验、Job 轮询、Dry Run 结果 |
| Build / Runtime | required | Frontend lint、typecheck、build；后端目标 pytest/编译 |
| External Provider Probe | not_applicable | 普通验证不调用真实飞书/付费 LLM；真实租户权限需人工执行 |
| Database / Migration | required | 0060→0061→0062 upgrade、downgrade -1、再 upgrade；PostgreSQL claim 并发回归 |
| Docs / Governance | required | 文档事实同步、Change Completion、diff check |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| LLM/飞书外部失败 | 可能重试或进入稳定失败码 | Worker 复用 retry/fail 语义；checkpoint、stable client_token/request_id 和 Bitable Upsert 键避免重复创建；不把第三方正文返回前端 |
| Dry Run 误写飞书 | 默认配置阻断发布器；结果 URL 为空 | 只有显式 `AIMA_FEISHU_DRY_RUN=false` 才进入写入路径 |
| 上传文件安全 | 文件名、扩展名、ZIP 结构、大小和完整性均校验 | Artifact 入库前后双重校验 |
| 数据迁移 | 需要 0062 | `feishu_bitable_mirrors` claim 字段由 Alembic 管理，回滚先停止 Worker 再逆序 downgrade |
| 回滚 | 可回滚代码；Dry Run 不产生外部写入 | 已创建的真实飞书新文档/新表不由回滚动作删除；新 Attempt 继续使用已持久化身份 |

# 文档、依赖、部署与发布影响

- 同步产品状态、API 说明、Blueprint、前端 README、Figma 开发指南、Word 报告附录和本 Change。
- 沿用仓库锁定的 Python/Node/Worker 工具链；Playwright 是前端 E2E 的生产依赖并纳入验证矩阵。
- 部署先执行 0062 migration，再启动/滚动重启现有报告与镜像 Worker。
- 真实飞书发布前仍需配置 Secret、权限并显式关闭 Dry Run；本轮不代替真实租户验收。

# 完成审计

- [x] upstream_re_read：已重新核对用户确认的双 Excel/日期/Dry Run 要求、现有报告入口、Job Runtime、Artifact 边界和管理员 Contract。
- [x] change_coverage：R1—R7 均已映射到 API、Worker、前端、Contract、测试或文档证据。
- [x] reverse_audit：已从前端上传动作反查 API/Artifact/Job/Worker/结果轮询，并从 Worker 报告编排反查页面入口和 Dry Run 边界。
- [x] unresolved_cleared：前一轮 Review 的外部资源 checkpoint/重试收敛、镜像 claim fencing、首个 GET 失败恢复三条行为线程均有最终回归；前端 query cache-buster 与页面恢复边界已记录，真实飞书租户 Probe 仍明确不适用。

# 完成证据与状态

| ID | 环境 | 检查 | 结果 | 证明边界 |
| --- | --- | --- | --- | --- |
| V1 | Windows 本地 `.uv-venv` | 报告/飞书/Job 目标 pytest | 37 passed | checkpoint、部分成功后 retry 只复用一组逻辑资源、API 编排、Dry Run、真实发布分支和 Worker 回归 |
| V2 | Windows 本地 Node 工具链 | TypeScript、ESLint、Frontend build | 全部通过 | 前端类型、静态质量和构建 |
| V3 | Windows 本地 Node 工具链 | 报告策略 Playwright E2E，首个 Job GET 返回 503 后继续轮询；route 覆盖 cache-buster query | 8 passed | job_id 保留、没有重复 POST，轮询 query 不会落入未声明 mock |
| V4 | Windows 本地 `.uv-venv` | 目标后端 Ruff/Mypy | 相关源文件无错误 | Python 静态质量和类型边界 |
| V5 | Prompt / 入口兼容性 | analysis taxonomy API + voice taxonomy/relevance unit | 30 passed | 当前受管 Prompt 指针继续满足 v4 taxonomy/voice contract；未把不兼容 v4.6 文件切成全局基线 |
| V6 | 仓库质量脚本 | docs、architecture、table ownership、Change completion | UTF-8 终端复跑后记录 | 文档、架构、表 Owner 和治理门禁 |
| V7 | Windows 本地 PostgreSQL | Alembic migration cycle、mirror claim integration | 127.0.0.1:5432 连接超时；required CI 待新 HEAD 复跑 | 真实 Schema upgrade/downgrade 与多实例 claim |

## 未验证内容与剩余风险

真实 PostgreSQL、真实飞书租户权限、真实 LLM 账号和生产 Worker 部署不在本地 Fake/Dry Run 验证范围内。目标源文件的 Mypy 已通过；PostgreSQL migration/claim 集成仍需由 required CI 提供 Linux/数据库证据，Windows 上 Vite/Playwright 退出清理仍需单独环境治理。

## 交付状态

实现、目标测试、前端构建、Contract 和文档同步已完成。按用户授权，本 Change 与同分支飞书多维表同步改动将提交并推送到既有 PR #580，供维护者通过 PR 审核；PR 合并和真实飞书写入不在本次授权范围内。新 HEAD 推送后会重新运行 required CI，再请求复审。
