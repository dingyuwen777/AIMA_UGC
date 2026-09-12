---
schema: coding-change/v1
id: CHG-20260913-015402-xiaohongshu-comment-supplement
title: 修复小红书多图帖子评论补采中断
level: L2
status: in_progress
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

# 目标、范围与非目标

## 成功标准

- [ ] 多张图片即使重复 Provider `index`，Canonical `position` 仍唯一、稳定并保持响应顺序。
- [ ] PostgreSQL 纵切能保存全部图片、继续调用 `get_note_comments` 并入库评论。
- [ ] 评论作者主 ID 漂移但稳定备用 ID 一致时复用既有账号；身份线索指向不同账号时拒绝错误合并。
- [ ] 目标业务帖子经本地真实辅助补采后，声音广场评论 API 能读到已采集评论及父子关系。
- [ ] 未预期 Scope 失败日志保留 run/scope/platform/异常类型，不输出 Raw、Secret 或异常原始消息。
- [ ] 不新增依赖、Migration、公共 Contract、补采按钮或专用重试 API。

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
| R1 | 修复目标帖子因多图重复位置而抓不到评论的问题 | 用户 2026-09-13 明确要求；Issue #473 补充验收 | not_satisfied | 待目标帖子真实补采与数据库/API验收 |
| R2 | 修复是系统性的，未来网页辅助补采走同一生产 Mapper/Runtime | 用户前序要求；Issue #473 AC5 | not_satisfied | 待纵切、调用链复核与本地网页入口验证 |
| R3 | 保持评论及父子关系经声音广场现有页面展示，不新增专用按钮/API | 用户前序决定；Issue #473 AC1—AC5 | not_satisfied | 待真实评论入库后用现有 HTTP Contract 验收 |
| R4 | 验证无问题后合并到主分支 | 用户 2026-09-13 明确授权 | not_satisfied | 待两阶段 Review、Ready 检查、PR/CI 与合并后 main 验证 |

# 实施与验证计划

1. 用重复图片 `index=0` 的 Mapper 测试复现 `[0,0,0]`，改为按数组顺序生成 `[0,1,2]`。
2. 让 Content Owner 在主 ID 未命中时按已观察到的稳定备用 ID 收敛账号；多个身份线索冲突时 fail closed。
3. 扩展正式 Collection Runtime PostgreSQL 纵切，断言媒体位置唯一、评论请求被发出、评论成功入库。
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

- [ ] upstream_re_read：合并前重读用户要求、Issue #473、相关生产 Mapper/Runtime、归档 Change 与最新 main。
- [ ] change_coverage：R1—R4 均有新鲜实现或验证证据，`not_satisfied` 清零。
- [ ] reverse_audit：从网页辅助补采入口追到正式 Mapper/写库，并从声音广场评论加载追到 PostgreSQL；不增加平行链路。
- [ ] unresolved_cleared：真实 Provider、业务库/API、Review、PR/CI/main 证据完整，剩余风险明确。

# 完成证据与交付状态

待实现与验证后填写；当前不声明 Ready、完成或可合并。
