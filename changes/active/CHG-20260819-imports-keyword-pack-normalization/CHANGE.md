---
schema: rvc-change/v1
id: CHG-20260819-imports-keyword-pack-normalization
title: imports_test 本地词包与关键词规范化匹配
level: L2
status: in_progress
owner: ChatGPT
branch: feature/imports-keyword-pack-normalization
created: 2026-08-19
updated: 2026-08-19
depends_on: []
affected_areas:
  - analysis_offline_filter
  - imports_test
affected_paths:
  - backend/src/aima_ugc/modules/analysis/offline_content.py
  - backend/src/aima_ugc/adapters/providers/imports_test
  - tests/unit/analysis/test_offline_content_processing.py
  - tests/unit/collection
  - docs/blueprint/04-后端任务API与前端.md
contracts: []
data_changes: none
---

# 目标

1. `imports_test` 不再把清洗关键词硬编码在 `test.py`，改为读取独立 UTF-8 词包文件。
2. 把用户提供的 102 条车型名称与品牌词“爱玛”加入本地清洗词包；任意词命中标题或正文时保留内容。
3. 清洗匹配消除确定没有业务意义的机械书写差异：Unicode NFKC、大小写 casefold、所有空白、`-`、`_`、`·`；命中结果仍写词包中的标准展示名称。
4. 规范化后等价的词条只形成一个有效匹配身份，按词包首次出现顺序保留展示名称，避免同一内容重复写等价命中词。
5. 文档明确本地词包只是 `imports_test` 的配置来源，不替代 Stage 7 PostgreSQL `KeywordPack/Keyword/KeywordPackItem` 父事实；正式前端关键词管理进入 Stage 8 时必须再次决策“采集发现词包”和“结果清洗词包”是否分角色，以及真正业务别名如何建模。

# 成功标准

- [ ] `test.py` 只配置 `KEYWORD_PACK_FILE`，不再维护 `KEYWORDS=(...)`。
- [ ] 新词包文件包含“爱玛”和用户给出的 102 条车型原始清单。
- [ ] 102 条车型中的完全重复项、以及规范化后等价项不会导致重复 `matched_keywords`。
- [ ] `F2Lite-碟刹` 可以命中大小写、空格、`-/_/·` 书写变体；全角英数字经 NFKC 后可以命中。
- [ ] 仍只匹配 Canonical `title + text`，不静默扩展到作者或其他字段。
- [ ] `matched_keywords` 返回词包标准展示名，不返回帖子中的变体文本。
- [ ] 空词包、只有注释/空行的词包明确失败。
- [ ] README 说明词包文件怎么编辑、规范化规则、重复/等价词处理和未来前端边界。
- [ ] Blueprint 固化 Stage 8 关键词管理的未决产品门禁，后续开发不得静默替用户决定词包角色/业务别名模型。
- [ ] 目标测试、相关回归、Ruff、mypy、Secret/Docs/Architecture 与最终适用 GitHub Actions workflows 通过。

# 范围

- 本地 `imports_test` 词包文件与加载器；
- 离线关键词过滤的匹配规范化；
- 对应单元测试与使用说明；
- Stage 8 前端关键词管理的未来决策门禁。

# 非目标

- 不新增或修改 PostgreSQL 表、Migration、HTTP API、前端页面。
- 不修改 `keywords.normalized_text` 的正式数据库写入 Contract；当前数据库 API 尚未建立，正式写入语义留到 Stage 8 决策。
- 不把 102 个车型自动变成 102 个 TikHub 搜索请求。
- 不建立车型实体表、车型主数据、别名关联表或模糊/拼音/错别字匹配。
- 不启动 Stage 8。

# 必须保持不变

- Canonical、五平台 Mapper、Analysis Contract 和 Excel Contract 不变。
- 过滤仍是“任一关键词命中则保留”，只检查 title/text。
- `matched_keywords` 继续使用现有 `UnifiedContentRecordV1` 字段。
- 不新增第三方依赖。

# 已确认关键决策

- 用户确认把本轮提供的 102 条车型加入清洗词包。
- 机械变体由程序规范化处理，不要求用户手工列出大小写/空格/连接符的全部变体。
- 当前采用独立本地词包文件供 `imports_test` 使用；未来正式网页配置继续复用 Stage 7 Keyword Pack 数据边界，但词包使用角色与真正业务别名模型保留为 Stage 8 决策门禁。
- 用户原始 102 条车型中存在 6 个完全重复名称；`黑翼S3 60` 与 `黑翼S360` 在忽略空格后规范化等价。本次不把重复输入伪装成不同匹配身份，按首次出现的标准名称作为该规范化身份的展示值。

# 实施步骤

1. Red：补充独立词包加载与规范化匹配测试，观察当前代码因能力不存在/行为不符而失败。
2. Green：增加本地词包加载器和词包文件，接入 `imports_test.test.py`。
3. Green：在离线过滤生产实现中加入受控规范化，不改变 title/text 之外的匹配范围。
4. 更新 README 与 Stage 8 Blueprint 门禁。
5. 两阶段 Review，运行目标回归和仓库质量门禁；最终 PR head workflows 全绿后合并并归档 Change。

# 验证计划

- `uv run pytest tests/unit/analysis/test_offline_content_processing.py tests/unit/collection/test_imports_keyword_pack.py -q`
- `uv run pytest tests/unit/collection/test_p1g_imports_run_all.py tests/unit/collection/test_imports_test_run_directory.py -q`
- `uv run ruff check backend/src tests scripts`
- `uv run ruff format --check backend/src tests scripts`
- `uv run mypy backend/src`
- `uv run python scripts/contracts/generate.py --check`
- `uv run python scripts/quality/check_architecture.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv run python scripts/quality/check_docs.py`
- 最终 PR head 的所有适用 GitHub Actions workflows 必须成功。

# 文档影响

- `imports_test/README.md`：改为词包文件使用说明。
- `docs/blueprint/04-后端任务API与前端.md`：记录未来关键词管理页面的决策门禁。
- `System README` 当前“数据库 normalized_text 算法尚未冻结”的事实保持不变，本次本地清洗规范化不得被描述成数据库 Contract。

# Git / PR 状态

- 分支：`feature/imports-keyword-pack-normalization`
- PR：待 Red 测试提交后创建 Draft PR。
