---
schema: coding-change/v1
id: CHG-20260929-112600-content-labeling-v4-6
title: 将首次正式 AI 打标基线升级为 Prompt V4.6
level: L2
status: done
owner: codex
branch: feature/656-content-labeling-v4-6
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - administration
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v4.6.md
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling_bootstrap.txt
  - backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py
  - backend/src/aima_ugc/modules/analysis/schemes.py
  - backend/src/aima_ugc/modules/analysis/content_labeling.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/adapters/llm/openai_compatible.py
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py
  - backend/src/aima_ugc/bootstrap/analysis_identity.py
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - tests/unit/analysis/
  - tests/integration/content/
contracts:
  - Analysis Scheme definition semantics
  - ContentLabeling model payload/input hash
  - content-labeling.v4.6 output protocol
data_changes: []
---

# 变更摘要

- **要解决的问题**：第一次正式 AI 打标已经确定使用用户上传的 Prompt V4.6，但 main 的 bootstrap、Scheme Contract、模型输入、Validator 和离线链仍保留 V4/旧闭集假设。
- **拟议修改**：原样纳入 V4.6 Prompt，切换首次 bootstrap，并只修改让该 Prompt 能被 Scheme、正式 Analysis 和离线共用链路正确执行所需的后端逻辑与文档；不增加前端回归。
- **预期结果**：第一次正式 Analysis Run 以 V4.6 为基线，Prompt/Taxonomy/模型输入/本地校验语义一致，旧 V3/V4 Scheme 兼容路径继续保留。

# 背景、现状与问题

## 背景

用户明确确认当前尚未开始正式 AI 打标，V4.6 是第一次正式打标 Prompt，并要求仓库 Prompt 文本与本轮上传文件一致。Requirement Source 为 #656。

## 当前现状

- Git bootstrap 原先指向 V4；运行时正式事实仍由数据库唯一 active Analysis Scheme Version 持有。
- V4.6 Parser 支持基础已经存在，但此前缺少正式 V4.6 Prompt 资产和完整 Scheme round-trip。
- Analysis Scheme Contract 原先强制“无法判断 / 无法分类”，与 V4.6 三分类、四情感闭集冲突。
- Canonical 已有 platform，但旧 ContentLabeling 模型 payload/input hash 没有 platform。
- 旧离线 Excel 完备规则会覆盖 irrelevant 语义，并在失败时存在本地业务分类兜底。
- 前端 Taxonomy/筛选从 active Scheme/Filter Options 动态读取，本任务不改变该机制。

## 问题、根因或约束

真正需要闭合的是“V4.6 作为运行时协议”而不是单独替换 Markdown 文件：同一 Prompt 必须能被 Parser、Scheme compiler、模型输入、Validator、正式 PostgreSQL Analysis 和离线链一致消费；同时不能为了实现方便改写用户上传的业务文本。

## 不修改的后果

如果只新增 Prompt 文件而不修正上述边界，首次正式打标可能仍使用旧 bootstrap、Scheme 无法保存 V4.6、官号平台白名单缺少 platform 上下文，或离线入口覆盖 V4.6 的 irrelevant/失败语义。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 用户确认尚未开始正式打标，V4.6 为首次正式 Prompt | #656 / 当前任务 | 不需要历史结果迁移或重打 |
| E2 | 上传原文件 CRLF SHA-256 为 `44e584274fd2bd5b5d5bf81143f29068c84d44d97c6d723af51c24a29887a1a5`；LF 规范化文本 SHA-256 为 `9a8fa7e98680ee707871f0303d4154dfbae4e900c0be90535edd8b5793ab02cb` | 用户上传文件 + Git Prompt blob 对照 | Prompt 业务文本不得改写 |
| E3 | Git Prompt 与上传文件的 LF-normalized Git blob SHA 均为 `03adad6611f96d8b4eb88352025792680fdcade1` | 当前分支 Prompt 与上传文件规范化对照 | 证明业务文本逐字一致 |
| E4 | V4.6 只允许 3 类 voice_type、4 类 sentiment，并规定 irrelevant/EMPTY_INPUT/clear 协议 | 用户上传 V4.6 | Parser/Validator 必须严格执行 |
| E5 | Canonical Content 已有 platform | `backend/src/aima_ugc/contracts/canonical/content.py` | platform 应进入模型 payload 与 input hash |
| E6 | 前端分类目录由 active Scheme / Filter Options 动态投影 | `backend/src/aima_ugc/bootstrap/content_http.py`、前端现有实现 | 无需增加前端回归或平行枚举 |
| E7 | CI 先要求 changed Change 进入 ready_for_review，再执行代码/测试层 | `.github/workflows/ci.yml`、`scripts/quality/check_change_completion.py` | current-head CI Green 属于 Ready 之后的 delivery gate |

## 推断与待确认

- 部署到生产/测试环境后，数据库是否已经因页面访问等原因形成旧 V4 的纯系统 bootstrap，是环境事实；本 PR 不写生产数据。实现已提供“尚无 Analysis Run 且仍为纯系统 bootstrap”时升级到当前 Git 基线的受限路径。
- Release/Deploy 不在本任务授权范围。

# 目标、成功标准与非目标

## 目标

让 V4.6 成为系统第一次正式 AI 打标的可靠基线，并确保 Prompt 原文、结构化 Scheme、模型上下文、本地校验和正式/离线执行链一致。

## 成功标准

- [x] Prompt V4.6 与用户上传原文文本一致，只有 CRLF/LF 存储换行差异。
- [x] bootstrap pointer 指向 V4.6，Parser/Scheme 可以 round-trip 到原始 Prompt。
- [x] platform 进入模型 payload 与 input hash，evidence 仍只取五个文本字段。
- [x] V4.6 的三分类、四情感、irrelevant、EMPTY_INPUT 和 clear 终态由 Validator 守住。
- [x] V4.6 离线链不再覆盖 irrelevant，也不伪造失败后的业务标签。
- [x] 前端机制不修改，不新增前端回归测试。
- [ ] 合并前 current-head PR required CI 必须全部通过。

## 范围

- Analysis Prompt/Parser/Scheme/Validator/模型输入与首次 bootstrap。
- 离线 V4.6 冲突覆盖修正。
- Analysis 当前实现文档与必要后端/Contract/PostgreSQL 回归。

## 非目标

- 不增加前端回归测试，不重构前端 Taxonomy/筛选机制。
- 不新增 DB Schema/Migration。
- 不做历史正式打标迁移/重打。
- 不升级依赖。
- 不 Release/Deploy，不写生产数据。

## 必须保持不变

- `ContentLabelAnalysisV3` 持久化结构不变。
- Analysis Scheme 仍是运行时唯一 active 业务事实源，Run 继续冻结 Prompt/Taxonomy/Model 身份。
- 旧 V3/V4 Scheme 兼容读取/编译路径继续可用。
- 前端继续动态消费 active Taxonomy。
- CI、Review、Branch Protection、Release/Deploy 门禁不降低。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只改 Analysis/Administration 后端与对应文档/测试 | E1、#656 | 不扩大到前端重构 |
| 接口与契约 | 调整 Scheme definition 旧硬编码与内部模型 payload；HTTP Result 结构不破坏 | E4-E6 | generated client 形状保持 |
| 数据与迁移 | 无 Schema/Migration、无历史结果迁移 | E1 | 不产生数据迁移风险 |
| 错误与失败语义 | V4.6 Validation/Provider 失败保留失败事实，不造业务分类 | E4 | 离线与正式语义一致 |
| 兼容性 | V4.6 新基线 + 旧 V3/V4 Scheme 兼容 | 当前 Scheme 架构 | 不破坏已有配置历史 |
| 部署与回滚 | 本 PR 不部署；代码回滚即可恢复源码基线 | #656 非目标 | 生产 active 状态需部署时单独核验 |

# 修改方案与决策依据

## 最小充分方案

1. **Prompt 与 Parser**
   → 原样新增 `content_labeling_v4.6.md`，bootstrap pointer 指向 V4.6；Parser 从自描述 Markdown 解析闭集且不把“标签规则”混进标签。
   → 直接验证固定 hash、版本、3/4/5/8/9 Taxonomy 闭集。

2. **Analysis Scheme**
   → V4.6 bootstrap 生成可编辑结构化 definition，但 compiler 必须精确重建原 Markdown；旧 marker-based Scheme 路径不改语义。
   → 直接验证 bootstrap/compile round-trip 和 PostgreSQL 首次 bootstrap。

3. **模型输入与 Validator**
   → platform 进入 payload/input hash；V4.6 voice_evidence、irrelevant、EMPTY_INPUT、clear 终态按 Prompt 执行。
   → 直接验证 Unit/Contract 行为。

4. **离线路径**
   → V4.6 不注入旧 Excel relevance 覆盖；失败时不启用本地业务分类 fallback。
   → 直接验证离线 Validation/Provider 错误传播与 irrelevant 语义。

5. **文档与交付**
   → 同步 Analysis README/Appendix；不增加前端回归。
   → current-head CI 与独立 Review 通过后才允许合并。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 原样保留 V4.6 Prompt | E1-E4 | Prompt 本身是已确认业务事实源，Parser 应适配 Prompt 而不是反向改写 Prompt |
| D2 platform 纳入输入身份 | E5 | 平台参与官号白名单判定，必须成为模型上下文和幂等输入的一部分 |
| D3 不新增前端回归 | E6 + 用户明确要求 | 前端 Contract/动态目录机制未改变，没有独立新 UI 行为需要新增测试 |
| D4 PR CI 在 Ready 后执行 | E7 | 避免“需要 CI Green 才能 Ready、但 CI 又要求先 Ready”的循环依赖 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Prompt 文件与用户上传原文文本一致 | #656 / AC1 | satisfied | E2/E3；`tests/unit/analysis/test_content_labeling_v46.py` 固定 LF-normalized SHA |
| R2 | bootstrap pointer 指向 V4.6 | #656 / AC2 | satisfied | `content_labeling_bootstrap.txt` + V4.6 prompt path test |
| R3 | V4.6 闭集正确解析且标签规则不混入 taxonomy | #656 / AC3 | satisfied | `test_v46_taxonomy_and_semantic_closed_sets_are_parsed_without_rule_bullets` |
| R4 | Scheme bootstrap/compiler round-trip 保留原 Prompt | #656 / AC4 | satisfied | V4.6 Scheme unit + PostgreSQL bootstrap integration |
| R5 | Scheme Contract 去除旧未知值硬编码并保留通用约束 | #656 / AC5 | satisfied | `contracts/administration.py` + Scheme Contract tests |
| R6 | platform 进入模型 payload/input hash，evidence 边界保持 | #656 / AC6 | satisfied | `test_v46_model_payload_and_input_hash_include_platform` + evidence validator |
| R7 | V4.6 Validator 锁定 voice_evidence/irrelevant/EMPTY_INPUT/clear | #656 / AC7 | satisfied | `tests/unit/analysis/test_content_labeling_v46.py` 对应回归 |
| R8 | 离线链不覆盖 irrelevant，不伪造失败业务结果 | #656 / AC8 | satisfied | V4.6 Excel/offline failure tests + `openai_compatible.py` |
| R9 | 不新增前端回归且动态 Taxonomy Contract 保持 | #656 / AC9 | satisfied | diff/reverse audit：无前端业务实现与新前端测试；现有 active Taxonomy HTTP 形状不变 |
| R10 | 合并必须经过 current-head required CI | #656 / AC10 | explicitly_deferred | E7：CI workflow 只在 Change Ready 后执行完整层；merge 在 CI Green 前保持禁止 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `modules/analysis/prompts/` | 新增原文 V4.6、切 bootstrap | 建立首次正式基线 | R1-R3 |
| `prompt_taxonomy.py` / `schemes.py` | 支持 V4.6 Markdown Taxonomy 与 exact round-trip | 数据库 Scheme 是运行时唯一事实源 | R3-R5 |
| `content_labeling.py` | platform/input hash、V4.6 Validator/失败语义 | 完整执行 Prompt 协议 | R6-R8 |
| `contracts/administration.py` | 去掉旧 unknown 硬编码 | V4.6 Scheme 可保存 | R5 |
| `adapters/llm/openai_compatible.py` | V4.6 不注入旧 Excel 覆盖 | 避免调用层反向修改业务判断 | R8 |
| Analysis docs/tests | 同步当前实现并建立后端证据 | 防止 Prompt/运行链漂移 | R1-R10 |

执行状态：

- [x] 调查当前实现和事实源；确认首次正式打标与 V4.6 原文
- [x] 建立 L2 任务路由和验证矩阵
- [x] 行为变化建立针对性回归
- [x] 完成最小实现，没有新增依赖、Migration 或前端重构
- [x] 同步受影响 Analysis 文档
- [x] 完成需求追溯与完成审计
- [x] 进入独立 Review 与 current-head CI delivery gate

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Prompt Parser、Scheme compiler、Validator、payload/hash、offline V4.6 回归 |
| 接口 / 契约 | required | Analysis Scheme definition 语义与既有 HTTP Result shape |
| 集成 / 持久化 / 运行依赖 | required | PostgreSQL Analysis Scheme 首次/未使用 bootstrap 路径 |
| 用户 / 工作流验收 | not_applicable | 本次无新 UI/用户交互；用户明确不增加前端回归，前端动态 Taxonomy 机制未改 |
| 跨组件关键路径 | not_applicable | 现有 Analysis Job 组装方式未改变；Parser/Scheme/Persistence 独立层已有直接证据 |
| 外部依赖 / 供应方探测 | not_applicable | 不需要真实付费 LLM Provider 才能证明 Prompt 协议与本地 Contract 正确性 |
| 构建 / 打包 / 运行 | required | current-head CI 的 Python 静态、单元/Contract/API、Wheel/Runtime 现有 required layer |
| 文档 / 治理 / 其他 | required | Prompt hash、Change/Requirement、Docs/Secret/Governance gates |

## 验证计划

- 目标测试：V4.6 Prompt/Parser/Scheme/Validator/payload/offline。
- 相关回归：Analysis 既有 V3/V4、Scheme、OpenAI-compatible、offline。
- 静态检查或构建：Ruff、mypy、generated contract drift、Wheel（按 CI scope classifier）。
- 专项真实边界：PostgreSQL Analysis Scheme bootstrap integration。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --changed-since <PR-base>`；current-head PR CI 作为合并前硬门禁。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Prompt 被意外改写或 V4.6 与 Scheme/Validator 漂移 | 固定文本 hash、round-trip、Parser/Validator 测试 |
| 兼容性 | 兼容旧 V3/V4 Scheme；V4.6 成为新的首次正式基线 | legacy compiler/parser 路径保留并由相关回归覆盖 |
| 数据 / Migration | 不适用 | 没有历史正式打标结果，DB Schema 不变 |
| 部署 / 运行 | 本 PR 不执行部署 | active Scheme 环境事实在实际部署时核验；未使用纯系统 bootstrap 可受限刷新 |
| 回滚 / 恢复 | 源码可逆，无数据迁移需要反向操作 | 回滚代码/Prompt pointer 即可恢复代码基线 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 Analysis README 与 AI 打标 Appendix，说明 V4.6 首次基线、platform 输入、Scheme round-trip 和离线语义。
- **依赖 / Runtime**：不新增、不升级依赖；API/Worker/Scheduler 进程模型不变。
- **配置 / Secret**：不新增 Secret 或 LLM Provider 配置项。
- **部署 / Release**：本任务不执行 Release/Deploy；代码合并后仍需按正常发布流程进入服务器。
- **兼容 / 消费方通知**：前端继续消费同一动态 Taxonomy Contract，不需要新增前端业务逻辑。

# 完成审计

- [x] upstream_re_read：已重新读取 #656、用户上传 V4.6、AIMA 项目规则、Analysis 当前代码/Contract/文档及 current main 事实。
- [x] change_coverage：已按 AC1-AC10 建立逐条 Requirement Traceability；当前 Change 不作为自身需求来源。
- [x] reverse_audit：已从 active Scheme → Taxonomy/Filter Options/管理员配置消费者，以及 Prompt → Scheme → LLM → Validator → Result 反向检查；无新增前端行为，前端回归不适用。
- [x] unresolved_cleared：实现类要求已满足；R10 仅按 CI 先 Ready 后执行的仓库机制明确延期到 delivery gate，CI Green 前禁止 merge。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | PR #658 current branch | 用户上传文件与 Git Prompt blob/hash 对照 | LF-normalized Git blob SHA 同为 `03adad6611f96d8b4eb88352025792680fdcade1` | Prompt 业务文本一致 |
| V2 | PR #658 current branch | 独立代码 Review：Prompt→Scheme→payload→Validator→offline→consumer | 已修正唯一发现的 CRLF/LF hash 测试假设，当前无新增 blocking Finding | 实现路径与 Requirement 一致 |
| V3 | PR #658 current branch | V4.6 Unit/Integration 测试资产审查 | 已覆盖 Parser、round-trip、platform/hash、evidence、irrelevant、EMPTY_INPUT、offline failure、PostgreSQL bootstrap | 测试目标与主要失败投影对应 |
| V4 | PR #658 current-head delivery | GitHub Actions required CI | 由 ready_for_review 后的 CI 执行；CI Gate Green 前禁止 merge | 最终合并证据由仓库 required gate 提供 |

## 未验证内容与剩余风险

- 真实生产/测试服务器当前 active Scheme 属于部署环境事实，本 PR 未部署、未写生产数据库；因此不宣称生产环境已经切换到 V4.6。
- 真实 LLM Provider 输出质量不属于本次 PR 的外部 Probe 门禁；本次保证 Prompt/Contract/Validator/执行链正确接入。

## 交付状态

- 提交：`feature/656-content-labeling-v4-6` 已包含实现与回归。
- 拉取请求：PR #658，当前进入 ready_for_review/CI 阶段。
- CI：current-head required CI 是 merge 前硬门禁。
- 合并：用户已授权；仅在 current-head required CI 与独立 Review 无 blocking Finding后执行。
- Change 归档：合并后由仓库 Change Archive Automation 处理，不在 Implementation PR 提前归档。
- 发布 / 部署：不适用；用户本次仅授权代码合并。

## 备注

不增加前端回归测试；Prompt 正文不因 Parser/Schema 需要被自动改写。
