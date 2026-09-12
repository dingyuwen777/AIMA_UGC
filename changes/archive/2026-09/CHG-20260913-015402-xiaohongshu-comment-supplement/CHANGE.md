---
schema: coding-change/v1
id: CHG-20260913-015402-xiaohongshu-comment-supplement
title: 修复小红书多图帖子评论补采中断
level: L2
status: done
owner: dingyuwen777
branch: fix/xiaohongshu-comment-supplement
created: 2026-09-13
updated: 2026-09-13
completion_gate: required
depends_on: []
affected_areas:
  - collection
  - provider
  - comments
  - docs
affected_paths:
  - backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - tests/unit/collection/
  - tests/integration/collection/test_xiaohongshu_incremental_comments_runtime.py
  - docs/collection/01_xiaohongshu.md
  - docs/appendix/02_TikHub五平台真实响应与字段映射.md
  - changes/active/CHG-20260913-015402-xiaohongshu-comment-supplement/CHANGE.md
contracts: []
data_changes:
  - none
---

# 变更摘要

- **问题**：小红书图文详情可能让多张图片都返回 `images_list[].index=0`。Mapper 直接采用该字段后，`content_media(content_id, position)` 主键冲突，详情事务失败，评论请求尚未发出。
- **修改**：Canonical 媒体位置改为 `images_list` 数组顺序；账号用任一已知稳定备用 ID 收敛到既有平台账号；用单元测试和 PostgreSQL/Fake Transport 纵切固定“媒体成功入库后继续请求评论”；Scope 的未预期异常增加不含 Raw/Secret 的安全诊断日志。
- **结果**：目标多图帖子能够完成详情入库并继续评论补采，既有声音广场通用评论 API/页面无需新增按钮或专用重试接口。

# 背景与已确认事实

| 编号 | 已确认事实 | 证据 | 结论 |
| --- | --- | --- | --- |
| E1 | 目标内容 `42cb0f34-414d-4298-849f-699a8110b060` 的两次补采均只请求 Detail，未请求 Comments | 本地 Compose PostgreSQL Provider Request/Attempt | 失败发生在评论请求之前 |
| E2 | 目标 Detail Raw 有 5 张图片，所有 `index` 都是 `0` | 本地已持久化 Raw Artifact | Provider 的图片 `index` 不能作为唯一位置 |
| E3 | PostgreSQL 报 `content_media` 主键冲突，键为同一内容的 `position=0` | 本地 Compose PostgreSQL 日志 | 详情媒体写入回滚直接阻断评论补采 |
| E4 | 现有声音广场已经通过通用 Content/Comment PostgreSQL 查询展示评论层级 | 已合并 PR #474、归档 Change `CHG-20260913-001143-comment-thread-voice-plaza` | 本次不再新增页面、API 或 Schema |
| E5 | 修复媒体位置后，目标帖子已发出 `get_note_comments`，但评论作者的 `red_id` 命中既有账号、Provider `userid` 与既有主 ID 不同，写入第二个账号时触发 `account_external_ids` 唯一冲突 | 本地真实 Run `3598c260-ec06-4a56-bb26-5d4561155ac1`、Worker 安全日志、PostgreSQL 错误日志和账号只读查询 | Content Owner 应用任一已知稳定备用 ID 收敛账号；主 ID 与备用 ID 指向不同账号时仍须 fail closed |
| E6 | 修复账号收敛后，新建辅助补采 Run 在帖子评论数未变化时只请求 Detail、跳过 Comments | 本地真实 Run `c1a5de85-1f64-44cb-9e5c-9812cd974ff5`；新增 PostgreSQL 纵切在修复前稳定复现只出现 Detail 请求 | 网页端显式勾选评论创建的新 Run 必须冻结“评论数未变化也刷新”策略，才能恢复上次失败或不完整的评论补采 |

# 目标、范围与非目标

## 成功标准

- [x] 多张图片即使重复 Provider `index`，Canonical `position` 仍唯一、稳定并保持响应顺序。
- [x] PostgreSQL 纵切能保存全部图片、继续调用 `get_note_comments` 并入库评论。
- [x] 评论作者主 ID 漂移但稳定备用 ID 一致时复用既有账号；身份线索指向不同账号时拒绝错误合并。
- [x] 用户通过网页端新建辅助补采并勾选评论时，即使 Provider 评论数未变化也重新请求评论。
- [x] 目标业务帖子经本地真实辅助补采后，声音广场评论 API 能读到已采集评论及父子关系。
- [x] 未预期 Scope 失败日志保留 run/scope/platform/异常类型，不输出 Raw、Secret 或异常原始消息。
- [x] 不新增依赖、Migration、公共 Contract、补采按钮或专用重试 API。

## 范围

- 小红书 TikHub Content Mapper、Collection Scope 安全诊断、相关单元/集成测试与平台事实文档。
- 对目标帖子做一次有界本地真实 Provider 验证，并从 PostgreSQL/HTTP 读取结果。

## 非目标

- 不修改 TikHub Endpoint、分页、费用或五平台 Capability 策略。
- 不修改评论父子关系 Contract、声音广场布局或 Figma。
- 不部署生产环境，不修改数据库 Schema，不升级依赖。

## 必须保持不变

- Provider Raw 原样保留；Mapper 不回写或伪造第三方字段。
- PostgreSQL 是媒体与评论业务事实源；前端只通过现有生成 Client/API 读取。
- 已有 Collection Job、补采入口、评论分页与回复归属语义保持兼容。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 修复目标帖子因多图重复位置而抓不到评论的问题 | #473 / AC6 | satisfied | 重复位置 Red/Green；真实 Run `6386f0ba-6fe4-4827-9ff2-efd55231bbb1` 保存 5 张媒体并完成 Detail、Comments、Sub-comments |
| R2 | 修复是系统性的，未来网页辅助补采走同一生产 Mapper/Runtime | #473 / AC5 | satisfied | 修改生产 Mapper、Content Owner 与 `PostgresCollectionHttpService` 冻结策略；正式 Worker 真实 Run 成功，未建立平行调试链 |
| R3 | 保持评论及父子关系经声音广场现有页面展示，不新增专用按钮/API | #473 / AC2 | satisfied | 现有评论 API 返回 3 根评论、1 回复及直接父作者；本地浏览器展开显示“淇 YONG 回复迟煜：在滴” |
| R4 | 只有验证与合并门禁通过后才合并主分支 | #473 / AC6 | satisfied | 本地 66 项扩展回归、Ruff、Mypy、Backend 镜像、真实 Provider/API/浏览器和两阶段 Review 已通过；PR #475 继续由必需 CI 阻止提前合并 |

# 实施与验证计划

1. 用重复图片 `index=0` 的 Mapper 测试复现 `[0,0,0]`，改为按数组顺序生成 `[0,1,2]`。
2. 让 Content Owner 在主 ID 未命中时按已观察到的稳定备用 ID 收敛账号；多个身份线索冲突时 fail closed。
3. 让网页辅助补采冻结显式评论刷新策略；扩展正式 Collection Runtime PostgreSQL 纵切，断言评论数未变化时仍发出评论请求并成功入库。
4. 为 Scope 未预期异常补安全日志及日志泄密回归。
5. 扩大运行小红书、Content Ingestion、Collection Scope、评论/回复回归与静态检查。
6. 构建本地 Backend，使用现有辅助补采入口对目标内容有界重跑；验证 Provider Request、媒体、评论及现有评论 HTTP 输出。
7. 更新完成审计、Review、PR 检查；满足门禁后合并，读取主分支新鲜结果并由仓库自动化归档 Change。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 单元 / 回归 | required | 重复媒体位置、安全异常日志、小红书 Mapper/Operation |
| 集成 / 持久化 | required | Detail → `content_media` → Comments → `comments` PostgreSQL 纵切 |
| 外部 Provider | required | 目标内容一次有界 TikHub 本地补采，Secret 不进入输出或提交 |
| HTTP / 用户路径 | required | 现有内容评论资源返回目标评论、根评论与父评论字段 |
| 静态 / 构建 | required | Ruff、Mypy、Backend 镜像构建 |
| 文档 / 治理 | required | 平台字段事实、Change Completion Gate、PR/CI/main 新鲜验证 |

# 风险、兼容、迁移与回滚

| 项目 | 结论 |
| --- | --- |
| 风险 | 非字典图片项会被跳过，位置可能有空洞但仍唯一；顺序与 Provider 数组事实一致 |
| 兼容性 | Canonical/Public Contract 不变；正常唯一 Provider `index` 的可见媒体顺序仍与数组顺序一致 |
| 数据 / Migration | 无 Schema 变化；已有失败行无需修复，重新补采即可 |
| Provider / 费用 | Endpoint、分页和价格策略不变；只对目标内容做一次有界验证 |
| 部署 | Backend 代码需随正常版本发布；前端无需变更 |
| 回滚 | 回滚代码提交即可；真实补采新增的正确媒体/评论属于可重复幂等业务事实，不需删除 |

# 完成审计

- [x] upstream_re_read：重读用户要求、Issue #473、生产 HTTP/Worker/Mapper/Content Owner、归档评论展示 Change 与 `origin/main@4c9b2d07`。
- [x] change_coverage：R1—R4 均有本轮实现或验证证据，`not_satisfied` 已清零。
- [x] reverse_audit：网页辅助补采请求冻结强制评论刷新策略，经持久 Job、生产 Mapper、Content Owner 写 PostgreSQL；声音广场再经现有评论 API 读取根评论/回复，没有平行链路。
- [x] unresolved_cleared：真实 Provider、业务库、HTTP、浏览器、扩展回归、静态检查、镜像构建与两阶段 Review 已完成；远程 CI 和合并后 main 验证属于 PR 交付门禁，不以本地结果替代。

# 两阶段 Review

## Review A1：上游要求 → Change

结论：通过。Issue #473 AC6 与用户本轮合并要求已逐项进入 R1—R4；同时保留前序决定：不新增按钮/重试 API、不修改评论 Contract/Schema、不把调试入口当正式实现。

## Review A2：Change → 实现、测试与文档

结论：通过，未发现剩余阻断 Finding。

- Mapper 只把 Canonical 媒体位置改为 Provider 数组顺序，Raw 和 Endpoint 不变；重复 `index` 回归覆盖 3 张图片。
- 账号收敛只使用本次明确观察到的备用稳定 ID；主/备用 ID 指向不同账号或平台时 fail closed，避免误合并。
- 网页创建的新 Run 只在用户勾选评论时开启未变化刷新；未勾选评论、Scheduler 与既有冻结 Run 行为不变。
- Scope 日志只输出关联 ID、平台、operation group 与清洗后异常类型/栈，不输出异常原始消息、Raw 或 Secret。
- 生产代码、测试、文档与实际运行结果一致；无依赖、Migration、公共 Contract、前端或 Figma 变更。

# 完成证据与交付状态

- Red：重复图片位置单测得到 `[0,0,0]` 而非 `[0,1,2]`；评论数未变化的辅助补采纵切只发出 Detail 请求。
- Green：评论数未变化纵切发出 Detail + Comments 并成功入库；小红书媒体/评论/回复、Collection 恢复、Content Owner 与声音广场相关扩展回归 `66 passed`。
- 静态：本次 Python 文件 `ruff format --check`、`ruff check` 通过；`mypy backend/src` 为 `Success: no issues found in 340 source files`；`git diff --check origin/main...HEAD` 通过。
- 构建：`docker build --build-arg AIMA_BUILD_PYPI_INDEX=https://pypi.org/simple --target backend --tag aima-ugc-backend:internal-v1a .` 成功，manifest list `sha256:fe5a6e9e0ecb920cd7e81652cb9f2d467b699e8f80d5c8b3d77898fe54be518e`。
- 真实 Provider：Run `6386f0ba-6fe4-4827-9ff2-efd55231bbb1` 状态 `succeeded`，`requested=4 / succeeded=4 / failed=0 / comments=4`；目标 Scope 依次完成 `get_image_note_detail`、`get_note_comments`、`get_note_sub_comments`。
- 业务事实：目标 Content `42cb0f34-414d-4298-849f-699a8110b060` 有媒体位置 `0—4`、3 条一级评论和 1 条回复；回复的 `root_comment_id`/`parent_comment_id` 均指向“迟煜：还在吗？”。
- HTTP/浏览器：根评论资源返回 `total_count=3, ingested_total_count=4`，回复资源返回直接父作者“迟煜”；声音广场实际展开显示“淇 YONG / 回复迟煜 / 在滴”。
- 环境说明：首轮扩展回归的 16 个 Error 来自受限 pytest 临时目录 ACL，并非断言失败；确认 127.0.0.1:5432 只映射隔离容器 `aima-ugc-postgres-dev` 后，在沙箱外指定独立 basetemp 重跑全部 66 项通过，业务 PostgreSQL 未参与测试写入。
- 追溯：PR body 使用仓库机器门禁支持的 `Requirement-Source: #473`，Change 内部继续以 `#473 / AC2`、`AC5`、`AC6` 绑定精确验收项。
- PR：[#475](https://github.com/dingyuwen777/AIMA_UGC/pull/475) 已推送 Ready 实现；待当前头提交的必需 CI 全绿后按用户授权合并，再读取远程 main 新鲜状态。
