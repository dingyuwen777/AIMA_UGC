---
schema: coding-change/v1
id: CHG-20260902-collection-strategy-figma-sync
title: 同步采集策略 Figma 与真实车型和词包后端契约
level: L2
status: proposed
owner: dingyuwen777
branch: fix/306-collection-strategy-figma-sync
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas: [frontend, figma-sync, tests]
affected_paths: [frontend/src/features/collection-strategy, frontend/tests/collection-strategy.spec.ts, frontend/e2e/collection-strategy.spec.ts]
contracts: [existing-openapi-generated-client]
data_changes: [none]
---

# 目标

让 `/collection-strategy` 当前生产前端与正式 Figma `release` 中采集策略页面保持一致，同时严格服从现有后端 Contract：页面头部操作、关键词包创建入口、采集计划的词包/车型发现范围、计划详情车型展示均使用真实运行时数据，不猜测或新增 API。

# 成功标准

- [ ] 页面头部仅显示“刷新数据”和“新建采集计划”，关键词包卡片头部提供唯一“新建词包”入口。
- [ ] 采集计划列表第三列与 Figma 一致为“词包 / 车型”，能组合展示 API 返回的词包与车型范围。
- [ ] 计划详情显示真实词包与车型；车型使用 `display_name · code`，历史 deprecated/merged 车型仍可解析，目录缺失时保留原始 ID。
- [ ] 新建计划继续只从 active 车型目录选择，并保持“词包或车型至少一个”的现有资格约束。
- [ ] 前端通过 generated Orval client 完整分页读取车型目录，不改后端 Contract、generated client、依赖或数据库。
- [ ] Vitest、Playwright Browser Mock、lint、typecheck、build、Change/CI 门禁形成新鲜证据，并完成合并、归档与 Issue 关闭。

# 范围

- 调整 Collection Strategy Feature 的 API wrapper、Store、页面组合、关键词包面板、计划列表与计划详情。
- 补充 Store/单元测试和 `frontend/e2e/collection-strategy.spec.ts` Browser Mock 验收。
- 仅使用现有 AIMA UI 组件、Token、generated client 与共享 `VehicleMultiSelect`。

# 非目标

- 不新增或修改后端 endpoint、OpenAPI Contract、数据库 Schema/Migration。
- 不修改 generated API client。
- 不增加依赖或升级工具链。
- 不实现 Figma 旧注释中与真实后端不一致的词包编辑、删除、复制能力。
- 不改变采集调度、Provider、Capability、全局相关性或 Eligibility 业务规则。

# 必须保持不变

- `CollectionPlanCreateRequest` / `CollectionPlanResponse` 既有字段及五个平台机器值保持不变。
- 新建计划车型选择仍使用 `VehicleMultiSelect` 的 active-only 目录；历史展示目录与可创建目录语义不得混用。
- `Asia/Shanghai`、现有 Cron 预设、Provider Capability/Search Config、全局相关性、词包分页和启停资格保持不变。
- 车型展示失败不得伪造业务名；未解析 ID 必须保留可追溯原始值。

# 关键决策

- 车型目录展示数据由 Collection Strategy Store 统一加载，详情和列表共享，不让组件各自猜测或重复请求。
- 历史展示读取 `/api/v1/vehicle-models` 时不传 `status`，按 `limit=200` + `offset` 直到覆盖 `total`，因此 active/deprecated/merged 均可解析；创建选择器继续保留 active-only。
- 列表发现范围按 Figma 的三行密度展示前两项，剩余项用“另有 N 项范围”汇总；车型项加“车型：”前缀，详情用 `display_name · code`。
- 采用 connector-only 降级 Git 交付是本轮已获用户明确授权的宿主能力例外；仍保留 Issue、Change、PR、CI、Review、归档和 main 新鲜校验，不绕过门禁。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 页头只保留刷新与新建计划，新建词包移动到关键词包卡片头部 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | Browser Mock 回归待实现 |
| R2 | 计划列表同时展示真实关键词包与车型范围，并与 Figma 六列表格一致 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | Store/Browser Mock 回归待实现 |
| R3 | 计划详情展示真实车型名与 code，历史状态可解析，缺失目录回退原始 ID | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | Browser Mock 回归待实现 |
| R4 | 新建计划保持 active-only 车型选择与词包/车型至少一个的资格规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | 既有创建验收与新增目录请求断言待验证 |
| R5 | 车型目录必须走 Orval generated client，并按 offset/limit 完整分页 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | Vitest Store 分页回归待实现 |
| R6 | 平台、Provider、Cron、北京时间、Capability/Eligibility、相关性与分页既有行为保持 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | 既有前端测试与 CI 待验证 |
| R7 | 不修改后端 Contract、generated client、依赖和数据库 | https://github.com/dingyuwen777/AIMA_UGC/issues/306 | not_satisfied | 最终 PR diff 审计待完成 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Store 车型目录全量分页、无 status 历史读取、既有资格行为 |
| 接口 / 契约 | required | generated `listVehicleModels` 参数及 CollectionPlan 车型字段只读复用；PR diff 不改 Contract/generated |
| 集成 / 持久化 / 运行依赖 | not_applicable | 本次不修改持久化、数据库或真实外部服务语义；浏览器使用正式 HTTP 形状 Mock 验证前端接线 |
| 用户 / 工作流验收 | required | Playwright 验证页头、关键词包卡片入口、计划范围、详情车型、新建计划 active-only 请求 |
| 跨组件关键路径 | required | Store → Page → PlanPanel/PlanDetailDrawer 车型目录接线与创建 selector 独立 active-only 路径 |
| 外部依赖 / 供应方探测 | not_applicable | 不需要 TikHub/Figma 运行时外部供应方探测；Figma 为正式设计事实源且已读取当前节点 |
| 构建 / 打包 / 运行 | required | frontend lint、typecheck、Vitest、Vite build 与相关 Playwright/全栈 CI |
| 文档 / 治理 / 其他 | required | Issue #306、Active Change、Requirement-Source、Completion Gate、Review、归档、main 新鲜 CI |

# 完成审计

- [ ] upstream_re_read：完成前重新读取 Issue #306、当前 Figma 节点、后端 Contract、generated client 和受影响前端 Owner。
- [ ] change_coverage：完成前逐条对照 Issue 与 Figma，确认页面显示和真实后端数据流均覆盖。
- [ ] reverse_audit：完成前执行后端能力→前端入口与前端动作→后端真实能力双向审计，并复核验证矩阵。
- [ ] unresolved_cleared：完成前清零所有 not_satisfied，且无未经批准延期。

# 任务

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立四维任务路由：现有前后端项目 / feature 修复 / Vue3+TS+Python Contract / L2
- [x] 建立失败测试或说明测试例外
- [x] 建立并维护验证矩阵
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成需求追溯与完成审计

# 验证

## 计划

- 目标测试：`npm --prefix frontend test -- --run frontend/tests/collection-strategy.spec.ts`（以仓库实际脚本为准执行）
- 浏览器验收：`frontend/e2e/collection-strategy.spec.ts`
- 相关测试：现有 Collection Strategy 前端测试集
- 静态检查或构建：frontend lint、typecheck、build
- 就绪检查：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`
- 正式证据以 GitHub Actions 使用仓库锁定工具链执行的结果为准；当前宿主不冒充锁定本地工具链。

## 新鲜证据

- RED 阶段：已新增要求对应回归，等待 PR CI 证明当前实现不满足。

# 文档影响

- 产品/架构文档不需要修改：公共 Contract、路由、数据模型、部署方式均不变化。
- Change 与 Issue 作为本次治理和需求追溯文档；完成后按仓库规则归档 Change。

# 交付

- 提交：待创建
- 拉取请求：待创建
- 发布：不适用；合并 main 后由现有发布流程按需处理
