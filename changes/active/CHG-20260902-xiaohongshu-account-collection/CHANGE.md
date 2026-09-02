---
schema: coding-change/v1
id: CHG-20260902-xiaohongshu-account-collection
title: 小红书指定账号按日期采集笔记与评论
level: L2
status: in_progress
owner: chatgpt
branch: feature/296-xiaohongshu-account-collection
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - provider
  - collection-debug
  - export
  - documentation
affected_paths:
  - backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py
  - backend/src/aima_ugc/adapters/providers/tikhub/runtime.py
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
  - tests/unit/collection/
  - tests/fixtures/providers/tikhub/xiaohongshu/
  - docs/collection/01_xiaohongshu.md
  - docs/appendix/04_TikHub接口选型与真实验证台账.md
contracts: []
data_changes: []
---

# 目标

实现 Issue #296：给 `tikhub_test` 增加小红书指定账号人工采集入口。账号发现补齐正式 TikHub App V2 用户搜索、用户信息与用户发布笔记 Operation；取得 `note_id` 后继续复用现有 Detail / Comments / Replies / Mapper / Canonical / JSONL / Excel 链路。

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/296

本次默认人工目标账号为：爱玛电动车、爱玛三轮电动车、爱玛东2楼、我是玛小爱、元宇宙女孩的实验室；身份解析以配置的小红书号 `red_id` 精确匹配为主，昵称只作辅助核验。

# 成功标准

- [ ] 支持 `nickname + red_id` 或已知 `user_id` 的多个账号配置。
- [ ] `red_id` 精确匹配优先；昵称歧义不得自动选第一条。
- [ ] 正式 TikHub Operation/Runtime 支持 `search_users`、`get_user_info`、`get_user_posted_notes` 及安全分页。
- [ ] 用户笔记按 `Asia/Shanghai` 日期边界过滤；不假设 Provider 顺序而提前漏页。
- [ ] 日期范围内笔记复用现有 Detail / Comments / Replies / Mapper / Canonical / Excel 处理链。
- [ ] 人工调试支持 `limited/all` 评论模式；`all` 只移除软数量目标，仍保留 Provider 终止和硬页数保护。
- [ ] 输出继续使用现有 `contents.jsonl`、`comments.jsonl`、统一 Excel、Raw 与 run summary。
- [ ] 单账号失败不丢弃其他账号成功结果，summary 能定位账号与失败阶段。
- [ ] 不改数据库 Schema、HTTP API、前端、Canonical Schema、Excel Schema、依赖或 Runtime 版本。
- [ ] 真实 TikHub Probe 只在 GitHub Runner 且可安全引用 Actions Secret 时有界执行；Secret 不进入 Git、日志、Fixture、Issue、PR 或 Artifact。

# 范围

- 扩展 `operations/xiaohongshu.py` 的用户相关 App V2 Operation、Extractor 与分页状态机。
- 扩展 `runtime.py` 的小红书用户相关调用包装，不把 Provider 私有 cursor 暴露到业务层。
- 在 `tikhub_test` 增加账号配置、解析缓存、日期过滤、多账号失败隔离与人工运行入口。
- 复用当前 `_process_content`/等价公共处理链，并最小重构使关键词发现和账号发现共享内容处理。
- 补 Fixture/Unit/纵切测试以及当前平台/调试文档。

# 非目标

- 不接入正式 Collection Plan、Scheduler、数据库写模式或前端。
- 不新增账号专属 Canonical/Excel Schema。
- 不新增自动 App/Web fallback。
- 不为本功能顺手升级依赖、Runtime、CI 或 Workflow。
- 不把真实 TikHub Probe 变成普通 CI。

# 必须保持不变

- `Provider Raw → Mapper → Canonical` 正式边界。
- 小红书 Content 身份仍为 `platform + external_content_id(note_id)`。
- 现有 Detail、Comments、SubComments、Mapper、Raw、Canonical 与统一 Excel Owner 不复制第二套实现。
- Production Collection 的 `CollectionDecisionPolicyV1.comment_mode=adaptive` 不因人工调试的 `limited/all` 模式改变。
- Secret 只通过既有安全配置/Secret 引用进入 Transport。

# 关键决策

- 账号采集是新的 Discovery Source，不是新的 Content Pipeline。
- `search_users` 先解析稳定 `user_id`；错误 `user_id` 的用户信息/用户笔记请求仍会计费，因此不通过试错调用猜身份。
- `red_id` 是人工配置的主匹配条件；昵称变更不改变稳定账号选择，但需在 summary 暴露配置名与实际名差异。
- 用户发布笔记接口按 cursor 翻页；在没有真实证据证明严格倒序前，不因某页出现早于起始日期的笔记提前终止。
- 日期配置使用人类可读的包含式 `start_date/end_date`，内部转换成北京时间 `[start_at, end_at_exclusive)`。
- `comment_mode=all` 属于 `tikhub_test` 人工执行策略，不修改正式 Collection Decision Contract。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 指定多个账号按日期抓全部目标笔记 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | not_satisfied | 待实现与验证 |
| R2 | 账号消歧以 red_id 精确匹配，不猜同名账号 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | not_satisfied | 待实现与验证 |
| R3 | 取得 note_id 后复用现有详情/评论/回复/Canonical/Excel | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | not_satisfied | 待实现与纵切验证 |
| R4 | 完整评论模式不受软目标截断但保留硬保护 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | not_satisfied | 待实现与边界测试 |
| R5 | 不改变数据库/API/前端/Canonical/Excel Contract | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | not_satisfied | 完成前 diff/Contract 审计 |
| R6 | TikHub 真实结构验证仅 GitHub Runner，且 Secret 不泄露 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | not_satisfied | 若存在安全 Actions Secret 则有界 Probe；否则显式未验证 |

# Validation Matrix

| 验证层 | 状态 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 用户 Operation、账号消歧、cursor、日期边界、去重、评论模式、失败隔离 |
| 接口 / Contract | required | 保持 Canonical/Excel/正式 Collection Contract 不变；用户 Operation 的生产 Adapter API 有回归 |
| 集成 / Persistence / Runtime Dependency | required | `tikhub_test` 使用 Fake Transport 走真实 Runtime/Mapper/Raw/JSONL/Excel 文件链；数据库不参与 |
| 用户 / Workflow Acceptance | required | 从人工账号配置入口到 run summary/JSONL/Excel 的调用者工作流 |
| 跨组件 Golden Path | not_applicable | 本次不接前端/API/Worker/数据库，不存在新的跨进程产品链 |
| External Dependency / Provider Probe | required | 新接 TikHub 用户 Operation 需要确认当前真实 shape；仅 GitHub Runner + 安全 Secret 时执行 |
| Build / Package / Runtime | required | 受影响 Python 包的格式/lint/type/unit 与 Wheel/仓库 CI |
| Docs / Governance / Other | required | Change/Issue 追溯、Secret scan、TikHub 平台文档与调试 README 同步 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取 Issue #296、用户批准方案、当前 TikHub 官方文档和仓库事实。
- [ ] change_coverage：逐条核对账号解析、日期分页、评论模式、输出与失败隔离要求。
- [ ] reverse_audit：从人工入口反查到生产 Operation/Transport/Mapper/Exporter，并确认没有第二套 Provider 解析/输出。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零或有正式延期依据。

# 任务

- [x] 创建 Requirement Source Issue #296。
- [x] 从当前 main `f60f598c84e0696873cc01fc30f4d817ed51ae52` 建立本地等价首个 Change/Red 提交，再首次创建远程任务分支。
- [ ] 建立失败测试并在 GitHub Runner 确认 Red。
- [ ] 实现小红书用户 Operation/Runtime。
- [ ] 实现账号解析、日期窗口、缓存和账号 Discovery。
- [ ] 复用现有内容处理并实现 `limited/all` 人工评论模式。
- [ ] 增加五账号人工配置入口。
- [ ] 补脱敏 Fixture、Unit/纵切回归。
- [ ] 更新 `tikhub_test` README、小红书采集导航与真实验证台账。
- [ ] 执行目标测试、完整受影响 CI、独立 Review 和 Completion Audit。
- [ ] 根据用户授权决定是否 merge；merge 后执行 main fresh CI、关闭 Issue 并清理分支。

# 验证

## 计划

- Red：新增用户 Operation 行为测试，确认当前主分支因缺少实现失败。
- Green：目标 Unit + `tikhub_test` Fake Transport 纵切。
- Static：仓库固定 `ruff format --check`、`ruff check`、`mypy backend/src`。
- Contract/Regression：相关 Unit/Contract；确认 Canonical/Excel schema 无漂移。
- Provider Probe：只在 GitHub Runner 能安全引用既有 Actions Secret 时执行少量 `search_users/get_user_posted_notes` 请求并生成脱敏 Fixture；没有安全 Secret/Runner 触发能力时不得使用聊天密钥绕过。
- Delivery：PR 当前 head CI + Review；获 merge 授权后 main fresh CI。

# 文档影响

- 更新小红书采集实现导航、TikHub 真实验证台账和 `tikhub_test` 使用说明；不新增 Blueprint。

# 兼容、Migration、部署与回滚

- 数据库 Migration：无。
- HTTP/OpenAPI：无。
- 依赖/Runtime：无。
- 部署：无额外部署步骤。
- 回滚：撤销本 Change 代码/文档即可；现有关键词采集链保持原接口与默认行为。

# 交付

- Requirement Source：#296
- 分支：`feature/296-xiaohongshu-account-collection`
- PR：待首次 push 后创建
- 发布：不适用
