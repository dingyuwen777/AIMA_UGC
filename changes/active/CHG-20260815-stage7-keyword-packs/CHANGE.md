---
schema: rvc-change/v1
id: CHG-20260815-stage7-keyword-packs
title: 建立 Stage 7 关键词与词包父事实
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage7-keyword-packs
created: 2026-08-15
updated: 2026-08-15
depends_on: []
affected_areas: [system, collection, database, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/system/, backend/src/aima_ugc/adapters/persistence/postgres/keywords.py, backend/src/aima_ugc/database_schema.py, migrations/, tests/unit/system/, tests/integration/database/test_keyword_repository.py, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/README.md, .github/workflows/stage7-keyword-packs.yml]
contracts: []
data_changes: [keyword_packs, keywords, keyword_pack_items]
---

# 目标

建立 Stage 7 当前剩余父事实中的“关键词/词包”最小纵切，使关键词以单词为数据库事实、词包通过关系表组织关键词，并为后续 Plan/Run Snapshot 提供稳定 PostgreSQL 父数据。

# 成功标准

- [ ] `keyword_packs`、`keywords`、`keyword_pack_items` 由 System 模块拥有并进入应用 Schema 注册。
- [ ] `keywords.normalized_text` 由数据库唯一约束保证同一显式规范化值只保存一次；本 Change 不擅自定义 NFKC/casefold/空白等规范化算法。
- [ ] `keyword_pack_items` 使用 `(pack_id, keyword_id, platform)` 复合主键，保留平台、优先级、启用状态和备注；`platform='all'` 可作为当前父事实保存。
- [ ] PostgreSQL Repository 可创建/读取词包和关键词、关联词条并按词包读取关联项，不由文件驱动运行时采集。
- [ ] 新 Alembic Revision 仅追加上述三张表；`20260815_0010 → head`、`base → head` 均通过 `alembic check`。
- [ ] Unit、PostgreSQL Integration、架构/表 Owner/Secret/文档质量门禁有独立 GitHub Actions 新鲜证据。
- [ ] 受影响长期文档与机器事实同步；Stage 7 仍保持进行中，不把本单元完成写成整个 Stage 7 完成。

# 范围

- System 领域的 `KeywordPack`、`Keyword`、`KeywordPackItem` 稳定对象。
- 三张关键词相关 PostgreSQL 表及 System 写 Owner。
- PostgreSQL Keyword Catalog Repository。
- 第 `20260815_0011` Alembic Revision。
- 目标 Unit/Integration 测试和独立 Stage 7 Keyword Packs CI。
- 只同步本单元实际影响的 System README、Blueprint 03 和 Blueprint README。

# 非目标

- 不创建 `collection_plans`、`collection_plan_platforms`、`collection_plan_keyword_packs`、Occurrence 或 Run Snapshot。
- 不实现 Plan 保存时“所有目标平台至少一个可用关键词”的业务校验；该规则需要 Plan 父事实后才能闭环。
- 不冻结关键词字符串的 NFKC、casefold、空白折叠或同义词算法；写入 API/导入边界尚未进入本单元。
- 不实现 HTTP API、OpenAPI、前端页面、文件批量导入、Scheduler、预算或 Provider 调用。
- 不调用 TikHub；Provider 网络响应不能验证本 Change 的 PostgreSQL 关键词父事实。

# 必须保持不变

- PostgreSQL 继续是业务事实源；文件只允许后续作为导入、导出或 Seed，不成为 Worker 的关键词事实源。
- 已发布 Migration `20260813_0001` 至 `20260815_0010` 不改写。
- `collection_runs`、`collection_scopes`、Provider Request/Attempt、Canonical 与 XHS 纵切不修改。
- Secret 不进入关键词文本、备注、代码、日志、测试 Fixture 或 Change。
- Stage 7 Scheduler 继续受 `misfire_policy`、`max_catch_up_runs` 与停机补跑费用/容量决策门禁阻塞。

# 已确认关键决策

1. Blueprint 02 已冻结关键词以单词为最小数据库事实，同一 `normalized_text` 只保存一次，词包和关键词使用关系表。
2. Blueprint 02 同时要求词条具备平台、启用、优先级和备注；Blueprint 03 的 `keyword_pack_items` 字段摘要漏写备注。本 Change 将备注落实为关系属性 `keyword_pack_items.note`，并同步修正 Blueprint 03，不新造第二套语义。
3. `normalized_text` 是显式稳定身份字段；当前只验证非空和唯一，不在没有 API/导入契约的情况下猜测规范化算法。
4. 本单元只建立关键词父事实。Plan 关联、Run 展开/冻结和 Worker 消费 Snapshot 留给后续 Stage 7 父事实单元。

# 方案比较

## 方案 A：三张关系表 + 显式 `normalized_text`（采用）

按已批准 Blueprint 建立 `keyword_packs`、`keywords`、`keyword_pack_items`，由数据库唯一/外键/复合主键保护身份和关系；规范化值由未来正式写入边界产生。本方案增量最小，不提前冻结尚未批准的文本算法。

## 方案 B：词包保存 JSON/逗号字符串或运行时文件（拒绝）

实现快，但无法用关系约束保证关键词身份、平台关联和后续 Plan/Run 引用，会直接违反当前 Blueprint 的 PostgreSQL 事实源与关联表要求。

## 方案 C：本 Change 同时定义统一文本规范化算法（暂不采用）

可以更早自动生成 `normalized_text`，但 NFKC、大小写、全半角、空白和中文语义会改变关键词身份与去重结果；当前 Blueprint 未批准这些业务语义，且写入 API/导入边界不在本单元，因此现在静默决定会扩大范围。

# 实施任务

1. Red：先加入目标 Unit/Integration 测试和本单元 CI，确认当前代码因关键词模型/Repository/表缺失而失败。
2. Green：最小增加 System 模型、表、Repository、Schema 注册和 `20260815_0011` Migration，使目标测试通过。
3. Refactor：只在测试通过后消除本 Change 新代码中的重复，不整理无关 System/Collection 文件。
4. 文档：同步 System README、Blueprint 03 字段事实和 Blueprint README Stage 7 进度摘要。
5. Review：先逐项复核需求范围，再检查正确性、约束、Migration、兼容、安全和无关改动。
6. 集成：PR CI 成功后合并；合并后重新验证 main，再把 Change 设为 done 并归档。

# 验证计划与本轮证据

Red 计划：

```text
GitHub Actions / Stage 7 Keyword Packs
→ Unit 导入尚不存在的关键词模型
→ PostgreSQL Integration 导入尚不存在的 Keyword Repository
→ 读取真实失败日志确认失败原因
```

Green/Review 计划：

```text
uv lock --check
uv sync --locked
uv run pytest tests/unit/system/test_keyword_models.py -q
uv run pytest tests/integration/database/test_keyword_repository.py -q
uv run alembic upgrade head
uv run alembic check
uv run alembic downgrade 20260815_0010
uv run alembic upgrade head
uv run alembic check
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run python scripts/contracts/generate.py --check
uv run python scripts/contracts/check_compatibility.py
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

当前宿主没有可访问的用户本地 Git 工作区或可用 `gh`，所以本 Change 的新鲜执行证据由 GitHub Actions 提供；用户本地 modified/staged/untracked/未推送提交仍不可见，不把远端状态冒充本地 `git status`。

# 文档影响

- `backend/src/aima_ugc/modules/system/README.md`：增加关键词目录职责、三张表与独立验证入口。
- `docs/blueprint/03-数据库与文件存储.md`：把 Blueprint 02 已批准但字段摘要漏记的 `note` 补到 `keyword_pack_items`。
- `docs/blueprint/README.md`：只把本单元真实进入 main 后的关键词/词包机器事实从“剩余父事实”移出；不得宣称 Stage 7 完成。

# 兼容、Migration、部署与回滚

- 兼容：纯新增表和内部 Repository；不改现有公共 HTTP/Pydantic Contract、表、列或运行行为。
- Migration：新增 `20260815_0011`，直接父 Revision 为 `20260815_0010`；无现有数据迁移。
- 部署：部署使用该 Repository 的后续代码前必须先升级到 `0011`；当前已有入口不调用它，因此本单元不改变生产请求路径。
- 回滚：尚未写入业务数据时可 downgrade 到 `0010`；一旦三张新表已有业务数据，downgrade 会删除这些表，执行前必须先备份/导出，不把结构回滚等同于无损数据回滚。

# 安全、性能与运维风险

- 本单元不持有 Secret，不接受 Provider Token/API Key；Secret Scan 继续作为门禁。
- 关键词和备注是业务配置文本，后续公开 API 仍需单独建立权限、审计和输入长度边界；本 Change 不提前伪造认证语义。
- 唯一索引 `normalized_text` 与三列复合主键足以支撑当前身份/关联约束；没有测量证据前不添加额外索引。

# Git

- 基线 main：`22aea46cff29e9939c51832b9b71a21f817d81c7`
- 分支：`feature/stage7-keyword-packs`
- 本地工作区：当前宿主不可见
- Commit：Red/Green 待本 Change 实际产生后记录
- PR：待创建
- CI：待执行
- 合并：未合并
- Change：`in_progress`，不得在集成前归档
