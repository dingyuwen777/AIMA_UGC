---
schema: coding-change/v1
id: CHG-20261002-025000-five-platform-accounts
title: 五平台稳定账号采集与当前主线集成
level: L3
status: in_progress
owner: codex
branch: fix/pr662-account-integration
created: 2026-10-02
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas:
  - "provider"
  - "export"
  - "tests"
  - "docs"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/tikhub"
  - "backend/src/aima_ugc/adapters/providers/tikhub_test"
  - "backend/src/aima_ugc/platform/export"
  - "tests/unit/collection"
  - "tests/unit/platform"
  - "docs/appendix"
  - "changes/active/CHG-20261002-025000-five-platform-accounts"
contracts: []
data_changes: []
---

# 变更摘要

把原 PR #662 的四平台指定账号入口接入当前生产账号与内容处理链，使五平台按稳定身份抓取作品、一级评论及二级回复。修复主线集成、完整性及失败隔离缺口，保留共享 Mapper、Runtime 和 Excel 支撑。

# 背景、现状与问题

## 背景

Owner 要求交付原 PR #662；#591/#592 已另行取消，不进入本 Change。

## 当前现状

PR #662 原 Head 为 d473058d2487e41d80a1baf4ea5d994c3fcd42a3，main 为 da99a65fa94e94b298bb1750cb36e54cf60c8384。原 PR 提供四个入口，却把账号逻辑放进通用 runner，并重复 main 已存在的小红书账号实现。

## 问题、根因或约束

合入 main 后 Excel 的两个独立函数产生同位置冲突；小红书 subclass 的 comment_mode 被旧 runner 初始化覆盖。原 PR 还有跨 family 自动 fallback、日期提前停页及技术上限误报完整，需要按现有模块 Owner 收敛。

## 不修改的后果

直接合并可能破坏既有小红书全量语义，遗漏作品、评论或回复，并把部分结果误报成功。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | main 已有生产 account_runtime 与独立小红书账号 subclass | backend/src/aima_ugc/adapters/providers/tikhub/account_runtime.py；tikhub_test/operations/xiaohongshu_accounts.py | 复用现有 Owner |
| E2 | 原 runner 初始化覆盖 comment_mode，抖音 HTTP 400 自动切 Dou+ | tikhub_test/operations/runner.py | 修复集成和隐藏 fallback |
| E3 | main 报告工作簿与 PR 评论标注导出冲突 | git diff --cc -- backend/src/aima_ugc/platform/export/excel.py | 保留两项独立能力 |

## 推断与待确认

本轮有界 Probe 共实际发送 23 次请求，取得五平台身份/作品及部分评论响应形状。该证据不证明五平台真实全量评论/回复完成；具体覆盖与 HTTP 400、请求上限、首次记录器校验失败的限制见 V3。

# 目标、成功标准与非目标

## 目标

五平台账号入口稳定、完整性可观察，并可在当前 main 上安全交付。

## 成功标准

- [ ] AC1–AC7 的实现与回归已验证；AC8 的同 Reviewer 修复复核及正式 CI 门禁待闭合。

## 范围

账号生产适配、人工入口、共享内容评论链、Mapper 与共享 Excel 的必要支持、相关测试和文档。

## 非目标

新增正式账号 Collection Source、数据库 Schema、前端、调度、生产预算、依赖升级、Release 或部署。

## 必须保持不变

既有关键词行为、Canonical 与 HTTP Contract、数据库写 Owner、生成 Client、主检出与正在运行的服务。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 账号 Discovery 归 account_runtime，内容评论归 shared runtime | E1 | 删除重复账号实现 |
| 接口与契约 | 保持既有关键词、小红书入口；四平台入口纯文件 | README AC4 | 不新增公共 HTTP Contract |
| 数据与迁移 | 不适用，纯文件采集，不写生产库 | README AC5 | 无 Migration |
| 错误与失败语义 | 保存成功数据，partial 明确且局部隔离 | README AC3/AC5 | 不隐藏重试或 fallback |
| 兼容性 | 保持现有文件/导入语义与合法关键词行为 | README AC4/AC6 | 共享 Exporter |
| 部署与回滚 | 受保护 PR 合并；可 revert 实现，历史文件保留 | README AC8 | 不执行 Release/Deploy |

# 修改方案与决策依据

## 最小充分方案

1. 建立正式 AC 与当前 Change，合入最新 main 并同时保留两项 Excel 函数；验证冲突标记与解析。
2. 将四平台账号 Discovery 调用接入 account_runtime，独立账号执行器复用通用内容处理；删除重复小红书实现；以 FakeTransport 验证真实入口。
3. 修复日期、身份、分页、失败隔离和文件交付，增加针对失败边界的回归；以受限本机 Probe 核验当前真实形状。
4. 同步文档，执行 changed-scope preflight、Completion Audit、独立 Assembly Review 与同 Reviewer Repair Verify，再取得 current-head/current-base CI 并交付原 PR。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2 | 现有账号 Owner 可承接新入口，避免重复实现和 subclass 状态互相覆盖 |
| D2 | E3 | 两个函数服务不同合法消费者，应保留而非选择一方 |

## 备选方案与取舍

保留原 4500 行 runner 会继续混合两套小红书实现；另建独立采集器会复制 Mapper/分页/导出。本方案只拆出账号执行职责，复用当前内容链与生产 Owner。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 账号采集 AC1 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC1 | satisfied | V1/V2/V4：稳定身份、URL 冲突、作者匹配和 lean upMid 的公开入口反例 |
| R2 | 账号采集 AC2 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC2 | satisfied | V1/V2/V4：北京时间日期、缺失时间、映射失败、重复页/停滞与作品硬上限 |
| R3 | 账号采集 AC3 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC3 | satisfied | V1/V2/V4：已知正数软目标之后继续一级/回复分页；双源共享上限 |
| R4 | 账号采集 AC4 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC4 | satisfied | V1/V2/V4：五平台公开入口使用生产链；关键词、小红书、Mapper/runtime 回归 |
| R5 | 账号采集 AC5 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC5 | satisfied | V1/V2/V4：单作品/根评论 HTTP 或 TransportFailure 隔离、成功行保留与摘要 |
| R6 | 账号采集 AC6 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC6 | satisfied | V1/V2/V4：原子重开验证、长 ID/公式防护及生产 reader/mapper 三条评论身份保持 |
| R7 | 账号采集 AC7 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC7 | satisfied | V3：23 次本机有界真实发送，生产 Transport/Operation；脱敏摘录，无自动跨 family fallback |
| R8 | 账号采集 AC8 | backend/src/aima_ugc/adapters/providers/tikhub_test/README.md#AC8 | not_satisfied | V1/V2 已通过；独立审查、Ready 与 current-head/current-base CI 待闭合。合并后状态由真实 PR/Commit/CI/原生 Archive 持有。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| tikhub/account_runtime.py、operations、mappers | 正式账号请求与生产映射 | 共享 Owner | R1–R4 |
| tikhub_test/operations、四平台账号入口 | 账号装配、完整性、失败隔离 | 保持小红书与关键词 | R1–R5 |
| platform/export、tests | 评论标注与文件验证 | 防身份错误、原子发布 | R6 |
| README、Change | 正式事实与证据 | 可审查交付 | R7–R8 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 身份、日期、分页、失败隔离、Mapper |
| 接口 / 契约 | required | Canonical、Excel 与现有导入器 |
| 集成 / 持久化 / 运行依赖 | required | 文件重开、JSONL、原子发布；无数据库写入 |
| 用户 / 工作流验收 | required | 五平台账号公开入口与失败摘要 |
| 跨组件关键路径 | required | FakeTransport → Operation → Mapper → Canonical → Excel |
| 外部依赖 / 供应方探测 | required | 本机有界生产 Transport/Operation Probe |
| 构建 / 打包 / 运行 | required | changed-scope preflight 对真实影响执行 |
| 文档 / 治理 / 其他 | required | 需求追溯、Completion、Review、CI、main-fresh、Archive |

## 验证计划

- 目标测试：账号纵切、分页完整性、局部 HTTP 失败与导入语义。
- 相关回归：五平台关键词、当前小红书、Mapper/Runtime/Excel。
- 静态检查或构建：python scripts/dev/validate_changed.py --base origin/main --execute。
- 专项真实边界：最多 25 次 Provider 调用，单页发现/评论/回复；不发 LLM、不写数据库。
- 就绪检查：python scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 原账号逻辑可能提前停页或误报完成 | 强制 partial、入口纵切与当前 Provider 验证 |
| 兼容性 | 保持既有关键词/小红书；新四平台纯文件 | 不提升为正式 Collection Source |
| 数据 / Migration | 不适用 | 无数据库 Schema 或业务写入 |
| 部署 / 运行 | 仅 PR 集成 | 不变更现有服务及 .runtime |
| 回滚 / 恢复 | revert 本 PR | 无数据迁移，保留历史采集文件 |

# 文档、依赖、部署与发布影响

- 长期文档：同步 TikHub 调试 README、字段/接口台账及导出实际语义。
- 依赖 / Runtime：不新增或升级依赖。
- 配置 / Secret：四平台人工账号配置，真实凭据仅内存/环境；Secret 不持久化。
- 部署 / Release：不适用，Owner 未授权发布或部署。
- 兼容 / 消费方通知：README 更新入口及 incomplete 状态语义。

# 完成审计

- [x] upstream_re_read：已重读当前 README AC1–AC8 与 Owner 决定；#591/#592 是取消，竞争范围保留。
- [ ] change_coverage：AC1–AC7 已逐项绑定实现/测试/Probe；AC8 独立审查与合并前门禁仍需闭合。
- [x] reverse_audit：五平台公开入口 → 生产 Operation/Mapper → Canonical/共享 Excel 已用 FakeTransport 纵切；评论文件 → 生产 reader/mapper 证明三条独立 ID。无前端/数据库能力变更。
- [ ] unresolved_cleared：not_satisfied 尚未清零。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V0 | d0bf5943 集成原 PR 与 main da99a65f | Git merge 与冲突解析 | 保留 main 报告工作簿及评论标注导出 | 当前集成边界 |
| V1 | 9ff83534；Python 3.14.7 / uv 0.12.3；child PYTHONUTF8=1、PYTHONIOENCODING=utf-8；清除 child SSLKEYLOGFILE | .venv/Scripts/python scripts/dev/validate_changed.py --base origin/main --execute | exit 0；Ruff 38 文件、mypy 435 源文件通过；1899 passed、16 skipped、12 subtests passed | 当前 backend-only 影响范围的单元、Contract、API 回归 |
| V2 | 同一实现 revision / Windows 本机 | .venv/Scripts/python -m pytest -q --tb=short tests/unit/collection/test_account_entrypoint_flows.py tests/unit/fullstack/test_seed_collection_plan_provider.py | exit 0；44 passed，其中账号公开入口 43 个参数化场景 | 五平台软目标/上限/身份/缺失时间/映射及传输局部失败；Excel 生产重导入 |
| V3 | 本轮 Probe 的历史观测，不能当作修复后全量重跑 | 生产公开入口 → 生产 Transport/Operation，api.tikhub.io，实际 23 次发送 | 12 个脱敏记录 + 首轮 11 次发送计数；HTTP 200 与微博评论 HTTP 400 如实记录 | 五平台真实字段的有限摘录；Bilibili V2 upMid；不证明完整真实评论/回复链 |
| V4 | 当前修复代码；Python 3.14.7 / uv 0.12.3 / Windows；无新付费请求 | .venv/Scripts/python scripts/dev/validate_changed.py --base origin/main --execute；.venv/Scripts/python scripts/quality/check_docs.py | 均 exit 0；Ruff 39 文件；mypy 435 源文件；1931 passed、16 skipped、12 subtests passed；文档 gate 通过 | 稳定 ledger F-662-001–008 的直接回归及相邻关键词/小红书/Mapper/Excel；旧快手过滤断言改为验证坏项保留，与公开入口 partial 验收共同约束 |


## 未验证内容与剩余风险

FIRST_ASSEMBLY 在 9ff83534/da99a65f 给出 BLOCK，8 项稳定 Findings 已按同批修复并通过 V4，仍待同 Reviewer REPAIR_VERIFY 和 current-head/current-base CI，PR 保持 Draft。真实 Probe 未完成五平台全量评论/回复，微博评论出现 HTTP 400；有限响应形状由离线生产入口反例补充，不宣称真实全量验收。未执行 Release/Deploy/生产 Migration 或数据库写入。

## 交付状态

- 提交：9ff83534 已正常推送到原 feature/BOLL，未改写原作者历史。
- 拉取请求：https://github.com/dingyuwen777/AIMA_UGC/pull/662，Draft。
- CI：当前本机 preflight 已通过；Draft 的 required full CI 尚待进入 Ready 后取得。
- 合并：未合并。
- Change 归档：未归档。
- 发布 / 部署：不适用，本次只做 PR 集成。

## 备注

#591 已按 Owner 决定直接关闭，#592 以 not_planned 关闭，不视为需求已实现。

## 不随归档目录失效的证据导航

原生归档只移动本文件，附件保留在原 active 目录；以下使用已发布实现 revision 的不可变链接，文件标签保留完整仓库路径。

- [backend/src/aima_ugc/adapters/providers/tikhub_test/README.md](https://github.com/dingyuwen777/AIMA_UGC/blob/9ff83534f0e00cbd1d86c81ded7a674143431e93/backend/src/aima_ugc/adapters/providers/tikhub_test/README.md)
- [tests/unit/collection/test_account_entrypoint_flows.py](https://github.com/dingyuwen777/AIMA_UGC/blob/9ff83534f0e00cbd1d86c81ded7a674143431e93/tests/unit/collection/test_account_entrypoint_flows.py)
- [changes/active/CHG-20261002-025000-five-platform-accounts/evidence/probe_accounts.sanitized.json](https://github.com/dingyuwen777/AIMA_UGC/blob/9ff83534f0e00cbd1d86c81ded7a674143431e93/changes/active/CHG-20261002-025000-five-platform-accounts/evidence/probe_accounts.sanitized.json)
- [docs/appendix/04_TikHub接口选型与真实验证台账.md](https://github.com/dingyuwen777/AIMA_UGC/blob/9ff83534f0e00cbd1d86c81ded7a674143431e93/docs/appendix/04_TikHub接口选型与真实验证台账.md)
