# AIMA_UGC Roadmap

docs/roadmap/ 只回答：**当前已经明确批准、尚未完成、仍需要真实实施或验收的工作是什么？**

它不保存已完成 Stage、单次 PR/CI、历史验收流水，也不收纳“以后也许做”的候选方向。

## 当前 Active Roadmap

1. [docs/roadmap/02_生产上线实施路线.md](02_生产上线实施路线.md)：从已完成公司内网基线继续到完整 Production Go-Live；
2. [docs/roadmap/03_4000万历史数据迁移实施方案.md](03_4000万历史数据迁移实施方案.md)：完成服务器容量门禁、独立生产写授权、正式 4000 万 Campaign 和全量对账。

## Roadmap 准入

一项内容只有同时满足以下条件才进入本目录：

- 已被业务/技术 Owner 明确批准；
- 尚未完成；
- 有当前价值，不只是“值得研究”；
- 有可观察退出条件；
- 依赖、授权和不可逆边界清楚。

研究文档中的推荐、外部最佳实践、AI 优化候选、Monitoring / Dashboard / Gold Set 等内容，不会因为被写出来就自动获得 Roadmap 身份。

## 每篇 live Roadmap 的最低要求

前 20 行必须声明“- 状态：Active”，并至少能回答目标、当前已完成基线、仍未完成 Gate、退出条件、依赖和授权、非目标。

## 完成后的生命周期

长期有效知识迁到 Product / Blueprint / Operations / Appendix；施工、PR、CI、SHA、验收历史进入 [changes/archive/](../../changes/archive/) 与 Git；完成的 Roadmap 从 docs/roadmap/ 删除。

不要把完成文档改成 Completed 后永久留在 live Roadmap。
