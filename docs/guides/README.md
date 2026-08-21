# AIMA_UGC 开发指南

`docs/guides/` 放**开发过程怎么做**的说明，不承担系统架构事实。

当前指南：

- [`前端与Figma工作流.md`](前端与Figma工作流.md)：页面如何从 Figma/原型进入 Vue 代码，哪些内容可以自动生成，哪些边界必须由代码和 Contract 决定。

文档分工：

```text
为什么系统这样设计       → docs/blueprint/
当前模块具体怎么实现       → 模块 README
专题运行、排障和深挖       → docs/appendix/
开发过程中怎么操作         → docs/guides/
历史为什么改过             → changes/archive/
精确字段/Schema/接口        → 代码、Migration、Contract、生成物、测试
```

指南同样遵守“先问题、再流程、再工具”的写法，不把工具名称本身当成设计理由。
