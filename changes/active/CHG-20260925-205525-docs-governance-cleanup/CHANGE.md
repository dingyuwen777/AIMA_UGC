---
schema: coding-change/v1
id: CHG-20260925-205525-docs-governance-cleanup
title: 收敛 AIMA 文档 Owner 与重复事实源
level: L2
status: ready_for_review
owner: yuwen.ding
branch: docs/605-docs-governance-cleanup
created: 2026-09-25T20:55:25+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - docs
  - governance
  - developer-experience
affected_paths:
  - docs/README.md
  - docs/AGENTS.md
  - docs/02_环境运行与部署.md
  - docs/03_API接口说明.md
  - docs/04_测试与调试说明.md
  - docs/blueprint/README.md
  - docs/blueprint/01_总体架构与技术选型.md
  - docs/blueprint/03_数据库与文件存储.md
  - docs/blueprint/04_后端任务API与前端.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - docs/blueprint/07_技术决策与实施门禁.md
  - docs/appendix/README.md
  - docs/appendix/03_TikHub多接口验证与备用策略.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/appendix/13_AI大规模打标与成本优化方案.md
  - docs/guides/README.md
  - docs/guides/01_Figma与前端设计开发工作流.md
  - docs/guides/05_多人协作与Change自动归档.md
  - docs/operations/README.md
  - docs/roadmap/README.md
  - scripts/quality/check_docs_facts.py
  - tests/unit/test_docs_facts.py
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：AIMA 文档经过持续扩展后出现通用 Agent_Skills 规则副本、机器事实镜像和跨 Owner 重复，导致阅读入口变重、权责判断成本上升。
- **拟议修改**：保留 Agent_Skills 作为通用治理 canonical Owner；AIMA 只保留项目 Overlay、项目接线和项目事实；把运行/API/测试/Blueprint/Appendix/Guide 收敛到各自读者任务，并修正文档事实门禁，避免再次强迫 Markdown 镜像完整 OpenAPI/Schema/Job/Route。
- **预期结果**：读者可以从 docs 总入口定位唯一 Owner；精确机器事实回到代码/Contract/Schema/CI；长期专题知识保留但重复解释显著减少。

# 背景、现状与问题

## 背景

用户要求全面检查并整改 AIMA_UGC docs，目标是让文档遵循第一性原理、权责清楚、能够被人读懂，并在完成后合并 main。项目继续由 Agent_Skills 治理，本任务不是移除 Agent_Skills。

## 当前现状

main `ca1fbdc0844bb31156b4b45c21ab11775b88f8ea` 的 docs 有 55 个 Markdown、937236 bytes。目录分层原则基本正确，但部分文件已经成为“百科”：

- 环境运行文档同时重复 Windows/Release/Production；
- API Guide 和 Blueprint 手抄精确 Route；
- Blueprint 01/03 手抄完整 Job/Table inventory；
- Blueprint 06 与 Guides 重复通用 Agent_Skills 方法；
- docs/04 同时维护 AIMA 测试资产与通用 Testing 方法；
- Appendix 08 同时承担总体数据架构和具体 Replay/撤销实现；
- Appendix 13 混合当前事实与未批准候选；
- TikHub 验证方法和验证台账重复平台 Endpoint/价格事实。

## 问题、根因或约束

根因不是“文件数量多”，而是同一个事实存在多个完整解释 Owner，并且 `check_docs_facts.py` 的部分机器门禁还在主动要求 Markdown 复制完整机器 inventory。

因此只删文字不能闭环；必须同时修改 Owner 规则和门禁语义。

## 不修改的后果

继续按现状扩展会造成：

- Agent_Skills 与 AIMA 文档规则漂移；
- API/Schema/Job/Route 每次变化要求多处同步；
- 新成员知道“答案在 docs 里”但难判断谁是最终事实；
- 临时 Migration/评估/历史内容只增不退；
- 为保持 CI 绿色反向恢复已经不合理的文档镜像。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | main docs 为 55 个 Markdown、937236 bytes | GitHub main tree `ca1fbdc...` 全量统计 | 文档体量大，但不能把“减文件数”当目标 |
| E2 | 整改分支 docs 仍为 55 个 Markdown、677529 bytes，减少 259707 bytes / 27.7% | GitHub branch tree `2fc81ac...` 全量统计 | 精简主要来自重复内容，而非删除专题文件 |
| E3 | 原 `check_docs_facts.py` 要求 API Guide 含全部 OpenAPI Path，Blueprint 03 含全部表名，Blueprint 01 含全部 Job type，并在多个 Blueprint 维护 Route exact-set | main 质量脚本与对应文档 | 必须修治理机制，否则重复会重新长回来 |
| E4 | 当前分支已把 API/Schema/Job/Route 这四类门禁改为机器 Owner 入口校验，并增加防回归测试 | `scripts/quality/check_docs_facts.py`、`tests/unit/test_docs_facts.py` | 机器事实继续可验证，同时不要求 Markdown 镜像全集 |
| E5 | 当前分支全 docs 分四批做相对链接解析，均无 missing link；未发现 docs 引用 `.agents/skills/*/references/` | 2026-09-25 GitHub tree/content 全量审计 | Owner 导航迁移未制造明显断链或 canonical Reference 泄漏 |
| E6 | 当前 base→head diff 只涉及 docs、文档治理脚本/测试和本 Change，没有产品实现、Contract、Migration、依赖或配置文件 | GitHub compare main...`2fc81ac...` | 产品/数据/运行语义不在本次范围 |
| E7 | 容器无法 DNS 解析 github.com，无法通过独立 clone 在本地执行仓库命令 | 2026-09-25 `git clone` 返回 Could not resolve host | 专项命令执行交由 PR 当前 Head GitHub Actions；不伪造本地测试结果 |

## 推断与待确认

- PR 当前 Head 的 Python 单元测试、docs gates 和治理 gate 尚未由 CI 执行；这是 Ready 后的正式交付门禁，不作为“已经通过”声明。
- main 合并、Change Archive 与 Issue Closure 只能在 PR current-head CI / Review 成立后执行。

# 目标、成功标准与非目标

## 目标

让 AIMA 文档形成稳定的“一个读者问题 → 一个长期解释 Owner → 精确事实回机器 Owner”结构，同时保留项目特有的运行、排障、Replay、TikHub、Figma 和协作知识。

## 成功标准

- [x] docs 总入口和本地规则明确 Owner、知识迁移与退出生命周期。
- [x] Agent_Skills 继续是通用治理唯一 Owner，AIMA 只维护项目接线。
- [x] 运行/API/测试入口收敛为读者任务，而不是百科或机器 inventory。
- [x] Blueprint 不再复制完整 Job/Schema/API/Route 集合。
- [x] Appendix 08/13 与 TikHub 03/04 的职责清楚。
- [x] Figma/协作 Guide 不再维护通用 Agent_Skills 方法副本。
- [x] 文档治理脚本不再强制 API/Schema/Job/Route 镜像全集，并有回归测试。
- [x] 全 docs 导航静态审计未发现断链或 Agent_Skills Reference 路径复制。
- [ ] PR current-head required CI、独立 Review、merge/archive/closure 由 Ready 后交付阶段完成。

## 范围

见 frontmatter affected_paths；允许修改文档、文档事实质量脚本、其单元回归和本 Change/PR/Issue 治理信息。

## 非目标

- 修改 Agent_Skills canonical 源；
- 修改产品功能、API/Schema/Migration、数据库数据、Provider 行为、依赖、配置；
- Release / Deploy / 生产 Migration / 生产数据操作；
- 以文件数最少为目标删除仍有效知识。

## 必须保持不变

- Agent_Skills 仍通过根 AGENTS.md 治理本项目；
- 当前产品/HTTP/Schema/Job/Frontend/Provider 机器事实不变；
- 现有稳定文档路径尽量保持，历史 Change/Git 不改写；
- 未批准 AI/TikHub 等候选不得被升级为 Roadmap。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只做 Docs Governance Cleanup | #605、E1–E6 | 不吸收产品重构或 Agent_Skills Mutation |
| 接口与契约 | 不改变 public Contract；文档只链接机器 Owner | E3/E4 | OpenAPI/Generated Client 不变 |
| 数据与迁移 | 不涉及 Schema/Migration/数据 | E6 | 无数据迁移 |
| 错误与失败语义 | 文档/治理 gate 失败必须 fail closed | 当前 CI/quality 机制 | 不通过删门禁或恢复重复文档造 Green |
| 兼容性 | 保持主要文档路径；内容原地收敛 | docs/AGENTS 与知识迁移门禁 | 降低历史链接破坏 |
| 部署与回滚 | 无运行部署；PR 可整体回滚 | E6 | 不需生产回滚 |

# 修改方案与决策依据

## 最小充分方案

1. **先定 Owner**：重写 docs 总入口、本地规则和各目录 README，明确机器事实/当前说明/Roadmap/History。
2. **收敛通用治理副本**：Blueprint 06、Figma Guide、协作 Guide 只保留 AIMA 项目接线。
3. **收敛读者入口**：环境、API、测试文档只保留 AIMA 使用语义、命令和真实依赖，专项内容回已有 Owner。
4. **收敛架构 inventory**：Blueprint 01/03/04 保留机制与导航，完整 Job/Schema/Route 回机器 Owner。
5. **收敛专题职责**：Appendix 08 保留入口/Lineage/Replay/撤销；Appendix 13 明确未批准候选；TikHub 03 方法、04 台账。
6. **修根因门禁**：check_docs_facts 从 inventory 镜像校验改为机器 Owner 入口校验，并增加单元回归。
7. **验证与交付**：全 docs 链接/Owner 审计 → Change Ready → PR CI → Review → merge → archive/closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 不删 Agent_Skills 接线 | E3 + 用户明确纠正 | 问题是重复通用规则，不是 Agent_Skills 本身 |
| D2 不以文件数为 KPI | E1/E2 | 55 个文件仍可职责清楚；删除文件会增加知识丢失风险 |
| D3 修改 docs-facts gate | E3/E4 | 不修门禁会再次强迫文档长成机器镜像 |
| D4 不合并 TikHub 03/04 | 文档职责审计 | 方法与实证台账生命周期不同，拆分比合并更清楚 |
| D5 Appendix 13 保持旧路径但改正文身份 | 链接/历史兼容审计 | “评估”语义已清楚，重命名收益不足以抵消路径迁移成本 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 总入口与 docs 本地规则明确 Owner/迁移/退出 | #605 / AC1 | satisfied | `docs/README.md`、`docs/AGENTS.md` 已重构 |
| R2 | Blueprint 06 只保留 AIMA 治理接线 | #605 / AC2 | satisfied | `docs/blueprint/06_开发约束与分阶段实施.md` 只保留 Requirement/Change/CI/Docs/Archive 接线 |
| R3 | 环境文档变为日常运行入口 | #605 / AC3 | satisfied | `docs/02_环境运行与部署.md` 由 1197 行收敛到 346 行，专项导航至 Guides/Operations |
| R4 | API 文档不镜像 OpenAPI Route | #605 / AC4 | satisfied | `docs/03_API接口说明.md` 当前无手抄 `METHOD /api/...` 路由行；精确事实链接 OpenAPI |
| R5 | Appendix 08 只保留入口/Lineage/Replay/撤销 | #605 / AC5 | satisfied | 文档由 1344 行收敛到 603 行，总体 Canonical/存储原理链接 Blueprint |
| R6 | Appendix 13 区分事实与未批准候选 | #605 / AC6 | satisfied | 标题/正文改为容量与成本评估；候选明确不自动进入 Roadmap |
| R7 | Figma Guide 只保留 AIMA 项目接线 | #605 / AC7 | satisfied | `docs/guides/01_Figma与前端设计开发工作流.md` 当前 153 行，通用方法回 Agent_Skills |
| R8 | 协作 Guide 只保留 AIMA Change Archive 接线 | #605 / AC8 | satisfied | `docs/guides/05_多人协作与Change自动归档.md` 当前 123 行 |
| R9 | TikHub 方法与证据分责 | #605 / AC9 | satisfied | Appendix 03 只保留 A/B 方法/状态/切换门禁；Appendix 04 继续作为实证台账 |
| R10 | Blueprint/Testing 不再维护完整机器清单，门禁有回归 | #605 / AC10 | satisfied | Blueprint 01/03/04 与 docs/04 收敛；`check_docs_facts.py` + `test_docs_facts.py` 新增 anti-mirroring 回归 |
| R11 | 导航完整、无 Agent Reference 复制、候选不进 Roadmap | #605 / AC11 | satisfied | E5 全 docs 审计 missing=[]、agentRefs=0；Roadmap README 明确准入 |
| R12 | 不改变产品/Contract/Schema/依赖/配置/Provider 语义 | #605 / AC12 | satisfied | E6 compare 仅 docs、治理脚本/测试和 Change |
| R13 | Ready 后执行 CI/Review/merge/archive/closure | #605 / AC13 | explicitly_deferred | AC13 属于 Ready 后 Delivery Gate；PR #606 已建立，当前未宣称 CI/merge/archive/closure 完成 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| docs 导航/规则/README | 明确 Owner、准入、退出 | 防止知识再次跨 Owner 生长 | R1/R11 |
| 02/03/04 与 Blueprint | 移除百科/inventory，保留项目语义 | 降低读者与同步成本 | R3/R4/R10 |
| Appendix 03/08/13 | 分离方法、实现、评估身份 | 防止专题与架构/Roadmap混杂 | R5/R6/R9 |
| Guides 01/05 | 保留 AIMA 接线，通用方法回 Agent_Skills | 单一治理 Owner | R2/R7/R8 |
| check_docs_facts.py | inventory exact-set → machine-owner entry | 切断文档膨胀机制 | R4/R10 |
| test_docs_facts.py | anti-mirroring 回归 | 防止未来恢复第二套事实 | R10 |

执行状态：

- [x] 调查当前实现和事实源
- [x] 建立风险相称的任务路由和验证矩阵
- [x] 建立文档事实门禁失败机制的回归测试
- [x] 完成最小充分整改，不修改产品运行逻辑
- [x] 同步受影响长期文档
- [x] 完成需求追溯与完成审计
- [ ] PR current-head CI / Review / merge 后交付门禁

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | `tests/unit/test_docs_facts.py` 新增 API/Schema/Job/Route anti-mirroring 回归；实际执行由 PR current-head CI 完成 |
| 接口 / 契约 | not_applicable | 产品 public API/Contract 未修改；只调整文档对机器 Owner 的引用 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 无数据库、文件格式、队列或运行时生产逻辑变化 |
| 用户 / 工作流验收 | not_applicable | 无产品用户流程变化；文档读者任务由结构/导航审计覆盖 |
| 跨组件关键路径 | not_applicable | 无产品组件接线变化 |
| 外部依赖 / 供应方探测 | not_applicable | 无外部 Provider 行为变化 |
| 构建 / 打包 / 运行 | not_applicable | 无构建、镜像、Runtime、依赖或启动行为变化 |
| 文档 / 治理 / 其他 | required | E2/E5/E6 + PR CI 的 docs/governance gates；Issue/Change/PR 机器 Contract |

## 验证计划

- 目标测试：`tests/unit/test_docs_facts.py`、`tests/unit/test_docs_navigation.py`
- 相关回归：docs/quality/governance scope selected by CI
- 静态检查：`check_docs.py`、`check_docs_facts.py`、`check_agent_governance.py`
- 专项真实边界：全 docs GitHub tree/content 链接和 Owner 审计
- 就绪检查：AIMA `scripts/quality/check_change_completion.py` / CI current-head gate

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 精简误删知识、链接断裂、门禁失真 | Owner 迁移优先；55 文件不减少；全 docs 链接/Reference 审计；CI |
| 兼容性 | 产品兼容；文档路径大体保持 | E6；Appendix 13 等不做低价值重命名 |
| 数据 / Migration | 不适用 | 无 Schema/Migration/数据文件修改 |
| 部署 / 运行 | 不适用 | 无 Runtime/Compose/Release/配置修改 |
| 回滚 / 恢复 | Git 回滚 PR 即可 | 无数据副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：本任务本身就是 full docs governance 影响，Owner/README/主要入口同步。
- **依赖 / Runtime**：不新增、删除或升级依赖。
- **配置 / Secret**：不改变。
- **部署 / Release**：不需要 Release/Deploy；本次只合并文档治理代码。
- **兼容 / 消费方通知**：开发者后续按新的文档 Owner 导航；产品调用方无变化。

# 完成审计

- [x] upstream_re_read：已重新读取 #605、AIMA 根/docs AGENTS、目标文档、质量脚本，并读取 Agent_Skills 当前 canonical Docs/Coding/Review 规则。
- [x] change_coverage：已按 #605 AC1–AC13 重新建立 R1–R13；AC1–AC12 已有当前分支实现/静态证据，AC13 明确属于 Ready 后交付门禁。
- [x] reverse_audit：已从“机器事实 → 文档 Owner”和“文档读者任务 → 机器事实”双向审计；全 docs 分批链接解析均无 missing，未发现 Agent_Skills canonical Reference 路径复制。
- [x] unresolved_cleared：当前实现范围内无 not_satisfied；CI/Review/merge/archive/closure 按 #605 AC13 明确延期到 Ready 后执行，不冒充已经完成。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main `ca1fbdc...` | GitHub tree 全量 docs 统计 | 55 files / 937236 bytes | 整改前基线 |
| V2 | branch `2fc81ac...` | GitHub tree 全量 docs 统计 | 55 files / 677529 bytes，-27.7% | 没有靠删专题文件减量 |
| V3 | branch `2fc81ac...` | docs 分 root+blueprint / appendix / collection+guides / operations+product+roadmap 四批解析 | missing links = 0；Agent canonical Reference refs = 0 | 导航/治理边界静态闭环 |
| V4 | branch vs main | GitHub compare | 仅 docs、quality script/test、Change | 产品/Contract/Schema/依赖不受影响 |
| V5 | branch | 机器事实镜像审计 | API Guide 不再列完整 API Route；Blueprint 01/03/04 不再列完整 Job/Schema/API inventory | 解决第二套事实源根因 |
| V6 | 当前环境 | `git clone` 尝试 | 失败：Could not resolve host github.com | 无法提供本地命令执行证据；必须以 GitHub Actions 为正式执行证据 |

## 未验证内容与剩余风险

- PR #606 当前 Head CI 尚未运行；需要在本 Change Ready 后将 PR 转为 Ready 并使用 GitHub Actions 执行 docs/governance/unit gates。
- 当前 Agent 可以按 Review Skill 独立重建 Requirement/diff 做 Review，但无法制造不同人类/不同模型审查主体；如仓库平台要求外部 reviewer，应以平台 required review 为准。
- 未执行 Release/Deploy/生产环境验证，因为本次无运行行为变化。

## 交付状态

- 提交：当前分支已有 9 个整改提交（含本次 Ready Change 提交前的 8 个实现提交）
- 拉取请求：#606，当前为 Draft；本 Change 提交后转 Ready
- CI：待 current-head Ready PR 触发
- 合并：待 Review + required CI
- Change 归档：merge 后由 repository-native Change Archive 执行
- 发布 / 部署：不适用；本任务不改变运行产物或生产环境

## 备注

容器环境 DNS 不可用导致无法 clone GitHub 仓库执行本地专项命令；该限制不通过伪造测试结果绕过，正式证据改由 PR current-head GitHub Actions 提供。
