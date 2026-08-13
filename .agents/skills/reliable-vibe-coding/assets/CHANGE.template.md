---
schema: rvc-change/v1
id: $change_id
title: $title
level: $level
status: proposed
owner: $owner
branch: $branch
created: $created
updated: $updated
$depends_on
$affected_areas
$affected_paths
$contracts
$data_changes
---

# 目标

描述用户或系统最终获得的结果。

# 成功标准

- [ ] 使用可观察行为描述验收结果。

# 范围

- 列出本次允许修改的内容。

# 非目标

- 列出本次明确不做的内容。

# 必须保持不变

- 列出需要兼容的接口、数据、配置和既有合法行为。

# 关键决策

记录已经确认的取舍、依据和影响；L3 变更还应覆盖迁移、部署与回滚。

# 任务

- [ ] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据

# 验证

## 计划

- 目标测试：
- 相关测试：
- 静态检查/构建：

## 新鲜证据

- 尚未执行。

# 文档影响

- 待确认。

# 交付

- Commit：
- PR：
- 发布：
