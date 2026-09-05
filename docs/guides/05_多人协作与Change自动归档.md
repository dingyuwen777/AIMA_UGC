# 多人协作与 Change 自动归档

本文说明 AIMA_UGC 在多人使用 Agent_Skills 开发时，代码提交、Review、main 合并、Change 归档和 Requirement Closure 的实际职责边界。

精确机器事实以以下入口为准：

- [`scripts/quality/check_change_completion.py`](../../scripts/quality/check_change_completion.py)
- [`scripts/quality/archive_change_after_merge.py`](../../scripts/quality/archive_change_after_merge.py)
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
- [`.github/workflows/change-archive.yml`](../../.github/workflows/change-archive.yml)
- 当前 GitHub Ruleset / App / Environment 配置

其中 Requirement Traceability / Completion Audit 已由 [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) 的 CI Core 承担；不再维护独立 Completion Workflow。

## 1. 目标

普通业务变更只需要一个 Implementation PR 和一次有意义的 Maintainer merge：

```text
Requirement / Issue
→ changes/active/<ID>/CHANGE.md
→ 开发 / 测试 / 文档 / Completion Audit
→ status: ready_for_review
→ Implementation PR Ready
→ Maintainer Review
├─ CHANGES_REQUIRED → Change 继续 active，作者修复后 re-review
└─ PASS → merge Implementation PR 一次
           ↓
           Change Archive Automation
           ↓
           active/<ID> → archive/YYYY-MM/<ID>
           ready_for_review → done
           ↓
           implementation main-fresh + archive governance fresh
           ↓
           Closure Audit / Acceptance 回写 / Issue close
```

不再为普通任务创建第二个 Finalization/Archive PR。

## 2. 开发者负责到哪里

团队成员使用 Agent_Skills 开发时，正常请求是：

```text
修复这个功能，然后提交 PR
```

开发者负责：

- 建立/复用 Requirement Source；
- 建立需要的持久 Change；
- Coding / Testing / Docs；
- Requirement Traceability、Validation Matrix、Completion Audit；
- 把 Change 做到 `changes/active/...` + `status: ready_for_review`；
- push / PR / current-head CI；
- 把 PR 交付到 Ready。

开发者**不负责**：

- 把 Change 手工移入 `archive/`；
- 将 Change 手工改为 `done`；
- 为归档再创建第二个 PR；
- 在没有 main delivery authority 时自行合并 main。

普通 PR 如果尝试 `active → archive`，`Requirement Traceability and Completion Audit` 会失败。

## 3. Maintainer Review

Maintainer 可以人工 Review，也可以使用 Agent_Skills：

```text
评审 PR #<number>，通过后合并
```

Review 不通过：

```text
Change 保持 active/ready_for_review
→ 原作者修复
→ push 新 head
→ re-review
```

Review 通过：

```text
确认 current Requirement / current head / current base / required checks
→ merge Implementation PR
```

Maintainer 不需要手工修改 Change 目录。

## 4. merge 后自动归档

`Change Archive` Workflow 监听合并到 `main` 的 PR，也支持 `workflow_dispatch(pr_number)` 重跑。

自动化从 merged PR 的 changed files 中定位：

```text
changes/active/<CHANGE_ID>/CHANGE.md
```

规则：

- 没有 Active Change：明确 `not_applicable`，不为形式创建 Change；
- 恰好一个：允许继续；
- 多个：fail closed，不猜哪一个属于本次交付；
- merged PR 的 `merge_commit_sha` 必须属于当前 main 历史，且当前 Active Change 内容必须与该 merged revision 完全一致；后续 main 若改写同一 Change，则 fail closed，不归档错误版本；
- 当前 main 上 source 与 target 同时存在：fail closed；
- source 不存在、合法 archive 已存在：只有 archive 可由该 merged revision 按同一 lifecycle 冻结结果精确重建时才幂等 no-op；
- source 为 `ready_for_review`：只允许把 `status` 改为 `done`、把 `updated` 改为 merge 的北京时间日期并移动目录；
- 其他正文、产品文件、Migration、Docs、Workflow、其他 Change 都不能被归档程序修改。

归档 commit 由专用 `AIMA Change Archivist` GitHub App 身份直接写入 main。该身份只用于 Change lifecycle 基础设施，不承担产品开发、Review、Release 或 Deploy。

## 5. archive 不等于 Requirement 完成

`archive/done` 表示：

> 这一次施工交付已经真实进入 main，并且施工记录已经冻结。

它不表示：

> 整个 Issue 的所有 Acceptance Criteria 已经最终满足。

最终 Requirement 完成仍然需要：

```text
Implementation merge revision
+ 该 revision 的 required main-fresh Evidence
+ Change archive 成功
+ archive revision 的 required governance fresh Evidence（当前项目要求时）
+ Closure Audit
+ Acceptance 状态回写并重读
+ Issue close 并重读
```

如果 main-fresh 失败，已经发生的 merge/archive 保持历史事实，Issue 继续 open；修复或回滚建立新的工作单元，不把旧 Change 移回 active。

## 6. 归档失败

归档 Workflow 失败时：

```text
Implementation merged     ✓
Change archive             ✗
Requirement Closure        STOP
```

不能让 Agent 为了“完成任务”自行接管 `git mv` / direct main commit 来掩盖基础设施故障。

先修复权限、配置、并发漂移或 Change 数据问题，然后从 GitHub Actions 手工运行 `Change Archive`，填写原 merged PR 编号重试。

## 7. GitHub 权限边界

仓库平台层负责“谁能更新 main”，Agent_Skills 负责“当前 Agent 在已授权范围内怎样可靠工作”。两者不能互相替代。

归档自动化所需的 GitHub App 凭证只放在 `change-archive-main` Environment 中；仓库源码不保存私钥或个人 Token。普通开发者不得因为拥有 Write 权限而进入 main 更新 bypass；归档 App 也不得被当作通用开发身份使用。
