# 多人协作与 Change 自动归档

本文只说明 **AIMA_UGC 的多人协作机器接线和角色边界**。通用 Coding / Review / Testing / Git / Delivery 方法由 Agent_Skills 通过 [AGENTS.md](../../AGENTS.md) 取得，不在这里再写一套。

## 1. AIMA 的协作链

需要持久 Change 的任务，在 AIMA 中形成：

~~~text
Requirement / Issue
→ changes/active/<ID>/CHANGE.md
→ task branch
→ Implementation PR
→ current-head CI + Review
→ merge main
→ Change Archive Automation
→ changes/archive/YYYY-MM/<ID>/CHANGE.md
→ main-fresh / Acceptance / Issue Closure
~~~

不需要持久 Change 的轻量任务仍按当前治理完成 Requirement、验证和交付，但不会为了形式创建 Change。

## 2. 开发者负责到哪里

开发者在 AIMA 负责把当前 PR 做到可审查/可交付状态，包括：

- 关联正式 Requirement Source；
- 需要时建立 AIMA 顶层 Change carrier；
- 完成本次实现、测试和文档；
- 让 Change 满足项目 Completion Gate；
- push 当前 task branch 并保持 PR Head 与证据一致；
- 处理 Review finding 后重新提交同一 PR。

开发者不手工把 Active Change 移入 archive，也不为归档再开第二个 PR。

## 3. Maintainer 做什么

Maintainer 的项目动作很简单：

~~~text
审当前 PR / 当前 Head
→ 不满足：要求作者在原 PR 修复
→ 满足且 required checks 通过：merge Implementation PR
~~~

Review 的专业方法、Finding 分类和修复收敛遵守当前 Agent_Skills，不由本 Guide 定义。

## 4. AIMA Change Archive 的机器 Owner

机器入口：

- [.github/workflows/change-archive.yml](../../.github/workflows/change-archive.yml)
- [scripts/quality/archive_change_after_merge.py](../../scripts/quality/archive_change_after_merge.py)
- [scripts/quality/check_change_completion.py](../../scripts/quality/check_change_completion.py)

Workflow 从 merged PR 的 changed files 中只接受：

- 没有 Active Change → 明确 not-applicable；
- 恰好一个 Active Change → 可以确定性归档；
- 多个 Active Change → fail closed，不猜归属。

归档只允许改变同一 Change 的路径和生命周期字段，不修改产品代码、Migration、Docs、Workflow 或其他 Change。

## 5. 为什么归档不由开发者手工完成

AIMA 需要同时证明：

~~~text
哪一个 merged PR
→ 携带哪一个 ready_for_review Change
→ 该 Change 内容就是 merged revision 中的版本
→ 当前 main 没有被另一次修改抢先改变
~~~

所以由 repository-native automation 在 merge 事实发生后执行，比开发者提前把 Change 移到 archive 更可靠。

## 6. archive/done 不等于 Requirement 完成

archive/done 只表示：

> 这一次施工交付已经进入 main，施工记录已被冻结。

最终 Requirement / Issue 是否关闭仍取决于上游 Acceptance、implementation main-fresh、归档结果和当前治理要求的 Closure Evidence。

如果实现已经 merge，但 main-fresh 或后续 Closure 失败，不把原 Change 移回 active；修复或 Revert 建立新的工作单元。

## 7. 归档失败怎么办

归档失败时，Implementation merge 是历史事实，但 Closure 不能伪装完成。

先查：

- GitHub App / Environment 权限；
- merged PR changed files；
- Change 当前 main 内容是否漂移；
- 自动归档 Workflow 日志。

修复基础设施后，通过 Change Archive 的 workflow_dispatch 对原 merged PR 重跑。不要用手工 git mv、第二个 Archive PR 或 direct main commit 掩盖问题。

## 8. GitHub 权限边界

Change Archive 使用专用 AIMA Change Archivist 身份，只用于 Change lifecycle。它不是通用开发、Review、Release 或 Deploy 身份。

普通开发写权限也不自动等于 main bypass、Release、Deploy 或生产操作授权。

## 9. 想知道“我应该怎么和 AI 说”

用户只需要描述真实目标，例如：

~~~text
修复这个问题并提交 PR
~~~

或：

~~~text
评审 PR #123，通过后合并
~~~

Agent 应按 [AGENTS.md](../../AGENTS.md) 和当前 Agent_Skills 自行恢复 AIMA 的规则、事实和交付范围；已经由规则决定的分支名、Change carrier、验证路径等不应再机械反问用户。

本 Guide 只解释为什么 AIMA 最终会出现这些仓库对象，不要求用户手工执行 Git 命令。
