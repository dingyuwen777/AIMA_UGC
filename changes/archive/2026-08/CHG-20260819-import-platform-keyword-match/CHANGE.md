---
schema: rvc-change/v1
id: CHG-20260819-import-platform-keyword-match
title: Excel 导入平台名称受控包含匹配
level: L2
status: done
owner: ChatGPT
branch: fix/imports-platform-keyword-match
created: 2026-08-19
updated: 2026-08-19
affected_areas:
  - imports
  - imports_test
affected_paths:
  - backend/src/aima_ugc/adapters/providers/imports/excel_profile.py
  - tests/unit/collection/test_imports_excel.py
contracts: []
data_changes: none
---

# 目标

让 `aima-monitoring-excel.v1` 在“媒体名称（中文）”包含已知平台名称时稳定归一化到现有 Canonical `platform`，例如 `抖音 APP → douyin`、`小红书 APP → xiaohongshu`、`快手 APP → kuaishou`、`哔哩哔哩APP → bilibili`，同时保持未知中文媒体 fail-closed。

# 成功标准

- [x] 用户给出的 `抖音 APP`、`小红书 APP`、`快手 APP`、`哔哩哔哩APP`、`新浪微博` 均转换成功。
- [x] 仅对已知平台关键字做受控包含匹配，不使用编辑距离或任意相似度猜测。
- [x] 现有精确别名和合法 ASCII platform slug 行为保持兼容。
- [x] 未命中已知平台且不能形成合法 ASCII slug 的中文媒体仍返回 `platform_unmapped`。
- [x] Canonical Contract、Migration、数据库和五平台生产采集链不变。

# 范围

- Excel Import Profile 的平台名称归一化。
- 对真实 `APP` 后缀输入增加单元回归测试。

# 非目标

- 不修改 `CanonicalContentV1.platform` Contract。
- 不新增媒体名称/发布者字段。
- 不启动 Stage 8。
- 不做编辑距离、拼音、同义词或机器学习平台识别。

# 必须保持不变

- Canonical `platform` 继续是满足 `^[a-z0-9][a-z0-9_-]*$` 的稳定 slug。
- 已有精确别名映射继续有效。
- 未知合法 ASCII slug 继续按现有行为通过。
- 无法安全识别的平台继续 fail-closed，不静默猜测。
- Excel 任一行非法时仍不发布部分 `contents.jsonl`。

# 关键决策

用户已明确要求含有“抖音”“快手”“小红书”等平台名字的媒体名称应正确映射。实现采用“已知平台关键字 + 包含匹配”，而不是开放式模糊相似度；这样覆盖 `平台名 + APP/客户端等修饰词` 的真实输入，同时避免任意中文媒体名被猜成五个平台之一。

匹配顺序固定为：精确别名 → 既有合法 ASCII slug → 去空白后的已知中文平台关键字包含匹配 → `platform_unmapped`。因此不会改变原有 ASCII 自定义 platform 的优先级。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：`tests/unit/collection/test_imports_excel.py`
- 相关测试：仓库完整 `tests/unit` 与适用 Stage workflow
- 静态检查/构建：仓库既有 Ruff、mypy、Contract/API、Architecture 与 PR workflow 门禁

## 新鲜证据

Red：用户在 Windows/Python 3.14 直接运行 `imports_test/test.py`，真实输入 `抖音 APP`、`小红书 APP`、`快手 APP`、`哔哩哔哩APP` 等产生 8 条 `platform_unmapped`，稳定复现精确别名过窄问题。

Green（最终 PR head `92584fb37eb8857db7c74d49a8213c78c7bd5db8`）：PR #76 的 11 个 workflow 全部成功：

- CI `32212731802`：success；Stage 1 的 `Backend and repository checks` 实际执行 Ruff format/check、mypy、`pytest tests/unit -q`、contracts/api 测试及架构/Owner/Secret/文档检查；Stage 2 Platform、Stage 3A Database、Windows bootstrap 均 success。
- Stage 1-7 Audit Correctness `32212731804`：success。
- Stage 5A Provider Raw `32212731822`：success。
- Stage 5B Collection Execution `32212731815`：success。
- Stage 5C Provider Persistence `32212731820`：success。
- Stage 5D Provider Dispatch `32212731841`：success。
- Stage 6 XHS Vertical Slice `32212731837`：success。
- Stage 7 Keyword Packs `32212731807`：success。
- Stage 7 Plan Occurrence Run Snapshot `32212731876`：success。
- Stage 7 Provider Config Routing `32212731808`：success。
- Stage 7 Scheduler Runtime `32212731821`：success。

集成：PR #76 以普通 merge 正常合入 `main`，merge commit 为 `8d62781ce9f9ec3b01b2dd555e355f08bef78d38`；合并后重新读取 `main` 已确认其指向该提交。

# 文档影响

- `imports_test/README.md` 已长期说明“媒体名称→platform”与 Canonical 边界；本次只放宽该字段内部的安全归一化实现，不改变输入列、输出 Contract、运行方式或用户操作，因此不制造第二份别名/关键字清单，长期规则由代码测试维护。

# 交付

- 回归测试 Commit：`6bdb818d732348eec816641972b0ff9a777514c1`
- 实现 Commit：`37c34e9f06463371e0f4e60661881bb26f22a73e`
- 最终 PR head：`92584fb37eb8857db7c74d49a8213c78c7bd5db8`
- PR：#76，已合并。
- main merge commit：`8d62781ce9f9ec3b01b2dd555e355f08bef78d38`
- 发布：不涉及独立部署；随 `main` 正常集成。
