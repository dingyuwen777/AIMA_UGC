---
schema: coding-change/v1
id: CHG-20260918-230500-voice-plaza-figma-comment-thread
title: 声音广场 Figma 对齐与评论线程关系回归修复
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/541-voice-plaza-figma-comment-thread
created: 2026-09-18
updated: 2026-09-19
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - comments
  - tikhub
  - testing
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/src/features/task-center/
  - frontend/tests/
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - tests/
contracts:
  - Voice Plaza user-visible behavior
  - Content comments HTTP response semantics
data_changes: []
---

# 变更摘要

- **要解决的问题**：READY Figma 已成为声音广场正式视觉/交互基线，但当前 Vue 仍保留部分工程化文案与布局漂移；同时详情评论回归为必须额外点击才看到回复，且 XHS 明确父评论字段与原作者身份存在跨层丢失窗口。
- **拟议修改**：按 Figma Owner 链增量对齐 Voice Plaza/Task Center/Shared UI；恢复本地已入库回复首屏；补 XHS 明确父级兼容与原作者读取推导；不改变公共 Schema/HTTP 字段、generated client 或 TikHub 二级回复默认采集开关。
- **预期结果**：普通用户打开详情即可看到一级评论、二级回复、可证明的“回复谁”和原作者；不能证明直接父级时只表达根线程归属；页面视觉/状态/产品语言与正式 Figma 一致。

# 背景、现状与问题

## 背景

Requirement Source 为 Issue #541。用户已先行验收声音广场 Figma 文件 `qmZEFvPrB8u9JX5fyqc93S` Page `4627:7429` 为 READY，并要求随后由代码消费该基线；同时反馈评论线程关系在最近 TikHub 评论补采调整后不再像此前一样直接可见。

## 当前现状

- 归档 Change `CHG-20260913-001143-comment-thread-voice-plaza` 曾验收“一级评论 + 缩进回复 + 回复对象 + 原作者”。
- 当前 HTTP Contract 与 PostgreSQL Query 仍有 `root_comment_id`、`parent_comment_id`、`parent_author_display_name`、`is_by_content_author`。
- 旧 Store 只加载根评论，用户点击“查看 N 条回复”后才读取本地回复。
- XHS Mapper 只识别嵌套 `target_comment.id`，未兼容 Provider 明确扁平 `target_comment_id / targetCommentId`。
- Content/Comment 作者已经通过稳定账号身份收敛到 `author_account_id`，但 Query 旧实现只透传 Provider 的 `is_by_content_author`。
- PR #527 的五平台补采 Browser/Full-stack 覆盖了回复文本，但没有固定“回复谁”和原作者关系。

## 问题、根因或约束

1. **前端首屏可见性回归**：已入库回复没有随详情根评论一同读出，用户自然观察不到线程。
2. **前端语义错误**：直接父级未知时旧 UI 显示“回复这条一级评论”，等价于猜造 `parent=root`。
3. **XHS Mapper 兼容缺口**：Provider 明确 flat target ID 会被丢弃。
4. **原作者投影缺口**：账号身份已经收敛时，读取层没有利用该可靠关系补足缺失的 Provider 布尔标识。
5. 五个平台并非都能证明直接父级；修复必须允许 root-only 降级，不能为“显示完整”伪造数据。
6. Figma 是视觉/状态/交互事实源，但 API/Store/Provider/数据库 Contract 仍由代码事实源负责，不能把示例值写进生产语义。

## 不修改的后果

用户继续需要额外点击才能看见回复；部分 XHS 明确直接父级会丢失；历史数据即使作者账号已经可靠收敛也无法显示“原作者”；未知直接父级还可能被 UI 错误表达成直接回复一级评论。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Figma Formal Screen 已通过 Owner/Prototype/Geometry 审计并处于 READY | Figma `4627:7429`、Normal `4627:7431`、Compact `4725:1325`、Feature Owner `4804:1535` | 前端跟随设计，不重画第二套 Owner |
| E2 | PostgreSQL 评论 Query 已按 root/direct-parent 分页并 Join 父作者 | `content_queries.py::_comment_statement/list_comments_page` | 无需新增 parent Schema |
| E3 | HTTP Response 已包含 root/parent/parent-author/original-author | `ContentCommentResponse` | Contract shape 足够，不改 generated client |
| E4 | Store 旧行为必须点击后才请求回复 | `voice-plaza/store.ts::loadCommentRoots/loadCommentReplies` | 只需有界预取本地首屏 |
| E5 | XHS Mapper 旧实现只读取 nested target | `mappers/xiaohongshu.py::map_comment` | 增加 explicit flat target 兼容 |
| E6 | Content/Comment 账号可通过 stable/alternate IDs 收敛为同一 account | `test_comment_author_converges_by_existing_alternate_stable_id` | Provider bool 缺失时可从已收敛账号可靠推导 |
| E7 | 五平台能力文档允许部分平台只证明 root thread | `docs/appendix/02_TikHub五平台真实响应与字段映射.md` | parent 未知必须保持未知 |
| E8 | PR #527 没有把直接父级关系固定成跨层回归 | 归档 Change + Full-stack 测试审计 | 本 Change 必须补纵切与 Browser 回归 |
| E9 | Requirement Source #541 已按 canonical `[缺陷]` Issue Profile 归一，AC1—AC8 保持原需求语义 | GitHub Issue #541 live readback | current-head CI 可执行真实 Requirement Source Contract 校验 |

## 推断与待确认

- current-head GitHub CI、独立 Review、guarded merge、main-fresh、Change Archive 与 Issue Closure 是 PR Ready 之后的交付生命周期事实；在实际发生前不写成已完成。
- 不执行新的真实付费 TikHub Probe；当前修复仅接受 Provider 已明确给出的字段，不把外部猜测当 Contract。

# 目标、成功标准与非目标

## 目标

- 让声音广场 Vue 实现消费 READY Figma，而不改变真实业务 Contract 来迁就设计示例。
- 恢复评论线程首屏可读性和可证明的直接回复对象/原作者关系。
- 保持 Provider 能力边界与费用默认行为不变。

## 成功标准

- [x] 页面 Owner、产品文案、状态、AI/导出/详情/响应式实现已按 Figma 增量对齐。
- [x] 普通用户层不再展示 Run/Shard/Provider/Batch/TikHub/error_code/Raw Artifact/技术详情等工程信息。
- [x] 打开详情后已入库回复首屏自动读取，后续分页仍可继续。
- [x] 直接父级未知时不伪造“回复一级评论”。
- [x] XHS 明确 flat/nested target 都能保留 direct parent；账号已收敛时原作者可恢复。
- [x] TikHub 二级回复补采默认策略与费用行为不变。
- [ ] current-head required CI、独立 Review、guarded merge、main-fresh、archive/closure 实际完成。

## 范围

- Voice Plaza/Task Center/Shared UI 的 Design-to-Code Delta。
- 评论 Store、评论渲染语义。
- XHS comment Mapper 明确父级兼容。
- PostgreSQL comment read projection 的原作者恢复。
- 对应 Unit/Integration/E2E/Full-stack 回归与 Change。

## 非目标

- 不新增数据库字段或 Migration。
- 不修改公共 HTTP 字段或手写 generated client。
- 不重新设计 Figma。
- 不改变 TikHub 二级回复默认采集开关。
- 不部署生产环境。

## 必须保持不变

- Page → Pinia Store/local state → Feature API → generated client → HTTP → FastAPI 正式链路。
- Comment root/direct-parent 未知语义；无证据不猜 parent。
- 现有 Cursor、评论分页、Analysis Run、Export Job、人工复核 API Contract。
- 依赖/锁文件与生产部署方式。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | Figma 管视觉/状态/交互；代码事实源管数据/Contract | E1—E3 | 不发明 API，不复制 Owner |
| 接口与契约 | Shape 不变，只修既有字段语义投影 | E2/E3/E6 | generated client 不变 |
| 数据与迁移 | 不适用；既有字段足够 | E2/E3 | 无 Migration/回填 |
| 错误与失败语义 | 用户显示产品化错误；内部诊断继续留后端/日志 | E1 / #541 AC2 | 不泄漏 raw error/code |
| 兼容性 | Provider 显式值优先；未知 parent 仍未知 | E5/E7 | 不破坏既有 sparse observation |
| 部署与回滚 | 不部署；revert PR 可回滚 | 无 Schema/数据副作用 | 无额外恢复步骤 |

# 修改方案与决策依据

## 最小充分方案

1. **评论可见性** → Store 对当前根页中 `ingested_reply_count>0` 的根评论有界预取首个本地回复页 → 详情首屏直接看到线程 → Unit/E2E/Full-stack。
2. **直接父级** → XHS Mapper 接受 nested target 和明确 flat target ID → 缺字段继续为空 → Mapper Unit + Collection/PG Integration。
3. **原作者** → Query 先用 Provider 显式 `is_by_content_author`，为空时仅在 content/comment 两个 `author_account_id` 都存在时比较账号相等 → PG Integration。
4. **UI 语义** → parent author 已知显示“回复 X”；parent=root 显示“回复一级评论”；只知 root 时显示“属于该一级评论线程” → Component 回归。
5. **Design-to-Code** → Voice Plaza/Task Center/Analysis/Export/Detail 消费产品文案与状态；Voice Plaza 仅在 Feature Owner 内补正式页特有的 28px 顶距、标题层级和 32px 头部动作，Shared Owner 保持当前跨页基线 → Frontend Unit/Browser/build。
6. **交付** → PR Ready 后 current-head CI → 独立 Review → guarded merge → main-fresh/archive/Issue Closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E2/E4 | 回复已在 PG，无需 Provider 调用，只补读路径 |
| D2 | E5/E7 | 接受明确字段即可恢复事实，同时避免 root 猜 direct parent |
| D3 | E6 | 账号身份已是统一 Owner，可无回填恢复原作者 |
| D4 | E1 | Shared Owner 还被其它已验收页面消费；跨页基线不应为单页 Figma Delta 改写，Voice Plaza 特有几何留在 Feature Owner |
| D5 | E3 | Contract 已足够，不引入 Schema/生成链变化 |

## 备选方案与取舍

- **只改前端自动展开**：无法修 XHS 明确父级/原作者缺口，不能完成 AC4—AC6。
- **所有二级回复强制 parent=root**：会制造错误事实，违反 AC5，拒绝。
- **新增 parent/original-author Schema**：现有字段足够，无必要 Migration。
- **默认开启更多 TikHub 二级补采**：扩大费用且不是根因，违反 AC7。
- **为 Voice Plaza 改写 Shared Header/Button/PageShell**：会回归其它已验收正式页面；本次保留 Shared Owner 基线，只在 Voice Plaza Feature Owner 表达该页面实例的特有几何。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 前端按正式 Figma Owner/状态/产品语言实施且不修改真实 Contract 迁就示例 | #541 / AC1 | satisfied | Voice Plaza/Shared UI diff；Figma READY Context |
| R2 | 普通用户层不暴露工程信息 | #541 / AC2 | satisfied | AI/导出/详情/错误/来源文案清理与设计回归 |
| R3 | 筛选、AI任务、批量复核、导出、详情、评论、多媒体、错误、Compact/Wide 与 Figma 对齐 | #541 / AC3 | satisfied | Voice Plaza/Task Center/Shared Owner 实现与 E2E 回归 |
| R4 | Mapper→Canonical→PG→HTTP→Store→Vue 全链审查评论关系 | #541 / AC4 | satisfied | E2—E8；新增 Mapper/PG/Collection/Browser 回归 |
| R5 | 已入库回复首屏可见；不能证明 direct parent 时只降级到 root | #541 / AC5 | satisfied | Store prefetch + replyTarget 降级语义 |
| R6 | 至少固定 XHS 一级→二级→父作者及 Browser 用户可见关系 | #541 / AC6 | satisfied | XHS Mapper Unit、collection runtime Integration、comment-supplement Full-stack、Voice Plaza E2E |
| R7 | 不改变二级回复默认采集或 Provider 费用默认行为 | #541 / AC7 | satisfied | collection policy/default 未改；首屏预取只读 PG |
| R8 | required tests/build/review/checks 后 merge main 并 main-fresh | #541 / AC8 | explicitly_deferred | 属于 PR Ready 后真实交付门禁，当前不伪造 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| Voice Plaza Store / comments UI | 自动首屏回复、线程语义 | 恢复用户可读评论关系 | R4—R6 / E4 |
| XHS Mapper | flat target 兼容 | Provider 明确父级不能丢 | R4—R6 / E5 |
| PostgreSQL Content Query | 原作者投影 | 利用既有账号身份事实 | R4—R6 / E6 |
| Voice Plaza / Task Center dialogs | 产品化文案与状态 | 跟随 Figma | R1—R3 / E1 |
| Unit/Integration/E2E/Full-stack | 回归保护 | 固定跨层可观察行为 | R4—R8 / E8 |
| 当前 Change | 完成定义、验证与交付证据 | L3 Completion Gate | R1—R8 |

- [x] 调查当前实现、历史正常参照、PR #527 与 Figma 事实源
- [x] 建立 Issue、Change、任务分支和 Draft PR
- [x] 建立评论关系回归并完成最小实现
- [x] 完成 Figma Design-to-Code Delta，并验证未把单页几何扩散到其它正式页面
- [x] 完成需求追溯与反向能力审计
- [x] 同步当前 Change 到 ready_for_review
- [ ] 取得 current-head CI、独立 Review、merge/main-fresh/archive/closure 证据

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | XHS Mapper、Voice Plaza Store、评论组件、Task Center、Design baseline |
| 接口 / 契约 | required | 既有 ContentCommentResponse 语义不回退；generated client 不变 |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL content/comment identity、collection scope comment runtime |
| 用户 / 工作流验收 | required | Browser Mock 打开详情、AI/导出/任务中心/Figma 产品状态 |
| 跨组件关键路径 | required | TikHub Fake transport → Mapper → ingestion → PG → Voice Plaza comment read；Real Full-stack comment supplement |
| 外部依赖 / 供应方探测 | not_applicable | 不需要新的真实付费 Probe；只接受明确 Provider 字段并保持未知降级 |
| 构建 / 打包 / 运行 | required | frontend lint/audit/typecheck/build、Python quality、Wheel/stack smoke 由 CI 按 scope 执行 |
| 文档 / 治理 / 其他 | required | #541、Change machine contract、Completion Audit、PR current-head |

## 验证计划

- 目标测试：XHS mapper Unit、content Postgres integration、Voice Plaza/comment component Unit。
- 相关回归：Voice Plaza/Task Center Browser Mock、五平台 comment supplement Full-stack。
- 静态检查或构建：Ruff/Mypy（CI 分类适用项）、frontend lint/audit/typecheck/build、generated contract check。
- 专项真实边界：PostgreSQL Integration + Real Full-stack；External TikHub Probe 不适用。
- 就绪检查：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready` 及仓库 CI `check_change_completion.py`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 首屏会增加本地回复读取 | 当前根页最多 10 条，仅对 `ingested_reply_count>0` 请求；无 Provider 调用 |
| 兼容性 | 保持 HTTP/Schema/Store 公共行为；只补现有字段语义 | E2/E3/E5/E6 |
| 数据 / Migration | 不适用 | 现有 root/parent/account 字段足够，无回填 |
| 部署 / 运行 | 不新增配置/依赖/服务 | 沿用现有前后端运行与部署 |
| 回滚 / 恢复 | revert Implementation PR | 无 Migration、无不可逆数据写入 |

# 文档、依赖、部署与发布影响

- **长期文档**：正式 Figma 已是视觉事实源；无需复制第二份易漂移页面规格，当前 Change 保留 Implementation Trace；Shared Owner 最终未发生代码差异。
- **依赖 / Runtime**：不新增、不删除、不升级依赖；锁文件不变。
- **配置 / Secret**：不改变配置面、默认值或 Secret 处理。
- **部署 / Release**：本任务不部署、不创建 Release；仅合并代码到 main。
- **兼容 / 消费方通知**：HTTP Shape 不变；无需 generated client 迁移或外部消费方通知。

# 完成审计

- [x] upstream_re_read：已重新读取 #541、READY Figma、历史评论线程 Change、PR #527 五平台补采、当前 Mapper/PG/HTTP/Store/Vue/测试。
- [x] change_coverage：R1—R7 均由当前实现和对应自动化入口覆盖；R8 明确留给真实交付生命周期。
- [x] reverse_audit：已从 Raw/Mapper → Canonical → PostgreSQL → HTTP → generated client → Store → Vue 反查，也从 Figma Formal → Feature/Shared Owner → Vue 反查。
- [x] unresolved_cleared：无 `not_satisfied`；R8 的 CI/Review/merge/main-fresh/archive/closure 有正式 Issue AC8 作为延期依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Figma current | Formal/Owner/Prototype/Geometry/术语机器审计 | READY；invalid destinations=0、enabled dead actions=0、正式 UI 工程术语=0、Canvas overlap/overflow=0 | 当前设计可作为实现基线 |
| V2 | PR current branch | 逐层代码与历史正常参照审计 | PG/HTTP root/direct-parent 仍在；实际缺口收敛到 Store/XHS target/original-author/UI 降级 | 根因与修改范围有直接证据 |
| V3 | current-head GitHub Runner | Required CI | Requirement Source 已归一；本次同步提交触发新的完整 current-head run | CI 结果仍以该 run 实际结论为准 |

## 未验证内容与剩余风险

- 当前会话容器无法通过 DNS checkout GitHub 仓库，因此没有伪造本地 Green；可执行验证由 current-head GitHub Runner 完成。
- current-head CI、独立 Review、guarded merge、main-fresh、Change Archive、Issue Closure 尚未完成，均阻塞端到端完成结论。

## 交付状态

- 提交：当前 PR #542 head；精确 head 以 GitHub PR 为准。
- 拉取请求：#542，Ready。
- CI：current-head required checks 正在通过 GitHub Runner 取证。
- 合并：未执行；只在 final-head Green + 独立 Review 后 guarded merge。
- Change 归档：未执行；由 repository-native Archivist 在 merge 后负责。
- 发布 / 部署：不适用；用户未授权生产部署/Release。

## 备注

Implementation ↔ Figma Conformance 采用“Figma 管视觉/交互、真实 Contract 管系统语义”的既定边界；没有为设计示例新增 API 或持久化字段。
