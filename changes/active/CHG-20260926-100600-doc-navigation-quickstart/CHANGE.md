---
schema: coding-change/v1
id: CHG-20260926-100600-doc-navigation-quickstart
title: 修正文档导航、Roadmap 编号与运行速查入口
level: L2
status: in_progress
owner: yuwen.ding
branch: docs/609-doc-navigation-quickstart
created: 2026-09-26T10:06:00+08:00
updated: 2026-09-26
completion_gate: required
depends_on: []
affected_areas:
  - docs
  - governance
affected_paths:
  - docs/02_环境运行与部署.md
  - docs/guides/
  - docs/roadmap/
  - docs/operations/
  - docs/blueprint/
  - docs/product/
  - docs/appendix/
  - docs/README.md
  - docs/01_代码结构与修改导航.md
  - AGENTS.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：Windows Guide 文件名含空格、Active Roadmap 从 02 开始、运行总入口的启停命令不够前置，导致导航和日常启动体验不稳定。
- **拟议修改**：规范化三个文档路径并同步所有当前引用；把 docs/02 改成“先启动/停止速查、后详细解释”，不改变任何运行实现。
- **预期结果**：从 docs/02 第一屏即可启动/停止常见环境；Guide/Roadmap 路径连续且可稳定跳转。

# 背景、现状与问题

## 背景

Issue #609 来自用户对当前文档可用性的直接反馈：Windows Guide 跳转失败、Roadmap 编号不连续、运行总入口寻找启动/停止命令成本高。

## 当前现状

- Windows Guide 当前路径为 `docs/guides/03_Windows Docker Desktop Compose运行.md`；
- Active Roadmap 当前为 02、03；
- docs/02 的源码启动在正文前部，但 Compose/服务器入口和汇总导航分散，末尾还有第二个“一句话导航”；
- Release Bundle 当前真实包含 `start_compose.py` / `stop_compose.py`，生产启动/停止可直接从 Bundle 根执行。

## 问题、根因或约束

这是文档导航与 Owner 呈现问题，不是 Runtime 缺陷。总入口应该优先满足“我现在怎么启动/停止”的高频任务，同时避免复制专项 Guide/Operations 的配置、首次准备和排障全文。

## 不修改的后果

- 带空格路径继续存在不稳定跳转；
- Roadmap 排序持续让读者误以为缺少 01；
- 日常运行需要翻找正文或末尾才能拼出命令；
- 顶部/底部重复导航会继续形成两个维护点。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Windows Guide 文件名含空格 | docs/guides 当前目录 | 重命名且不保留重复副本 |
| E2 | Active Roadmap 只有 02、03 | docs/roadmap 当前目录 | 重编号为 01、02 |
| E3 | 源码 launcher 启动为 backend.py + frontend.py，停止为 Ctrl+C | docs/02 + scripts/dev | 顶部速查保留此入口 |
| E4 | Linux/WSL Compose 当前标准入口为 canonical compose + env.local | docs/02 + compose.yaml | 顶部提供 up/down |
| E5 | Windows Compose 使用 compose.yaml + compose.windows.yaml + env.local | Windows Guide | 顶部提供明确命令 |
| E6 | Release Bundle 包含 start_compose.py / stop_compose.py，生产 env 位于 /data/AIMA_UGC/env.production | scripts/release/release_bundle.py | 服务器速查使用 Bundle 脚本 |

## 推断与待确认

无。命令和文件路径都可从当前 main 直接确认。

# 目标、成功标准与非目标

## 目标

把 docs/02 变成真正的运行总入口，并消除当前已知路径/编号导航缺陷。

## 成功标准

- [ ] Issue #609 AC1–AC8 全部满足。

## 范围

见 frontmatter affected_paths；仅文档与治理载体。

## 非目标

- 不修改 Compose、Deploy/Release 脚本、Runtime、配置默认值；
- 不新增第二套运行手册；
- 不做 Production Go-Live 能力实现。

## 必须保持不变

- 当前源码 launcher、Compose、Release Bundle 启停语义；
- Windows storage override 和 Production env 边界；
- Product/Contract/Schema/Migration 行为。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | docs/02 只做速查与导航；专项细节留 Guide/Operations | E3-E6 | 防止总入口重新膨胀 |
| 接口与契约 | 不适用 | 文档路径/内容修改 | 无 API/CLI Contract 变化 |
| 数据与迁移 | 不适用 | 无 Schema/数据变化 | 无迁移 |
| 错误与失败语义 | 链接必须原子更新 | E1/E2 | 避免重命名中间断链 |
| 兼容性 | 仓库内路径全部迁移；不保留旧重复文档 | 单一 Owner | 外部旧书签可能失效 |
| 部署与回滚 | 不适用；Git 回滚 | 无 Runtime 修改 | 无部署操作 |

# 修改方案与决策依据

## 最小充分方案

1. 重命名 Windows Guide，去掉文件名空格；同步当前文档引用。
2. Roadmap 02→01、03→02；同步当前文档引用和所有简写导航。
3. 重构 docs/02 Section 1：四种环境启动/停止速查 + 详细文档入口；后文继续解释环境差异。
4. 删除 docs/02 末尾重复导航。
5. 扫描旧路径残留，运行文档/治理 CI。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 文件重命名不保留旧副本 | E1/E2 | 防止第二个文档 Owner |
| D2 docs/02 顶部只放命令和链接 | E3-E6 | 高频任务前置，同时避免重复专项内容 |
| D3 生产环境使用 Bundle start/stop 脚本 | E6 | 脚本是真实 Release 资产且负责资源规划 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Windows Guide 无空格路径且旧引用清零 | #609 / AC1 | not_satisfied | 待实现 |
| R2 | Active Roadmap 连续编号并同步引用 | #609 / AC2 | not_satisfied | 待实现 |
| R3 | docs/02 顶部列四种环境启动/停止 | #609 / AC3 | not_satisfied | 待实现 |
| R4 | 速查命令来自真实入口且详细内容仍归专项 Owner | #609 / AC4 | not_satisfied | 待实现 |
| R5 | 删除 docs/02 末尾重复导航 | #609 / AC5 | not_satisfied | 待实现 |
| R6 | 相对链接可解析且旧路径无残留 | #609 / AC6 | not_satisfied | 待验证 |
| R7 | 不改变产品/Runtime/Contract/Schema/Compose/Deploy 语义 | #609 / AC7 | not_satisfied | 待验证 |
| R8 | current-head CI/Review 与交付闭环 | #609 / AC8 | not_satisfied | 待交付 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| docs/02 | 顶部速查、导航收敛 | 日常运行入口 | R3-R5 |
| guides/03 | 无空格重命名 | 修复跳转 | R1 |
| roadmap/01、02 | 连续重命名 | 排序连续 | R2 |
| 当前引用文档 | 同步路径 | 防断链 | R1/R2/R6 |
| 文档/治理 CI | 验证 | 防回归 | R6-R8 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | not_applicable | 不改业务行为 |
| 接口 / 契约 | not_applicable | 不改公共接口 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不改运行依赖 |
| 用户 / 工作流验收 | required | 读者可从 docs/02 第一屏取得正确启停入口 |
| 跨组件关键路径 | not_applicable | 无运行链修改 |
| 外部依赖 / 供应方探测 | not_applicable | 无外部依赖事实需要核验 |
| 构建 / 打包 / 运行 | not_applicable | 不修改构建/运行产物 |
| 文档 / 治理 / 其他 | required | 链接、旧路径扫描、docs facts、Ready/CI |

## 验证计划

- 目标测试：文档链接/导航、docs facts；
- 相关回归：Change Ready、当前 required CI；
- 静态检查：旧文件名/旧 Roadmap 路径扫描；
- 专项真实边界：不适用，不执行真实部署；
- 就绪检查：项目文档治理与 Change completion gate。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 漏改链接、速查命令漂移 | 全仓扫描 + 机器事实核对 |
| 兼容性 | 仓库内兼容；外部旧书签可能失效 | 不保留重复旧文件 |
| 数据 / Migration | 不适用 | 无数据变化 |
| 部署 / 运行 | 不适用 | 只改文档 |
| 回滚 / 恢复 | Git 回滚 | 无运行副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：本任务本身即文档导航修复；
- **依赖 / Runtime**：不适用；
- **配置 / Secret**：不适用；
- **部署 / Release**：不执行；
- **兼容 / 消费方通知**：仓库内链接同步；外部保存旧 URL 的读者需改用新路径。

# 完成审计

- [ ] upstream_re_read：完成前重新读取 #609 与最终文档/脚本事实。
- [ ] change_coverage：完成前按 AC1–AC8 逐条核对。
- [ ] reverse_audit：检查本次速查是否复制专项全文、重命名后是否出现第二 Owner/断链。
- [ ] unresolved_cleared：Ready 前清零 not_satisfied 或有正式延期依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main c0e90c4 | 当前文档/脚本读取 | confirmed | E1-E6 基线成立 |

## 未验证内容与剩余风险

- 实现、current-head CI、独立 Review、合并后归档/关闭尚待执行。

## 交付状态

- 提交：待实现
- 拉取请求：待建立
- CI：待执行
- 合并：待执行
- Change 归档：待执行
- 发布 / 部署：不适用
