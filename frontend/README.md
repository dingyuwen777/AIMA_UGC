# AIMA_UGC 前端开发入口

当前前端是一个 Vue 3 + TypeScript + Vite + Pinia + Vue Router SPA。正式业务路由包括：

```text
/collection-runtime  采集运行中心
/voice-plaza        声音广场
```

根路由继续保留为兼容入口，并组合同一个 `CollectionRuntimePage`，不维护第二份业务页面。

## 目录与 Owner

```text
src/app/layouts/                         App Shell 与应用级布局
src/features/import-batches/pages/CollectionRuntimePage/  页面组合与页面私有组件
src/features/import-batches/api.ts       只包装生成 Client 和统一错误
src/features/import-batches/store.ts     列表、筛选、详情、上传和轮询状态
src/features/voice-plaza/                Content 查询、详情、显式 Analysis 与 durable Export
src/shared/styles/tokens.css              全局 Design Token 与最小 reset
src/generated/api/                       OpenAPI → Orval 生成物，禁止手改
```

页面组件使用 Vue SFC：业务样式写在各 `.vue` 文件的 `<style scoped>` 中；全局 CSS 只保存语义 Token
和基础 reset。不要建立与 Vue 平行的页面 CSS、API Client 或 Store。未来按正式 Figma 改版时，优先替换
Page、页面私有组件和 Token，不改变 Pydantic/OpenAPI、生成 Client、Feature API、Store 业务语义和 E2E
行为断言，除非产品语义本身已经通过新 Change 批准变化。

## 视觉基线与 Element Plus

Stage 8C 经用户批准，以
`docs/assets/stage8c/collection-runtime-center-prototype.png` 作为一次性桌面视觉基线；该例外及资产
SHA-256 记录在对应归档 Change。Stage 8D 同样经用户批准，以 `docs/assets/stage8d/` 下列表/详情图作为
一次性声音广场视觉基线，精确哈希和例外边界记录在 Stage 8D Change。后续正式 Figma Frame 建立后，
应按 Blueprint 16 的 Design-to-Code 流程
接管视觉事实源，不能让 PNG 与 Figma 长期形成两套未标明优先级的设计。

Element Plus 仍是仓库长期基础控件技术方向。但当前锁定的 Element Plus `2.14.4` 按组件导入时，会在
锁定的 TypeScript 7 原生检查和 `skipLibCheck=false` 下产生其依赖声明错误。Stage 8C 不升级依赖、不
关闭类型门禁，首屏因此使用 Vue SFC 内的原生语义表单/按钮/表格并保持 Feature 边界；这不是新建第二套
控件库。依赖兼容性应通过独立技术 Change 解决，不能在页面改版时静默升级或降低类型检查。

## 生成 Client

公共 HTTP Contract 变化后，从仓库根执行：

```bash
uv run python scripts/contracts/generate.py
npm --prefix frontend run generate:api
uv run python scripts/contracts/generate.py --check
```

页面和 Feature 不得手写 `/api` URL 或复制生成类型。

## 本地运行与验证

后端已在 `127.0.0.1:8090` 运行并准备好 PostgreSQL、Artifact 和 Secret 后，从仓库根执行：

```bash
npm --prefix frontend run dev
```

Vite 固定监听 `127.0.0.1:5173`，并把 `/api` 与 `/health` 代理到后端。

提交前执行：

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Vitest 使用生成 Client Mock 验证 Feature API/Store；Playwright 使用固定 Contract 形状的网络 Mock 验证
采集运行中心和声音广场页面、详情 Drawer、上传、显式 Analysis 与 durable Export Job。Playwright 固定使用独立开发端口 `4173`，避免与本地联调/CI smoke
的 `5173` 进程互相复用或抢占。它们不替代后端 API、PostgreSQL、Worker 或 Fencing 集成测试。
