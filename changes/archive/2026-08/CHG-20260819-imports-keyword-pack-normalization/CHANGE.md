---
schema: rvc-change/v1
id: CHG-20260819-imports-keyword-pack-normalization
title: imports_test 本地词包与关键词规范化匹配
level: L2
status: done
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

# 结果

本 Change 已完成并合入 `main`：

1. `imports_test` 的清洗关键词从 `test.py` 硬编码元组迁移到独立 UTF-8 文本词包 `keyword_pack.txt`。
2. 词包保存品牌词“爱玛”和用户提供的 102 条车型原始清单；标题或正文命中任一有效词即保留内容。
3. 离线相关性匹配使用 Unicode NFKC、`casefold()`、删除所有空白、忽略 `-/_/·`，消除大小写、全角/半角、空格和指定连接符造成的机械书写差异。
4. 规范化等价词按首次出现顺序合并为一个有效匹配身份，`matched_keywords` 仍保存词包标准展示名。
5. 本地词包没有变成 PostgreSQL 正式事实源，也没有改变 `keywords.normalized_text` 的数据库写入 Contract；Stage 8 前端/API 关键词管理的产品门禁已写入 `backend/src/aima_ugc/modules/system/README.md`。

# 词包事实

用户提供的 102 条车型原始行中有 6 个完全重复名称：

```text
FX3Pro
M豆Air
露娜2024Air
马赫U3-Z
仰望A5
黑翼S360
```

此外 `黑翼S3 60` 与 `黑翼S360` 在忽略空白后属于同一匹配身份。因此：

```text
源非注释词条 = 103  （爱玛 + 102 条车型原始行）
有效匹配身份 = 96   （爱玛 + 95 个车型匹配身份）
```

`keyword_pack.txt` 保留全部原始车型行用于人工核对，Loader 在运行时按规范化身份去重，首次出现的标准词作为展示值。

# 范围与兼容性

- Canonical、五平台 Mapper、Analysis Contract、Excel Contract 不变。
- 过滤仍只检查 Canonical `title` 与 `text`，没有扩展到作者、平台等其他字段。
- `filter_canonical_content_jsonl(keywords=...)` 调用接口保持兼容，只改变已批准的匹配语义。
- `matched_keywords` 继续使用 `UnifiedContentRecordV1` 现有字段。
- 没有新增依赖、HTTP API、前端页面、数据库表或 Migration。
- 没有把 102 个清洗车型自动变成 102 个 TikHub 搜索请求。
- 没有建立车型实体、正式别名表、模糊/拼音/错别字匹配。
- 没有启动 Stage 8。

# 未来 Stage 8 产品门禁

正式开发关键词管理 API/前端页面前，业务 Owner 必须明确：

1. 采集发现词包与结果相关性清洗词包是否同一角色，还是同一词包可以按用途分别绑定；
2. 真正业务别名/俗称是否需要“标准词 → 多别名”正式关系，以及它与 Keyword Pack、Run Snapshot、前端编辑体验的关系；
3. PostgreSQL `keywords.normalized_text` 的正式写入规范化算法，以及历史冲突的兼容/Migration 策略。

本次 `imports_test` 的 NFKC/casefold/空白/连接符规则只定义本地离线相关性清洗，不等同于数据库唯一身份 Contract。

# Red → Green 证据

## Red

PR #84 初始 Red head：`7cefa3692656e3f2cb0fe8a67e83c313fd6bf76c`。

Stage 5A Provider Raw run `32229439140`：

```text
84 passed, 2 failed
```

失败来自目标行为尚未实现：

- `F2Lite-碟刹` 无法命中大小写、空格、全角、连接符变体；
- `黑翼S3 60` / `黑翼S360` 尚未按规范化身份合并并保留首次标准名。

同一 Red run 的 Secret/Docs gate 成功。

## Green

中间实现 head `39f7f10819dd435dccc8ca141c4824d55f5e27d3`：P1 目标测试 `86 passed`，P1 Ruff/mypy/Contract/Architecture/Secret/Docs/Provider 测试均成功；最终全仓质量命令仅发现新测试 import 排序 I001。

整理 import 后 head `d0af36ef863b4e3d98dfe2d8dcc55894319d584c` 的 11/11 标准 workflows 成功。主 CI Stage 1：

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

最终 `ready_for_review` 候选 head：

```text
6e3f21401b4eaceb5f7a00e764e9469bf63d4769
```

该最终 head 再次取得 **11/11 标准 GitHub Actions workflows success**，包括 CI、Stage 1–7 Audit、Stage 5A–5D、Stage 6、Keyword Packs、Provider Config、Plan Occurrence 与 Scheduler。

# Git 集成证据

- 实现 PR：#84 `增加 imports_test 本地词包与关键词规范化匹配`
- 最终实现 head：`6e3f21401b4eaceb5f7a00e764e9469bf63d4769`
- PR #84 已从 Draft 转 Ready 后使用普通 merge 正常合并。
- 合并后的 `main` 集成提交：`24572957b3f5da651b9fe53631edb93f22c80e56`
- 该 merge commit 的第二父提交为最终实现 head，证明通过门禁的候选内容进入主分支。

# 回滚

普通代码回滚即可。`keyword_pack.txt` 没有进入数据库，不需要数据迁移；若回滚过滤规范化逻辑，应同时回滚本地词包入口和 README，避免文档宣称不存在的匹配能力。
