---
schema: rvc-change/v1
id: CHG-20260821-remove-derived-user-voice
title: 移除重复 is_user_voice 公共字段并优化发声类型判定
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/remove-derived-user-voice-final2
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - analysis
  - http
  - export
  - frontend
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/analysis/content_label.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/contracts/export/models.py
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/reporting.py
  - backend/src/aima_ugc/platform/export/excel.py
  - backend/src/aima_ugc/adapters/providers/imports_test/test.py
  - backend/src/aima_ugc/modules/analysis/prompts
  - contracts
  - frontend/src/generated/api
  - tests
  - docs/blueprint/13-统一数据Excel导出与调试复用.md
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
contracts:
  - ContentAnalysisResponse
  - UnifiedDataExcelAnalysisV1
  - PromptTaxonomy
data_changes: []
---

# 目标

把 `voice_type` 收敛为“内容发声类型”的唯一业务事实，不再在模型输出、数据库、HTTP、前端生成类型或 Excel 中维护/展示重复的 `is_user_voice` / “是否用户真实发声”。同时优化发声类型 Prompt，使模型综合作者昵称、公开简介、认证文案、标题和正文判断发声主体与表达目的，提高 7 类之间的区分准确性。

# 成功标准

- [x] LLM 输出仍只包含 `relevance + voice_type + sentiment + labels`，不存在 `is_user_voice`。
- [x] Prompt 明确要求综合作者 `display_name/bio/verification_label` 与标题/正文，不按单一昵称或单一营销词机械分类。
- [x] Prompt 对 `user_voice / creator_marketing / brand_official / dealer_promotion / media_information / other_organization / unknown` 给出可执行的证据组合、冲突处理和边界规则。
- [x] `ContentLabelAnalysisV3` 不提供 `is_user_voice` 字段或同名便利属性；需要判断用户发声时直接比较 `voice_type == 'user_voice'`。
- [x] PostgreSQL Schema 不变化，继续只持久化 `voice_type`，不新增/删除数据库列，因此不需要 Migration。
- [x] `ContentAnalysisResponse` 删除 `is_user_voice`，OpenAPI 和前端 generated client 同步删除该字段。
- [x] `UnifiedDataExcelAnalysisV1` 删除 `is_user_voice`，共享 Excel 删除“是否用户真实发声”列，只保留中文“发声类型”。
- [x] `imports_test` 默认内容/标签明细列同步删除“是否用户真实发声”。
- [x] Blueprint 13/15 与相关 README 同步为“voice_type 唯一事实”；不保留与实现冲突的当前设计说明。
- [x] Red 测试先证明当前公共 Contract/Excel 仍暴露重复字段；Green 后目标测试、Contract 生成、前端生成物、Ruff、Mypy、相关集成和永久 CI 已通过。

# 范围与非目标

## 范围

- Analysis/HTTP/Export 公共 Contract 的重复字段收敛；
- Prompt 发声类型判定规则优化；
- OpenAPI/JSON Schema/TypeScript generated client 同步；
- Excel 列与 imports_test 调试视图同步；
- Blueprint/README/测试同步。

## 非目标

- 不修改 `voice_type` 的 7 个机器枚举值；
- 不修改 relevance、sentiment、一级/二级标签 Taxonomy；
- 不修改 PostgreSQL 表、Migration 链或既有历史 Analysis 数据；
- 不新增置信度、理由文本、账号身份表或第二次模型调用；
- 不增加 Provider 字段、粉丝数等模型输入；
- 不新增依赖。

# 必须保持不变

- 一条内容仍只调用一次 LLM，同时完成 relevance、voice_type、sentiment、labels；
- `irrelevant` 离线最终业务 JSONL 删除、PostgreSQL 保留审计并默认过滤的语义不变；
- `ContentLabelAnalysisV3` 的序列化机器结果仍只有 relevance/voice_type/条件式 sentiment/labels 及版本审计字段；
- 旧 V1/V2 Analysis 可读；
- `voice_type` 仍是 PostgreSQL 持久化事实和查询筛选条件；
- 模型输入仍只允许 title、text、author.display_name、author.bio、author.verification_label；
- Prompt Taxonomy 标签闭集与本地 Validator 不变。

# 方案比较与已确认决策

## 方案 A：保留 `is_user_voice` 作为派生便利字段

优点：旧 API/Excel 消费方无需修改。

缺点：同一事实在 `voice_type` 和布尔值中重复表达；公共 Contract、前端类型和 Excel 多维护一列；后续分类扩展仍需解释两者关系。

结论：拒绝。

## 方案 B：只保留 `voice_type`，删除公共/展示层 `is_user_voice`

优点：唯一事实源清晰；模型输出维度最小；数据库、API、前端和 Excel 语义一致；“真实用户发声”直接由 `voice_type == user_voice` 表达。

代价：HTTP/Excel Contract 删除字段属于破坏性变化，旧消费方必须与后端同版本升级。

结论：采用。用户已明确授权按该方案修改并合并 `main`。

## 方案 C：先标记 deprecated，保留一个兼容周期再删除

优点：适合存在外部第三方 API 消费方的长期兼容场景。

缺点：当前仓库未发现独立外部消费者，前端 Client 由同一 OpenAPI 生成；继续保留重复字段只会延长双事实维护。

结论：当前不采用。

# Prompt 发声类型判定设计

发声类型判断分两层证据：

1. **主体证据**：作者展示名、公开简介、认证文案用于判断账号呈现的主体性质，例如品牌官方、门店/销售、媒体资讯、机构、个人创作者；任何单一昵称都不能单独定案。
2. **表达目的证据**：标题和正文用于判断当前内容是在分享个人体验/观点、商业种草导购、品牌官方传播、门店获客、媒体资讯转载还是机构通知。

综合原则：

- 标题/正文的当前表达目的优先于账号标签；作者信息用于增强或削弱某个类型证据。
- 作者信息与正文一致时可以提高判断确定性；冲突时按当前内容的主要表达目的分类。
- `user_voice` 需要可见的第一人称体验、个人观点、咨询/求助、购买/推荐意愿等个人表达证据，并且没有更强的组织化/营销目的证据。
- `creator_marketing` 需要创作者/达人语境与商业转化、种草、带货、合作、导购、优惠引导等内容目的形成组合证据；不能因“博主/达人”昵称自动判营销。
- `brand_official` 需要品牌官方/工作人员主体证据与产品发布、活动、声明、品牌传播等官方表达相互支持；仅昵称含“爱玛”不足以判定。
- `dealer_promotion` 需要门店/经销商/销售主体或明确到店、报价、优惠、留资、招商、库存、成交引导等获客目的；普通用户讨论价格不属于门店推广。
- `media_information` 需要媒体/资讯/行业报道主体或明显新闻报道、转载、资讯摘要的写法；个人转发新闻并加入大量个人体验时按主要信息量判断。
- `other_organization` 用于政府、协会、学校、非品牌企业等机构主体的通知/合作/公共事务传播。
- 无法从上述可见证据可靠区分时使用 `unknown`，不得为追求分类覆盖率硬猜。

# 兼容、部署与回滚

- 数据库：当前 `analysis_content_results` 实际表定义只持久化 `relevance / voice_type / sentiment` 等字段，不存在 `is_user_voice` 列；本次无 Schema 变化、无 Migration、无数据回填。
- HTTP：删除 `ContentAnalysisResponse.is_user_voice` 是破坏性 Contract 变化；后端与同仓库前端 generated client 必须同版本部署。
- Excel：删除“是否用户真实发声”列会使后续列序号左移；仓库内固定列测试、`imports_test` 展示配置和正式导出投影已同步。
- Prompt：继续使用仓库已固定的 `content-labeling.v3` 路径/版本；判断标准与示例允许在该 Markdown 内迭代，精确 Prompt 内容由 `prompt_sha256` 区分并进入 Analysis 审计，因此本次不人为创建 V4。
- 部署顺序：后端 Contract/OpenAPI 与同版本前端 generated client 一起发布；Excel 消费方按新列结构使用。数据库不需要先行迁移。
- 回滚：回退同一应用提交及其 OpenAPI/generated client/Excel Contract/Prompt；数据库无需 downgrade。

# 实施任务

[1] Red：增加公共 Contract/Excel/Prompt 目标测试并观察正确失败
→ 修改范围：tests/contracts、tests/unit/platform、tests/unit/analysis
→ 预期结果：当前实现仍存在 `is_user_voice`、旧 Excel 列和旧 Prompt 规则，因此测试失败
→ 验证方式：PR CI 读取失败用例与原因

[2] Green：删除派生公共字段并同步正式投影
→ 修改范围：http/export contracts、content_http、reporting projection、Excel、imports_test
→ 预期结果：所有下游只消费 `voice_type`
→ 验证方式：unit/contract/API/Stage 8D integration

[3] Green：优化 Prompt 发声类型规则
→ 修改范围：Prompt Markdown、Analysis tests
→ 预期结果：模型综合作者与内容证据分类，输出结构不增加字段
→ 验证方式：Prompt loader/LLM payload/validator tests

[4] 生成与文档同步
→ 修改范围：contracts、OpenAPI、frontend generated client、Blueprint 13/15、相关 README
→ 预期结果：机器 Contract 与长期设计完全一致
→ 验证方式：generate --check、frontend typecheck/build、docs check

[5] 复核、完整 CI、合并与归档
→ 修改范围：Change/PR 元数据
→ 预期结果：无旧字段残留于当前正式设计/公共机器 Contract；所有门禁绿色后合并 main
→ 验证方式：PR diff + 原生 CI + main 文件树核对

# 验证证据

## Red

PR #128 head `614fa641484e3d9929fff9ffb9a5ef32a400153d` 的 CI Stage 1 在 Contract 阶段得到 `56 passed / 3 failed`；三个失败分别证明 HTTP completed Analysis 仍要求 `is_user_voice`、Excel Analysis 仍要求该派生字段、Prompt 仍包含该字段且缺少新的主体/表达目的联合证据规则。同期 546 个既有 unit tests、Stage 2 Platform、Stage 3A Database 均通过，失败原因与目标行为一致。

## Focused Green

一次性受控 Runner 在候选工作树中实际完成：

- 目标测试：`41 passed`，另有 1 条既有 Starlette/httpx deprecation warning；
- `uv run ruff format --check backend tests scripts`：434 files already formatted；
- `uv run ruff check backend tests scripts`：All checks passed；
- `uv run mypy backend/src`：230 source files 无问题；
- `uv run python scripts/contracts/generate.py --check`：OpenAPI/Analysis/Canonical/Provider/Collection/Export Contract 已同步；
- `uv run python scripts/contracts/check_compatibility.py`：候选生成 Schema 进入 index 后通过漂移检查；
- `uv run python scripts/quality/check_docs.py`：通过；
- `npm --prefix frontend run typecheck`：通过；
- `npm --prefix frontend run build`：通过；
- 生产代码、Prompt、Blueprint、OpenAPI、Export Schema、generated client 的 `is_user_voice|是否用户真实发声` 残留扫描通过。

## 永久 CI

候选 head `56d14a823d29638efb9d4367e3d2f164dcda9c21` 的永久工作流已实际完成：

- `CI`：success；其中 Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 均 success；
- `Stage 5A Provider Raw`：success；
- `Stage 5B Collection Execution`：success；
- `Stage 5C Provider Persistence`：success；
- `Stage 5D Provider Dispatch`：success；
- `Stage 6 XHS Vertical Slice`：success；
- `Stage 7 Keyword Packs`：success；
- `Stage 7 Provider Config Routing`：success；
- `Stage 7 Plan Occurrence Run Snapshot`：success；
- `Stage 7 Scheduler Runtime`：success；
- `Stage 1-7 Audit Correctness`：success。

Stage 6 在前一候选曾得到 `105 passed / 1 failed`，唯一失败是 irrelevant 审计集成测试仍访问已删除的 `ContentAnalysisResponse.is_user_voice`；重新读取当前 feature 文件后确认同一测试实际有两处旧断言，并在 `56d14a823d29638efb9d4367e3d2f164dcda9c21` 前全部删除，随后 Stage 6 Unit / Quality / PostgreSQL integration 与全部 migration round-trip 均 success。

旧 `DEV Remove Derived User Voice Runner` 在 cleanup 前的 PR 事件快照中会因 feature 执行脚本已按设计自删除而报 `FileNotFoundError`；它不属于产品质量门禁。该一次性 Runner 已通过 PR #134 从 `main` 删除。当前 Change 更新后的 head 仍需在 cleanup 后的 `main` 上执行最后一轮永久 PR CI，全部成功后才允许合并。

# 文档影响

- Blueprint 13 已同步为 Excel/调试视图只保留“发声类型”，不维护二值用户发声列；
- Blueprint 15 已同步为 `voice_type` 唯一发声类型事实，并记录作者主体证据 + 标题/正文表达目的证据的 Prompt 规则；
- Analysis README 已从实际过期的 V2 当前说明同步到 V3，并补齐 relevance/voice_type、作者 bio/verification 输入和 Validator 事实；
- imports_test README 已同步默认发声类型列及最终 Excel 语义；
- `docs/API接口说明.md` 已检查，当前没有手工枚举 `is_user_voice` 字段，不维护第二份字段 Schema，因此无需修改；
- OpenAPI、Export JSON Schema、前端 generated client 已由仓库生成器同步，不手工修改生成物。

# Git / PR

- 初始基线 main：`01ad60d9662ea1b9523637bb1dbf8b1a79aacd63`
- 分支：`feature/remove-derived-user-voice-final2`
- PR：`#128 移除重复用户发声字段并优化发声类型判定`（Draft → 待转 ready_for_review）
- 业务候选提交：`b1c1a8948edeaab68bcf75a9f245cf71f8ab2c7a`；为触发永久 CI 创建了相同文件树的用户侧 trigger commit；Stage 6 残留测试修复提交为 `56d14a823d29638efb9d4367e3d2f164dcda9c21`。
- 一次性开发 Runner 仅用于受控生成/Green 验证；中间 Runner 修正均依据实际 Actions 日志处理。最终 main Runner 已通过 PR #134 清理，不属于长期仓库能力。
- 本 Change 未创建 Migration、未升级依赖。
- 合并：待当前 head 在 cleanup 后 main 上完成最后一轮永久 CI 后执行；合并后再将 Change 标记 `done` 并归档到 `changes/archive/2026-08/`。
