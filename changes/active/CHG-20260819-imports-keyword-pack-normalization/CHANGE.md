---
schema: rvc-change/v1
id: CHG-20260819-imports-keyword-pack-normalization
title: imports_test 本地词包与关键词规范化匹配
level: L2
status: ready_for_review
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
  - backend/src/aima_ugc/modules/system/README.md
  - tests/unit/analysis/test_offline_content_processing.py
  - tests/unit/collection/test_imports_keyword_pack.py
contracts: []
data_changes: none
---

# 目标与结果

1. `imports_test` 不再把清洗关键词硬编码在 `test.py`，改为读取独立 UTF-8 文本词包 `keyword_pack.txt`。
2. 本地词包已加入品牌词“爱玛”和用户提供的 102 条车型原始清单；标题或正文命中任一有效词即保留内容。
3. 离线相关性匹配统一执行 Unicode NFKC、`casefold()`、删除所有空白并忽略 `-/_/·`，消除明确的机械书写差异；`matched_keywords` 仍保存词包中的标准展示名称。
4. 规范化后等价的词条按首次出现顺序只形成一个有效匹配身份，避免同一内容重复写等价命中词。
5. 本地词包明确只是 `imports_test` 的配置来源，不替代 Stage 7 PostgreSQL `KeywordPack/Keyword/KeywordPackItem` 父事实；未来 Stage 8 关键词管理的产品门禁已写入 `modules/system/README.md`。

# 成功标准

- [x] `test.py` 只配置 `KEYWORD_PACK_FILE`，不再维护 `KEYWORDS=(...)`。
- [x] `keyword_pack.txt` 包含“爱玛”和用户给出的 102 条车型原始清单。
- [x] 102 条车型中的完全重复项、以及规范化后等价项不会导致重复 `matched_keywords`。
- [x] `F2Lite-碟刹` 可命中大小写、空格、`-/_/·` 与全角英数字变体。
- [x] 仍只匹配 Canonical `title + text`，未扩展到作者或其他字段。
- [x] `matched_keywords` 返回词包标准展示名，不返回帖子中的变体文本。
- [x] 空词包或只有注释/空行的词包明确失败。
- [x] README 已说明词包文件编辑方式、规范化规则、重复/等价词处理、输出与未来前端边界。
- [x] System README 已固化 Stage 8 关键词管理的未决产品门禁，后续不得静默替业务 Owner 决定词包角色、别名模型或数据库规范化算法。
- [x] 目标回归、全仓单元/Contract/API 测试、Ruff、mypy、Contract drift、Architecture、Ownership、Secret、Docs、Wheel 与前端门禁已通过；实现 head 的 11/11 标准 workflows 全部成功。

# 词包当前事实

用户提供 102 条车型原始行，其中 6 个名称存在完全重复：

```text
FX3Pro
M豆Air
露娜2024Air
马赫U3-Z
仰望A5
黑翼S360
```

另外：

```text
黑翼S3 60
黑翼S360
```

在本次“忽略空白”的相关性匹配规范化后属于同一匹配身份。为保留用户输入的可核对性，`keyword_pack.txt` 仍保存 102 条原始车型行；加载器按规范化身份去重并使用首次出现的标准词作为展示名。

因此当前：

```text
源非注释词条 = 103  （爱玛 + 102 条车型原始行）
有效匹配身份 = 96   （爱玛 + 95 个车型匹配身份）
```

# 范围

- `imports_test` 本地词包文件与加载器；
- 离线关键词过滤的受控匹配规范化；
- 对应测试与人工使用说明；
- 未来 Stage 8 关键词管理的长期决策门禁。

# 非目标

- 不新增或修改 PostgreSQL 表、Migration、HTTP API、前端页面。
- 不修改 `keywords.normalized_text` 的正式数据库写入 Contract；当前数据库 API 尚未建立，正式写入语义留到 Stage 8 决策。
- 不把 102 个车型自动变成 102 个 TikHub 搜索请求。
- 不建立车型实体表、车型主数据、正式别名关联表或模糊/拼音/错别字匹配。
- 不启动 Stage 8。

# 必须保持不变

- Canonical、五平台 Mapper、Analysis Contract 和 Excel Contract 不变。
- 过滤仍是“任一关键词命中则保留”，只检查 `title/text`。
- `matched_keywords` 继续使用现有 `UnifiedContentRecordV1` 字段。
- 不新增第三方依赖。

# 已确认关键决策

- 用户确认把本轮提供的 102 条车型加入清洗词包。
- 机械变体由程序规范化处理，不要求用户手工列出大小写、全角/半角、空格和连接符变体。
- 当前采用独立本地词包文件供 `imports_test` 使用；未来正式网页配置继续复用 Stage 7 Keyword Pack 数据边界。
- 未来正式网页/API 开发时，必须再决定“采集发现词包”和“结果相关性清洗词包”是否分角色，以及真正业务别名如何建模；本轮不提前选择。
- 本轮本地清洗规范化不等同于 PostgreSQL `keywords.normalized_text` 的正式写入算法。

# Red → Green 证据

## Red

Draft PR #84 初始 Red head：`7cefa3692656e3f2cb0fe8a67e83c313fd6bf76c`。

Stage 5A Provider Raw run `32229439140`：

```text
84 passed, 2 failed
```

两处失败均来自目标能力尚未实现：

1. `F2Lite-碟刹` 不能命中大小写、空格、全角和连接符变体，期望 2 行、实际 0 行；
2. `黑翼S3 60` / `黑翼S360` 未按规范化身份合并，实际返回后者而不是首次标准名。

同一 Red run 的 Secret/Docs gate 成功，排除仓库环境和文档扫描故障。

## Green 与质量收敛

实现后 Stage 5A head `39f7f10819dd435dccc8ca141c4824d55f5e27d3`：

- P1 Excel/Analysis/Export 相关测试：`86 passed`；
- P1 Ruff / mypy / Contract drift / Architecture / Secret / Docs / Provider tests 均成功；
- 最后的全仓质量命令仅发现新测试 import 排序 I001，未发现业务行为失败。

只整理 import 后的实现 head：

```text
d0af36ef863b4e3d98dfe2d8dcc55894319d584c
```

该 head 的标准 GitHub Actions：**11/11 workflows success**。

主 CI Stage 1 新鲜证据：

```text
ruff format: 313 files already formatted
ruff check: All checks passed
mypy: Success: no issues found in 169 source files
unit: 352 passed
contracts: 34 passed
api: 3 passed
Wheel: build + isolated install + import success
frontend: lint/typecheck/test/build success
Architecture / table ownership / Secret / Docs: success
```

Stage 5A 同一 head 再次成功，证明 P1 目标链与全仓质量门禁都通过。

# 两阶段复核

## 需求符合性

- 102 条车型原始输入已逐行进入词包；品牌词仍存在。
- 本地脚本入口只保留词包路径配置，不再要求修改 Python 元组。
- 机械变体匹配与标准名回写由测试锁定。
- 未扩大匹配字段，未把本地清洗词包误当 Provider 搜索计划。
- 未实现用户明确要求后续再决策的前端/API 语义。

## 代码质量与兼容性

- 规范化函数位于离线过滤生产实现，词包 Loader 复用该函数，没有复制第二套匹配规则。
- title 与 text 分别规范化后匹配，避免因为拼接后删除空白导致标题尾与正文头跨字段形成假命中。
- 现有 `filter_canonical_content_jsonl(keywords=...)` 调用接口保持兼容，只改变匹配语义为已批准的机械变体等价。
- 无 Contract/Schema/Migration/依赖变化；Canonical、Analysis、Excel 数据结构不变。
- 回滚为代码回滚即可；词包 txt 不进入数据库，不需要数据迁移。

# 文档与未来门禁

- `imports_test/README.md` 是本地脚本使用入口，说明如何维护词包和机械变体规则。
- `modules/system/README.md` 是正式 Keyword Pack 父事实的模块入口，已记录 Stage 8 前必须做的三项决策：Discovery/Relevance 角色、真正别名模型、正式数据库 `normalized_text` 写入算法与历史冲突处理。
- 未修改 Blueprint 04，因为当前尚未形成新的 HTTP/前端 Contract；把未决产品门禁放在 Keyword Pack 所属 System 模块说明更直接，Stage 8 实现时仍必须按 Blueprint 导航重新形成 Change/Contract。

# Git / PR 状态

- 分支：`feature/imports-keyword-pack-normalization`
- Draft PR：#84
- 当前实现验证 head：`d0af36ef863b4e3d98dfe2d8dcc55894319d584c`
- 本次 `ready_for_review` 元数据提交将成为新的最终候选 head；必须以它自己的标准 workflows 全绿作为合并门禁。
