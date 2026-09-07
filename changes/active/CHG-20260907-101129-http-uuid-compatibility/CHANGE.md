---
schema: coding-change/v1
id: CHG-20260907-101129-http-uuid-compatibility
title: 修复 HTTP 部署环境下前端 UUID 生成兼容问题
level: L2
status: proposed
owner: dingyuwen777
branch: fix/http-uuid-compatibility
created: 2026-09-07
updated: 2026-09-07
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - tests
affected_paths:
  - frontend/src/shared/
  - frontend/src/features/import-batches/
  - frontend/src/features/voice-plaza/
  - frontend/tests/
  - frontend/e2e/excel-import-submit-state.spec.ts
  - changes/active/CHG-20260907-101129-http-uuid-compatibility/CHANGE.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：前端直接调用仅在安全上下文暴露的 `crypto.randomUUID()`；用户通过普通 `http://服务器地址` 打开 Linux 部署页面时，本地 Excel 导入在发起 HTTP 请求前失败。
- **拟议修改**：新增一个前端共享幂等键生成入口，安全上下文继续使用原生 `randomUUID()`，缺少该方法时按 Web Crypto 标准用 `getRandomValues()` 生成 UUID v4；替换当前 3 处直接调用并补回归测试。
- **预期结果**：Windows 浏览器通过普通 HTTP 地址访问时，本地 Excel 导入仍能创建 Campaign；服务器目录导入和手动 Analysis Run 同样不再依赖 `randomUUID()` 是否暴露。

# 背景、现状与问题

## 背景

Issue #385 记录了 Linux 部署后，Windows 浏览器通过普通 HTTP 地址执行本地 Excel 导入时报错 `crypto.randomUUID is not a function`。这是用户可见工作流阻断，需要保持现有数据导入 Contract 和幂等语义做兼容修复。

## 当前现状

- `frontend/src/features/import-batches/store.ts` 的本地 Campaign 创建直接调用 `crypto.randomUUID()`。
- `DataImportDialog.vue` 的服务器目录 Campaign 创建和 `voice-plaza/store.ts` 的手动 Analysis Run 也直接调用同一方法。
- W3C Web Crypto Level 2 将 `randomUUID()` 标注为 `[SecureContext]`，但 `getRandomValues()` 不受该标注限制，并定义了用 16 个安全随机字节生成 UUID v4 的算法。
- 当前锁定前端为 Node 24.19.0、npm 11.17.0、Vue 3、TypeScript、Vite、Vitest 与 Playwright；本次不改变版本或依赖。

## 问题、根因或约束

根因是前端把安全上下文专用的 `randomUUID()` 当成所有部署访问方式都具备的基础能力。普通远程 HTTP Origin 不属于安全上下文，因此兼容浏览器可以保留 `crypto.getRandomValues()`，却不暴露 `crypto.randomUUID()`；直接调用会在创建 API 发出前抛出 TypeError。

## 不修改的后果

本地 Excel 导入继续在普通 HTTP 部署入口完全不可用；另两处调用也会在相同浏览器上下文触发同类错误。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 本地 Excel 导入在构造 `client_idempotency_key` 时直接调用 `crypto.randomUUID()` | `frontend/src/features/import-batches/store.ts` | 修复必须覆盖用户实际失败入口 |
| E2 | 服务器目录导入与手动 Analysis Run 还有两处相同直接调用 | `rg -n "randomUUID" frontend/src` | 应由单一共享实现消除相同触发面 |
| E3 | `randomUUID()` 是 SecureContext 方法；`getRandomValues()` 可在非安全上下文使用 | W3C Web Crypto Level 2 与 Secure Contexts 规范；MDN 兼容说明 | 可在不引入依赖的前提下实现标准 UUID v4 fallback |
| E4 | 当前 HTTP/DB/generated Contract 不要求变化 | generated request 仅要求字符串 `client_idempotency_key`；当前调用链调查 | 保持服务器、Schema、Migration 与 generated client 不变 |

## 推断与待确认

- 已确认根因与用户报告完全一致；未直接连接用户的 Windows 浏览器和 Linux 服务器，因此实际浏览器版本、访问 URL 与 `window.isSecureContext` 值仍待用户环境部署新前端后确认，但不阻塞兼容修复。

# 目标、成功标准与非目标

## 目标

让当前所有需要客户端幂等键的前端写入口在 `crypto.randomUUID()` 不存在、但 `crypto.getRandomValues()` 可用时仍生成标准 UUID v4 并继续既有请求流程。

## 成功标准

- [ ] 非安全上下文能力模型下，本地 Excel 导入生成 UUID v4 并调用既有 Campaign 创建接口。
- [ ] 服务器目录导入和手动 Analysis Run 复用同一 UUID 生成入口。
- [ ] 安全上下文继续优先使用原生 `crypto.randomUUID()`。
- [ ] 不修改 HTTP Contract、generated client、Schema/Migration、依赖与部署拓扑，并通过前端相关验证与 PR CI。

## 范围

- 前端共享客户端幂等键生成实现。
- 当前 3 处直接 `crypto.randomUUID()` 调用。
- Vitest 与 Playwright Browser Mock 回归、Change/PR 交付证据。

## 非目标

- 不把普通 HTTP 描述为完整生产安全方案，也不替代后续 HTTPS 门禁。
- 不修改导入、Analysis、Job、后端幂等、数据库或文件处理语义。
- 不新增 UUID 第三方依赖，不升级前端工具链。

## 必须保持不变

- `client_idempotency_key` 仍提交 UUID v4 形状的字符串，后端 API 与错误语义不变。
- Data Import Campaign 的上传、预检、启动、取消、重试与 Artifact/Content Owner 链路不变。
- Analysis Run 的 preview → confirm 冻结语义不变。
- 现有 HTTPS/localhost 环境继续优先使用浏览器原生 UUID 实现。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只修改前端共享能力及当前消费者 | E1、E2 | 不进入后端或部署配置 |
| 接口与契约 | 保持现有 `client_idempotency_key: string` Contract | E4 | 无 OpenAPI/generated 变化 |
| 数据与迁移 | 不适用：不修改数据库结构或持久数据语义 | E4 | 无 Migration/回填 |
| 错误与失败语义 | 有安全随机源时兼容生成；连 `getRandomValues()` 都不存在时明确失败 | E3 | 不用 `Math.random()` 降低幂等键质量 |
| 兼容性 | 原生方法优先，fallback 严格按 UUID v4 version/variant 位生成 | E3 | 安全与非安全上下文保持同一字符串形状 |
| 部署与回滚 | 前端静态产物正常更新；回滚为回退本次前端提交 | E4 | 无额外配置、迁移或停机步骤 |

# 修改方案与决策依据

## 最小充分方案

1. 建立非安全上下文浏览器回归
   → 修改范围：`frontend/e2e/excel-import-submit-state.spec.ts`
   → 预期行为：隐藏 `randomUUID` 后，本地文件仍创建 Campaign，提交键符合 UUID v4
   → 直接验证：目标 Playwright spec 先 Red、修复后 Green
2. 新增共享幂等键生成函数并替换 3 处调用
   → 修改范围：`frontend/src/shared/`、Import Store/Dialog、Voice Plaza Store
   → 预期行为：原生优先；缺失时用安全随机字节生成标准 UUID v4
   → 直接验证：Vitest 原生/fallback 单元测试、受影响 Store 测试
3. 执行相关回归、构建、完成审计与 PR 门禁
   → 修改范围：测试、Change、PR
   → 预期行为：无 Contract/依赖/部署漂移，最终 HEAD 可按正常规则合并
   → 直接验证：lint、typecheck、Vitest、Playwright、build、Change gate、PR CI

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1：使用共享生成入口 | E1、E2 | 3 个调用具有相同幂等键目的和失败条件，单一实现避免修复漂移 |
| D2：用 `getRandomValues()` fallback | E3 | 浏览器规范提供安全随机字节和明确 UUID v4 算法，无需新增依赖 |
| D3：不改后端或部署 | E4 | 错误发生在请求发出前，既有字符串 Contract 已能接收 fallback 结果 |

## 备选方案与取舍

- 只部署 HTTPS：这是完整生产安全的正确长期方向，但不能修复当前已明确存在的普通 HTTP 内网使用，并且 Production HTTPS 仍是独立 Roadmap 门禁。
- 引入第三方 UUID 包：可以兼容，但当前浏览器已有标准安全随机源，为一个小函数增加依赖、供应链与包体积没有必要。
- 使用 `Math.random()`：不采用；它不是加密安全随机源，会无理由降低幂等键碰撞质量。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 缺少 `randomUUID()` 但存在 `getRandomValues()` 时，本地 Excel 导入仍生成 UUID v4 并调用创建接口 | #385 / AC1 | not_satisfied | 待 Red → Green 浏览器工作流证据 |
| R2 | 服务器目录导入和手动 Analysis Run 统一复用同一实现 | #385 / AC2 | not_satisfied | 待实现与消费者回归 |
| R3 | 安全上下文继续优先使用原生 `randomUUID()` | #385 / AC3 | not_satisfied | 待 Vitest 原生路径证据 |
| R4 | Contract/Schema/依赖/部署不变，相关前端验证和 PR CI 通过 | #385 / AC4 | not_satisfied | 待最终 diff 与验证证据 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `frontend/src/shared/idempotency.ts` | 新增标准 UUID v4 幂等键生成函数 | 单一兼容 Owner | R1-R3 / E1-E3 |
| `frontend/src/features/import-batches/store.ts` | 本地导入改用共享入口 | 修复用户实际失败路径 | R1 |
| `DataImportDialog.vue` | 服务器目录导入改用共享入口 | 消除相同失败面 | R2 |
| `frontend/src/features/voice-plaza/store.ts` | Analysis Run 改用共享入口 | 消除相同失败面 | R2 |
| `frontend/tests/shared-domain.spec.ts` | 覆盖原生与 fallback UUID v4 | 证明算法与优先级 | R1、R3 |
| `frontend/e2e/excel-import-submit-state.spec.ts` | 覆盖本地 Excel 用户工作流 | 直接复现并回归报告问题 | R1 |

执行过程中保持最小闭环：

- [x] 调查当前实现和事实源；新建项目则确认现有资料、目标和硬约束
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据或说明测试例外
- [ ] 完成最小实现，不静默扩大范围
- [ ] 同步受影响的长期文档或明确不适用依据
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Vitest 证明原生优先、fallback 的 UUID v4 version/variant 与受影响消费者行为 |
| 接口 / 契约 | not_applicable | 不修改 Pydantic/OpenAPI/generated client；最终 diff 与 typecheck 验证现有字符串 Contract 消费不变 |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不修改后端、数据库、Job、Artifact 或文件处理语义；无需 PostgreSQL 集成冒充前端修复证据 |
| 用户 / 工作流验收 | required | Playwright Browser Mock 在缺少 `randomUUID()` 的页面上下文完成本地 Excel Campaign 创建 |
| 跨组件关键路径 | not_applicable | 不改变 Vue→API→后端接线或服务器行为；现有真实 Full-stack 证据不证明非安全上下文，本次由定向浏览器回归承担 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 TikHub、LLM 或其他外部 Provider，不执行付费 Probe |
| 构建 / 打包 / 运行 | required | lint、typecheck、Vite build 与 PR 当前 HEAD CI |
| 文档 / 治理 / 其他 | required | Issue #385、Change、Requirement Traceability、Completion Audit、独立 Review 与 Change gate |

## 验证计划

- 目标测试：`npm --prefix frontend run test:e2e -- excel-import-submit-state.spec.ts`
- 相关回归：`npm --prefix frontend run test -- --run`、受影响 Browser Mock spec/全量
- 静态检查或构建：`npm --prefix frontend run lint`、`npm --prefix frontend run typecheck`、`npm --prefix frontend run build`
- 专项真实边界：不适用；不修改后端、持久化、外部 Provider 或部署运行依赖
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready`

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | fallback 格式或 version/variant 位错误 | 用确定随机字节单元测试固定标准 UUID v4 输出，并以 Browser 工作流校验请求 |
| 兼容性 | 保持 | 原生路径优先，fallback 输出同一 UUID v4 字符串形状 |
| 数据 / Migration | 不适用 | 无数据库或持久数据结构变化 |
| 部署 / 运行 | 仅需发布新前端静态产物 | 不改配置、Compose、镜像拓扑或后端；完整生产仍应使用 HTTPS |
| 回滚 / 恢复 | 可直接回退本次前端提交 | 无 Migration、数据转换或不可逆副作用 |

# 文档、依赖、部署与发布影响

- **长期文档**：预计不适用；当前架构、调用链、用户能力和部署方式不变，兼容实现与原因由函数说明、Issue/Change 和测试承载。
- **依赖 / Runtime**：不新增、删除或升级依赖/Runtime。
- **配置 / Secret**：不改变配置、默认值或 Secret。
- **部署 / Release**：不改变 Release/Compose；合并后需按既有流程重新构建/部署前端才会生效，本任务不执行生产部署。
- **兼容 / 消费方通知**：无需 Contract 消费方迁移；现有 3 个前端消费者在同一提交切换。

# 完成审计

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前变更覆盖全部上游要求，没有把变更自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力或边界审计，并复核验证矩阵；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期或不适用项均有正式依据。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | `main@40e489c2` + 新增失败测试；Windows / Chromium / Playwright | `npm --prefix frontend run test:e2e -- excel-import-submit-state.spec.ts` | 退出码 1；3 个既有场景通过，新增场景失败；页面错误快照明确显示 `crypto.randomUUID is not a function` | 在真实“导入数据 → 本地文件 → 创建并预检”前端入口稳定复现用户报告，且请求未能进入成功上传流程 |

## 未验证内容与剩余风险

- 尚未在用户实际 Windows 浏览器与 Linux 部署地址上复测；本地会用浏览器能力降级模型稳定覆盖相同 API 暴露条件。

## 交付状态

- 提交：待创建
- 拉取请求：待创建
- CI：待执行
- 合并：待执行
- Change 归档：待合并后自动流程
- 发布 / 部署：不适用；用户要求提交主分支，未要求操作生产服务器。

## 备注

- 通用 Skill 主文件可读取，但其文字引用的 `当前场景所需完整约束/` 在当前安装目录中不存在；本次不依赖缺失内容作事实推断，按用户指令、项目 `AGENTS.md`、仓库机器事实、W3C 一手规范及现有测试/CI 门禁执行。
