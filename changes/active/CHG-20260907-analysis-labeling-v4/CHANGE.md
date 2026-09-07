---
schema: coding-change/v1
id: CHG-20260907-analysis-labeling-v4
title: 内容打标 V4 与真实用户语义校验
level: L3
status: ready_for_review
owner: dingyuwen777
branch: feature/analysis-labeling-v4
created: 2026-09-07
updated: 2026-09-07
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - llm-adapter
  - contracts
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/adapters/llm/openai_compatible.py
  - tests/unit/analysis/
  - tests/contracts/
  - tests/api/
  - tests/integration/content/
  - docs/appendix/07_AI舆情打标与分析实现.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/04_测试与调试说明.md
  - AGENTS.md
  - changes/active/CHG-20260907-analysis-labeling-v4/CHANGE.md
contracts:
  - Analysis Prompt 输出协议
  - Analysis Scheme Taxonomy
  - ContentLabelingLLMRequest
data_changes: []
---

# 变更摘要

- **要解决的问题**：当前 V3 把主体身份与内容意图压缩到单一 `voice_type`，对普通消费者个人交易、营销伪装成体验、品牌词兼容列表和非品牌情绪等边界缺少可校验的中间证据。
- **拟议修改**：保留 V3 兼容能力，新建 V4 Prompt 输出协议；模型内部输出 `source_type/content_intent/evidence/decision_status`，本地 Validator 检查跨字段一致性，只有冲突或不确定条目进入既有 Validation Retry 形成条件 Judge。
- **预期结果**：明确的个人二手交易不再计入“真实用户发声”；结构合法但业务矛盾、伪造证据或高歧义结果不会直接入库；正常内容仍只调用一次模型。

# 背景、现状与问题

## 背景

用户以真实错例“成色好、手续齐全、可带牌可不带牌，同时包含续航和舒适体验”为入口，确认暂不建立 Gold Set，其余按系统性方案实施。用户同时明确模型输入只能使用 `title/text/author.display_name/author.bio/author.verification_label`。

## 当前现状

- Git Prompt V3 已要求综合主体与表达目的，但输出只有 `relevance/voice_type/sentiment/labels`，代码无法检查模型从输入到最终类别的语义跳跃。
- `RuntimeTaxonomyValidator` 当前只校验 JSON 结构、Taxonomy membership、标签父子关系及 relevant/irrelevant 形状。
- 既有 Validation Retry 会只重试未通过条目，并保留请求、费用、停止和重试边界；默认正式配置至少允许一次 Validation Retry。
- PostgreSQL 中唯一 active Analysis Scheme 是运行时事实；Git Prompt 只负责空库 bootstrap，部署代码不能静默覆盖既有发布版。

## 问题、根因或约束

根因不是单一关键词缺失，而是输出协议缺少主体、意图与证据，导致本地代码只能判断“格式是否合法”，不能判断“普通消费者 + 个人交易却返回真实用户”等逻辑矛盾。仅凭五个公开文本字段也不可能保证每条内容 100% 正确，因此系统必须允许显式不确定并进行条件复判。

## 不修改的后果

交易帖中的体验描述仍可能覆盖交易目的；模型即使返回伪造证据或跨字段矛盾，只要最终枚举合法就会被接受；后续也无法区分主分类与复判请求。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 正式模型输入只有五个业务文本字段，`item_no` 仅用于配对 | `ContentLabelingModelItem.model_payload()` 与当前 V3 Prompt | V4、Validator、Judge 不得引入 Provider 私有或额外业务字段 |
| E2 | V3 `voice_type` 没有个人交易类别，且后半段真实体验可能与交易排除项冲突 | `content_labeling_v3.md` 机器 Taxonomy、边界与用户错例 | 新增“个人交易发声”，拆出主体和内容意图再校验 |
| E3 | 当前 Validator 不校验证据或跨字段业务语义 | `RuntimeTaxonomyValidator.validate_response()` | 在同一 Validator 增加 V4 语义一致性，不写中文关键词分类器 |
| E4 | Validation Retry 已只重试未解决 item，且正式默认重试次数为 1 | `ContentLabelingService.label_contents()`、`PlatformSettings.llm_validation_retries` | 复用既有重试、审计、费用和停止边界实现条件 Judge |
| E5 | active Scheme 在数据库，Git Prompt 只用于空库 bootstrap | `docs/blueprint/07_技术决策与实施门禁.md` 决策 P、`PostgresAnalysisSchemeRepository.bootstrap_default()` | 保持现有 V3 Scheme 可运行，不自动改写已发布配置 |
| E6 | `voice_type` 数据库列为非空字符串，合法值来自冻结 Scheme Taxonomy | `docs/blueprint/03_数据库与文件存储.md`、Analysis tables | 新增 Taxonomy 值不需要 Schema Migration，旧结果继续可读 |

## 推断与待确认

- 暂时无法量化 V4 相对 V3 的 Precision/Recall/F1；用户已明确暂不建立 Gold Set，因此本 Change 只证明协议和逻辑不变量，不把固定回归样例冒充真实效果评测。
- 当前机器未配置可安全执行的付费真实 LLM Probe；这不阻塞离线结构、Validator、兼容和 Job 链验证，但阻塞任何“真实模型准确率已提升”的结论。

# 目标、成功标准与非目标

## 目标

在不增加输入字段和持久化结构的前提下，把内容打标升级为可检查、可条件复判的 V4 协议，并修复普通消费者个人交易缺少独立类别的分类空间问题。

## 成功标准

- [x] V4 只接收既有五个业务字段，明确忽略内容中的 Prompt Injection 指令，并按 relevance → source → intent → voice → targeted sentiment → evidence-backed labels 顺序判定。
- [x] V4 增加“个人交易发声”，普通消费者个人交易不能与“真实用户发声”同时成立；二手经营主体仍归行业/渠道语义。
- [x] Validator 拒绝伪造证据、主体/意图/voice 冲突、relevance/sentiment/labels 冲突及 `needs_judge` 主判结果，不使用中文关键词硬编码重新分类。
- [x] 语义冲突或不确定时只对未解决条目发起 Judge；合法明确条目保持单次调用，Judge 仍只看到五个业务字段并沿用既有次数、停止、费用与审计边界。
- [x] 既有 V3 Scheme 输出仍可校验和执行；新空库 bootstrap V4；现有数据库不会被部署静默切换。
- [x] 持久结果继续只保存 `relevance/voice_type/sentiment/labels` 与既有身份字段；无 Schema/Migration、依赖或前端专用枚举复制。
- [x] 受影响单元、Contract/API、Job/集成、质量和文档门禁取得当前 HEAD 新鲜证据。

## 范围

- V4 Prompt、输出协议识别、V3 兼容解析、V4 Semantic Validator、条件 Judge 请求元数据。
- 当前 Taxonomy 的“个人交易发声”值及对应下游动态 Taxonomy 验证。
- 分析模块、LLM Adapter 的 targeted tests，以及当前实现文档同步。

## 非目标

- 不建立 Gold Set，不运行 V3/V4 真实数据准确率评测，不声称量化效果提升。
- 不加入 TikHub 商业字段、粉丝数、平台、URL、互动指标或其他模型输入。
- 不新增人工审核队列、预算系统、第三方模型或全量双调用。
- 不凭经验修改 DeepSeek thinking/reasoning/temperature；参数选择留给未来同一 Gold Set A/B。

## 必须保持不变

- PostgreSQL Analysis Result、HTTP 内容结果、Excel 与前端继续以既有 `relevance/voice_type/sentiment/labels` 为公共事实。
- 现有 active Scheme、历史结果、人工 override、Job/Lease/Fencing、Transport Retry、费用审计和输入 Hash 语义保持兼容。
- 不新增/升级依赖，不改变启动、部署或 Secret 边界。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只改 Analysis 主分类/校验及 OpenAI-compatible 请求提示元数据 | E1-E4 | 不进入 Provider Mapper、Content Owner 或前端平行分类 |
| 接口与契约 | 新增 V4 内部输出字段；公共持久/HTTP 结果不扩字段 | E1、E6 | 内部协议升级，外部消费者保持兼容 |
| 数据与迁移 | 无 Schema/Migration；旧结果和 V3 Scheme 原样保留 | E5、E6 | 新空库默认 V4，既有库显式发布后生效 |
| 错误与失败语义 | V4 语义冲突进入 Validation Retry；耗尽后沿用既有 failed | E3、E4 | 不吞错、不伪造成功、不新增第二套重试 |
| 兼容性 | 用明确输出协议标记区分 V3/V4 | E5 | 旧 Scheme 不因新代码部署而全部校验失败 |
| 部署与回滚 | 代码可按普通发布回滚；active Scheme 独立按已有版本机制回滚 | E5 | 不自动覆盖数据库业务事实 |

# 修改方案与决策依据

## 最小充分方案

1. 新建 V4 Prompt 并保留 V3；Prompt 添加固定输出协议标记、内部主体/意图/证据/判定状态和个人交易边界。  
   → 修改范围：`prompts/`、`prompt_taxonomy.py`  
   → 预期结果：Git bootstrap 使用 V4，数据库 V3 可被明确识别。  
   → 验证方式：Prompt loader、Taxonomy、最小对照与注入防护测试。
2. 增加 V4 严格解析与 Semantic Validator，按模型输入逐条验证证据和跨字段不变量。  
   → 修改范围：`content_labeling.py`  
   → 预期结果：结构合法但语义矛盾的结果不能进入公共 Analysis。  
   → 验证方式：先写失败测试，再覆盖合法、伪造证据、个人交易冲突、目标情感和标签证据边界。
3. 复用 Validation Retry 增加 `primary/judge` 请求种类；只有语义错误或 `needs_judge` 进入 Judge 指令。  
   → 修改范围：`content_labeling.py`、`openai_compatible.py`  
   → 预期结果：清晰项一次完成，冲突项独立复判且仍只传五个字段。  
   → 验证方式：批次部分成功、请求 payload、Attempt 审计和停止/次数回归测试。
4. 同步受影响的当前文档和引用，完成分层验证、Completion Audit 与 Review。  
   → 修改范围：Analysis README、AI Appendix、相关 Blueprint/测试文档和当前 Prompt 导航。  
   → 预期结果：开发者知道 V4 如何工作、如何发布到既有库及当前限制。  
   → 验证方式：文档链接/事实检查、目标测试、完整后端门禁和 Change Ready Check。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：V4 输出内部证据而不扩公共 Result | E1、E3、E6 | 能增加可校验性，同时避免数据库/API/前端同步和历史迁移 |
| D2：条件 Judge 复用 Validation Retry | E4 | 已有未解决 item、次数、费用、停止与审计机制，新增第二套调用链会扩大风险 |
| D3：保留 V3 并用协议标记路由 | E5 | 防止已有数据库 active Scheme 在代码升级后直接失效 |
| D4：参数调优延期 | 用户明确暂不建 Gold Set | 没有同一基准集时无法证明某个 DeepSeek 参数更准确 |

## 备选方案与取舍

- 只扩写 V3：改动小，但代码仍无法校验伪造证据或主体/意图矛盾，不能系统解决。
- 在 Python 中写二手关键词规则：会把“手续今天终于办齐”等真实体验误杀，也会形成第二套自然语言分类器，拒绝采用。
- 所有内容固定双调用：成本和吞吐翻倍，且清晰样本没有独立收益证据，拒绝采用。
- 自动覆盖既有数据库 active Scheme：会破坏已发布配置和显式回滚语义，拒绝采用。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 模型输入严格限于五个既有业务字段 | #388 / AC1 | satisfied | V4 Prompt 输入契约、`ContentLabelingModelItem.model_payload()` 与 `test_v4_model_payload_still_contains_only_the_five_approved_business_fields` 共同验证 |
| R2 | 实施 V4 Prompt、主体/意图拆分、证据输出和个人交易类别 | #388 / AC2 | satisfied | `content_labeling_v4.md`、Semantic Rules 与个人交易回归测试；实现提交 `71a53786` |
| R3 | 增加本地语义一致性 Validator，不写关键词分类器 | #388 / AC3 | satisfied | `RuntimeTaxonomyValidator` 只校验证据原文归属、闭集和 source/intent→voice 映射；伪造证据、映射冲突和规则原子性红绿测试通过 |
| R4 | 只有冲突/歧义内容进入 Judge，正常内容保持单次调用 | #388 / AC4 | satisfied | partial/mixed batch 测试证明清晰项不重试、结构项进 repair、语义项进 judge；Judge payload 不携带旧响应 |
| R5 | relevance、voice_type、targeted sentiment、多标签形成统一且兼容的 V4 链 | #388 / AC5 | satisfied | Analysis 单元、Contract/API、PostgreSQL Content 全套与冻结 V3 Scheme 回归共同覆盖；公共 `ContentLabelAnalysisV3` 未扩字段 |
| R6 | 暂不建立 Gold Set，参数调优与量化准确率评测随之延期 | #388 / AC6 | explicitly_deferred | 用户本轮明确“先不建立 Gold Set”；不把少量固定样例冒充 Gold Set |
| R7 | 完成后同步最新 main，通过门禁后合并到主分支 | #388 / AC7 | satisfied | 2026-09-07 已通过 SSH fetch；`origin/main=e6475474` 且任务分支包含该基线；实现、Review 与本地门禁完成，远程 CI/merge 继续作为交付硬门禁 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v4.md` | 新增 V4 决策树、内部字段、证据与最小对照 | 建立系统性分类协议 | R1-R5 / E1-E3 |
| `prompt_taxonomy.py`、`schemes.py` | 默认 V4，并识别 V3/V4 输出协议 | 新 bootstrap 与旧 Scheme 兼容 | R2、R5 / E5 |
| `content_labeling.py` | V4 解析、证据和语义一致性 Validator、Judge 路由 | 拒绝结构合法但业务矛盾结果 | R3-R5 / E3-E4 |
| `openai_compatible.py` | 区分 primary/repair/judge 指令 | 条件复判且保持五字段输入 | R1、R4 / E1、E4 |
| Analysis/Contract/API/Integration tests | Red-Green 与兼容回归 | 证明协议、分类、重试和消费者边界 | R1-R5 |
| Analysis README、AI Appendix、相关导航 | 定向同步当前行为与发布边界 | 防止文档继续把 V3 写成当前默认 | R2、R5-R7 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档
- [x] 取得仍覆盖当前版本的验证证据
- [x] 完成需求追溯、完成审计和独立复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | V4 loader/parser、五字段、个人交易、证据来源、跨字段一致性、条件 Judge、V3 兼容 |
| 接口 / 契约 | required | 公共 Analysis Result 不扩字段；动态 Taxonomy 暴露新值；旧消费者与生成边界保持 |
| 集成 / 持久化 / 运行依赖 | required | frozen Scheme V3/V4、Analysis Worker/Job 通过 Fake LLM 写入既有 Result 结构 |
| 用户 / 工作流验收 | not_applicable | 不新增或修改页面操作流程；分类值由现有 Taxonomy API 动态消费，API/Contract 层承担验证 |
| 跨组件关键路径 | required | Canonical 五字段 → Service → primary/judge → Validator → Analysis Result 的少量 Fake golden path |
| 外部依赖 / 供应方探测 | not_applicable | 用户延期 Gold Set，真实 LLM Probe 付费且无法证明总体准确率；本次不发送真实内容 |
| 构建 / 打包 / 运行 | required | Ruff、mypy、目标 pytest、相关后端测试与既有 CI |
| 文档 / 治理 / 其他 | required | 当前文档事实同步、链接检查、Secret/架构/Change/两阶段 Review/CI 门禁 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | V4 输出更严格导致模型首次响应被拒绝，或新增类别影响聚合 | 条件 Judge、明确 `无法判断` 兜底、动态 Taxonomy 与精确真实用户过滤回归 |
| 兼容性 | V3 active Scheme 必须继续可执行 | 输出协议标记路由；无标记按 V3 校验 |
| 数据 / Migration | 无结构迁移 | 旧结果保留；既有库通过已有 Scheme 发布/回滚，不自动改写 |
| 依赖 / Runtime | 不变 | 不新增或升级 Python/Node/镜像依赖 |
| 部署 | 代码发布与 Scheme 发布分层 | 新空库直接 bootstrap V4；既有库需管理员显式发布 V4 定义 |
| 回滚 | 可回滚代码并独立回滚 Scheme Version | 无不可逆数据写入或历史重写 |

# 文档影响

Docs Impact 为 `targeted`：更新 Analysis 模块 README、AI 实现 Appendix 及仍把 V3 路径/七类 `voice_type` 写成当前事实的直接导航；不重写无关 Blueprint、Roadmap 或部署文档。

# 完成审计

- [x] upstream_re_read：已重新读取用户 AC1-AC7、Analysis Blueprint/Appendix、V3/V4 Prompt、Scheme/Result Contract、Worker 调用链及 `e6475474..71a53786` 最终实现 diff。
- [x] change_coverage：已逐条反查五字段、个人交易、证据校验、Judge 分流、公共结果兼容、Gold Set 延期和 Git 同步；没有用 Change 自身替代上游要求。
- [x] reverse_audit：已从公共 `ContentLabelAnalysisV3`、数据库冻结 Scheme、Analysis Worker、动态 Taxonomy、真实用户精确过滤、离线 Checkpoint 和 Wheel 包反向核对消费者边界。
- [x] unresolved_cleared：实现范围内无 `not_satisfied`；Gold Set 与模型参数调优按用户决定保留 `explicitly_deferred`，不声称量化效果。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `71a53786` / Python 3.14.7 / Windows | `uv run pytest tests/unit/analysis -q`；最终完整 unit | Analysis 专项 165 passed；完整 unit 为 878 passed、8 skipped，另有 3 个 POSIX-only 测试在 Windows 因 `os.geteuid/os.chown` 不存在失败 | V4 协议、Validator、repair/judge 分流、V3 Scheme 兼容及平台证据边界 |
| V2 | `71a53786` / PostgreSQL 18.4 隔离容器 | `uv run pytest tests/integration/content -q`；Scheme 发布/回滚与 voice_type Schema 专项 | 53 passed；专项 2 passed | 新空库 V4、Analysis Worker/Job、持久结果、旧 Schema 与版本发布回滚链 |
| V3 | `71a53786` / 当前锁定依赖 | Contract 104 tests；API 53 tests；CI 精确 Ruff、mypy、架构、Owner、Docs、Contract 生成、治理、Secret | 全部通过；mypy 294 source files；Ruff 609 files formatted / lint passed | 公共边界未漂移、静态质量、架构与文档一致性 |
| V4 | `71a53786` / uv build | `uv build --wheel`；Zip 打开与包内容检查 | 构建 `aima_ugc-0.1.0-py3-none-any.whl` 成功，366 entries，包含 `content_labeling_v4.md` | 部署包可携带新默认 Prompt |

## 未验证内容与剩余风险

- V4 在真实数据上的 Precision/Recall/F1、混淆矩阵与 end-to-end exact match 未验证；原因是用户明确延期 Gold Set。
- DeepSeek thinking/reasoning/temperature 的最优组合未验证；无统一真实基准时不应凭经验固定。

## 交付状态

- 提交：治理提交 `bac37351`、失败测试提交 `d9f7a55f`、实现提交 `71a53786`。
- 需求与拉取请求：GitHub Issue #388；PR #387。
- CI：本地同实现提交门禁已完成；GitHub 同-SHA CI 仍是合并硬门禁。
- 合并：最新 `origin/main=e6475474` 已同步且无新提交；仅在 PR 检查通过后合并。
- Change 归档：合并后由既有流程处理。
- 发布 / 部署：不在本次请求范围；既有数据库 Scheme 仍需显式发布。

# 两阶段 Review

- **阶段 1：需求与风险重建**：不依赖 Change checkbox，重新以用户五字段/个人交易/Judge/兼容/延期决定与现有 Scheme/Worker/Result Contract 为完成定义；最高风险是把结构错误错误送入 Judge、语义规则可折叠个人交易、旧 V3 active Scheme 失效、证据超出输入和公共结果扩张。
- **阶段 2：实现与证据对照**：发现并修复“混合未解决批次整体进 Judge”和“个人交易映射可与真实用户相同/主体映射可缺失”两项阻塞问题；补充失败测试后转绿。复查最终生产 diff、测试、文档和 Wheel，未发现剩余合并阻塞 Finding。真实 LLM 准确率仍明确属于 Gold Set 延期边界。
