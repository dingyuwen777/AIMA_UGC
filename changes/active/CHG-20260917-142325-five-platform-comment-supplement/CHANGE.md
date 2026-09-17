---
schema: coding-change/v1
id: CHG-20260917-142325-five-platform-comment-supplement
title: 五平台评论补采身份解析与网页闭环
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/five-platform-comment-supplement
created: 2026-09-17
updated: 2026-09-17
completion_gate: required
depends_on: []
affected_areas:
  - imports
  - tikhub
  - collection
  - content
  - frontend
  - docs
affected_paths:
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/tikhub/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/
  - frontend/src/features/import-batches/
  - frontend/src/features/voice-plaza/
  - frontend/src/generated/api/
  - tests/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - docs/
  - changes/active/CHG-20260917-142325-five-platform-comment-supplement/CHANGE.md
contracts:
  - Collection eligibility and run HTTP API
  - Comment target identity and coverage
data_changes:
  - Content external typed identities and provenance
---

# 变更摘要

完成 Issue #526 与 `docs/roadmap/04_五平台评论补采产品化实施方案.md` 的正式五平台补采闭环。现有原生 ID 继续走正式 TikHub Operation；只有分享链接、来源哈希或微博长文章 ID 的内容先取得精确评论目标身份。解析失败或无映射时明确保留原因，绝不以任意内容 ID 构造评论请求。

# 当前事实、目标与边界

- 当前 `main` 为 `7f1ca524c1c43fc4e61b8601f5d0e241e5023493`。声音广场评论层级与分页子项已落地；五平台身份解析、Eligibility 诊断、Run Coverage、真实五平台补采验收仍未完成。
- 本变更复用现有 Collection Run、持久 Job、Provider Attempt/Raw、Content Owner、PostgreSQL、Pydantic/OpenAPI/Orval 和声音广场。保持 Canonical 主身份、已存在合法原生 ID、公共请求和既有内容详情兼容。
- 不进行模糊搜索、跨 API family 隐藏 fallback、终态重试 API、依赖升级或额外任务系统。真实 Probe 显式限额，不进入普通 CI。
- 微博 `ttarticle` 的页面评论可按用户最新决定计入产品中的“父帖评论”。实际采集仍须有文章页面评论线程的正式 Operation 与精确归属证据，或有唯一原始父 `status_id` 的精确关联证据；结果必须保留真实来源。没有可验证线程的样本记 `identity_unavailable`，不把文章 ID 发往帖子评论接口。
- 用户提供的正向样本页面显示 1 条评论，但页面计数不能替代已获取评论。完整文章 ID 及去掉 `230940` 的数字在 TikHub App Detail/Comments 的 4 次限额 Probe 中均返回 HTTP 400；当前正式 Operation 未取得该评论。

# 方案比较与决定

| 方案 | 正确性与兼容 | 成本与风险 | 选择 |
| --- | --- | --- | --- |
| 复用现有 Collection/Content Owner，增加显式 typed comment target 解析和响应诊断 | 保持现有主链与 Canonical 主键，能逐步核验五平台 | 需要跨 Provider、持久化、HTTP 和页面验证 | 采用；与已批准 Roadmap 一致 |
| 仅让上游 Excel 预先提供所有原生 ID | 原生 ID 精确且费用低 | 无法覆盖已有短链数据，用户仍看不到阻塞原因 | 作为精确输入优先级，不单独作为全部方案 |
| 通过标题/作者搜索猜测目标并直接补采 | 可能误抓他帖评论 | 数据污染与额外付费，无法审计精确归属 | 禁止 |

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 五平台 URL/分享身份识别并保留 Canonical 主身份 | #526 / AC1；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | 已补 `ttarticle_id`、host/完整路径/重复参数保护；五平台短链精确解析仍缺 |
| R2 | 评论请求只接受平台白名单 typed ID，非法定位符零请求 | #526 / AC2；docs/roadmap/04_五平台评论补采产品化实施方案.md | satisfied | `comment_target.py`、TikHub Runtime、五平台单元回归；来源哈希和文章 ID 不再回退发请求 |
| R3 | 精确解析有独立 Attempt/Raw、持久结果与明确失败语义 | #526 / AC3；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | 当前只对缺少精确映射的来源 fail closed；独立解析 Operation/Attempt/Raw 尚未实现 |
| R4 | 五平台评论与回复分页耗尽、可恢复且 Coverage 真实 | #526 / AC4；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | 批次补采已去除抽样停机并修复回复短缺，隔离 PostgreSQL 回归通过；五平台分页/恢复矩阵未完成 |
| R5 | Eligibility 与 Run/Scope 可解释直接、待解析、阻塞及部分结果 | #526 / AC5；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | 已增加诊断、混合来源失败 Scope、持久评论 Coverage 与页面平台汇总；回复级数量/完整阶段验收仍缺 |
| R6 | 网页创建、跟踪、恢复、结果跳转及数据库评论分页闭环 | #526 / AC6；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | 已接线结果跳转与覆盖展示；既有声音广场分页可复用，逐平台全栈尚未证明 |
| R7 | 调试入口复用生产实现，失败样本受控重放或明确不可获取 | #526 / AC7；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | `imports_test` 已复用身份解析；staging 行级受控重放及对账未完成 |
| R8 | 五平台多层测试、真实 Provider Probe、全栈和费用台账 | #526 / AC8；docs/roadmap/04_五平台评论补采产品化实施方案.md | not_satisfied | 四平台固定公开样本 Detail/一级评论通过；“爱玛”快手候选的非空根评论与回复 Mapper 通过，但用户提供的另一快手链接 Detail 空、五平台多页和真实全栈缺证据 |
| R9 | 文档迁移、Completion Audit、Review、PR/main CI 与 Roadmap 退出 | #526 / AC9；docs/roadmap/README.md | not_satisfied | 合并前后按当前门禁验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 五平台身份白名单、URL 解析、分页、Coverage 与前端状态；新增行为先取得失败回归 |
| 接口 / Contract | required | Pydantic/OpenAPI/生成 Client 的新增可选诊断字段和兼容检查 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL typed identity、Attempt/Raw、Job 恢复、评论写入及去重 |
| 用户 / Workflow Acceptance | required | Batch/Campaign 五平台选择、202、刷新恢复、终态说明、结果跳转和评论层级分页 |
| 跨组件 Golden Path | required | Browser → Vue → API → Worker/Fake TikHub → PostgreSQL → 声音广场，逐平台验证关键接线 |
| 外部依赖 Probe | required | 五平台真实 TikHub 请求/业务成功/分页/回复与身份能力；显式限额、脱敏、费用核对 |
| Build / Package / Runtime | required | 后端目标/模块测试、前端 lint/typecheck/build、CI current-head 与 main fresh |
| Docs / Governance / Other | required | Blueprint/Appendix/模块文档、Secret/架构/Owner 检查、Change Completion Audit 与 Review |

# 逐步实施与验证

1. Provider 事实：核对正式 Operation、价格、真实输入格式及五平台脱敏样本；先一页，再选代表样本跑到 exhausted。记录每平台请求数、费用和失败语义；未知操作不写成正式 Capability。
2. 身份识别与保护：导入时保留原生及待解析身份；建立单一 `CommentTargetResolution`；正式 Runtime 仅接受平台允许 typed ID。以五平台合法/恶意 URL、哈希、短链、文章 ID 失败回归验证零误请求。
3. 精确解析与持久化：只对有真实证据的平台接入独立解析 Operation/Attempt/Raw，向 Content Owner 写 typed ID 与来源；真实 PostgreSQL 验证并发、冲突和恢复不重发。无映射输入保持 unavailable。
4. 评论与回复：沿现有 Scope/Runtime 抓到 Provider exhausted，保留每页 Raw、游标和父子关系；以五平台分页/业务失败/回复短缺/取消/恢复测试证明 Coverage。
5. HTTP 和页面：增加兼容的 Eligibility/Run Coverage 响应，生成 Client；既有 Supplement Drawer 和 Run Detail 显示可操作原因及结果入口；声音广场继续从 PostgreSQL 读取。用 Contract、组件、Mock Browser 和真实全栈验证。
6. 离线调试与已处理数据：`imports_test` 复用生产身份解析；受控重放当前失败样本，核对原内容身份、评论去重、费用和不可获取原因。
7. 同步文档并执行 Completion Audit：重新读取 Issue/Roadmap，逐项核对 R1–R9、前后端和结果反向能力；运行项目 Ready Check、独立 Review、current-head CI；满足后 merge，执行 main fresh CI 与仓库原生归档/Issue 关闭检查。

# 兼容、数据、部署与回滚

- 预计不增加数据库表、Migration、依赖或 Job type；若真实 Schema/FK 无法表达来源，先回到设计门禁，不用 JSON 绕过。
- HTTP 只增加可选响应诊断，旧请求和详情响应兼容。前后端同版本发布；本任务不包含生产部署或数据迁移。
- 可关闭新增平台解析入口并回滚代码；保留已写入的 typed identity、Raw 和评论。请求前 typed ID 保护不得回滚。

# Completion Audit

- [ ] upstream_re_read：完成前重读 #526、Roadmap、当前 Contract 与机器事实，独立重建退出条件。
- [ ] change_coverage：核对上游 AC1–AC9 到 R1–R9，记录实际满足和限制。
- [ ] reverse_audit：后端能力 → 前端入口、前端动作 → 真实 API/Worker/Provider、评论结果 → Content/Attempt/Raw；复核各验证层证据等级。
- [ ] unresolved_cleared：`not_satisfied` 清零；延期和不适用需正式依据。

# 本轮已取得的验证证据（2026-09-17）

- Windows 本地 Python 单元、Contract、API：排除 3 个环境/本地数据相关文件后，`1196 passed, 8 skipped`。排除项分别依赖 POSIX 主机行为、Windows 路径表示和本机既有忽略 Raw 输出；不能将此结果写成完整套件通过。
- 隔离 PostgreSQL 18.4 容器完成 Alembic `upgrade head` 后，Collection 集成测试 `99 passed`；新增批次补采不因抽样目标提前停止的测试单独通过。补充五平台 typed ID 从 Content Owner 账本读取的参数化回归后，再次使用一次性容器运行目标文件 `9 passed`。测试没有写入用户开发数据库；临时密码文件和容器已清理。
- 前端 28 个 Vitest 文件共 `157 passed`，指定 Collection/Voice Plaza 的 Playwright Mock E2E `26 passed`；lint、生产构建和 TypeScript 检查通过。
- 后端 `mypy backend/src` 检查 346 个源码文件通过；OpenAPI 生成一致性及兼容检查、文档和架构/表 Owner 检查通过。
- 真实 TikHub 有界 Probe 的请求数、计划费用和局限记录于 Roadmap 实施进度；四个平台固定样本 Detail/一级评论成功，原固定快手样本的 Detail/非空评论闭环未通过。
- 后续有界 Probe 找到一个可见的“爱玛”快手候选，Detail、30 条根评论和 10 条回复的结构/归属通过生产 Mapper；用户给的另一快手链接仍返回空 `data.photos`。微博标准帖 Detail/评论成功，但其 Detail 不含用户另给长文章 ID，不能证明长文章的父帖映射。长文章正向样本的 4 次 App 请求均为 HTTP 400；不能据页面显示的 1 条评论断言已补采。完整请求/费用与边界见 Roadmap 和 TikHub 台账。
- 这些验证只覆盖当前部分实现。R1、R3–R9 尚未满足，严格 Ready Check、PR current-head CI、两阶段 Review 和 main fresh CI 尚未执行；不得合并。

# 交付状态

- Requirement Source：#526，已创建并读回，9 条 AC 均未勾选。
- Git：本地分支 `feature/five-platform-comment-supplement`，基于 `7f1ca524`；首个治理提交 `57ce4040`，早期 PR #527 已创建并明确“逻辑未就绪”。实现尚未形成完成提交，current-head CI、Review、main 验证均未通过，禁止合并。
- 发布和生产部署：不在本次范围。
