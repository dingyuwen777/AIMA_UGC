---
schema: rvc-change/v1
id: CHG-20260819-import-platform-keyword-match
title: Excel 导入平台名称受控包含匹配
level: L2
status: in_progress
owner: ChatGPT
branch: fix/imports-platform-keyword-match
created: 2026-08-19
updated: 2026-08-19
affected_areas:
  - imports
  - imports_test
affected_paths:
  - backend/src/aima_ugc/adapters/providers/imports/excel_profile.py
  - backend/src/aima_ugc/adapters/providers/imports_test/README.md
  - tests/unit/collection/test_imports_excel.py
contracts: []
data_changes: none
---

# 目标

让 `aima-monitoring-excel.v1` 在“媒体名称（中文）”包含已知平台名称时稳定归一化到现有 Canonical `platform`，例如 `抖音 APP → douyin`、`小红书 APP → xiaohongshu`、`快手 APP → kuaishou`、`哔哩哔哩APP → bilibili`，同时保持未知中文媒体 fail-closed。

# 成功标准

- [ ] 用户给出的 `抖音 APP`、`小红书 APP`、`快手 APP`、`哔哩哔哩APP`、`新浪微博` 均转换成功。
- [ ] 仅对已知平台关键字做受控包含匹配，不使用编辑距离或任意相似度猜测。
- [ ] 现有精确别名和合法 ASCII platform slug 行为保持兼容。
- [ ] 未命中已知平台且不能形成合法 ASCII slug 的中文媒体仍返回 `platform_unmapped`。
- [ ] Canonical Contract、Migration、数据库和五平台生产采集链不变。

# 范围

- Excel Import Profile 的平台名称归一化。
- 对真实 `APP` 后缀输入增加单元回归测试。
- 同步 `imports_test` 使用说明。

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

# 任务

- [x] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：`tests/unit/collection/test_imports_excel.py`
- 相关测试：`tests/unit/collection/test_imports_test_export.py`、`tests/unit/collection/test_p1g_imports_run_all.py`
- 静态检查/构建：仓库既有 Ruff/CI 门禁及 PR 适用 workflow

## 新鲜证据

- 尚未执行。

# 文档影响

- `backend/src/aima_ugc/adapters/providers/imports_test/README.md` 需要明确平台名称是受控包含匹配，不是仅支持精确值。

# 交付

- Commit：待完成
- PR：待创建
- 发布：不涉及独立部署；经正常 PR/CI 集成。
