# AIMA_UGC docs/ 本地规则

本文件只适用于 docs/ 及其子目录，是根 [AGENTS.md](../AGENTS.md) 的文档 Overlay。AIMA 继续使用 Agent_Skills 的通用 Docs / Coding / Review 等治理；这里仅维护 AIMA 文档树自己的 Owner、命名、生命周期和知识迁移规则。

## 1. Owner Gate

新建、拆分、合并或大改文档前，先确定目标读者的问题属于哪个 Owner：

- 产品当前能力 → [docs/product/](product/)
- 长期架构与技术决定 → [docs/blueprint/](blueprint/)
- 已批准未完成事项 → [docs/roadmap/](roadmap/)
- 正式运行/部署/迁移操作 → [docs/operations/](operations/)
- 平台实现差异 → [docs/collection/](collection/)
- 专题实现/限制/调试 → [docs/appendix/](appendix/)
- 开发/协作操作 → [docs/guides/](guides/)

如果已有 Owner 能承担，就修改现有 Owner 或增加导航，**不要为同一事实再建一篇平行说明**。

精确 Route、字段、表、Migration、依赖、生成物、枚举全集等已有机器 Owner 时，Markdown 只解释语义与定位，不手工维护完整镜像。

通用 Agent_Skills 方法不复制进 AIMA 文档。AIMA 只保留项目 Overlay、仓库接线和项目事实。

## 2. 技术文档文件名规范

- 每个长期目录保留一个 README.md 作为导航和职责边界；
- 顺序型长期文档使用两位数字前缀，例如 01_、02_；
- 文件名描述读者任务或长期主题，不使用 PR、临时日期或“最终版/新版”等易失效名字；
- 已有稳定路径除非职责确实变化且迁移收益明确，否则优先原路径内重构，避免无意义链接迁移。

## 3. 单一解释 Owner

允许多个文档引用同一事实，但只允许一个文档完整解释。其他位置只保留必要上下文和唯一 Owner 链接。

不要复制第二套：

- Agent_Skills 通用治理规则；
- OpenAPI Route/字段全集；
- Schema/表/索引全集；
- Worker Registry；
- 生成 Client；
- 动态 Stage/PR/CI 状态；
- 没有核验日期的供应商价格/能力快照。

## 4. 知识迁移门禁

删除、合并或大幅缩短文档前，逐项判断旧内容：

~~~text
仍是当前长期知识
→ 迁到正确 Owner

已经有机器事实 Owner
→ 删除手抄镜像，保留必要解释/链接

已批准但尚未完成
→ Roadmap

只是候选/建议
→ 明确标记为评估材料；未批准不得进入 Roadmap

只属于历史施工/验收
→ changes/archive / Git

已失效且无历史解释价值
→ 删除
~~~

没有完成上述映射时，不得只为了“目录变干净”删除知识。

## 5. Live 文档退出

- Roadmap 完成：长期知识迁移后删除 live Roadmap；
- 临时 Migration/回填/升级手册：最后一个目标环境退出该过程后，把长期操作知识并入正式 Owner，再删除临时文档；
- 历史证据不回填到 Current 文档形成流水账。

## 6. 导航与验证

仓库内具体文件承担定位/验证职责时，使用完整仓库相对路径作为链接文字，并确保链接可点击。

修改完成后至少验证：

- 本地链接存在；
- 机器事实入口真实；
- 没有复制 Agent_Skills canonical Reference 路径作为 AIMA 本地事实；
- 没有把待实现/候选写成当前能力；
- 没有因删文档造成知识无 Owner；
- 适用的文档事实与导航检查通过。
