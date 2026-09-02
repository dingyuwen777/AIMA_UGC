---
schema: coding-change/v1
id: CHG-20260902-xiaohongshu-account-collection
title: 小红书指定账号按日期采集笔记与评论
level: L2
status: done
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
  - backend/src/aima_ugc/adapters/providers/tikhub/account_runtime.py
  - backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu_accounts.py
  - backend/src/aima_ugc/adapters/providers/tikhub_test/README.md
  - backend/src/aima_ugc/adapters/providers/tikhub_test/__init__.py
  - backend/src/aima_ugc/adapters/providers/tikhub_test/operations/runner.py
  - backend/src/aima_ugc/adapters/providers/tikhub_test/operations/xiaohongshu_accounts.py
  - backend/src/aima_ugc/adapters/providers/tikhub_test/xiaohongshu_accounts_test.py
  - docs/collection/01_xiaohongshu.md
  - tests/unit/collection/test_xiaohongshu_account_collection.py
  - tests/unit/collection/test_xiaohongshu_account_completeness.py
  - tests/unit/collection/test_xiaohongshu_account_incomplete_pagination.py
  - tests/unit/collection/test_xiaohongshu_account_operations.py
contracts: []
data_changes: []
---

# 目标

实现 Issue #296：给 `tikhub_test` 增加小红书指定账号人工采集入口。账号发现补齐 TikHub App V2 用户搜索、用户信息与用户发布笔记 Adapter；取得 `note_id` 后继续复用现有 Detail / Comments / Replies / Mapper / Canonical / JSONL / Excel 链路。

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/296

默认人工目标账号为：爱玛电动车、爱玛三轮电动车、爱玛东2楼、我是玛小爱、元宇宙女孩的实验室；身份解析以配置的小红书号 `red_id` 精确匹配为主，昵称只作辅助核验。默认起始日期为 `2026-08-01`，结束日期取运行当天北京时间日期。

# 成功标准

- [x] 支持 `nickname + red_id` 或已知 `user_id` 的多个账号配置。
- [x] `red_id` 精确匹配优先；昵称歧义或搜索分页不完整时 fail closed，不自动选第一条。
- [x] TikHub Adapter 支持 `search_users`、`get_user_info`、`get_user_posted_notes` 及 Provider-private 安全分页。
- [x] 用户笔记按 `Asia/Shanghai` 日期边界过滤；不假设 Provider 严格倒序而提前漏页。
- [x] 日期范围内笔记复用现有 Detail / Comments / Replies / Mapper / Canonical / Excel 处理链。
- [x] 人工调试支持 `limited/all` 评论模式；`all` 移除评论/回复数量软目标，但保留 Provider 终止和硬页数保护。
- [x] 输出继续使用现有 `contents.jsonl`、`comments.jsonl`、统一 Excel、Raw 与 run summary。
- [x] 单账号失败不丢弃其他账号成功结果；无法完整翻页时使用 failed/partial 事实而不是假完整。
- [x] 不改数据库 Schema、HTTP API、前端、Canonical Schema、Excel Schema、依赖或 Runtime 版本。
- [x] TikHub 真实 Probe 只允许 GitHub Runner + Actions Secret；仓库未配置该 Secret 时在网络请求前安全跳过，聊天中的密钥不进入 Git/Workflow/日志/Fixture/Issue/PR/Artifact。

# 范围

- 新增小红书账号 App V2 Operation、Extractor 与分页状态机。
- 新增账号 Discovery Runtime Adapter，不把 Provider 私有 `search_id/cursor` 暴露到业务层，也不把账号来源升级为正式 Collection Capability。
- 在 `tikhub_test` 增加账号配置、精确消歧、解析缓存、日期过滤、多账号失败隔离与人工运行入口。
- 最小扩展共享调试 Runner：允许账号 `all` 模式显式取消评论/回复数量软目标；关键词入口继续使用原有限量语义。
- 复用现有 Detail / Comments / Replies / Mapper / Raw / Canonical / Excel Owner。
- 补 Unit/Fake Transport 纵切、完整性边界测试与当前平台/调试文档。

# 非目标

- 不接入正式 Collection Plan、Scheduler、数据库账号采集模式或前端。
- 不新增账号专属 Canonical/Excel Schema。
- 不新增自动 App/Web fallback。
- 不升级依赖、Python/Node Runtime、数据库或 CI 常驻 Workflow。
- 不把未执行成功的真实 TikHub Probe 伪装成真实响应 Fixture/验证台账。

# 必须保持不变

- `Provider Raw → Mapper → Canonical` 正式边界。
- 小红书 Content 身份仍为 `(platform, external_content_id)`，其中 `external_content_id=note_id`。
- 现有 Detail、Comments、SubComments、Mapper、Raw、Canonical 与统一 Excel Owner 不复制第二套实现。
- Production Collection 的 `CollectionDecisionPolicyV1.comment_mode=adaptive` 不因人工调试 `limited/all` 改变。
- Secret 只通过既有安全配置或 Actions Secret 引用进入 Transport；任何人工文件、日志和提交均不得持有真实密钥。

# 关键决策

- 账号采集是新的 Discovery Source，不是新的 Content Pipeline。
- `search_users` 负责解析稳定 `user_id`；错误 `user_id` 的用户信息/用户笔记调用可能仍会计费，因此不通过付费接口试错猜身份。
- `red_id` 是人工配置主匹配条件；昵称只辅助核验。仅昵称匹配必须遍历到可证明完整的搜索终点后才能判定唯一。
- 用户发布笔记按 Provider cursor 翻页；没有真实证据证明严格倒序前，不因某页出现早于起始日期的笔记提前终止。
- 日期配置使用包含式 `start_date/end_date`，内部转换为北京时间 `[start_at, end_at_exclusive)`。
- `comment_mode=all` 属于 `tikhub_test` 人工执行策略；一旦正式 Decision 决定进入评论/回复抓取，正数或未知计数不再作为数量停止条件，最终仍受 Provider 分页终止和硬页数保护约束。
- 只有 `provider_exhausted` 或真实 `empty_page` 支持“账号分页正常结束”；缺列表结构、`search_id/cursor` 缺失、重复页、停滞页、`has_more=true` 空页均按 incomplete 处理。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 指定多个账号按日期抓目标范围内全部可完整遍历笔记 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | satisfied | `run_xiaohongshu_accounts`、五账号薄入口、北京时间日期窗口、用户笔记分页与 `test_xiaohongshu_account_collection.py` / `test_xiaohongshu_account_incomplete_pagination.py`；异常分页不会宣称完整。 |
| R2 | 账号消歧以 red_id 精确匹配，不猜同名账号 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | satisfied | `resolve_account_candidate` + 搜索分页完整性门禁；同名歧义、缺 `search_id`、异常响应结构均有 fail-closed Unit/Fake Transport 测试。 |
| R3 | 取得 note_id 后复用现有详情/评论/回复/Canonical/Excel | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | satisfied | Fake Transport 纵切验证 Account Discovery → 现有 `_process_content` → Detail/Comments/Replies → Canonical JSONL → 共享三 Sheet Excel；未新增第二套 Mapper/Exporter。 |
| R4 | 完整评论模式不受数量软目标截断但保留硬保护 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | satisfied | 先在 `b87786b50a9f7fdb7a00dba1db5addac89325915` 得到“第 2 页未消费”的 Red，再改为共享 Runner `target=None/fetch_all=True`；一级评论、二级回复及硬页数 partial 均有回归测试。 |
| R5 | 不改变数据库/API/前端/Canonical/Excel Contract | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | satisfied | 最终实现仅修改 Provider Adapter、人工调试、文档和 Unit；CI Scope 正确跳过 PostgreSQL/Full-stack，Contract/API、Architecture/Ownership、Wheel 均通过；无 Migration/OpenAPI/Canonical/Excel Schema/依赖变更。 |
| R6 | TikHub 真实结构验证仅 GitHub Runner，且 Secret 不泄露 | https://github.com/dingyuwen777/AIMA_UGC/issues/296 | explicitly_deferred | 有界 Runner Probe `33604014094` / Job `100163797816` 仅引用 `secrets.TIKHUB_API_KEY`，因仓库未配置该 Secret 输出 `PROBE_SKIPPED` 并在网络请求前退出；临时 Workflow 已从 PR 移除。真实 Provider shape 因缺安全 Secret 未验证，聊天密钥未被写入或使用。 |

# Validation Matrix

| 验证层 | 状态 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | passed | 用户 Operation、账号消歧、cursor、日期边界、去重、`limited/all`、失败隔离、异常分页/异常响应结构均纳入 Unit/Fake Transport。 |
| 接口 / Contract | passed | Canonical/Excel/正式 Collection Contract 未改；`tests/contracts` 与 `tests/api` 通过。 |
| 集成 / Persistence / Runtime Dependency | passed | 文件模式 Fake Transport 纵切走真实 Runtime/Mapper/Raw/JSONL/Excel；数据库不参与且被 CI Scope 正确判定不适用。 |
| 用户 / Workflow Acceptance | passed | 五账号薄入口、逐账号 summary、Canonical JSONL 和共享 Excel 路径已覆盖。 |
| 跨组件 Golden Path | not_applicable | 本次不接前端/API/Worker/数据库，不新增跨进程产品链。 |
| External Dependency / Provider Probe | explicitly_deferred | 官方 TikHub 文档于 2026-09-02 重新核验；真实 Runner Probe 因 Actions Secret 未配置在网络前安全跳过，因此不创建伪真实 Fixture。 |
| Build / Package / Runtime | passed | PR 最终 HEAD `508ae9bb1213ab2515190f410494f6a26ad8271e` 的 CI `33606034733`、Runtime Acceptance `33606034487`、Change Completion Gate `33606259726` 全部成功；merge commit `066ff0b40dfe3fb693e5a80de6efcd11f6cee7f1` 的 main fresh CI `33606905199`、Runtime Acceptance `33606904924`、Change Completion Gate `33606904936` 也全部成功。 |
| Docs / Governance / Other | passed | README/小红书采集文档已同步，Docs and Governance/Secret scan 通过；临时 Probe Workflow 已清理；PR #298 已按 `expected_head_sha` 正常合并。 |

# Completion Audit

- [x] upstream_re_read：完成前重新读取 Issue #296、用户批准方案、最新仓库 `AGENTS.md`、当前 Canonical Agent_Skills Coding/Review 规则以及 2026-09-02 TikHub 官方 `search_users/get_user_info/get_user_posted_notes` 文档。
- [x] change_coverage：逐条核对账号解析、日期分页、完整评论/回复、输出、失败隔离和异常分页；Review 新发现的 incomplete-pagination 缺口已通过 4 个 Red→Green 用例修复。
- [x] reverse_audit：从 `xiaohongshu_accounts_test.py` 反查到 account Runtime/Operation、现有 Transport/Mapper、共享 `_process_content`、RunOutputStore 和统一 Excel Exporter；未发现第二套 Provider HTTP/Mapper/JSONL/Excel 实现。
- [x] unresolved_cleared：R1-R5 均已满足；R6 的真实 Provider shape 验证因仓库没有安全 Actions Secret 明确延期，且有 Runner pre-network skip 证据，不存在未说明的 `not_satisfied`。

# 任务

- [x] 创建 Requirement Source Issue #296。
- [x] 建立任务分支和 PR #298；在最终 Review 前同步最新 `main`，合并前 merge-base 为 `03c13bc90f4917b8c992ce1584b61b86b4ee2aab`。
- [x] 建立用户 Operation、完整评论和异常分页失败测试，并在 GitHub Runner 获得干净 Red。
- [x] 实现小红书用户 Operation/Account Runtime。
- [x] 实现账号解析、日期窗口、稳定身份缓存和账号 Discovery。
- [x] 复用现有内容处理并实现 `limited/all` 人工评论模式。
- [x] 增加五账号人工配置入口。
- [x] 补 Unit/Fake Transport 纵切和完整性边界回归；未生成未经真实 Provider 验证的伪 Fixture。
- [x] 更新 `tikhub_test` README 与小红书采集文档。
- [x] 执行受影响 CI、Runtime Acceptance、独立 Agent_Skills Review 和 Completion Audit；Review 发现的异常分页问题已修复。
- [x] 尝试安全 GitHub Runner Provider Probe；因 Actions Secret 未配置在网络请求前安全跳过并清理临时 Workflow。
- [x] PR #298 已使用 `expected_head_sha=508ae9bb1213ab2515190f410494f6a26ad8271e` 正常合并，真实 merge commit 为 `066ff0b40dfe3fb693e5a80de6efcd11f6cee7f1`；main fresh CI/Runtime/Completion Gate 全部成功。

# 验证

## Red 证据

- 用户 Operation 首轮 Red：主分支尚无小红书账号 Operation/公共入口，Runner 在目标 import/能力处失败。
- 严格 `all` Red：`b87786b50a9f7fdb7a00dba1db5addac89325915` 上 757 passed / 1 failed；Fake Transport 的第 2 页评论未被消费，证明正数 `comment_count` 不能作为 `all` 完成边界。
- 最新 main 同步后的异常分页 Red：`3bbdc1ff3c625fc42285156a3394bb56326a20dc` 上 761 passed / 2 failed，证明缺 `search_id` 时错误继续到用户笔记、cursor 停滞时错误标记 completed。
- 响应结构 Red：`137e8147f0ec3a587231f4fc5410b3245bfc69f5` 上 761 passed / 4 failed，新增两项精确证明 HTTP 200 但缺用户/笔记列表被误判为正常空页。

## Green 证据

- PR 最终 HEAD `508ae9bb1213ab2515190f410494f6a26ad8271e`：CI `33606034733` 完整成功，包括 format/Ruff/Mypy、Unit/Contract/API、Architecture/Ownership、Wheel 和 CI Gate；Runtime Acceptance `33606034487`、Change Completion Gate `33606259726` 成功。
- 合并后 `main` HEAD `066ff0b40dfe3fb693e5a80de6efcd11f6cee7f1`：fresh CI `33606905199` 成功，fresh Runtime Acceptance `33606904924` 成功，fresh Change Completion Gate `33606904936` 成功。
- main fresh CI 的实际 scope 中，PostgreSQL Integration、Real Full-stack Golden Path 正确为 skipped，因为本 Change 不涉及数据库/前端跨进程链；Repository Quality、Docs/Governance、CI Gate 均 success。
- 真实 Probe：run `33604014094` / job `100163797816` 在 `TIKHUB_API_KEY` Actions Secret 为空时输出 `PROBE_SKIPPED` 并退出，未发生 TikHub 网络请求；临时 Workflow 随后从分支恢复。

## 外部事实限制

- TikHub 官方文档已确认当前 endpoint、`search_id` 与用户笔记 cursor 语义，以及错误 `user_id` 仍可能计费的风险。
- 仓库没有可安全引用的 `TIKHUB_API_KEY` Actions Secret，因此本 Change **没有取得新的真实 Provider Response shape 证据**。实现使用官方文档 + 防御性 Extractor/Pagination + Fake Transport/现有 Mapper 测试；真实 shape 验证保留为明确延期项。

# 文档影响

- `backend/src/aima_ugc/adapters/providers/tikhub_test/README.md`：增加五账号入口、身份规则、日期语义、`limited/all`、输出和 Probe 安全边界。
- `docs/collection/01_xiaohongshu.md`：增加账号 Discovery 的当前实现定位、人工文件模式边界与复用链路。
- 未更新 TikHub 真实验证台账，因为真实 Probe 没有发出网络请求，不能伪造“已真实验证”。

# 兼容、Migration、部署与回滚

- 数据库 Migration：无。
- HTTP/OpenAPI：无。
- Canonical/Excel Schema：无。
- 依赖/Runtime：无。
- 部署：无额外生产部署步骤；这是人工文件模式入口。
- 兼容：现有关键词 `run_xiaohongshu` 和正式 Collection Decision 默认语义保持不变；共享 Runner 仅增加“无数量软目标”的可选内部能力。
- 回滚：撤销本 Change 的账号 Operation/Runtime、人工账号 Runner/入口、共享 Runner 小扩展、测试和文档即可；现有关键词采集链无需数据迁移。

# 交付完成证据

- Requirement Source：Issue #296。
- 实现 PR：#298，已合并到 `main`；merge commit `066ff0b40dfe3fb693e5a80de6efcd11f6cee7f1`。
- 合并后 `main` fresh CI `33606905199`、Runtime Acceptance `33606904924`、Change Completion Gate `33606904936` 全部成功。
- R1-R5 已由实现、Unit/Fake Transport、文件输出/Excel纵切和 main fresh 验证直接支持；R6 的真实 Provider shape 验证按安全条件明确延期，不影响本次人工入口代码交付，但仍不得宣称真实 shape 已验证。
- 本 Change 的实现、Review、合并与 main 新鲜验证已闭环，因此转为 `done` 并归档。

# 交付

- Requirement Source：#296
- 原任务分支：`feature/296-xiaohongshu-account-collection`
- 实现 PR：#298
- merge commit：`066ff0b40dfe3fb693e5a80de6efcd11f6cee7f1`
- 当前状态：`done`，进入 `changes/archive/2026-09/CHG-20260902-xiaohongshu-account-collection/`。
- 发布：不适用
