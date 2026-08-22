---
schema: rvc-change/v1
id: CHG-20260822-reusable-continuation-prompt
title: 固化持续开发与上线通用提示词
level: L2
status: in_progress
owner: dingyuwen777
branch: docs/reusable-continuation-prompt-20260822
created: 2026-08-22
updated: 2026-08-22
depends_on: []
affected_areas:
  - documentation
  - development_workflow
  - roadmap_navigation
affected_paths:
  - docs/guides/AIMA持续开发与内网上线通用提示词.md
  - docs/guides/README.md
  - docs/roadmap/README.md
contracts: []
data_changes: []
---

# 目标

为 `dingyuwen777/AIMA_UGC` 固化一份可以在未来新会话中反复复制使用的通用提示词，使 Agent 能根据仓库当前真实状态，自动判断并继续下一最小正式开发单元，持续推进：

```text
Stage 8F 前后端闭环
→ Internal V1-A 最小部署环境
→ Internal V1-B 公司服务器真实部署与 Smoke
→ 公司内网 V1
→ 后续 Production Hardening
```

提示词不能把某个 SHA、PR、分支或“当前正在 Stage 8F”写成永久事实，而必须强制每次从当前 `main`、Active Change、Roadmap、Contract、代码和测试重新恢复状态。

# 范围

- 新增一份仓库内长期保存的通用提示词 Guide；
- 在 Guide README 与 Roadmap README 增加固定入口；
- 明确未来每个新会话的 Git/CI/Change/PR/合并/归档工作流；
- 保留当前已批准的内网 V1 范围，但要求以后以当前 `main` 的更新正式决策为准。

# 非目标

- 不修改运行时代码；
- 不修改 HTTP Contract、Schema、Migration 或依赖；
- 不在本 Change 中开始 Stage 8F 代码开发；
- 不执行公司服务器部署；
- 不修改 `AGENTS.md` 的统一规则正文；
- 不把历史 SHA 或当前 PR 状态固化进通用提示词。

# 必须保持不变

- `AGENTS.md` 仍是统一入口，并由通用提示词强制每次先读；
- Reliable Vibe Coding 的 Change / CI / PR / Branch Protection 门禁不降低；
- 当前代码、Contract、Migration、generated、tests 和锁文件仍是精确机器事实；
- 后续 Agent 不得从聊天或提示词猜实现；
- 用户已确认的首版延期范围不能被后续 Agent 静默恢复为内网 V1 阻塞项。

# 已确认关键决策

通用提示词必须满足：

1. 每次重新读取当前 `main/AGENTS.md`、Skill、Blueprint 导航/门禁、Roadmap、代码导航和相关机器事实；
2. 先检查 Active Change、开放 PR、CI 和当前 `main`，未闭环单元优先完成；
3. 默认每个会话只完成一个可独立验收的最小正式单元；
4. 用户通过该通用提示词授权当前单元按正常分支/PR/CI 流程完成后合并 `main`，并在合并后归档 Change；不得直接绕过门禁写 `main`；
5. 到 Internal V1-B 时，只有工具环境和仓库事实足以确定目标服务器/部署方式时才执行真实部署；不能猜服务器地址、凭据或网络；
6. 如果存在真正需要用户决定的新上游业务/安全语义，按 `AGENTS.md` 用户决策门禁处理；已经固化的决定不重复询问；
7. 完成一个单元后同步 Roadmap，使同一提示词在下一会话可以自然继续。

# 成功标准

- [x] 新增可直接复制使用的通用提示词文档；
- [x] 提示词不包含需要长期维护的 SHA/PR/当前 Stage 完成状态；
- [x] 提示词明确仓库事实恢复顺序、Active Change/PR/CI 判断、单元执行、验证、合并和归档；
- [x] 提示词与当前内网 V1 路线和长期 Production Roadmap 一致；
- [x] Guide README 与 Roadmap README 都能导航到该提示词；
- [ ] 当前 PR 最新 HEAD 的仓库 CI/专项 Workflow 全部通过；
- [ ] PR 合并后归档本 Change。

# 验证计划

这是纯文档/开发工作流 Change，TDD 不适用。验证：

- 仓库 docs/架构质量门禁；
- 链接和路径可解析；
- 通用提示词人工逐条对照 `AGENTS.md`、Reliable Vibe Coding、内网 V1 Roadmap 与完整 Production Roadmap；
- 当前 PR HEAD 的完整仓库 CI 与专项 Workflow。

# Git / PR

- 分支：`docs/reusable-continuation-prompt-20260822`
- 当前状态：`in_progress`
- PR：待创建
- Merge：仅在最新 HEAD 门禁成功后通过 PR 合并
- 归档：PR 实际合并后进行
