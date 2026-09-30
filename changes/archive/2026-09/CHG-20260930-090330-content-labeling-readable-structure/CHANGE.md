---
schema: coding-change/v1
id: CHG-20260930-090330-content-labeling-readable-structure
title: 恢复内容打标 Prompt 表格释义与示例结构
level: L2
status: done
owner: assistant
branch: refactor/676-content-labeling-readable-structure
created: 2026-09-30 09:03:30 +08:00
updated: 2026-09-30
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - persistence
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md
  - backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py
  - backend/src/aima_ugc/modules/analysis/schemes.py
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis_schemes.py
  - tests/unit/analysis
  - backend/src/aima_ugc/modules/analysis/README.md
  - docs/appendix/07_AI舆情打标与分析实现.md
contracts:
  - content-labeling.v3.0 prompt and output protocol
  - analysis scheme compilation compatibility
data_changes: []
---

# 变更摘要

- **要解决的问题**：当前唯一 Prompt 的业务语义已经闭环，但在 #675 收敛时弱化了旧版“表格释义 + 判断边界 + 示例”的人类可读结构，降低模型对标签和分类边界的理解清晰度。
- **拟议修改**：只重构 `content_labeling.md` 的解释层，保留当前业务规则、协议标记、机器 Taxonomy/Semantic Rules 以及 Scheme Compiler 依赖的动态闭集骨架；新增必要回归验证结构兼容。
- **预期结果**：Prompt 恢复表格释义和 few-shot 示例，同时 Loader、bootstrap、Scheme Compiler、Validator 与既有打标链路继续正常工作。

# 背景、现状与问题

## 背景

Requirement Source 为 GitHub Issue #676。业务 Owner 明确要求：不恢复旧 Prompt 的业务规则，只恢复旧 Prompt 的表达结构，并确保修改后仍能正常用于打标后合并 main。

## 当前现状

- `content_labeling.md` 是唯一内容打标 Git bootstrap/灾备 Prompt，内部协议为 `content-labeling.v3.0`。
- Prompt 已正确规定电动车行业整体相关性、三类 `voice_type`、source_type/content_intent、四类情感和 9×39 标签。
- `PromptTaxonomyLoader` 读取机器区块；`schemes.py` 还依赖发声类型、情感和标签的人类可读闭集结构做结构化 Scheme 编译。
- 当前解释层以列表为主，缺少旧版同等清晰的表格含义、边界和综合示例。

## 问题、根因或约束

本次问题是 Prompt 表达结构退化，不是当前分类业务规则错误。直接把动态闭集改成纯表格会破坏现有 Scheme Compiler，因此必须在保持编译器识别骨架的前提下恢复解释表格和示例。

## 不修改的后果

当前打标仍可运行，但模型更依赖标签名称自行理解边界，尤其在相近标签、多标签、咨询/真实用户、营销兜底等场景中缺少明确的可执行解释。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 当前唯一 Prompt 协议为 `content-labeling.v3.0`，机器 Taxonomy/Semantic Rules 已存在 | `content_labeling.md` / `prompt_taxonomy.py` | 机器协议和值集合不得漂移 |
| E2 | Scheme Compiler 用正则替换发声、情感与标签的人类可读动态闭集 | `backend/src/aima_ugc/modules/analysis/schemes.py` | 不直接破坏现有动态闭集骨架 |
| E3 | 当前相关性口径是“实质讨论电动车行业即 relevant”，不限爱玛 | `content_labeling.md` §5 | 不恢复旧版只围绕爱玛的规则 |
| E4 | 旧 V4.5 具备标签释义表、高混淆场景和综合示例 | Git 历史 `content_labeling_v4.5_豆包生产稳定版_零空白完整提示词.md` | 只借鉴表达形式，不继承旧业务判断 |

## 推断与待确认

无阻塞待确认项。Prompt 表达增强可能改变模型输出分布，但本次不宣称准确率提升；只验证业务 Contract 与运行链路不被破坏。

# 目标、成功标准与非目标

## 目标

恢复当前 Prompt 的表格释义、边界说明和 few-shot 综合示例，使模型更容易理解当前业务规则，同时保持现有打标运行 Contract 不变。

## 成功标准

- [ ] #676 AC1—AC6 均有当前实现与新鲜验证证据。

## 范围

- `content_labeling.md` 人类可读解释层。
- 与 Prompt 结构、机器区块、Scheme Compiler 兼容直接相关的 Analysis 单元回归。

## 非目标

- 不恢复旧版只围绕爱玛的相关性口径。
- 不改变任何业务枚举、9×39 父子关系、JSON 输出结构或零空白规则。
- 不修改 HTTP Contract、数据库 Schema/Migration、前端、依赖或部署。
- 不做真实付费 LLM Probe、生产部署或生产重新打标。

## 必须保持不变

- `content-labeling.v3.0` protocol marker。
- `AIMA_TAXONOMY` 和 `AIMA_SEMANTIC_RULES` 的当前 schema、值集合与语义。
- Scheme Compiler 的结构化编辑/编译能力。
- 数据库 active Analysis Scheme 仍是运行时唯一业务事实源。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只改 Prompt 表达层和必要回归 | #676 / E1-E4 | 不扩大到前端/数据库/部署 |
| 接口与契约 | 保持 v3.0 输出和机器闭集不变 | #676 AC1/AC3 | 不改 public Contract |
| 数据与迁移 | 不适用：无 Schema/数据写入变化 | #676 非目标 | 无 Migration |
| 错误与失败语义 | 保持 Loader/Compiler/Validator fail-closed 语义 | E1/E2 | 现有错误边界不变 |
| 兼容性 | 保留现有 Scheme Compiler 结构兼容 | E2 | 解释表格放在不会破坏动态替换的位置 |
| 部署与回滚 | 不适用：本次只做代码交付 | #676 非目标 | 可直接回滚 PR，无数据恢复 |

# 修改方案与决策依据

## 最小充分方案

1. 保留当前固定输出、三分类、情感/标签动态闭集和两个机器 JSON 标记区块。
2. 在相关性、发声类型、source_type、content_intent、情感等章节增加当前规则的表格解释与高混淆边界。
3. 在 9×39 动态标签骨架之后增加每个二级标签的“覆盖内容/判断边界/典型表达”表格，并明确典型表达不是关键词匹配规则。
4. 增加与当前规则一致的多标签、竞品、咨询、交易、活动、无关关键词碰撞等 few-shot 示例。
5. 增补结构回归，直接证明 protocol marker、机器区块、9×39 与 Scheme compile roundtrip 均保持成立。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：保留动态闭集骨架 | E2 | 避免为排版破坏管理员 Scheme 编译 |
| D2：表格作为解释层增强 | E3/E4 | 恢复可读性而不回滚业务语义 |
| D3：机器区块保持当前值集合 | E1 | Loader/Validator 的运行 Contract 不应因排版变化而改变 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 当前 v3.0 业务规则、输出结构和既有分类语义保持不变 | #676 / AC1 | satisfied | Prompt 仍为 `content-labeling.v3.0`；现有三类发声、相关性、零空白和固定 JSON 规则未改 |
| R2 | 恢复表格释义、边界和综合示例 | #676 / AC2 | satisfied | `content_labeling.md` 新增发声类型、相关性、主体、意图、情感表格，以及 39 项标签解释、高混淆规则和综合示例 |
| R3 | Git Markdown 标签可直接编辑并自动归一化机器 Taxonomy，Scheme Compiler 继续可用 | #676 / AC3 | satisfied | `prompt_taxonomy.py` 从人类标签区恢复 labels；`schemes.py`/Repository 持久化归一化定义；旧指南不匹配时自动移除 |
| R4 | Loader/bootstrap/compile/Validator 有直接回归承载 | #676 / AC4 | satisfied | `test_content_labeling.py` 与 `test_analysis_scheme_compilation.py` 新增 Git 直改、机器镜像不覆盖、删除标签拒绝、指南失效回归；实际执行由 current-head CI 完成 |
| R5 | 不恢复旧 Prompt/协议，不改 HTTP/DB/前端 public Contract | #676 / AC5 | satisfied | 当前 diff 仅 Prompt、Analysis loader/compiler/persistence、单元回归及实现文档；无 Contract/Schema/Migration/前端文件 |
| R6 | Review/CI/main-fresh 保持为正式交付门禁 | #676 / AC6 | satisfied | PR #677 已建立；本 Change 只声明门禁已接入，不把尚未执行的 current-head/main-fresh CI 写成通过，合并仍依赖平台真实结果 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `backend/src/aima_ugc/modules/analysis/prompts/content_labeling.md` | 增加当前语义的表格释义、边界和 few-shot 示例 | 恢复旧版表达结构 | R1-R3 / E1-E4 |
| `tests/unit/analysis/test_analysis_scheme_compilation.py` | 增加/强化表格化后 compile roundtrip 结构回归 | 防止排版破坏 Scheme Compiler | R3/R4 / E2 |
| `tests/unit/analysis/test_voice_type_taxonomy.py` | 增加机器闭集与表达结构关键约束回归 | 防止业务/机器语义漂移 | R1-R4 / E1 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据或说明测试例外
- [x] 完成最小实现，不静默扩大范围
- [x] 同步受影响的长期文档或明确不适用依据
- [x] 取得仍覆盖当前版本的实现侧验证证据
- [x] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Prompt Loader、Content Labeling/Voice Taxonomy 与 Scheme Compilation 回归 |
| 接口 / 契约 | required | v3.0 marker、机器 Taxonomy/Semantic Rules 与 9×39 父子关系不漂移 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不改数据库或运行依赖；Scheme compile 可由确定性单元证明 |
| 用户 / 工作流验收 | required | 唯一 Prompt 本身具备表格释义、边界和当前规则示例 |
| 跨组件关键路径 | not_applicable | 不改跨组件接线；现有 Prompt→Scheme 编译由组件回归直接覆盖 |
| 外部依赖 / 供应方探测 | not_applicable | 不需要确认任何第三方当前事实，不调用付费 LLM |
| 构建 / 打包 / 运行 | not_applicable | 不改构建/打包/启动；PR CI 仍执行项目常规门禁 |
| 文档 / 治理 / 其他 | required | Change Ready、PR current-head Review/CI、main-fresh、Issue Closure |

## 验证计划

- 目标测试：Analysis Scheme compilation、voice type taxonomy、content labeling/validation。
- 相关回归：`tests/unit/analysis` 与 changed-scope CI。
- 静态检查或构建：仅对实际修改的 Python 测试文件执行项目现有静态检查；Prompt Markdown 由 Parser/Compiler 回归验证。
- 专项真实边界：不适用，不调用真实 Provider。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 旧业务规则回流、Compiler 结构失配、机器闭集漂移 | 以 current main 为语义基线，只借鉴旧版结构；结构/机器回归 fail closed |
| 兼容性 | 应保持当前运行 Contract | 不改 protocol/schema/value set；保留动态闭集骨架 |
| 数据 / Migration | 不适用 | 无 DB/Schema/数据变化 |
| 部署 / 运行 | 无新增步骤 | 数据库 active Scheme 生命周期保持现状 |
| 回滚 / 恢复 | 可直接回滚本 PR | 无不可逆数据副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：当前系统事实和运行机制不变，预计不需要同步 README/Appendix；如实现调查发现事实变化再 targeted 更新。
- **依赖 / Runtime**：不新增、不升级。
- **配置 / Secret**：不变。
- **部署 / Release**：不执行。
- **兼容 / 消费方通知**：无 public consumer Contract 变化。

# 完成审计

- [x] upstream_re_read：已重读 #676、当前 Prompt、`prompt_taxonomy.py`、`schemes.py`、Scheme Repository 与相关回归。
- [x] change_coverage：AC1—AC5 已由实现和回归直接承载；AC6 明确保留为 PR current-head Review/CI、merge 与 main-fresh 外部门禁，不冒充已执行。
- [x] reverse_audit：已核对 Git Markdown 标签 → Loader 归一化 → bootstrap definition → Compiler/Version → RuntimeTaxonomyValidator；也核对管理员 `definition.labels` → Compiler → 归一化 Prompt/机器镜像 → 持久 Version。
- [x] unresolved_cleared：实现范围内无 `not_satisfied`；平台 CI/main-fresh 作为交付阶段证据继续在 PR/Issue 生命周期闭环。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | PR #677 implementation head `e6a7d428` | 直接解析 `content_labeling.md` 人类标签区、`AIMA_LABEL_GUIDE` 和 `AIMA_TAXONOMY.labels` | 9 个一级、39 个二级；guide/machine 与 human 顺序完全一致 | 默认 Prompt 三层标签表达当前无漂移 |
| V2 | PR #677 implementation head `e6a7d428` | 代码级静态审计：Git Markdown→Loader normalize→bootstrap/compile→Repository persisted definition→Validator | 链路闭合；直接 Git 标签编辑不再依赖手工同步 machine labels | 两种编辑入口汇合到同一运行时 Taxonomy |
| V3 | PR #677 current head | GitHub Actions current-head CI | 待 PR 转 Ready 后由平台执行；当前未声称通过 | 合并前 required 自动化证据 |

## 未验证内容与剩余风险

- 当前实现已完成，但本宿主无法在容器中直接拉取 GitHub 仓库执行本地测试；因此不声明本地 pytest/ruff 通过。PR 转 Ready 后以 GitHub Actions current-head 结果作为实际自动化证据。

## 交付状态

- 提交：当前实现代码已推进至 `e6a7d428023a523356bb1b9f3ef70e7a8741ec01`；本 Change 状态更新会形成新的治理提交，CI 必须绑定最终 PR head。
- 拉取请求：#677，当前准备从 Draft 进入 Ready。
- CI：current-head CI 待 Ready 事件触发，未执行前不声明通过。
- 合并：CI/Review 未闭环前不合并。
- Change 归档：merge 后由仓库自动化负责。
- 发布 / 部署：不适用，本任务仅代码交付。

## 备注

无。
