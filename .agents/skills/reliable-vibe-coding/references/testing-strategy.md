# 分层测试与验收策略

这份规则用于回答一个常见问题：**一个功能应该用 Mock、Integration、Contract、Real Full-stack 还是真实 Provider Probe 来证明？**

目标不是把所有测试都做成最真实、最昂贵的端到端，而是让每一层证明它最擅长证明的事实，并用少量跨层 Golden Path 证明系统真正接通。

## 核心原则

默认采用：

```text
Browser Mock Acceptance
→ 广覆盖用户可见行为和状态

Backend / API / PostgreSQL Integration
→ 广覆盖服务器业务规则、事务、持久化、Worker/Job

Contract
→ 保证前后端或生产者/消费者使用同一机器 Contract

Real Full-stack Golden Path
→ 少量关键路径证明真实组件组装后确实接通

Real Provider Probe
→ 极少、有界地验证外部供应商当前真实接口；默认不作为普通 CI 回归主力
```

不要把“更接近生产”误解成“所有场景都应该 Real Full-stack”。测试层越真实，通常越慢、越贵、越容易受环境影响，也越难稳定制造失败边界。因此：

- **状态空间广度**优先放在可控、便宜的层；
- **跨组件接线事实**用少量真实链路证明；
- **外部 Provider 当前可用性**用有界 Probe 单独证明；
- 任一层都不得声称证明自己没有实际运行的下游边界。

## 1. Browser Mock Acceptance

### 证明什么

在真实 Browser / 前端运行时中，用可控的 HTTP Mock 驱动页面，证明：

- 页面、路由、菜单、按钮、表单和抽屉可操作；
- enabled / disabled 资格表达正确；
- 前端向 API 发出的 method、URL、query、payload 正确；
- loading、empty、queued、running、retry、partial success、success、failure、cancel 等用户可见状态正确；
- 400/404/409/422/429/500/503 等错误和稳定 `request_id` 正确显示；
- 轮询、刷新、A→B→A 切换、缓存失效、跨页跳转和最终结果入口正确；
- 前端不根据猜测编造后端不存在的历史、状态或结果。

### 默认覆盖宽度

对存在用户界面的业务，Browser Mock Acceptance 通常应是**用户可见状态覆盖最宽的一层**。真实系统难以稳定制造的边界，例如第 2 次 Retry、部分成功、某 Scope 失败、503、空页、权限/资格变化，优先在这一层穷举。

### 不能证明什么

Browser Mock **不能单独证明**：

- FastAPI/真实 Route 确实接受该请求；
- Pydantic/后端业务守卫与 Mock 一致；
- PostgreSQL 事务、约束和数据真正写入；
- Job/Worker/Scheduler 真正执行；
- 外部 Provider 真正返回数据；
- 从 Browser 到最终持久化结果的真实链路已经接通。

因此禁止把 `Browser Mock passed` 描述成 `Real Full-stack passed`。

## 2. Backend / API / PostgreSQL Integration

### 证明什么

使用真实后端入口和真实 PostgreSQL（任务确实依赖数据库行为时），验证：

- Service / Repository 业务规则；
- HTTP status、错误 Contract、404/409/422 等后端边界；
- UNIQUE/FK/CHECK、事务、锁、幂等、Fencing、Migration；
- Job 创建与 Worker/Handler 状态转换；
- 查询、分页、资格判断、current/history、最终持久化结果；
- 失败、重试、取消、并发、接管等服务器状态机。

### 为什么不把这些都交给 Browser

这些问题多数与 DOM 无关。直接在后端/数据库层验证更快、更稳定，失败时也更容易定位根因。

### 不能证明什么

它不能证明真实浏览器中的交互、视觉状态、按钮条件和跨页面体验正确。

## 3. Contract / Generated Client

### 证明什么

对存在正式机器 Contract 的边界，验证生产者和消费者说的是同一种语言，例如：

```text
Pydantic / Schema
→ OpenAPI / JSON Schema
→ Generated Client
→ Contract compatibility / drift check
```

它防止出现：Browser Mock 自己使用字段 A、后端真实接口已经改成字段 B，而两边各自测试仍然绿色。

### 不能证明什么

Contract 一致不等于业务行为正确，也不等于数据库/Worker/Browser 已真实运行。

## 4. Real Full-stack Golden Path

### 证明什么

让真实关键组件组装运行，例如：

```text
Browser
→ Frontend
→ Generated Client
→ Real API
→ Real PostgreSQL
→ Real Job / Worker
→ Real PostgreSQL
→ Browser 看到最终结果
```

它回答的是：

> 前面分别验证过的组件，真正连在一起时能不能工作？

### 默认覆盖宽度

Real Full-stack 默认只保留**少量高价值 Golden Path**，通常覆盖：

- 一个最关键成功链；
- 有独立价值时再增加一个代表性失败/恢复链；
- 公共接线、配置、进程边界发生重大变化时增加对应路径。

不要为了覆盖每个 UI 状态复制大量 Real Full-stack 场景。状态穷举优先由 Browser Mock 和 Backend Integration 承担。

### 不能证明什么

一条 Golden Path 通过不等于所有错误状态、资格组合、并发边界和 Provider 异常都已覆盖。

## 5. Real Provider Probe

### 证明什么

仅在任务确实依赖外部 Provider 当前真实能力、字段、分页、错误或计费事实时，有界调用生产 Adapter/Operation，验证：

- endpoint / 参数当前可用；
- Sanitized Raw shape 与 Mapper 假设一致；
- pagination / stable ID / capability 与真实响应一致；
- 必要的费用、限流和错误边界。

### 固定边界

- 默认关闭；
- 不进普通 CI，除非仓库已有明确批准的专门机制；
- 明确请求/费用上限；
- 不打印 Secret；
- 不默认写生产库；
- 失败要区分代码缺陷与供应商/网络不稳定。

Fixture/Fake/Mock 回归不能声称证明 Provider 此刻在线；真实 Probe 也不应替代稳定 Fixture/Mapper 回归。

## 6. Validation Matrix

L2/L3 Change 在实现前按当前任务边界建立 Validation Matrix。每一层只使用：

```text
required
not_applicable
```

`required` 要写本次要证明的 Scope；完成前补当前 Evidence。`not_applicable` 必须说明为什么该层对当前任务没有独立证明价值，不能为了少跑测试而省略。

推荐模板：

```markdown
| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | 用户可见状态、请求 payload、错误/结果闭环 |
| Backend/API/PostgreSQL Integration | required | 业务守卫、事务、Job/Worker、持久化 |
| Contract / Generated Client | required | Pydantic/OpenAPI/generated client 无漂移 |
| Real Full-stack Golden Path | required | 1 条关键成功链真实接通 |
| Real Provider Probe | not_applicable | 本次不修改外部 Provider 能力/字段 |
```

矩阵不是固定测试数量配额。例如可以出现很多 Browser Mock、很多 Backend Integration，但只有一条 Real Full-stack；也可以是纯后端任务没有 Browser 层。

## 7. 任务类型默认选择

### 有用户界面的新功能或行为变化

通常：

- Browser Mock Acceptance：`required`，覆盖用户状态空间；
- Backend/API Integration：只要后端行为受影响就 `required`；
- Contract：公共 API/生成 Client 受影响时 `required`；
- Real Full-stack：存在跨组件关键链时至少一条 Golden Path；纯前端表现修改可 `not_applicable`；
- Real Provider Probe：仅外部 Provider 事实变化时需要。

### 纯后端/数据库

Browser 可 `not_applicable`；Backend/PostgreSQL Integration 通常是主证据。公共 Contract 受影响时补 Contract；存在关键跨进程链时考虑 Real Full-stack。

### Provider / Mapper

稳定 Fixture/Operation/Mapper 测试是主回归；只有需要确认供应商当前真实事实时才跑有界 Real Probe。若能力最终暴露给用户，还应在上层补 Browser/API 证据。

### 纯文档/配置/生成物

记录 TDD 例外，以解析、链接、生成差异、静态检查、构建或仓库一致性为证据；不要为了填 Matrix 编造无价值 Browser/DB/Full-stack 测试。

## 8. Completion Audit 与 Review

进入 Ready 前，不只问“测试是不是绿”，而要问：

1. Requirement 的用户可见行为是否有 Browser 证据（适用时）；
2. 服务器规则和持久化是否有 Backend/DB 证据（适用时）；
3. 公共边界是否有 Contract 证据；
4. 是否至少有足够的 Real Full-stack Golden Path 证明关键接线，而没有用 Mock 冒充；
5. 外部 Provider 事实是否真的需要 Probe；需要时是否有界、可审计；
6. `not_applicable` 是否有真实依据；
7. 是否存在“某一层已经通过，所以跳过另一层独立风险”的错误推理。

Review 必须按证据等级陈述结论，例如：

- `Browser Mock Acceptance passed`；
- `PostgreSQL Integration passed`；
- `Real Full-stack Golden Path passed`；

不要笼统写“E2E 全通过”掩盖测试实际使用了 Mock 还是实链。

## 9. 常见反模式

禁止：

- 所有状态都做成 Real Full-stack，导致慢、脆、难制造失败；
- 只有 Browser Mock，却宣称后端/数据库/Worker 已真实闭环；
- 只有 Backend tests，却没有验证重要用户可见行为；
- Mock 手写第二套与正式 Contract 脱节的类型/字段体系；
- 为了测试方便关闭真实 PostgreSQL 约束；
- 把付费 Provider 调用塞进普通 CI；
- 固定“每个功能必须 N 个 Mock + M 个 Integration + 1 个 Full-stack”而忽略实际风险；
- 看到任一层绿色就用它替代 Completion Audit。
