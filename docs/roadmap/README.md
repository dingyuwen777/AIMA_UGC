# AIMA_UGC Roadmap

`docs/roadmap/` 只回答一个问题：

> **当前已经明确批准、尚未完成、下一步仍需要真实实施或验收的工作是什么？**

这里不再保存已完成 Stage、单次 PR/CI 过程、历史验收流水，也不把“以后也许可以做”的候选产品方向写成当前施工计划。

## 当前 Active Roadmap

1. [`docs/roadmap/02_生产上线实施路线.md`](02_生产上线实施路线.md)：从已完成公司内网 V1 继续到完整 Production Go-Live 的生产强化；
2. [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](03_4000万历史数据迁移实施方案.md)：完成公司服务器容量门禁、独立生产写授权、4000 万正式 Campaign 和全量对账；
3. [`docs/roadmap/04_搜索与品牌车型过滤实施路线.md`](04_搜索与品牌车型过滤实施路线.md)：分阶段完成 Keyword Pack 搜索职责与品牌/车型过滤分类职责解耦，并覆盖数据库、后端、前端、旧数据重分类与 Legacy Cleanup。

公司内网 V1、Stage 8F、Internal V1-A/V1-B、Stage 12 软件建设等已经完成的施工阶段不再继续占用 live Roadmap。需要理解历史原因或当时证据时，查 [`changes/archive/`](../../changes/archive/) 和 Git 历史。

## Roadmap 文件最低要求

每个 live Roadmap 文件都必须明确：

```text
- 状态：Active
- 目标：...
- 退出条件：...
- 依赖：...
```

并同时满足：

- 目标尚未完成；
- 目标已经被业务/项目正式批准；
- 有明确业务或生产价值；
- 有可观察的完成条件；
- 授权、外部环境或上游依赖清楚；
- 不把已完成历史包装成“背景很长的当前计划”。

完成后必须先把仍有效的长期知识迁移到 Blueprint、Operations、Appendix、Product 或模块 README，再从 live Roadmap 删除。历史施工记录不复制到新的 `docs/archive` / `docs/history`。

## 不自动进入 Roadmap 的候选方向

下列方向只有在后续被明确批准并形成可验收需求时才建立独立 Issue/Change/Roadmap；旧 Stage 文档曾经提到它们不构成当前承诺：

- Monitoring / Alert / VOC / Ticket；
- Web Report Center；
- 通用 Dashboard / 工作台数据驾驶舱；
- Gold Set / 自动模型评测；
- 双人审批；
- 个人导出列配置；
- Provider 自动 Availability 观测；
- 大范围 Count 估算基础设施/SLO；
- 其他没有当前需求来源和退出条件的产品愿望。

## 与其他文档的边界

```text
Product
→ 当前用户能做什么

Blueprint
→ 长期架构和已经拍板的技术边界

Operations
→ 当前能力怎样部署、运行、恢复、迁移

Roadmap
→ 已批准且未完成的目标

Change / Git
→ 某次施工为什么发生、怎样验证
```

总导航见 [`docs/README.md`](../README.md)。
