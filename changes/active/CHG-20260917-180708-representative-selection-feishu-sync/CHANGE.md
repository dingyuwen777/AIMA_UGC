---
schema: coding-change/v1
id: CHG-20260917-180708-representative-selection-feishu-sync
title: 代表性正负面内容筛选与飞书多维表同步
level: L2
status: ready_for_review
owner: chatgpt
branch: feature/merge-BOLL2-main
created: 2026-09-17
updated: 2026-09-17
completion_gate: required
depends_on: []
affected_areas:
  - analysis
  - imports
  - external-provider
  - configuration
  - documentation
affected_paths:
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/feishu/
  - backend/src/aima_ugc/entrypoints/representative_selection_main.py
  - backend/src/aima_ugc/platform/config/settings.py
  - tests/unit/analysis/
  - tests/unit/platform/
  - env.local.example
  - docs/
contracts: []
data_changes:
  - 本地代表性筛选运行审计文件
  - 飞书多维表记录的 Upsert（仅显式 write-feishu 模式）
---

# 变更摘要

本变更为已经完成打标的 Excel 增加独立的代表性正负面内容筛选入口，并支持把确认后的结果安全同步到飞书多维表。结果按平台和情感分成四组，每组最多 10 条；Dry Run 默认不产生飞书写入，写入模式只创建新表，不修改旧表。同步过程还修复了报告发布、浏览器降级、LLM 并发契约和测试配置隔离问题。

# 背景、现状与问题

## 背景

已有打标 Excel 已包含平台、发声类型、情感和内容证据，但此前没有独立的代表性内容筛选及飞书同步闭环。报告发布模块还存在失效异常处理器、浏览器关闭降级和类型检查问题；测试可能受到本地 `.env` 的飞书配置影响。

## 当前现状

代表性筛选入口读取一个或多个已打标 Excel 的“内容”Sheet，按“平台 + 内容ID”去重，只处理抖音和小红书的真实用户发声，并在四个平台/情感分组内选择内容。飞书适配器会动态读取表字段、创建新的时间命名数据表、写入并回读核验。离线报告继续复用统一报告渲染链路。

## 问题、根因或约束

旧流程不能在不重新打标的情况下复用已有标签完成代表性筛选，也没有满足新表写入、快照、回读和 Secret 隔离的完整保护。相关报告代码还保留了已删除异常的注册、浏览器资源关闭边界不完整及若干静态类型问题。

## 不修改的后果

维护者无法从已完成打标的数据快速生成可审计的代表性结果；误写旧飞书表或把 Secret/本地配置带入测试的风险会继续存在，报告发布相关 CI 也无法稳定通过。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 代表性筛选入口只消费已打标 Excel，不应重新执行全量导入和打标 | `backend/src/aima_ugc/entrypoints/representative_selection_main.py`、相关入口测试 | 保持独立入口和已有标签语义 |
| E2 | 飞书写入需要字段动态读取、模板复制、写入前快照和写入后回读 | `backend/src/aima_ugc/adapters/feishu/bitable.py`、Mock HTTP 测试 | 新表写入必须 fail closed，旧表不被修改 |
| E3 | 离线报告使用统一报告 Renderer，真实飞书调用不属于普通 CI | `backend/src/aima_ugc/platform/reporting/README.md`、报告测试 | 复用报告事实源，普通 CI 使用 Mock |
| E4 | 项目使用 bounded concurrency，并要求测试与文档保持同一契约 | `tests/unit/analysis/test_llm_concurrency_contract.py`、Ruff/Mypy | 并发上限和重试边界必须同步 |

## 推断与待确认

真实飞书租户权限和外部 LLM 账户状态不在普通 CI 的可验证范围内；本变更只验证 Mock/离线边界，真实租户 Probe 仍需人工按权限执行。

# 目标、成功标准与非目标

## 目标

- 从一个或多个已打标 Excel 生成四组代表性正负面内容。
- 通过独立 Dry Run 产物审阅结果，并在显式写入时创建新的飞书数据表。
- 修复同一 PR 触及的报告发布、类型检查、浏览器降级、测试隔离和治理文档门禁问题。

## 成功标准

- [x] 四组筛选均只使用已有平台、发声类型和情感标签，每组最多 10 条且不足时不硬凑。
- [x] Dry Run 不调用飞书；写入模式保留快照、执行字段预检并回读核验。
- [x] Mypy、Ruff、目标回归测试和项目质量门禁通过。
- [x] 文档导航和 PR Requirement Source 可由机器检查确认。

## 范围

修改代表性筛选、飞书适配器、离线报告发布边界、相关测试、模块文档、Change 文档和 CI 所需治理导航。

## 非目标

- 不修改原始 Excel、既有导入/打标/报告主流程的业务口径。
- 不新增数据库表、Alembic Migration、公共 HTTP API 或第三方依赖。
- 不删除飞书旧记录，不把 Dry Run 变成真实外部写入。
- 不把真实飞书或付费 LLM Probe 加入普通 CI。

## 必须保持不变

- 已有平台稳定 ID、发声类型、情感标签和报告统计口径保持不变。
- Secret 继续只从受控 Secret 文件读取，不进入日志、Job Payload 或运行摘要。
- 现有持久 Job、Artifact 和配置边界保持兼容。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 复用现有 analysis、Feishu adapter、离线 imports_test 和 reporting Owner | E1、E2、E3 | 不新建平行任务系统 |
| 接口与契约 | 复用现有 Python 入口和配置，增加 `--input-xlsx` 与已有写入模式边界 | E1、E4 | 不新增公共 HTTP Contract |
| 数据与迁移 | 不修改 PostgreSQL Schema；本地运行审计和新飞书表写入只在显式模式产生 | E2 | 无 Migration，保留外部写入保护 |
| 错误与失败语义 | 字段预检、回读不一致和外部失败均 fail closed；LLM/网络失败保留稳定错误摘要 | E2、E3 | 不隐藏部分成功或 Secret |
| 兼容性 | 保持已有 Excel、平台 ID、报告和 Dry Run 行为；`xhs` 文档缩写统一为 `xiaohongshu` | E1、E3、E4 | 旧输入和离线调用继续可用 |
| 部署与回滚 | 代码提交可回滚；不需要数据库迁移或生产部署步骤 | E2、E3 | 外部写入只由人工显式触发 |

# 修改方案与决策依据

## 最小充分方案

1. 在分析模块增加已打标 Excel 的读取、去重、候选分组和四组代表性选择，并保留离线 JSONL 审计产物。
2. 在飞书适配器中动态读取字段并创建时间命名新表，执行预检、快照、批量写入和回读核验。
3. 修正报告发布、浏览器资源关闭、类型边界、测试环境配置和离线并发文档，使实现、测试和说明保持一致。
4. 补齐模块 README、Appendix 导航和治理 Change 的稳定引用，使用本地质量脚本验证。

每一步均由目标单元测试、Mock HTTP、Ruff/Mypy、文档/治理门禁或组合验证直接证明。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1 | 直接消费已有 Excel 标签，避免重复导入和重新打标 |
| D2 | E2 | 动态字段和新表快照/回读能避免模板漂移和旧表误写 |
| D3 | E3、E4 | 继续用统一报告事实源和有界并发，减少重复实现与资源风险 |

## 备选方案与取舍

不采用直接更新旧飞书表或在 HTTP 请求中同步执行长任务：前者破坏审计和回滚边界，后者无法可靠承载 LLM、文件和外部网络耗时。也不采用重新跑全量打标，因为已有 Excel 标签已是本次筛选的事实输入。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 只读取一个或多个文件的“内容”Sheet，并按平台 + 内容ID 跨文件去重 | user:confirmed-requirements / AC1 | satisfied | `labeled_content_reader.py`；单文件、跨文件 Reader 测试 |
| R2 | 只处理抖音和小红书，且只从真实用户发声建立候选池 | user:confirmed-requirements / AC2 | satisfied | `build_candidate_pool()`；候选池单元测试 |
| R3 | 使用已有发声类型和情感标签作为硬筛选条件，不重新打标 | user:confirmed-requirements / AC3 | satisfied | `build_candidate_pool()`、`RepresentativePrompt` 和独立筛选入口 |
| R4 | 四组结果每组最多 10 条，数量不足不硬凑 | user:confirmed-requirements / AC4 | satisfied | 四组选择、本地兜底和不足摘要测试 |
| R5 | 筛选结果保留主题、理由、评分和原始内容字段 | user:confirmed-requirements / AC5 | satisfied | `selected_results.jsonl` 与结果序列化测试 |
| R6 | 每次写入在同一 Base 内新建按生成时间命名的数据表，旧表和旧记录不更新、不删除 | user:follow-up-confirmation / AC6 | satisfied | `create_table_from_current()` 和新表写入/回读测试 |
| R7 | 飞书字段动态读取、类型转换、写入前快照和写入后回读核验 | user:confirmed-requirements / AC7 | satisfied | 字段映射、类型转换、快照和回读测试 |
| R8 | Secret 不进入日志或运行结果，默认 Dry Run | user:security-boundary / AC8 | satisfied | Secret 文件边界、默认入口和稳定错误输出测试 |
| R9 | 不新增第三方依赖、不新增数据库 Migration 或公共 HTTP API | user:confirmed-implementation-plan / AC9 | satisfied | 依赖、Migration 和 API 差异检查 |
| R10 | 运行入口、配置、README 和测试同步 | user:confirmed-implementation-plan / AC10 | satisfied | 独立入口、配置、模块文档和相关测试 |
| R11 | 已完成 Dry Run 后可只同步已有结果，避免重复调用大模型 | user:follow-up-confirmation / AC11 | satisfied | `--write-feishu-from-run` 和入口测试 |
| R12 | 支持直接使用飞书 `/base/` 链接中的 app_token，不强制依赖 Wiki Token | user:follow-up-confirmation / AC12 | satisfied | `AIMA_FEISHU_APP_TOKEN` 及 Base 直连测试 |
| R13 | 已打标的多个 Excel 可直接传入代表性筛选入口 | user:follow-up-confirmation / AC13 | satisfied | 重复 `--input-xlsx`、跨文件读取和入口参数测试 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| analysis / representative selection | 筛选、提示、四组结果和离线恢复边界 | 实现四组代表性选择 | R1—R5 / E1 |
| Feishu adapter / publication | 字段预检、新表创建、快照、写入和回读 | 保护外部写入 | R6—R8 / E2 |
| reporting / imports_test | 报告发布、配置和并发文档同步 | 修复 CI 与运行边界 | R9—R10 / E3、E4 |
| tests/unit、tests/integration | 增加/调整行为和配置回归 | 固化真实行为 | R1—R13 |
| docs/ 与本 Change | 更新导航、事实说明和追溯结构 | 满足文档/治理门禁 | R10 / E3 |

执行过程中已完成调查、方案、实现、验证和交付前门禁，未扩大到数据库迁移、公共 API 或真实外部 Probe。

# 验证矩阵

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit | required | Excel Sheet/去重、候选池、Prompt、四组选择、配置和不足数量目标测试 |
| 外部 Adapter Mock | required | Token、字段、创建/写入/回读和失败边界 Mock 测试 |
| Build / Runtime | required | Ruff format/check、Mypy、目标 pytest |
| External Provider Probe | not_applicable | 真实 LLM/飞书不进入普通 CI；人工 Probe 受外部网络和租户权限控制 |
| Docs / Governance | required | 文档导航、Change Completion、架构、表 Owner、Secret 扫描 |

## 验证计划

- 目标测试：代表性筛选、Feishu adapter、报告发布和并发契约测试。
- 相关回归：Ruff、Mypy、API/Unit 相关测试和质量脚本。
- 静态检查或构建：Ruff format/check；Mypy 363 个源文件。
- 专项真实边界：PostgreSQL/Docker 未启动，集成依赖项不在本机执行；真实飞书不进入普通 CI。
- 就绪检查：使用 `python scripts/quality/check_change_completion.py --root . --require-active-ready`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 外部飞书字段或权限变化导致写入失败 | 写入前动态预检，失败时不开始批量写入；写入后回读 |
| 兼容性 | 保持已有 Excel、平台 ID、报告和 Dry Run 行为 | 相关单元/API 测试与文档同步 |
| 数据 / Migration | 不适用 | 不修改 PostgreSQL Schema，不新增 Migration |
| 部署 / 运行 | 不需额外部署步骤 | 代码路径和配置边界保持现有方式，真实写入显式开启 |
| 回滚 / 恢复 | 代码可按提交回滚，外部旧表不被修改 | 新表写入和本地审计产物提供人工核对边界 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 imports、analysis、reporting README 和报告 Appendix 导航，确保真实仓库文件链接可点击。
- **依赖 / Runtime**：不新增、不升级第三方依赖；继续使用锁定的 Python/Node 工具链。
- **配置 / Secret**：增加/明确飞书和报告非 Secret 配置读取边界，Secret 仍通过外部文件读取。
- **部署 / Release**：不需要数据库迁移、停机或额外 Release 步骤；真实飞书写入仍由人工显式触发。
- **兼容 / 消费方通知**：现有离线入口、报告统计和稳定平台 ID 保持兼容。

# 完成审计

- [x] upstream_re_read：已重新核对用户确认的筛选规则、Prompt、Excel 表头、飞书字段和现有 LLM/Secret 边界。
- [x] change_coverage：R1—R13 均有实现、测试或明确不适用证据，未把本 Change 作为需求来源。
- [x] reverse_audit：已核对入口参数、Dry Run/写入开关、新表创建、字段预检、回读和失败边界。
- [x] unresolved_cleared：代码级关键字段、Secret、幂等、导航和质量门禁问题已清零；真实外部 Probe 的环境限制已明确记录。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | Windows 本地 `.venv` | Ruff format/check、Mypy | 751 files formatted；363 个源文件无错误；Ruff 通过 | 静态质量和类型边界 |
| V2 | Windows 本地 `.venv` | 相关 pytest | 56 passed | 代表性筛选、飞书、报告和配置回归 |
| V3 | 仓库质量脚本 | check_docs、check_docs_facts、scan_secrets、architecture、table ownership | 全部通过 | 文档、事实源、安全和 Owner 门禁 |
| V4 | 仓库治理脚本 | check_change_completion --require-active-ready | Ready Check 通过 | Active Change 追溯和完成审计 |

## 未验证内容与剩余风险

本机未启动 PostgreSQL/Docker，因此真实数据库集成未执行；Windows 不适用的 POSIX 宿主测试由 Linux CI 负责。真实飞书和 LLM 账户 Probe 不作为普通 CI 证据。

## 交付状态

- 提交：当前分支提交并推送到 PR #530。
- 拉取请求：PR #530，Requirement Source 指向本 Change 文件。
- CI：等待当前最新提交的 CI 重新完成。
- 合并：未合并，等待维护者审核。
- Change 归档：未归档，保持 `ready_for_review`。
- 发布 / 部署：不适用；本变更未执行生产发布或真实业务写入。

## 备注

本 Change 的秒级 ID 和一级标题按当前主线治理资产 Contract 迁移，业务需求追溯和实现范围保持不变。
