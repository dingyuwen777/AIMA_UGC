# AIMA_UGC 开发指南

docs/guides/ 只放**开发者或协作者在 AIMA 项目里怎么操作**的说明。

通用 Analysis / Coding / Testing / Review / Figma / Git / Delivery 方法继续由 Agent_Skills 通过 [AGENTS.md](../../AGENTS.md) 的项目治理入口取得；Guide 只解释 AIMA 自己的技术栈、目录、Figma 文件、脚本、Workflow 和协作接线。

## 当前指南

1. [docs/guides/01_Figma与前端设计开发工作流.md](01_Figma与前端设计开发工作流.md)：AIMA Figma 与 Vue / Generated Client / Feature Owner 的项目接线；
2. [docs/guides/02_管理员配置Figma开发基线.md](02_管理员配置Figma开发基线.md)：管理员配置正式节点与代码 Owner；
3. [docs/guides/03_Windows_Docker_Desktop_Compose运行.md](03_Windows_Docker_Desktop_Compose运行.md)：Windows Docker Desktop 完整 Runtime；
4. [docs/guides/04_Docker国内构建源与本地重置.md](04_Docker国内构建源与本地重置.md)：镜像/包下载通道、缓存和项目级重置；
5. [docs/guides/05_多人协作与Change自动归档.md](05_多人协作与Change自动归档.md)：AIMA 的 Requirement / Change / PR / 归档机器接线；
6. [docs/guides/06_本地Release离线包构建.md](06_本地Release离线包构建.md)：Windows 本地生成和验证离线 Release Bundle；
7. [docs/guides/07_采集运行中心Figma开发基线.md](07_采集运行中心Figma开发基线.md)：采集运行中心正式 Figma Owner 链和 Design-to-Code 基线。

## Guide 不承担什么

Guide 不保存动态 Stage/PR/SHA、完整 API/Schema/Job 集合、通用 Agent_Skills 方法、已批准但未完成的产品路线或一次 Migration 的永久历史证据。

这些内容分别回到机器事实、Agent_Skills、Roadmap 或 [changes/archive/](../../changes/archive/)。

## 临时 Guide 的退出

只服务一次安装、迁移、升级或工具过渡的 Guide，在过程退出后要把仍有效知识迁入长期 Owner，再删除临时文档；操作文档不能只增不减。
