---
schema: coding-change/v1
id: CHG-20260917-142325-five-platform-comment-supplement
title: 五平台评论补采身份解析与网页闭环
level: L3
status: ready_for_review
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

完成 Issue #526 与 `docs/blueprint/08_采集策略与平台能力.md` 的正式五平台补采闭环。现有原生 ID 继续走正式 TikHub Operation；受支持的分享链接先取得精确评论目标身份。微博 `ttarticle` 长文章按用户最新决定不补采评论。解析失败或无映射时明确保留原因，绝不以任意内容 ID 构造评论请求。

# 当前事实、目标与边界

- 立项时 `main` 为 `7f1ca524c1c43fc4e61b8601f5d0e241e5023493`，声音广场评论层级与分页已落地；本 Change 补齐身份解析、Eligibility 诊断、Run Coverage 和五平台真实补采验收。
- 本变更复用现有 Collection Run、持久 Job、Provider Attempt/Raw、Content Owner、PostgreSQL、Pydantic/OpenAPI/Orval 和声音广场。保持 Canonical 主身份、已存在合法原生 ID、公共请求和既有内容详情兼容。
- 不进行模糊搜索、跨 API family 隐藏 fallback、终态重试 API、依赖升级或额外任务系统。真实 Probe 显式限额，不进入普通 CI。
- 用户最新决定：微博 `ttarticle` 长文章不进行评论补采，移除新增的文章 ID 提取逻辑。历史记录即使有 `ttarticle_id` 和 `status_id`，也在评论目标解析及 Batch/Campaign 资格判定中阻断；普通微博帖子维持原能力。
- 用户随后明确决定：TikHub 无法证明精确归属的快手短链、微博视频链接和 B站 `b23.tv` 短链按不可获取处理；五平台原生 ID 补采继续验收。此边界不排除普通 `photo_id`、`status_id`、`av_id/bv_id`，也不允许猜测或错配 ID 发评论请求。
- 用户提供的正向样本页面显示 1 条评论，但完整文章 ID 及去掉 `230940` 的数字在 TikHub App Detail/Comments 的 4 次限额 Probe 中均返回 HTTP 400；该页面计数不能写成已获取评论。

# 方案比较与决定

| 方案 | 正确性与兼容 | 成本与风险 | 选择 |
| --- | --- | --- | --- |
| 复用现有 Collection/Content Owner，增加显式 typed comment target 解析和响应诊断 | 保持现有主链与 Canonical 主键，能逐步核验五平台 | 需要跨 Provider、持久化、HTTP 和页面验证 | 采用；与已批准 Roadmap 一致 |
| 仅让上游 Excel 预先提供所有原生 ID | 原生 ID 精确且费用低 | 无法覆盖已有短链数据，用户仍看不到阻塞原因 | 作为精确输入优先级，不单独作为全部方案 |
| 通过标题/作者搜索猜测目标并直接补采 | 可能误抓他帖评论 | 数据污染与额外付费，无法审计精确归属 | 禁止 |

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 五平台 URL/分享身份识别并保留 Canonical 主身份；`ttarticle` 长文章排除 | #526 / AC1 | satisfied | 导入身份规则保留五平台原生或分享定位字段及 Canonical 主身份；小红书/抖音受支持短链已实测并持久化来源；快手短链、微博视频链接和 B站 `b23.tv` 按用户决定作为不可获取留原因，微博长文章排除；目标单元、隔离 PostgreSQL 与网页五平台选择 Mock E2E 通过 |
| R2 | 评论请求只接受平台白名单 typed ID，非法定位符和长文章零请求 | #526 / AC2 | satisfied | `comment_target.py`、TikHub Runtime、五平台单元回归；历史 `ttarticle_id` 连同 `status_id` 一并拒绝，来源哈希和文章 ID 不再回退发请求 |
| R3 | 精确解析有独立 Attempt/Raw、持久结果与明确失败语义 | #526 / AC3 | satisfied | 小红书/抖音短链经独立 Attempt/Raw 解析并将 typed ID 写入原 Content；评论 503 恢复复用详情 Raw；空详情、歧义、网络未知和跨 Content 身份冲突分别在隔离 PostgreSQL 留下 Raw/Attempt 与稳定原因，冲突零评论请求；摄取事务内同一目标 ID 加锁并复核归属，模拟绕过早期检查仍被阻断；其他三类链接依用户决定不可获取 |
| R4 | 五平台评论与回复分页耗尽、可恢复且 Coverage 真实 | #526 / AC4 | satisfied | 隔离 PostgreSQL 五平台原生 ID 两页一级评论至终止、五平台回复根归属/线程 Coverage、五平台 503 新 Attempt 与详情 Raw 复用；小红书第二页 503 复用首页 Raw/游标并去重；回复短缺为 partial；既有 Job/Provider 测试覆盖取消、Fencing、并发 CAS 和 deadline。真实 TikHub 五平台一级评论均到终止，快手 221 条不重复，抖音跨页 5 条重复按 ID 去重；抖音/B站/快手有真实回复正例，小红书/微博用真实字段 Fixture 和 PostgreSQL 纵切覆盖结构 |
| R5 | Eligibility 与 Run/Scope 可解释直接、待解析、阻塞及部分结果 | #526 / AC5 | satisfied | Eligibility 直采/待解析/阻塞及原因；持久 Scope 身份解析状态、一级评论/回复分项计数、Coverage、Attempt、失败码与页面平台汇总；混合来源失败 Scope 不发错误请求；五平台真实浏览器/API/Worker/PostgreSQL 全栈检查各 Scope 已解析和评论分项数；回复短缺和冲突集成覆盖 partial/unavailable |
| R6 | 网页创建、跟踪、恢复、结果跳转及数据库评论分页闭环 | #526 / AC6 | satisfied | Campaign Excel 导入五平台原生 ID → 网页 202 → 持久 Worker/Fake TikHub/隔离 PostgreSQL → Run Detail → 声音广场一级评论和小红书双页回复，Playwright Full-stack 1 passed；Batch 与分页/刷新复用现有组件和 Mock E2E 回归 |
| R7 | 调试入口复用生产实现，失败样本受控重放或明确不可获取 | #526 / AC7 | satisfied | `imports_test` 继续复用生产身份解析/评论 Runtime，相关四个文件 18 passed；旧 Run 1930 行只读审计为 1876 complete、18 partial、36 unavailable，34 个 HTTP 失败与 82 条跨帖错配均能定位到已有 Raw；短缺和失败保留原状态，不重发 1876 行已成功请求，未改写原始结果 |
| R8 | 五平台多层测试、真实 Provider Probe、全栈和费用台账 | #526 / AC8 | satisfied | 单元/Contract、隔离 PostgreSQL 70 passed、前端 Mock E2E 与五平台浏览器全栈 1 passed；真实 TikHub 新增 23 次有界请求，计划 0.041 美元：快手 12 页 221 条到空页，其余四平台一级评论均到 Provider 终止，抖音跨页 5 条重复；抖音/B站分别 3/1 条回复到终止，快手 6/6。小红书/微博固定样本无有回复的根评论，历史真实字段 Fixture 与数据库纵切覆盖；不可获取链接与样本限制已记台账，不把计划费用当实际账单 |
| R9 | 文档迁移、Completion Audit、Review、PR/main CI 与 Roadmap 退出 | #526 / AC9 | explicitly_deferred | Product、API、Blueprint、Appendix、模块 README 已承载长期事实，live Roadmap 已退出；上游和反向能力审计及两阶段本地 Review 已完成。PR current-head CI 必须在 Ready/push 后通过，main fresh CI 必须在 merge 后通过；这两项按仓库生命周期顺序暂记待执行，不豁免合并门禁或最终验收 |
| R10 | 微博 `ttarticle` 长文章不补采评论；删除新增的文章 ID 提取，历史定位字段即使伴随 `status_id` 也零请求 | user:2026-09-17-ttarticle-decision#AC1 | satisfied | `imports/identity.py`、`comment_target.py`、`collection_targets.py` 和补采页不可用说明；目标单元/离线入口 48 passed，隔离 PostgreSQL Eligibility 10 passed，前端目标 8 passed |

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
7. 同步文档并执行 Completion Audit：重新读取 Issue、原路线图的 Git 历史与现行 Product/Blueprint/Appendix，逐项核对 R1–R9、前后端和结果反向能力；运行项目 Ready Check、两阶段 Review、current-head CI；满足后 merge，执行 main fresh CI 与仓库原生归档/Issue 关闭检查。

# 兼容、数据、部署与回滚

- 预计不增加数据库表、Migration、依赖或 Job type；若真实 Schema/FK 无法表达来源，先回到设计门禁，不用 JSON 绕过。
- HTTP 只增加可选响应诊断，旧请求和详情响应兼容。前后端同版本发布；本任务不包含生产部署或数据迁移。
- 可关闭新增平台解析入口并回滚代码；保留已写入的 typed identity、Raw 和评论。请求前 typed ID 保护不得回滚。

# Completion Audit

- [x] upstream_re_read：本轮重读 #526 的 AC1–AC9、原路线图退出定义、当前 HTTP Contract、正式 Runtime/Mapper、数据库关系和 CI；确认长文章排除及三类无法精确映射链接的用户决定没有降低五平台原生 ID 门槛。
- [x] change_coverage：AC1–AC8 对应 R1–R8 均有单元、Contract、隔离 PostgreSQL、浏览器全栈或有界真实 Probe 的适用证据；AC9 的文档与审计完成，PR/main CI 按生命周期继续执行。
- [x] reverse_audit：五平台后端目标在 Eligibility、网页创建、Run Detail 和声音广场均有入口；前端请求经生成 Client 到持久 Job/TikHub Operation/Mapper/Content Owner，分层评论数来自数据库 Candidate/Comment，身份来源经 Attempt/Raw 可回溯；冲突、歧义、缺身份和长文章不发错误请求。
- [x] unresolved_cleared：R1–R8、R10 已满足；R9 仅将按时间顺序必须在 Ready/merge 后运行的 PR/main CI 明确记为 `explicitly_deferred`，不得据此跳过任一 CI 或合并门禁。

## 两阶段 Review（2026-09-17）

1. 上游完成定义复核：从 #526 重建五平台原生身份、短链范围、评论/回复分页、持久恢复、网页闭环、离线兼容与真实费用边界；逐项核对 R1–R10。小红书/微博固定样本无真实回复正例已在台账注明，使用历史真实字段 Fixture 与 PostgreSQL 纵切验证结构，不把不可见评论写成已抓取。
2. 实现与证据复核：检查 Content 身份所有权的发送前及摄取事务检查、Candidate/Attempt/Raw 追溯、Root/Reply 分类、Scope 检查点、可选 HTTP 响应和生成 Client。复核中发现检查点推进原进度会破坏重试，已保持原进度；快手回复缺 `parent_comment_id` 的真实形状用 `root_comment_id` 判层级；`comments_completed` 前先持久化覆盖阶段。目标回归、70 例隔离数据库及浏览器全栈重新通过，无未解决的重要代码问题。

# 本轮已取得的验证证据（2026-09-17）

- Windows 本地 Python 单元、Contract、API：排除 3 个环境/本地数据相关文件后，`1196 passed, 8 skipped`。排除项分别依赖 POSIX 主机行为、Windows 路径表示和本机既有忽略 Raw 输出；不能将此结果写成完整套件通过。
- 隔离 PostgreSQL 18.4 容器完成 Alembic `upgrade head` 后，Collection 集成测试 `99 passed`；新增批次补采不因抽样目标提前停止的测试单独通过。补充五平台 typed ID 从 Content Owner 账本读取的参数化回归后，再次使用一次性容器运行目标文件 `9 passed`。测试没有写入用户开发数据库；临时密码文件和容器已清理。
- 前端 28 个 Vitest 文件共 `157 passed`，指定 Collection/Voice Plaza 的 Playwright Mock E2E `26 passed`；lint、生产构建和 TypeScript 检查通过。
- 后端 `mypy backend/src` 检查 346 个源码文件通过；OpenAPI 生成一致性及兼容检查、文档和架构/表 Owner 检查通过。
- 最新长文章排除决策的 48 个目标单元/离线入口测试通过；隔离 PostgreSQL 18.4 完成 Alembic `upgrade head` 后，Eligibility 目标集 10 passed，证实历史 `ttarticle_id` 与 `status_id` 并存时也不会成为可补采 Target。一次性容器与临时密码文件已清理。
- 真实 TikHub 有界 Probe 的请求数、计划费用和局限记录于 TikHub 接口台账；四个平台固定样本 Detail/一级评论成功，原固定快手样本的 Detail/非空评论闭环未通过。
- 后续有界 Probe 找到一个可见的“爱玛”快手候选，Detail、30 条根评论和 10 条回复的结构/归属通过生产 Mapper；用户给的另一快手链接仍返回空 `data.photos`。微博标准帖 Detail/评论成功，但其 Detail 不含用户另给长文章 ID，不能证明长文章的父帖映射。长文章正向样本的 4 次 App 请求均为 HTTP 400；不能据页面显示的 1 条评论断言已补采。完整请求/费用与边界见 TikHub 台账。
- 同一快手候选的追加分页 Probe：4 次请求、计划费用 0.004 美元；前两页一级评论 30+20 条正确归属且无跨页重复，第二页后仍有下一游标。一条根评论的回复第一页 6 条、次页空页终止，均正确归属；另 1 次请求、计划费用 0.001 美元核对其报告回复数也为 6。此证据只证明快手部分真实分页和该线程回复覆盖，尚未证明一级评论最终耗尽。
- 小红书 App V2 图文详情 `share_text` 实测：已验证长链接返回唯一详情和一致 `note_id`；近期公开短链返回 HTTP/业务码 200、唯一详情和 typed `note_id`。旧公开“爱玛”短链两次 HTTP 400。实际 4 次详情请求、计划费用 0.040 美元；长链接 Probe 计划的第二次评论请求因费用上限不足在发送前被拒绝。隔离 PostgreSQL 中小红书与抖音短链解析→评论→原 Content 写入通过；新增小红书评论 503 重试回归先失败后修复，确认复用已持久的解析 Raw。
- 官方 endpoint-info 核价后，抖音 App V3 官方示例短链 1 次请求、计划 0.001 美元，返回唯一可映射数字 `aweme_id`。快手已验证作品做 3 组“生成短链 → 按 URL 查询”回环，共 6 次请求、计划 0.009 美元，生成目标 ID 与输入相同，解析响应虽为 HTTP/业务码 200 且 `data.result=1`，`data.photo.photoId` 三次都与输入不一致；未证明精确归属，正式请求必须继续阻断。详见 TikHub 台账。
- 微博视频详情官方链接示例的带前缀 ID 与去前缀数字分别 HTTP 400；另一官方数字示例 HTTP/业务码 200 且实际 `data.status.idstr` 为数字，说明文档所列 `items[0].data.idstr` 与现行返回不一致。B站 Web V3 URL 详情对一个公开 `b23.tv` 短链 HTTP 400。微博 4 次/B站 1 次业务请求计划费用分别 0.004/0.001 美元；这些样本不支持把短链解析接入正式补采。
- 短链详情空列表的隔离 PostgreSQL 回归先显示泛化 `scope_execution_failed`，修复后 Scope 稳定返回 `identity_unavailable`，只产生一次解析请求，不写 typed ID 或评论。
- 用户指定离线脚本的旧 Run 中 2 行小红书 `comment_content_identity_mismatch` 经逐条只读核对，原 Canonical 身份与 typed `note_id` 相同，Provider 返回的 76 条和 6 条评论均指向其他内容；原有过滤正确，不能把它们挂回原内容。另为合法的“Canonical 主身份与 typed ID 不同”场景新增失败回归，并在核对 Provider typed ID 后安全挂载一级评论和回复；相关离线工作流 22 passed，串帖过滤测试继续通过。旧 Run 未修改，也未对这两行再次付费。
- 用户确认三类链接不可获取后，Eligibility 的可解析候选与阻塞计数修正，隔离 PostgreSQL 目标用例 4 passed，补采纵切集 51 passed；采集运行页 Playwright 16 passed。五平台原生 ID 各通过两页一级评论入库、回复与线程 Coverage，以及评论 503 后新 Attempt 恢复并复用详情 Raw，三组目标共 15 passed。快手 Detail 的视频与封面 `position` 冲突曾导致入库失败，修复后五平台均为成功终态；五平台 Mapper 单元 16 passed。用户指定 `enrich_comments.py` 相关四个测试文件 18 passed，未直接运行付费的真实数据脚本。前端 lint/typecheck/build、本次 Python Ruff 与 `mypy backend/src` 通过。
- 最终本地增量：隔离 PostgreSQL 18.4 跑 70 例全部通过，五平台根/回复发送期间可轮询到正确阶段；事务内目标所有权检查在模拟早期检查失效后仍拒绝冲突，Raw/Attempt 留证。`enrich_comments.py` 直接相关的六个测试文件 22 passed；前端 lint/typecheck/生产 build、浏览器全栈五平台 1 passed、Python Ruff/mypy、Contract 生成与兼容、文档/Secret/表 Owner 检查通过。真实 TikHub 新增 23 次请求、计划 0.041 美元：快手一级评论 12 页 221 条到空页，另外四平台到 Provider 终止；抖音/B站/快手回复正例分别为 3/1/6 条。构建在受限沙箱中因 Windows helper `spawn EPERM` 失败，授权运行后退出 0；这是环境权限差异，不是源码构建失败。
- Roadmap 长期规则已迁入 Product、API、Blueprint、Appendix 和 Collection README，原 live 文件退出，历史计划及阶段证据由本 Change 和 Git 保留。PR current-head CI 与 merge 后 main fresh CI 仍是后续必须通过的门禁，未在本地结果中冒充已通过。

# 交付状态

- Requirement Source：#526；AC1–AC8 本地证据已复核，AC9 的 PR/main CI 待生命周期对应阶段取得。
- Git：本地分支 `feature/five-platform-comment-supplement`、PR #527；Ready 后运行 current-head CI，全部门禁通过方可合并，合并后确认 main fresh CI 与归档。
- 发布和生产部署：不在本次范围。
