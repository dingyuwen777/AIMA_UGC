---
schema: coding-change/v1
id: CHG-20261002-211727-manual-full-comments-workbench
title: 主动采集默认全量评论与工作台交互修复
level: L3
status: implementing
owner: codex
branch: codex/manual-full-comments-workbench
created: 2026-10-02
updated: 2026-10-02
completion_gate: required
depends_on: []
affected_areas: [collection, workbench, voice-plaza, contracts, docs]
affected_paths: [backend/src/aima_ugc/contracts/http.py, backend/src/aima_ugc/bootstrap/collection_http.py, frontend/src/features/collection-supplement, frontend/src/features/import-batches, frontend/src/features/workbench, frontend/src/features/voice-plaza, tests/contracts, tests/integration/collection, frontend/tests, frontend/e2e, frontend/e2e-fullstack, contracts, frontend/src/generated, docs/product, docs/blueprint]
contracts: [CollectionRunCreateRequest, CollectionSupplementPreviewRequest]
data_changes: []
---

# 变更摘要

用户主动采集的二级回复默认关闭，一次性发现仍冻结 Adaptive。统一三个主动入口默认全量一级评论和二级回复，同时恢复工作台已应用筛选、雷达标签选择及无活动任务时的声音广场展示。

# 背景、现状与问题

## 背景

用户要求依次实施引用对话的两份方案。本 Change 只承担第一阶段；第二阶段按账号补采另建正式单元。

## 当前现状

main 77060d1c：HTTP 默认 include_sub_comments=false；手动 Run comment_policy=adaptive；工作台 filters 只在内存；雷达依赖图形事件及隐藏按钮；声音广场永久渲染活动任务区域。

## 问题、根因或约束

默认和快照策略分散，导致主动入口实际行为不一致。页面缺少可恢复的已应用筛选事实及可见标签交互。全量表示 Provider 当前可访问范围，必须保留分页安全上限及 partial。

## 不修改的后果

用户省略选项会漏采回复，主动发现会抽样；页面刷新丢失筛选，标签切换不可靠，无任务仍占用展示区域。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 默认二级回复 false | contracts/http.py；test_manual_comment_defaults.py 本轮 3 failed | 明确更改请求默认与三个页面入口 |
| E2 | 手动 Run 冻结 adaptive | bootstrap/collection_http.py:create_run | 同时冻结 policy.comment_mode=full |
| E3 | Full 引擎已存在 | run_policy.py；test_tikhub_plan_full_comments.py | 复用正式引擎，保留页上限 |
| E4 | filters 不持久化；几何已计算标签边界 | workbench/store.ts；radarGeometry.ts | sessionStorage 与已有几何复用 |

## 推断与待确认

真实浏览器、隔离 PostgreSQL 与 Full-stack 结果尚待本轮验证；不能由代码读取推断通过。

# 目标、成功标准与非目标

## 目标

主动采集默认完整评论；刷新恢复工作台条件；每个一级心智标签可操作并显示对应详情；无活动任务隐藏 AI 区域。

## 成功标准

- [ ] Issue #696 AC1–AC7 对应实现、测试与文档证据完整。
- [ ] 本地验证、独立 Review、当前 head/base CI 满足交付门禁。

## 范围

HTTP 默认与手动策略、三个主动入口、工作台筛选与雷达、声音广场活动任务区域及直接相关测试、生成物和正式文档。

## 非目标

账号补采另阶段；不修改周期计划默认，不增加 endpoint、依赖或 Schema，不部署生产，不改变安全页上限。

## 必须保持不变

历史快照、周期策略、Raw/Canonical/Owner 入库、Job 恢复/取消、Preview 指纹冲突、北京时区和生成 Client。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 根 Agent 唯一写入；独立只读 Review | #696 | collection/workbench/voice-plaza |
| 接口与契约 | 默认二级开启，显式 false 继续有效 | #696 / AC1 | 生成消费者同步 |
| 数据与迁移 | 不新增表列、不重写历史快照 | E2/E3 | 无 Migration |
| 错误与失败语义 | 保留 409、partial、安全页上限 | #696 / AC6 | 不承诺第三方不可访问数据 |
| 兼容性 | 周期 Adaptive/Full 按原选择 | #696 / AC2 | 仅新手动 Run 冻结 Full |
| 部署与回滚 | 用户仅要求合并 main | 用户指令 | 无生产部署；可回滚代码 |

# 修改方案与决策依据

## 最小充分方案

1. HTTP 默认与前端公共默认开启一级/二级；手动 Run 冻结一致 Full，生成 Contract。验证默认、关闭与 PG 快照。
2. 工作台参考目录加载后恢复 schema_version 筛选；复用归一化与 Taxonomy 清理，set/reset 持久化。验证 reload 首次请求与损坏/过期条件。
3. 按 radarGeometry 渲染可见 HTML 标签按钮，单一 selectedMind 驱动高亮与右侧详情。验证鼠标、键盘、指标和下钻。
4. 活动任务非空才显示区域；同步正式文档。验证终态消失和轮询不回归。
5. 本地分层验收、完成审计、独立两阶段 Review、CI、merge、原生 Archive/main-fresh/Closure。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 | E1/E2/E3 | 同时闭合默认及正式执行策略，不另造采集引擎 |
| D2 | E4 | 持久已应用条件，复用参考目录与标签几何 |

## 备选方案与取舍

仅修改 UI 默认不能修复省略字段调用或主动发现 Adaptive；仅使用 ECharts 文本事件不能稳定提供键盘及选中态。选用已批准的 HTTP/快照/HTML 标签完整闭环。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 主动入口默认评论回复且可关闭 | #696 / AC1 | not_satisfied | 本轮 Red 3 failed |
| R2 | 新手动 Run Full，周期历史兼容 | #696 / AC2 | not_satisfied | 尚未验证 |
| R3 | 完整已应用筛选恢复与安全清理 | #696 / AC3 | not_satisfied | 尚未验证 |
| R4 | 可见可操作标签与详情高亮联动 | #696 / AC4 | not_satisfied | 尚未验证 |
| R5 | 无活动任务隐藏 AI 区域 | #696 / AC5 | not_satisfied | 尚未验证 |
| R6 | 本地各层证据与分页边界 | #696 / AC6 | not_satisfied | 尚未验证 |
| R7 | 正式文档与无迁移依赖升级 | #696 / AC7 | not_satisfied | 尚未验证 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| contracts/http.py、collection_http.py、生成物 | 默认及冻结 Full | E1/E2 | R1/R2 |
| collection-supplement、TikHubSupplementDialog | 共用开启默认及关闭联动 | 三个入口一致 | R1 |
| workbench/store.ts | 已应用筛选持久与恢复 | E4 | R3 |
| BrandMindCard.vue | 可见按钮与动态详情标题 | E4 | R4 |
| VoicePlazaPage.vue | 活动区域条件渲染 | 当前永久区域 | R5 |
| 相关测试与正式文档 | 回归、验收及事实同步 | Requirement | R6/R7 |

- [x] 调查当前实现和事实源
- [x] 建立任务路由和验证矩阵
- [x] 默认行为建立失败证据
- [ ] 完成最小充分实现
- [ ] 同步受影响长期文档
- [ ] 取得当前版本验证证据
- [ ] 完成追溯、完成审计和两阶段复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 评论 Full 引擎及前端 store/选项/标签/任务回归 |
| 接口 / 契约 | required | HTTP 默认、非法组合、生成 OpenAPI/Client |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PostgreSQL 手动 Run 冻结与历史兼容 |
| 用户 / 工作流验收 | required | 浏览器补采选项、reload、标签详情/下钻、活动任务 |
| 跨组件关键路径 | required | 正式 comment-supplement Full-stack |
| 外部依赖 / 供应方探测 | not_applicable | 无新 endpoint/Mapper；现有 Full 引擎回归证明本轮接线 |
| 构建 / 打包 / 运行 | required | lint、typecheck、build、generated checks |
| 文档 / 治理 / 其他 | required | 文档检查、Change 完成门禁、Review/CI |

## 验证计划

- pytest Contract、Full 评论运行及相关 collection HTTP 集成。
- Vitest collection-supplement/workbench/voice-plaza；Playwright workbench 和相关流程。
- 真实 PostgreSQL 与 comment-supplement Full-stack 使用隔离状态。
- python scripts/dev/validate_changed.py --base origin/main；python scripts/quality/check_change_completion.py --root . --require-active-ready。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 默认增加请求/费用/时长 | 页面明确范围，保留关闭与安全上限 |
| 兼容性 | 默认语义调整已获用户批准 | 显式选项、历史快照及周期策略保留 |
| 数据 / Migration | 不适用 | 不改变数据库 Schema 或存量数据 |
| 部署 / 运行 | 无本轮部署 | 用户要求本地验证并合并 main |
| 回滚 / 恢复 | 可回滚实现提交 | 无数据迁移；既有冻结 Run 继续执行原语义 |

# 文档、依赖、部署与发布影响

- **长期文档**：docs/product/02 与 docs/blueprint/08 按实现同步评论默认、筛选恢复与标签联动。
- **依赖 / Runtime**：不适用，无升级或新增。
- **配置 / Secret**：仅浏览器 sessionStorage 版本化筛选；不写 Secret。
- **部署 / Release**：不适用，本轮无生产部署授权要求。
- **兼容 / 消费方通知**：生成 Contract 与页面提示体现默认及调用量影响。

# 完成审计

- [ ] upstream_re_read：重新读取 #696 与引用方案并独立重建要求。
- [ ] change_coverage：全部上游要求有实施与验证。
- [ ] reverse_audit：API/入口/异步状态与浏览器实际行为双向核对。
- [ ] unresolved_cleared：not_satisfied 清零；无隐藏延期。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main 77060d1c + 新测试；本地 Python | pytest tests/contracts/test_manual_comment_defaults.py -q | 3 failed，断言 include_sub_comments True | 已复现默认关闭 |

## 未验证内容与剩余风险

当前处于实现阶段；Green、PG、浏览器、Full-stack、Review 和 CI 尚未取得。

## 交付状态

- 提交：待首个治理/Red 提交。
- 拉取请求：待首个本地提交 push 后创建早期 Draft。
- CI：尚未运行。
- 合并：尚未合并。
- Change 归档：合并后由原生 Workflow 完成。
- 发布 / 部署：不适用，本轮仅要求 merge main。

## 备注

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/696。用户已授权必要管理员合并；该权限不替代质量门禁。
