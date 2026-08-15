---
schema: rvc-change/v1
id: CHG-20260815-stage7-keyword-packs
title: 建立 Stage 7 关键词与词包父事实
level: L3
status: done
owner: dingyuwen777
branch: feature/stage7-keyword-packs
created: 2026-08-15
updated: 2026-08-15
depends_on: []
affected_areas: [system, collection, database, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/adapters/persistence/postgres/keywords.py, backend/src/aima_ugc/database_schema.py, migrations/versions/20260815_0011_stage7_keyword_packs.py, tests/unit/system/test_keyword_models.py, tests/integration/database/test_keyword_repository.py, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/README.md, .github/workflows/stage7-keyword-packs.yml]
contracts: []
data_changes: [keyword_packs, keywords, keyword_pack_items]
---

# 目标

建立 Stage 7 的“关键词/词包”稳定父事实，使关键词以单词为 PostgreSQL 业务事实、词包通过关系表组织关键词，并为后续 Plan、Occurrence、Run Snapshot 和 Scheduler 提供可约束、可审计的父数据。

# 成功标准

- [x] `keyword_packs`、`keywords`、`keyword_pack_items` 由 System 模块拥有并进入应用 Schema 注册。
- [x] `keywords.normalized_text` 由数据库唯一约束保证同一显式规范化值只保存一次；本 Change 未擅自定义 NFKC/casefold/空白等尚未批准的规范化算法。
- [x] `keyword_pack_items` 使用 `(pack_id, keyword_id, platform)` 复合主键，保留平台、优先级、启用状态和备注；`platform='all'` 可作为父事实保存。
- [x] PostgreSQL Repository 可创建/读取词包和关键词、关联词条并按词包读取关联项，不由文件驱动运行时采集。
- [x] Alembic `20260815_0011` 只新增上述三张表；`20260815_0010 → head` 与 `base → head` 均有 PostgreSQL 18.4 新鲜验证。
- [x] Unit、PostgreSQL Integration、Ruff、mypy、Contract 漂移/兼容、Architecture、Table Ownership、Secret Scan、Docs Check 均有 GitHub Actions 新鲜证据。
- [x] System README、Blueprint 03 和 Blueprint README 已与合入 main 的机器事实同步；Stage 7 仍明确保持进行中，没有把本实现单元完成误写为整个 Stage 7 完成。
- [x] 实现 PR #48、文档 PR #49 均合并到 main；两次合并后的 main 相关 CI 均重新通过后才归档本 Change。

# 范围

- System `KeywordPack`、`Keyword`、`KeywordPackItem` 稳定对象。
- `keyword_packs`、`keywords`、`keyword_pack_items` 三张 PostgreSQL 表及 System 唯一写 Owner。
- `PostgresKeywordCatalogRepository`。
- Alembic `20260815_0011`，父 Revision 为 `20260815_0010`。
- 目标 Unit/Integration 测试与独立 Stage 7 Keyword Packs CI。
- System README、Blueprint 03、Blueprint README 的当前事实同步。

# 非目标

- 不创建 `collection_plans`、`collection_plan_platforms`、`collection_plan_keyword_packs`、Occurrence 或 Run Snapshot。
- 不实现 Plan 保存时“所有目标平台至少一个可用关键词”的业务校验；该规则需要 Plan 父事实后才能闭环。
- 不冻结 NFKC、casefold、空白折叠、同义词等关键词规范化算法；正式写入 API/导入边界进入范围后再按批准 Contract 决定。
- 不实现 HTTP API、OpenAPI、前端页面、文件批量导入、Scheduler、预算或 Provider 调用。
- 不调用 TikHub；Provider 网络响应不能证明本 PostgreSQL 父事实实现正确，因此真实付费 Provider Probe 对本 Change 不适用。

# 必须保持不变

- PostgreSQL 继续是业务事实源；文件只允许后续作为导入、导出或 Seed，不成为 Worker 的关键词事实源。
- 已发布 Migration `20260813_0001` 至 `20260815_0010` 未改写；本 Change 只追加 `0011`。
- `collection_runs`、`collection_scopes`、Provider Request/Attempt、Canonical、XHS 纵切与四个平台 Operation 未被本 Change 改动。
- Secret 未进入关键词文本、备注、代码、日志、Fixture、Job Payload、数据库明文或 Change。
- Stage 7 Scheduler 仍受 `misfire_policy`、`max_catch_up_runs` 与停机补跑费用/容量决策门禁约束。

# 已确认关键决策

1. Blueprint 02 已冻结关键词以单词为最小数据库事实，同一 `normalized_text` 只保存一次，词包和关键词使用关系表。
2. Blueprint 02 要求词条具备平台、启用、优先级和备注；Blueprint 03 当时字段摘要漏写备注。本 Change 将备注落实为关系属性 `keyword_pack_items.note`，并在机器事实合入后同步修正 Blueprint 03。
3. `normalized_text` 是显式稳定身份字段；当前只验证非空和唯一，不在没有 API/导入契约的情况下猜测规范化算法。
4. 本单元只建立关键词父事实。Plan 关联、Run 展开/冻结和 Worker 消费 Snapshot 留给后续 Stage 7 实现单元。

# 实施与 TDD

## Red

先提交 Change、失败测试和独立 CI，不含生产实现。

GitHub Actions Run `31869801537`：

- `Stage 7 Keyword Packs Unit`：失败，退出码 2；收集阶段因 `aima_ugc.modules.system.models` 不存在 `Keyword` 而失败。
- `Stage 7 Keyword Packs PostgreSQL`：失败，退出码 2；先确认当时 Alembic head 为 `20260815_0010` 且无 drift，随后因 `aima_ugc.adapters.persistence.postgres.keywords` 不存在而失败。
- 当时 Quality 的 import 顺序问题不作为 Red 证据。

Red commit：`c56207d17d329fb9619d93308b1f812b4b8092c5`。

## Green / Refactor

最小增加 System 模型、三张表、Repository、Schema 注册和 `0011` Migration。过程中只有 Ruff 格式/import 排序问题，均读取日志后按仓库实际规则修正；没有删除测试、降低断言、跳过门禁或增加绕过逻辑。

在 Review 中发现原 Integration 尚未用真实 PostgreSQL 行为证明关联表复合主键与外键，随后补充对应 `IntegrityError` 与表结构断言，再重新跑完整门禁。

最终实现分支 Run `31870301677` 与 Change 状态更新后的 Run `31870378491` 均为 Unit、Quality、PostgreSQL 3/3 success。

# 实现结果

- `KeywordPack`：稳定词包身份、名称、描述、启用和版本。
- `Keyword`：原文、显式 `normalized_text`、启用状态；数据库唯一约束负责稳定去重事实。
- `KeywordPackItem`：`pack_id + keyword_id + platform` 关系身份，以及 `priority/enabled/note` 关系属性。
- `PostgresKeywordCatalogRepository`：调用方拥有事务；支持词包/关键词创建读取、按规范化文本读取、关联创建和按词包列出关联。
- 三张表均 `Table.info['owner']='system'`，进入 `database_schema.py` 注册。
- `20260815_0011` 只追加三张表，downgrade 反向删除三张新表。

# 验证证据

## PR #48：实现

- Head：`623e9bf6db5dde5be773be8384bd0c51e7e3b67b`。
- PR 触发主 CI、Stage 4、Stage 5B/5C/5D、Stage 6、Stage 7 Provider Config、Stage 7 Keyword Packs 共 8 个 workflow；全部 success。
- Squash 合并到 `main`：`8e72cbdb71e9e62c169a7c0c99c9f9f2d4cb44d8`。
- 合并后 main：17/17 Check Run completed；检查结果中无 `failure`、`cancelled`、`timed_out`。

## PR #49：长期文档同步

- 最终 diff 只有 `docs/blueprint/03-数据库与文件存储.md` 与 `docs/blueprint/README.md`。
- PR 触发 CI、Stage 6 XHS、Stage 7 Provider Config、Stage 7 Keyword Packs 共 4 个 workflow；全部 success。
- Squash 合并到 `main`：`af369abf72d305af14bda834a9a19134a65ac17f`。

## 文档合并后 main

在 `main@af369abf72d305af14bda834a9a19134a65ac17f`：

- CI run `31870824217`：Stage 1、Stage 2 Platform、Stage 3A Database、Windows bootstrap 全部 success；Stage 3A 重新验证 Schema/Owner、upgrade/no drift、PostgreSQL Repository 与 base round trip。
- Stage 6 XHS run `31870824226`：Unit、Quality、PostgreSQL 全部 success；PostgreSQL 重新验证多条上一正式 Revision → head 与 base round trip。
- Stage 7 Provider Config run `31870824216`：success。
- Stage 7 Keyword Packs run `31870824233`：Unit、Quality、PostgreSQL 全部 success；PostgreSQL 再次完成 `alembic upgrade head`、`alembic check`、目标 Integration、`20260815_0010 → head` 与 `base → head`。

因此本 Change 的实现、Migration、约束、长期文档和合并后集成状态均已闭环。

# 文档同步

- `backend/src/aima_ugc/modules/system/README.md`：记录关键词目录职责、三张 System Owner 表、规范化身份边界与独立验证入口。
- `docs/blueprint/03-数据库与文件存储.md`：补齐 `keyword_pack_items.note`、当前 System Owner、Alembic 链到 `0011`，并把第二条及后续 Revision 的“上一正式 Revision → head + base round trip”写成当前门禁。
- `docs/blueprint/README.md`：把关键词/词包父事实列为已进入 main 的 Stage 7 实现单元，并从 Stage 7 剩余父事实中移除；Stage 7 仍为进行中。

# 兼容、Migration、部署和回滚

- 公共 HTTP/Pydantic Contract：无变化。
- 依赖与锁文件：无变化。
- 数据库：纯新增三张表；无旧数据迁移。
- 部署：后续任何使用 Keyword Repository 的代码部署前必须升级到 `0011`；本 Change 本身没有把它接入既有 HTTP/Worker/Scheduler 请求路径。
- 结构回滚：可 downgrade 到 `0010`，但会删除三张新表。一旦其中存在业务数据，必须先备份/导出；Migration 可逆不等于业务数据无损回滚。
- 生产：本轮未部署生产环境，也未操作生产数据。

# 未验证与剩余风险

- 当前宿主无法访问用户本地 Git 工作区，因此本地 modified/staged/untracked、未推送提交仍无法确认；整个开发只在新远端任务分支和 PR 中进行，没有把“远端干净”冒充本地 `git status`。
- 关键词自动规范化算法尚未批准，这是刻意保留的后续写入边界决策，不是本父事实单元的缺陷。
- 后续公开关键词写入 API 仍需权限、审计、输入长度和规范化 Contract；本 Change 没有提前伪造这些语义。
- Scheduler 的 `misfire_policy`、`max_catch_up_runs` 与停机补跑费用/容量保护仍未批准，只阻塞正式 Scheduler，不反向影响本 Change 完成。

# Git

- 基线 main：`22aea46cff29e9939c51832b9b71a21f817d81c7`
- 实现分支：`feature/stage7-keyword-packs`
- 文档收尾分支：`docs/stage7-keyword-packs-close`
- Red commit：`c56207d17d329fb9619d93308b1f812b4b8092c5`
- 实现 PR：#48，squash merge `8e72cbdb71e9e62c169a7c0c99c9f9f2d4cb44d8`
- 文档 PR：#49，squash merge `af369abf72d305af14bda834a9a19134a65ac17f`
- Change：done；在实现、文档与两次 main CI 均确认后归档到 `changes/archive/2026-08/`。
