# 本地交付与临时资源

用户当前决定：完成修改并执行本地验证，先不合并远程 main。根开发分支 `feat/714-role-export-preferences` 保留供人工验收；Human Local Acceptance 为 PENDING。需求 #714 保持 open，没有以自动测试替代用户验收。

## 已核对的 Git 状态

- 起点及再次 fetch 的 `origin/main` 均为 `6f9779c56fdb3b4d3a83d8fb0cdd02e4cb9dd79d`。
- 实现与测试 checkpoint 已形成可独立审查的本地提交；未 push、未创建 PR、没有远程 CI 或 merge 记录。
- 两个隔离实现 worktree 在工作区干净、`git cherry HEAD <branch>` 每项均为已整合补丁后移除，临时分支 `feat/714-role-api-tests` 和 `feat/714-role-ui` 已删除；根任务分支没有删除。
- 未发布 Release、部署、执行生产 Migration 或操作生产数据。

## 已完成的临时资源清理

- Full-stack 的本机 Fake LLM、生产 API 测试进程及 Worker：先核对精确命令行和父子进程关系，再停止任务进程；8090/8091/8092/8093、4173/4174 没有遗留监听。
- Reporting 专属 PostgreSQL 容器 `aima-ugc-714-report-tests-20261010`：核对完整容器 ID、`aima.task=714`、AutoRemove、无用户 bind/显式 named mount；镜像默认匿名 volume 仅该容器使用。停止后容器与匿名数据卷均已移除。
- 任务工具误生成的嵌套 `AIMA_UGC/.agents/changes/...`：确认仅含本任务重复占位文件后移除，没有触碰正式根 `.agents` 或顶层 `changes`。
- 本轮 `frontend/dist` 与 `frontend/test-results`：确认位于 workspace 内、无外部链接、无 Git 受控文件后清理。

- 主 PostgreSQL 测试容器 `aima-ugc-714-tests-20261010`：独立测试者交回前确认随机诊断子库、活动连接、runner/探针进程均为零；Parent 再核对完整容器 ID、当前 task 标签、AutoRemove、无用户 bind/显式 named mount及匿名卷仅该容器使用，停止后容器和匿名卷均已移除。
- `.task-tmp`：独立 Review 读完最后直接日志、正式证据保存且测试 Agent 终态交回后清理。唯一 junction 为存储安全测试创建、链接和目标均在该任务目录内；先不递归移除链接本身，再核对无在用进程/附属 worktree/其他链接，删除任务 Source 克隆、临时 Secret、日志和测试数据。

最终只保留源码、测试、正式文档和本 Change 的精简审计证据，项目依赖环境继续保留。临时脚本/原始日志已经清理，精确结果组合、失败历史、修复与环境边界由本 Change 证据和对应生产测试维护，不将精简记录冒充一次全套全绿。
