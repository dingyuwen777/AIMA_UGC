# AIMA_UGC 开发指南

`docs/guides/` 放**开发过程中怎么操作**的说明，不承担数据库 Schema、API 字段或业务表的精确机器事实。

当前指南：

- [`01_Figma与前端设计开发工作流.md`](01_Figma与前端设计开发工作流.md)：Figma/原型怎样进入 Vue 代码、设计资产怎样组织、哪些内容可以自动化、哪些边界必须由当前 Contract 和代码决定。
- [`02_AIMA持续开发与内网上线通用提示词.md`](02_AIMA持续开发与内网上线通用提示词.md)：用于新的 ChatGPT/GitHub Coding Agent 会话；固定提示词本身不保存 SHA、PR 或当前 Stage 状态，而是要求每次从当前 `main`、Active Change、Roadmap 和机器事实重新判断下一最小正式单元，持续推进 Stage 8F、内网 V1 和后续 Production Hardening。

如果目标不是“设计页面”，而是“我应该改哪个代码文件”，先读：

- [`../01_代码结构与修改导航.md`](../01_代码结构与修改导航.md)

如果目标是“在新会话继续当前开发并最终推进到内网上线”，直接复制：

- [`02_AIMA持续开发与内网上线通用提示词.md`](02_AIMA持续开发与内网上线通用提示词.md)

提示词只是**启动工作流的入口**，不替代当前仓库事实。真正的阶段状态和下一步仍由：

- [`../roadmap/01_内网V1上线实施计划.md`](../roadmap/01_内网V1上线实施计划.md)
- [`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)
- 当前代码 / Contract / Migration / generated / tests / locks

共同决定。

文档分工：

```text
为什么系统这样设计       → docs/blueprint/
当前模块具体怎么实现       → 模块 README
专题实现、排障和深挖       → docs/appendix/
开发过程中怎么操作         → docs/guides/
历史为什么改过             → changes/archive/
精确字段/Schema/接口        → 代码、Migration、Contract、生成物、测试
```

指南同样遵守“先问题、再流程、再工具”的写法。工具名称本身不是设计理由；例如是否用 Figma，要由页面复杂度、长期维护、设计资产复用和当前前端代码结构决定。
