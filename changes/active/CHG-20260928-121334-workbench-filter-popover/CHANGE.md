---
schema: coding-change/v1
id: CHG-20260928-121334-workbench-filter-popover
title: 修复工作台声音流筛选浮层错位与自动滚动误关闭
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/642-workbench-filter-popover
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - workbench
affected_paths:
  - frontend/src/features/workbench/components/WorkbenchMultiSelect.vue
  - frontend/e2e/workbench.spec.ts
  - docs/product/02_当前产品能力与用户流程.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：声音流为空时原生 Popover 面板被浏览器默认几何样式推离触发器；声音流有内容自动滚动时，全局 scroll 监听把兄弟列表滚动误判为页面滚动并立即关闭面板。
- **实际修改**：用失败浏览器回归固定原生面板锚点与自动滚动共存行为；重置原生 Popover UA 几何；记录面板定位时的触发器坐标，仅在祖先滚动后触发器确实移动时关闭面板。
- **预期结果**：空/有内容时所有筛选面板都紧贴对应触发器、位于视口内、可持续操作；页面/筛选条滚动仍关闭，面板和声音流列表滚动不误关闭。

# 背景、现状与问题

## 背景

Issue #642 来自用户 2026-09-28 的工作台截图和两条明确复现：空声音流时下拉错位；有内容时下拉无法弹出。用户确认当前工作台和三个模块加载速度可接受，并授权验证无问题后合并 `main`。

## 当前现状

- `WorkbenchMultiSelect` 用作者 `left/top/maxHeight` 定位 `position: fixed` 面板，并在原生 API 可用时调用 `showPopover()`。
- 原生 Popover UA 样式仍保留全边 `inset` 与自动 margin，作者 `left/top` 没有成为唯一几何事实。
- 组件在 `window` 捕获阶段监听所有 `scroll`；只有滚动目标位于面板内时忽略，声音流列表是触发器兄弟节点，因此自动滚动会关闭面板。
- 现有 Browser 覆盖首次关闭、fallback、视口内和基本操作，但没有断言原生 Popover 与触发器的精确相对位置，也没有在声音流持续自动滚动时保持面板打开。

## 问题、根因或约束

两个症状来自不同机制：原生 Popover UA 几何导致空列表场景错位；声音流视觉轨道 scroll 事件导致有数据场景误关闭。只调整 z-index、延时或停掉声音流滚动都会保留另一条复发路径。修复需要让作者坐标成为原生/fallback 的共同几何事实，并依据滚动目标与触发器的结构关系决定是否关闭。

## 不修改的后果

空数据筛选时浮层遮挡其它模块；有数据时筛选入口不可用，真实后端筛选能力无法操作。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 空声音流时“发声”面板出现在品牌心智区域 | 用户截图 | 原生 Popover 必须断言锚点几何，不只断言可见 |
| E2 | 原生 Popover top layer 有 UA inset/auto margin；当前作者 CSS 未重置 | 当前组件与 Chromium 行为 | 明确重置 `inset`/`margin` |
| E3 | 声音流自动动画持续写 `scrollTop`，产生列表 scroll | `SoundStreamCard.vue` 与既有 Browser | 兄弟列表滚动必须被忽略 |
| E4 | `dismissOnScroll()` 对所有面板外 scroll 都关闭 | `WorkbenchMultiSelect.vue` | 只处理 viewport/触发器祖先滚动 |
| E5 | 当前加载性能、三模块独立状态与后端聚合已在 #641 验收 | main@76a1291f / PR #641 | 本 Change 不动数据加载和聚合链 |
| E6 | Review 补充焦点断言后，fallback 用例 5 次并发重复有 1 次在点击后立即关闭；触发器聚焦引起的筛选条滚动已在定位前完成，但延迟派发的 scroll 仍被误判 | Browser Review 回归 | 祖先 scroll 还需验证触发器相对定位坐标是否真的变化，不能只看事件 target |

# 目标、成功标准与非目标

## 目标

让声音流所有筛选面板在空、短、长且自动滚动的声音流状态下都能按触发器正确打开和操作，同时保持既有关闭、可访问性和视口边界语义。

## 成功标准

- [x] #642 / AC1–AC5 全部有实现和新鲜证据。
- [x] 原生 Popover 与 fallback 的位置和生命周期都有 Browser Evidence。
- [ ] Completion Audit、独立 Review、current-head CI、main 合并和收尾完成；其中本地 Completion Audit 已完成，Review 与交付生命周期按顺序后置。

## 范围

- Workbench 多选浮层 CSS 几何与 scroll dismiss 判定。
- 空/自动滚动声音流 Browser 回归。
- 直接相关的产品行为说明。

## 非目标

- 不调整工作台后端查询、轮询频率或已验收的加载性能。
- 不停止声音流自动滚动，不改变悬停/聚焦暂停语义。
- 不改公共 API、generated client、Schema/Migration、布局 Contract 或依赖。

## 必须保持不变

- 首次关闭、原生 top layer、fallback、外部点击、Escape、焦点恢复、ARIA 和视口钳制。
- 三模块并发、独立重试、独立布局和真实后端筛选。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 几何 Owner | 作者 `position` 是原生/fallback 共同事实，重置 UA 剩余 inset/margin | E1–E2 | 不再被 top layer 自动居中二次偏移 |
| Scroll dismiss | viewport 关闭；trigger 祖先滚动后只有定位坐标确实改变才关闭；panel 和其它兄弟内部滚动忽略 | E3–E4、E6 | 筛选条/页面真实移动时状态一致，声音流与打开动作的延迟 scroll 不干扰 |
| 数据/性能 | 不改 Store/API/PostgreSQL | E5 | 保持用户已接受的加载速度与数据口径 |

# 修改方案与决策依据

## 最小充分方案

1. 新增原生 Popover 空流回归，断言面板与触发器相对坐标及视口边界。
2. 新增长声音流自动滚动回归，断言列表继续滚动且面板持续打开、选项可操作。
3. 面板 CSS 重置原生 Popover 的 `inset` 和 `margin`，继续使用现有实时测量的 `left/top/maxHeight`。
4. `dismissOnScroll()` 识别 viewport/document 与包含 trigger 的滚动祖先；祖先事件还要比较定位时和当前触发器坐标，避免打开动作先滚动、后派发事件的竞态；忽略 panel 内部和触发器无关的兄弟滚动。
5. 复跑所有 Workbench Browser、完整 Browser Mock、Unit/lint/typecheck/build 与文档/治理门禁。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 重置 UA 几何 | E1–E2 | 直接让现有真实测量坐标生效，保留 top layer |
| D2 按 trigger 结构和定位坐标过滤 scroll | E3–E4、E6 | 关闭语义取决于 trigger 是否真的移动，避免绑定具体声音流类名和打开时序竞态 |
| D3 保持数据链不变 | E5 | 当前性能已获用户确认，问题局限在浮层表现层 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 空声音流时原生面板紧贴触发器且在视口内 | #642 / AC1 | satisfied | Browser Red 横向偏移 289.6875px；Green 精确断言横向误差 ≤2px、垂直间距 0–8px 和四边安全距离。 |
| R2 | 长声音流持续滚动时面板保持可见、可操作 | #642 / AC2 | satisfied | 18 条声音 Browser 验证列表打开前后持续滚动超过 3px，面板仍可见、ARIA 为 open 且选项可操作。 |
| R3 | 页面/trigger 祖先滚动关闭；panel/兄弟列表滚动忽略 | #642 / AC3 | satisfied | 新回归覆盖兄弟声音流忽略、筛选条实际横移 40px 后关闭；既有回归覆盖 panel 自身忽略和 window 关闭。 |
| R4 | fallback、外部点击、Escape、焦点、首次关闭不回退 | #642 / AC4 | satisfied | Workbench Browser 20/20 通过，包含无 Popover API、首次关闭、面板内焦点经 Escape 返回触发器、外部点击、window scroll 和原生筛选器互斥。 |
| R5 | 工作台性能、真实筛选、滚动、布局和状态不回退，无 Contract/Schema/依赖变化 | #642 / AC5 | satisfied | Workbench 20/20、完整 Browser 161/161、Vitest 255/255、lint/typecheck/build；最终 diff 无 Store/API/Contract/Schema/依赖。 |
| R6 | Completion、Review、CI、merge/main/archive/cleanup 完成交付 | #642 / AC6 | explicitly_deferred | 本地 Completion 已完成；独立 Review、最终提交 CI、合并、main-fresh、归档和分支清理只能在 Ready 提交后按顺序执行，不豁免。 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `WorkbenchMultiSelect.vue` | 重置 Popover 几何并收窄 scroll dismiss | 切断两个根因 | R1–R4 / E1–E4 |
| `frontend/e2e/workbench.spec.ts` | 增加空流锚点和自动滚动共存回归 | 覆盖现有测试缺口 | R1–R5 |
| 产品工作台说明 | 澄清无关内部滚动不关闭筛选 | 同步用户可见行为 | R3–R5 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 理由 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 现有 Workbench Store/组件回归不退化 |
| 接口 / 契约 | not_applicable | 不改公共 Contract；执行生成检查证明无 drift |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不改后端或持久化 |
| 用户 / 工作流验收 | required | 原生/fallback、空/自动滚动、几何、操作与关闭 |
| 跨组件关键路径 | required | SoundStream 自动滚动与 MultiSelect 同时运行 |
| 外部依赖 / 供应方探测 | not_applicable | 不涉及外部 Provider |
| 构建 / 打包 / 运行 | required | lint、typecheck、Vite build、Browser Mock |
| 文档 / 治理 / 其他 | required | targeted 产品事实、Completion、PR CI |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | 过滤过宽会让页面滚动不关闭；过滤过窄会让声音流继续误关闭 | viewport、祖先、panel、兄弟四类 Browser 回归 |
| 兼容性 | 保持原生 Popover 与无 API fallback | 同一 open/position 事实 |
| 数据 / Migration | 不适用 | 无后端、表或数据变化 |
| 部署 / 运行 | 普通前端源码发布 | 无新配置/服务 |
| 回滚 / 恢复 | 可回滚本 PR | 无不可逆行为 |

# 文档、依赖、部署与发布影响

- **长期文档**：只 targeted 更新工作台筛选关闭语义。
- **依赖 / Runtime**：无变化。
- **配置 / Secret**：无变化。
- **部署 / Release**：只合并源码，不执行 Release/Deploy。

# 完成审计

- [x] upstream_re_read：已重读 #642、用户截图/请求、产品事实、最终组件、Browser 回归和完整 diff。
- [x] change_coverage：R1–R5 均由实现与新鲜证据满足；R6 仅后置必须绑定最终提交/合并状态的生命周期动作。
- [x] reverse_audit：已从 window/document、筛选条祖先、panel 自身、声音流兄弟列表四类 scroll 来源反查关闭；从 open/ARIA/原生 top layer/fallback 反查自动滚动与选项操作。
- [x] unresolved_cleared：无 `not_satisfied`；R6 的 Review、CI、merge、main-fresh、归档和 cleanup 按正式顺序后置，不降低门禁。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | main@76a1291f | 用户截图 + 当前代码检查 | 已确认根因 | UA 几何与兄弟滚动是两条独立机制 |
| V2 | fix/642 Red | `cd frontend && npm run test:e2e -- --grep "空声音流时原生\|声音流自动滚动时筛选"` | 2 failed：原生面板横向偏移 289.6875px；自动滚动场景点击后面板立即消失 | 两条回归分别稳定复现 #642 的空流错位与有数据打不开 |
| V3 | 当前候选工作树 | 同 V2 targeted Green | 2 passed | 两条根因均被切断 |
| V4 | 当前候选工作树 | `cd frontend && npm run test:e2e -- e2e/workbench.spec.ts` | 20 passed | 工作台筛选、日期、失败、刷新、滚动和独立布局无回退 |
| V5 | 当前候选工作树 | `cd frontend && npm test -- --run` | 33 files / 255 tests passed | 前端组件与状态回归通过 |
| V6 | 当前候选工作树 | `cd frontend && npm run lint && npm run typecheck` | 通过 | 静态规则及 TypeScript/Vue 类型正确 |
| V7 | 当前候选工作树 | `cd frontend && npm run build` | 835 modules，build 成功 | 正式打包通过；只有仓库既有的大 chunk 提示 |
| V8 | 当前候选工作树 | `cd frontend && npm run test:e2e` | 161 passed | 全页面 Browser Mock Acceptance 无回退 |
| V9 | 当前候选工作树 | governance / Secret / docs / docs-facts gates | 全部通过 | 治理接线、敏感信息和长期文档事实一致 |
| V10 | Review 修复后候选 | fallback + 自动滚动两用例 `--repeat-each=10` | 20 passed | 打开瞬间祖先 scroll 竞态消除，声音流兄弟滚动忽略且实际筛选条滚动仍关闭 |
| V11 | Review 修复后候选 | Workbench / Unit / lint / typecheck / build / 完整 Browser | 20、255、通过、通过、成功、161 passed | 最终实现的分层前端证据全部新鲜通过 |

## Review、CI 与交付记录

- 当前状态：生产实现、文档、Red→Green、完整前端验证和 Completion Audit 已完成，Change 已转 `ready_for_review`。
- Review 第一阶段（实现/风险）：发现 AC4 焦点恢复与原生互斥缺直接断言，并在补测后复现打开瞬间祖先 scroll 延迟派发竞态；已改为记录定位坐标、只在 trigger 实际移动时关闭。两组高风险用例并发重复 10 次后 20/20 通过，最终实现无剩余阻断项。
- Review 第二阶段（测试/文档）：从 AC1–AC5 反查原生/fallback、空/长列表、四类 scroll、焦点/互斥、真实筛选、布局与完整前端证据；产品文档与最终关闭语义一致。结论：`NO_BLOCKING_FINDINGS_WITHIN_SCOPE`。
- CI / merge / archive：Review 无阻断项并形成最终提交后，转 Ready、等待 current-head required checks，再按用户授权合并并完成 main-fresh、原生归档与分支清理。
