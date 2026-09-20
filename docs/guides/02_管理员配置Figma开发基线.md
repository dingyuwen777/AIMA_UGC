# 管理员配置 Figma 开发基线

本文维护 `/admin/configuration` 当前正式 Design-to-Code 基线。HTTP 字段、Schema、权限和业务状态机继续以当前 Contract、代码与测试为准，不在本文复制第二份机器事实。

## 1. 正式设计事实源

```text
Figma File: qmZEFvPrB8u9JX5fyqc93S
Page: 3957:2
```

`3957:2` 是“管理员配置”完整设计事实源。以下 Node 只是 MCP 精确读取、状态定位和 targeted visual review 的 Anchor，不是相互独立的业务页面：

| 业务域 | Node |
| --- | --- |
| 品牌与车型 | `7511:10359` |
| AI 模型 | `4804:15203` |
| TikHub | `7708:12501` |
| AI 分析规则 | `4804:15542` |
| 操作记录 | `4804:15700` |
| 报告策略默认态 | `7434:40097` |
| 报告策略唯一 Feature Owner | `7434:40096` |
| 权限、身份与数据来源规格 | `7127:33626` |
| 行为与状态规格 | `7127:33634` |
| 响应式开发验收 | `7127:34621` |

旧的 `4758:508 响应式验收 · 配置表单与审计表（未更新）` 不是现行实现基线。

## 2. 当前正式范围

当前 Web 实现六个真实 Tab：

```text
品牌与车型
AI 模型
TikHub
AI 分析规则
操作记录
报告策略
```

“报告策略”当前只实现前端准备面：选择本期/上期 `.xlsx`、填写报告日期范围、执行本地格式与日期校验、重置输入，并明确展示报告服务尚未接入。它不发送报告写请求，不生成假任务、假成功态或假飞书链接。

当前 Word 报告继续沿用既有离线报告链路；Figma 中的提交中、同步失败和成功结果是后端接入后的验收目标。正式 Web Report Job / API / Scheduler / Delivery Contract 建立后，必须从后端机器事实、generated client 和任务中心真实 read model 接通，不得用前端延时或永久 Mock 冒充。

## 3. 当前代码 Owner

- 路由与管理员可见性 → [`frontend/src/app/routes.ts`](../../frontend/src/app/routes.ts) 与 [`frontend/src/app/router.ts`](../../frontend/src/app/router.ts)；
- App Shell → [`frontend/src/app/layouts/AppShell.vue`](../../frontend/src/app/layouts/AppShell.vue)；
- 管理员配置页面组合 → [`frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue`](../../frontend/src/features/admin-configuration/pages/AdminConfigurationPage.vue)；
- 品牌与车型页面私有实现 → [`frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/CatalogConfigurationPanel.vue`](../../frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/CatalogConfigurationPanel.vue)；
- AI 分析规则页面私有实现 → [`frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/AnalysisSchemePanel.vue`](../../frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/AnalysisSchemePanel.vue)；
- 操作记录页面私有实现 → [`frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/AuditPanel.vue`](../../frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/AuditPanel.vue)；
- 报告策略页面私有 Feature Owner → [`frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/ReportStrategyPanel.vue`](../../frontend/src/features/admin-configuration/pages/AdminConfigurationPage/components/ReportStrategyPanel.vue)；
- Provider 配置唯一业务 Owner → [`frontend/src/features/admin-configuration/components/ProviderConfigurationPanel.vue`](../../frontend/src/features/admin-configuration/components/ProviderConfigurationPanel.vue)；
- 结构化标签唯一编辑 Owner → [`frontend/src/features/admin-configuration/components/AnalysisLabelsEditor.vue`](../../frontend/src/features/admin-configuration/components/AnalysisLabelsEditor.vue)；
- Feature API → [`frontend/src/features/admin-configuration/api.ts`](../../frontend/src/features/admin-configuration/api.ts)；
- HTTP 类型链 → [`frontend/src/generated/api/client.ts`](../../frontend/src/generated/api/client.ts)。

Figma MCP 返回的 React/Tailwind 代码只用于恢复设计结构；生产实现保持当前 Vue 3 + TypeScript + CSS/Design Token 技术栈，不引入 Tailwind、第二套 UI Library、第二套 API 或第二套状态管理。

## 4. 必须保持的真实系统边界

### 权限

`/admin/configuration` 继续只对 `administrator` 可达。前端 Route Guard 只负责交互，后端 Authorization 仍是最终守卫；不因为设计状态新增登录体系或绕过后端权限。

### 品牌与车型

- Brand Code、Vehicle Code 创建后保持稳定机器身份；
- Brand Alias 继续通过 Brand Alias API；
- Vehicle 品牌归属只由 Vehicle API 修改；
- 已引用实体的删除、停用、合并资格由当前 Contract/后端最终决定；
- 当前没有 Brand Merge Contract，不得从设计文案推导并新增前端假能力；
- Brand Code、Vehicle Code 继续保存在数据库与响应 Contract 中，但创建时由服务端生成，管理员不输入也不能修改；已创建 Code 仅在技术信息按需查看。

### Provider

AI 模型与 TikHub 继续复用同一个 Provider 配置业务 Owner：

- Secret/API Key 不回显；
- 测试连接只测试已保存配置；
- 有未保存修改时先保存再测试；
- 同一配置测试进行中禁止重复发起；
- 切换配置后迟到结果不能覆盖当前选择；
- Archive / Restore / Permanent Delete Eligibility 继续由当前正式接口决定；
- timeout、retry、concurrency、RPS 等高级参数仍属于当前 Contract。

### AI 分析规则

- Analysis Scheme = Prompt Template + voice types + sentiments + labels 的完整版本；
- 修改后先保存草稿，再发布；
- 发布、恢复、归档继续沿用当前版本冲突与审计规则；
- `无法分类 / 无法判断` 等必需兜底标签继续由结构化编辑器约束；
- Prompt 保持高级编辑路径，业务标签使用结构化编辑器；
- Figma 示例版本号、日期和规则名只用于排版。

### 操作记录

- 默认展示人类可读“谁在什么时候做了什么、影响了什么”；
- raw event/object/request ID 与 `safe_detail` 只在技术详情按需展开；
- 不新增当前 Contract 不支持的全库搜索；
- 当前 offset pagination 继续沿用正式 API。

### 报告策略

- 浏览器当前只验证文件扩展名与日期范围，不把 `.xlsx` 扩展名检查描述成工作簿内容已校验；
- 报告服务未接入时，主操作必须停止在明确的不可提交状态；
- 当前不得调用不存在的 API，不得在任务中心写入假任务，不得构造飞书文档或多维表格链接；
- 后续后端实现必须补齐真实任务、失败恢复、飞书同步结果和端到端持久化验收后，才能开放提交中、同步失败与成功状态。

## 5. 响应式与宽表格

基线：

```text
Sidebar 180px
Workspace 使用剩余宽度
页面水平 padding 24px
1440 为基准桌面
1180 为 Compact 验收
1920 为 Wide 验收
```

不能把 Figma Frame 写成生产固定宽高，也不能对整个页面做等比缩放。

### Wide

1440 / 1920 使用“资源列表固定或最小可读宽度 + 24px gap + 编辑区吸收剩余空间”。

### Compact

1180 使用纵向排列：

```text
资源列表
↓
编辑区
```

页面自身不能产生横向滚动。宽表格达到最小可读宽度后，只允许表格 Viewport 使用 `overflow-x: auto`；标题、刷新、分页和其它页面操作留在表格横滚容器外。

当前表格基线：

```text
品牌目录 / 车型目录：min-width 726px
操作记录：min-width 1176px
```

Audit 正式列宽参考：

```text
时间       160
操作人     110
操作       160
影响对象   210
操作说明   326
详情       210
```

## 6. 公共组件与 Feature 边界

继续复用现有公共 Owner：

- [`frontend/src/shared/ui/AimaButton.vue`](../../frontend/src/shared/ui/AimaButton.vue)
- [`frontend/src/shared/ui/AimaPageHeader.vue`](../../frontend/src/shared/ui/AimaPageHeader.vue)
- [`frontend/src/shared/ui/AimaFeedbackBanner.vue`](../../frontend/src/shared/ui/AimaFeedbackBanner.vue)
- [`frontend/src/shared/ui/AimaDialog.vue`](../../frontend/src/shared/ui/AimaDialog.vue)
- [`frontend/src/shared/ui/AimaModalContainer.vue`](../../frontend/src/shared/ui/AimaModalContainer.vue)
- [`frontend/src/shared/ui/AimaDrawer.vue`](../../frontend/src/shared/ui/AimaDrawer.vue)
- [`frontend/src/shared/ui/AimaIcon.vue`](../../frontend/src/shared/ui/AimaIcon.vue)

Brand Directory、Brand Detail、Vehicle Dialog、Scheme Version List、Audit Table 等业务组合保持在管理员配置 Page/Feature 内；只有真实跨 Feature 复用后才提升到 `shared`。

设计系统和代码组件不要求机械 1:1。Figma 的 Input、Select、Tab 等 Pattern 约束视觉语义，但本轮不能因此一次性重写全仓表单控件。

## 7. 验收证据

管理员配置 Design-to-Code 至少按以下链路验证：

```text
Fresh Figma Design Context / Screenshot
→ Browser Mock：6 个真实 Tab、报告前端边界、主要状态、Dialog、1180/1440/1920 Geometry
→ Lint / Typecheck / Unit / Build
→ 当前 required CI
→ Implementation ↔ Figma Conformance
```

Browser Mock 只证明前端可观察行为与请求语义，不冒充真实 Backend/PostgreSQL；本类纯前端同步如果 Contract、Backend 和 Persistence 没有变化，不机械扩大后端修改范围。

视觉复核重点：

- Brand Directory + Brand Detail/旗下车型层级；
- Brand/Vehicle 创建与编辑 Dialog；
- Provider 1440 Wide 与 1180 Stack；
- Scheme 268px 版本区 + 弹性编辑区；
- Structured Labels 的 40px 控件与兜底 Disabled 表达；
- Audit 1176px 局部横滚；
- Report 两份文件、日期范围、校验失败、重置和后端未接入状态；
- 页面自身无横向溢出；
- Loading / Empty / Error / Disabled 状态；
- Secret、技术标识和原始审计数据没有回到默认业务层。

只有代码验证和运行页面的 Figma Conformance 都有当前 revision 的新鲜证据后，才能描述为本轮 Design-to-Code 闭环完成。
