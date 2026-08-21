---
schema: rvc-change/v1
id: CHG-20260821-analysis-relevance-voice-type
title: AI语义相关性过滤与内容发声类型分类
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/analysis-relevance-voice-type
created: 2026-08-21
updated: 2026-08-21
depends_on: []
affected_areas:
  - analysis
  - content_query
  - offline_import
  - export
  - database
affected_paths:
  - backend/src/aima_ugc/contracts/analysis
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/analysis
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/bootstrap/analysis_worker.py
  - backend/src/aima_ugc/platform/export/excel.py
  - migrations/versions
  - contracts/analysis
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - tests
  - docs/blueprint/15-舆情AI打标与统一分析契约.md
  - backend/src/aima_ugc/modules/analysis/README.md
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
contracts:
  - ContentLabelAnalysisV3
  - ContentAnalysisResponse
  - ContentFilterSnapshot
data_changes:
  - analysis_content_results.relevance
  - analysis_content_results.voice_type
  - analysis_content_results.sentiment_nullable
---

# 目标

在现有“关键词相关性粗筛 → 去重 → AI 标签分析”基础上增加第二层 LLM 语义复核：

1. 模型在同一次打标请求中判断内容是否与爱玛品牌、产品、服务、渠道、营销传播或明确相关事件具有实质语义关联；
2. 对语义无关内容，不再强行生成情感和业务标签；离线工作数据集在最终原子回写时真正剔除该记录；
3. 同一次模型调用判断“内容发声类型”，区分真实用户个人表达与营销、官方、媒体等内容；
4. 正式 PostgreSQL 保留不可变 Raw、Candidate、Content 和 Analysis 历史，不因模型判断执行破坏性级联删除；默认声音广场/查询型导出排除当前 Prompt/Model 已判定的无关内容；
5. 保留 V1/V2 历史 Analysis 可读，新结果使用 V3，避免静默破坏历史 JSONL、checkpoint 和数据库事实。

# 成功标准

- [ ] 新 Prompt V3 在一次请求中要求 `relevance + voice_type + sentiment + labels`，并明确相关性和发声类型判断标准。
- [ ] `voice_type` 固定为 `user_voice | creator_marketing | brand_official | dealer_promotion | media_information | other_organization | unknown`。
- [ ] `user_voice` 只表示可见证据支持的个人真实体验、个人观点、咨询/求助、购买意愿等非组织化个人表达；达人商业推广、品牌官方、门店经销商、媒体资讯、机构传播分别落到自己的类型；证据不足为 `unknown`。
- [ ] V3 `relevance=relevant` 时必须有合法 sentiment 和至少一个合法标签对；`relevance=irrelevant` 时 sentiment 必须为空且 labels 必须为空。
- [ ] 模型输入只在现有标题/正文/作者展示名基础上增加公开作者 `bio` 与 `verification_label`；不发送 URL、ID、互动指标、粉丝数、Provider、命中关键词或 Raw。
- [ ] Runtime Validator 严格校验 relevance、voice_type、相关/无关条件结构、sentiment、标签 membership 和父子关系；非法输出仍进入既有有界 Validation Retry。
- [ ] 离线 JSONL checkpoint 可以记录 V3 的 relevant/irrelevant 成功决策；最终原子回写时删除 irrelevant 行，且中断恢复不会重复为已成功 irrelevant 内容付费。
- [ ] 离线摘要明确统计 `rows_irrelevant_removed`；最终 Excel/报告自然只消费保留下来的 relevant JSONL。
- [ ] 正式 Analysis Result 表可持久化 relevant 与 irrelevant 历史；历史 V1/V2 数据迁移为 `relevant + unknown`，不丢标签和情感。
- [ ] 默认 Content 查询、查询型 Analysis target 和查询型 Export 不返回当前配置已判 irrelevant 的内容；显式 `relevance=irrelevant` 可用于审计查看。
- [ ] Content HTTP Analysis 响应暴露 `relevance`、`voice_type`、`is_user_voice`；旧 pending/stale 仍保持空分析字段。
- [ ] Excel 在包含 Analysis 时增加“相关性 / 发声类型 / 是否用户真实发声”列；irrelevant 只有在显式审计数据源传入时才可能出现。
- [ ] Contract JSON Schema、OpenAPI、TypeScript Client 按仓库生成流程同步。
- [ ] 目标测试、Analysis/Content/Export 相关测试、Migration/Contract、四项质量门禁和完整 CI 通过。

# 范围与非目标

## 范围

- Provider-neutral Content AI 分析；
- Prompt、Pydantic Contract、Validator、离线 checkpoint/原子回写；
- 正式 Analysis PostgreSQL 持久化与默认业务查询过滤；
- HTTP/Excel 对新字段的消费；
- 相关 Contract/Schema/生成 Client、Migration、测试和长期文档。

## 非目标

- 不修改现有关键词 RelevanceService；它继续作为低成本确定性粗筛；
- 不使用模型判断去删除 Provider Raw、Candidate、来源账本或 Content 历史；
- 不根据粉丝数自动认定营销账号；
- 不增加置信度、解释文本、品牌实体抽取或三级标签；
- 不自动在 Import/Collection 后触发付费模型，仍保持用户显式发起 Analysis；
- 不修改 LLM Provider、价格、并发和预算策略；
- 不新增依赖。

# 必须保持不变

- Canonical 仍只保存平台可观察事实，AI 派生字段不进入 Canonical；
- 既有 `ContentLabelAnalysisV1/V2` 继续可读；
- Prompt Taxonomy 仍是具体情感/一级/二级标签闭集唯一事实源；
- Validation Retry / Transport Retry / LLM request audit / 费用计算边界保持不变；
- Raw、Candidate、Content Version、来源追溯和 Analysis 历史不可因模型分类被破坏性删除；
- PostgreSQL 一张表一个写 Owner；Analysis 表仍由 Analysis Repository 写；
- 不升级 Python/Node/依赖版本。

# 方案比较与已确认决策

## 方案 A：直接修改 V2，增加字段并物理删除 Content

优点：表面改动少。

缺点：破坏现有 JSONL/checkpoint/Schema；数据库物理删除会破坏来源追溯、外键和历史审计；模型误判不可逆。

结论：拒绝。

## 方案 B：新增 V3，一次模型调用同时做语义相关性、发声类型、情感和标签；离线剔除，数据库保留历史并默认过滤

优点：不增加模型调用次数；兼容 V1/V2；离线满足“无关数据直接从工作数据集中删除”；数据库仍保留可审计证据；后续可以按用户真实发声/营销/官方/媒体等做统计。

代价：需要新增 Contract、Migration，并同步 Query/Export。

结论：采用。

## 方案 C：相关性和发声类型拆成独立模型/独立任务

优点：每个模型职责更单一，可独立调优。

缺点：模型调用和费用增加；多一套 checkpoint、重试和持久化状态；当前需求没有证据证明需要两个模型阶段。

结论：当前不采用。

用户已明确：发声类型需要按“用户真实体验/个人表达、营销推广、官方传播、媒体转载等”合理分类，并授权按该目标细化类型。采用上面的 7 类，其中 `is_user_voice` 仅由 `voice_type == user_voice` 派生，避免数据库存两份可能不一致的事实。

# 相关性规则

`relevant`：内容主体对爱玛品牌、爱玛产品/车型、购买与价格、使用体验、质量故障、电池续航、智能功能、销售售后、渠道门店、爱玛营销传播/代言/活动，或与爱玛有明确比较、评价、争议、事件关系，具有可用于舆情分析的实质语义。

`irrelevant`：仅关键词碰撞、同名实体、标签/热词堆砌、正文主体完全是其他品牌/其他话题且爱玛只是无实质信息的带过、模板尾巴或无法形成任何爱玛舆情含义。

边界：竞品内容只有在明确比较/提及爱玛并形成对爱玛的判断时才 relevant；“信息少但确实在问/说爱玛”仍 relevant，不因文本短而删除。

# 发声类型规则

- `user_voice`：普通个人用户的真实体验、使用反馈、购买经历、个人观点、咨询、求助、购买/推荐意愿；不要求必须已购车，但必须是个人表达且无明显组织化推广证据。
- `creator_marketing`：达人/KOL/KOC/博主的商业推广、种草、带货、合作测评、导购式内容，或内容本身具有明确营销转化目的。
- `brand_official`：爱玛品牌、子品牌、官方账号、品牌工作人员以官方身份发布的品牌传播、活动、产品信息或声明。
- `dealer_promotion`：经销商、门店、销售、加盟商的促销、报价、到店、留资、招商、库存/车型推荐等获客内容。
- `media_information`：媒体、新闻、资讯号、行业号、聚合号的新闻报道、行业信息、转载/编辑内容；不是以个人使用体验为主体。
- `other_organization`：政府、协会、学校、企业机构等非个人主体的通知、合作、公共事务传播，且不属于品牌官方/经销商/媒体。
- `unknown`：仅凭标题、正文、作者展示名/简介/认证标签无法可靠区分上述类型。

判断内容性质，不声称识别账号真实法律身份；不得仅凭昵称、粉丝规模或“像广告”就臆测商业合作。

# Migration / 部署 / 回滚

- 新增 forward Migration `20260821_0023`：给 `analysis_content_results` 增加 `relevance`、`voice_type`，并允许 `sentiment` 对 irrelevant 为空；已有行回填 `relevance='relevant'`、`voice_type='unknown'`。
- 增加数据库 Check Constraint：relevance/voice_type 闭集；relevant 必须 sentiment 非空，irrelevant 必须 sentiment 为空。
- Analysis Label Pair 继续允许一个 Result 有 0 行，因此 irrelevant 无需伪造标签。
- 部署顺序：Migration → 新后端代码 → 生成前端 Client/前端部署。旧 V1/V2 历史结果仍按回填值可读。
- 回滚代码时，新增列可保留不影响旧读取；若执行 Alembic downgrade，应先确认不存在需要保留的 V3 irrelevant 结果，否则 downgrade 会丢失 relevance/voice_type 派生事实。

# 实施任务

[1] Red：新增 V3 Contract/Validator/离线删除/数据库字段与查询行为测试
→ 修改范围：tests/unit/analysis、tests/unit/platform、tests/unit/database、相关 integration/API tests
→ 预期结果：当前 V2 实现因缺 V3、缺字段/过滤/删除行为而失败
→ 验证方式：CI 目标测试观察预期失败

[2] Green：实现 Prompt V3、Contract V3、模型输入与 Validator
→ 修改范围：contracts/analysis、modules/analysis/prompts、content_labeling.py、prompt_taxonomy.py
→ 预期结果：一次 LLM 调用返回并严格验证 relevance/voice_type/条件式标签结果
→ 验证方式：Analysis unit/contract tests

[3] Green：实现离线 checkpoint 恢复和 irrelevant 原子删除
→ 修改范围：offline_labeling.py、imports_test README/摘要消费
→ 预期结果：irrelevant 成功结果可恢复，最终 JSONL 删除且不重复计费
→ 验证方式：offline labeling/checkpoint/run_all tests

[4] Green：实现 PostgreSQL V3 持久化和默认业务过滤
→ 修改范围：tables.py、persistence.py、postgres analysis/content_queries、analysis worker、Migration
→ 预期结果：relevant/irrelevant 都可审计持久化；默认声音广场/查询型 target/export 排除 irrelevant，显式审计可查询
→ 验证方式：schema、repository、voice plaza integration/API tests

[5] Green：同步 HTTP/Excel/生成 Contract
→ 修改范围：contracts/http.py、platform/export/excel.py、contracts/、OpenAPI、generated client
→ 预期结果：前端/Excel可消费 relevance/voice_type/is_user_voice
→ 验证方式：contract generation/check、Excel tests、frontend typecheck/build

[6] 文档、复核、完整验证与 Git 收口
→ 修改范围：Blueprint 15、Analysis README、imports_test README、Change
→ 预期结果：长期设计与机器事实一致，无无关重构
→ 验证方式：目标测试 → 相关测试 → quality scripts → full CI → PR diff/review

# 验证证据

尚未完成。每次只记录本轮实际执行的命令/CI、退出状态与失败数。

# 文档影响

必须同步 Blueprint 15、Analysis README、imports_test README；如 HTTP/Excel 字段影响统一说明，再同步现有 API/Excel 文档对应段落，不新建平行规范。

# Git / PR

- 基线 main：`a86b80a4d9c3246b9dcb3f5a688497c82565d084`
- 分支：`feature/analysis-relevance-voice-type`
- PR：未创建
- 合并：未执行
