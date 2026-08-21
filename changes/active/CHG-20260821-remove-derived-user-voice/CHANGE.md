---
schema: rvc-change/v1
id: CHG-20260821-remove-derived-user-voice
title: 移除重复 is_user_voice 公共字段并优化发声类型判定
level: L3
status: in_progress
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
  - backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py
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

- [ ] LLM 输出仍只包含 `relevance + voice_type + sentiment + labels`，不存在 `is_user_voice`。
- [ ] Prompt 明确要求综合作者 `display_name/bio/verification_label` 与标题/正文，不按单一昵称或单一营销词机械分类。
- [ ] Prompt 对 `user_voice / creator_marketing / brand_official / dealer_promotion / media_information / other_organization / unknown` 给出可执行的证据组合、冲突处理和边界规则。
- [ ] `ContentLabelAnalysisV3` 不提供 `is_user_voice` 字段或同名便利属性；需要判断用户发声时直接比较 `voice_type == 'user_voice'`。
- [ ] PostgreSQL Schema 不变化，继续只持久化 `voice_type`，不新增/删除数据库列，因此不需要 Migration。
- [ ] `ContentAnalysisResponse` 删除 `is_user_voice`，OpenAPI 和前端 generated client 同步删除该字段。
- [ ] `UnifiedDataExcelAnalysisV1` 删除 `is_user_voice`，共享 Excel 删除“是否用户真实发声”列，只保留中文“发声类型”。
- [ ] `imports_test` 默认内容/标签明细列同步删除“是否用户真实发声”。
- [ ] Blueprint 13/15 与相关 README 同步为“voice_type 唯一事实”；不保留与实现冲突的当前设计说明。
- [ ] Red 测试先证明当前公共 Contract/Excel 仍暴露重复字段；Green 后目标测试、Contract 生成、前端生成物、Ruff、Mypy、相关集成和完整 CI 通过。

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

- 数据库：无 Schema 变化，无 Migration，无数据回填。
- HTTP：删除 `ContentAnalysisResponse.is_user_voice` 是破坏性 Contract 变化；后端与同仓库前端 generated client 必须同版本部署。
- Excel：删除“是否用户真实发声”列会使列序号左移；仓库内所有固定列测试与调试配置同步更新。
- Prompt：语义规则发生实质变化。若仓库现有 `prompt_version` 语义要求内容版本升级，则升级 Prompt 版本并保留旧 Prompt 供历史审计；若精确内容仅以 `prompt_sha256` 区分，则必须在实现中明确记录依据，不能静默混用。
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
→ 修改范围：Prompt Markdown、prompt_taxonomy.py（如需版本升级）、Analysis tests
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

尚未完成。按 Red → Green 记录本轮真实 CI、命令、退出状态和失败数。

# 文档影响

必须同步 Blueprint 13、Blueprint 15、Analysis README、imports_test README；如 `docs/API接口说明.md` 当前显式描述该响应字段，则同任务同步删除。归档 Change 只保存历史原因，不回写旧历史事实。

# Git / PR

- 基线 main：`01ad60d9662ea1b9523637bb1dbf8b1a79aacd63`
- 分支：`feature/remove-derived-user-voice-final2`
- PR：待创建
- 合并：待执行
