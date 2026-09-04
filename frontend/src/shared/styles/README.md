# Shared Styles

`frontend/src/shared/styles/` 是跨页面视觉语义的代码 Owner。业务页面可以组合这些能力，但不要重新维护平行的全局字号、断点或页面缩放体系。

## 文件职责

- [`tokens.css`](tokens.css)：颜色、间距、圆角、Semantic Typography、Density 与 Layout Token。
- [`responsive.css`](responsive.css)：跨页面桌面端 reflow、overflow、Overlay 安全边界，以及历史页面 raw px 向 semantic token 收口的兼容层。

## 桌面端响应式基线

AIMA 当前正式桌面视觉以 `1440×900` 为锚点，但生产代码不得固定整页宽高。

```text
< 1180      窄窗口 / 浏览器高缩放下的可访问 reflow，不宣称完整 Mobile UI
1180–1279   Compact Desktop
1280–1599   Standard Desktop；1440 是正式视觉锚点
1600–1919   Large Desktop
>= 1920     Wide Desktop；字体、控件和留白只做有上限的渐进调整
```

原则：

1. 不使用 `transform: scale()`、整页 zoom 或纯 `vw` 字号模拟“自动缩放”。
2. Typography 使用 `clamp(min, fluid, max)`；1440 保持既有基线，小桌面守住最小可读字号，大屏达到上限后停止放大。
3. 空间不足优先由 `flex/grid` reflow、wrap、`minmax()` 和局部横向滚动解决，不继续缩小文字。
4. 普通页面不应产生整页横向滚动；具有真实二维语义的数据表可以在自己的容器内横向滚动。
5. Drawer/Dialog 使用设计首选宽度，但必须受当前 viewport safe margin 约束。
6. Shared UI 和新页面优先直接消费 semantic token。[`responsive.css`](responsive.css) 中针对旧页面 class 的规则只承担迁移兼容，不应成为新页面继续写 raw `9px/10px` 的理由。
7. Browser Zoom、系统缩放和 CSS viewport 是不同概念；不要使用 `devicePixelRatio` 决定字体大小。

## Semantic Typography

主要 token：

```text
--aima-font-size-page-title
--aima-font-size-section-title
--aima-font-size-card-title
--aima-font-size-body
--aima-font-size-control
--aima-font-size-body-small
--aima-font-size-caption
```

业务正文、表单和用户操作文本不新增低于 `caption` 的项目级字号。确有极特殊密度要求时先证明其语义和可访问性，而不是在业务页面新增 `9px/10px`。

## 验证

响应式修改至少复用现有 Playwright/Build 能力检查：

- 1440 正式 geometry/design 基线；
- Compact 与 Wide 代表性 viewport；
- 无非预期整页横向 overflow；
- Filter/Toolbar reflow；
- Table 局部 overflow；
- Drawer/Dialog safe margin；
- 页面标题和 semantic font 在宽屏只有限度增长；
- `lint`、`typecheck`、相关 unit/e2e、production build。