# AIMA_UGC Operations

docs/operations/ 承担：**已经存在的运行/部署/迁移能力怎样安全操作，以及真实生产动作需要满足哪些当前门禁。**

它不定义未来产品路线；尚未完成、但已经批准的目标由 [docs/roadmap/](../roadmap/) 负责。

## 当前运行文档

1. [docs/operations/01_生产部署与离线Release方案.md](01_生产部署与离线Release方案.md)：Docker/Compose、Host Root、Secret、离线 Release、发布/回滚边界；
2. [docs/operations/02_4000万历史迁移与Analysis Run运行手册.md](02_4000万历史迁移与Analysis%20Run运行手册.md)：Data Import Campaign、Persistent Canonical Replay、Historical Fill Only、容量验证、迁移对账与手动 Analysis Run；
3. [docs/operations/03_内容重分类与Legacy_Cleanup运行手册.md](03_内容重分类与Legacy_Cleanup运行手册.md)：内容重分类与 Legacy Cleanup 的 fail-closed 操作；
4. [docs/operations/04_声音广场读模型回填与性能验证.md](04_声音广场读模型回填与性能验证.md)：当前仍需要的声音广场读模型部署后回填与验证步骤。

## Operations 与 Roadmap 的区别

“代码已经有了，我现在怎样安全执行？”属于 Operations；“还有哪些批准的门禁没有完成？”属于 Roadmap。

同一个状态不要两边完整维护。Operations 可以说明执行前必须满足某个 Roadmap Gate，但完成状态仍由 Roadmap / 正式环境证据持有。

## 运行手册的内容边界

长期 Operations 优先保留：前置条件与授权、可执行入口、正常路径、观察与对账、失败边界、恢复/回滚、精确机器事实位置。

不复制架构原理、完整 Schema、完整 API 或历史 PR/CI 流水。

## 临时 Migration / 回填手册必须退出

当最后一个需要该过程的目标环境完成后：

1. 把仍长期有效的操作知识合并到正式 Operations / Appendix Owner；
2. 把本次执行、验收、异常和 SHA 证据留在 [changes/archive/](../../changes/archive/) 与 Git；
3. 删除该临时 live 文档。

因此 docs/operations/ 不是“每做一次 Migration 永久加一篇”的归档目录。
