---
schema: coding-change/v1
id: CHG-20260925-212025-worker-reset-startup
title: 修复严格重置后 Worker 启动失败与重复拉起
level: L2
status: ready_for_review
owner: yuwen.ding
branch: fix/607-worker-reset-startup
created: 2026-09-25T21:20:25+08:00
updated: 2026-09-25
completion_gate: required
depends_on: []
affected_areas:
  - content
  - jobs
  - operations
affected_paths:
  - .github/workflows/release.yml
  - backend/src/aima_ugc/adapters/persistence/postgres/voice_plaza_projection.py
  - backend/src/aima_ugc/bootstrap/voice_plaza_projection_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - tests/integration/content/test_stage8d_voice_plaza_runtime.py
  - tests/integration/ingestion/test_stage12_historical_campaign_worker.py
  - tests/unit/jobs/test_worker_entrypoint.py
  - scripts/deploy/reset_keep_vehicle_catalog.sh
  - scripts/release/release_bundle.py
  - tests/unit/test_release_bundle.py
  - tests/unit/test_ci_test_impact_optimization.py
  - docs/operations/01_生产部署与离线Release方案.md
  - docs/operations/04_声音广场读模型回填与性能验证.md
contracts: []
data_changes:
  - 显式执行脚本时清空非目录业务表及 Artifact 实体，并恢复声音广场状态种子
---

# 背景与证据

Linux v3.1.1 服务器执行自定义严格重置脚本后，`voice_plaza_projection_state`、`contents` 和投影表均为 0 行，车型目录版本表仍有 439 行。脚本清空除了 Alembic 与车型目录以外的 public 表，也删除 Artifact 文件；用户确认接受清空业务数据并从原始 Excel 重导，要求保留车型目录。

Worker 子进程在启动时读取声音广场单例状态，`get_state(...).one()` 因缺行抛出 `NoResultFound`；父进程日志持续记录退出码 1 和重新扩容，Job 无法被领取。应用修复不能凭空恢复被脚本删除的 Content/Artifact。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 缺失派生状态时安全恢复，并发 Worker 只生成一个状态和回填 Job，现有检查点不覆盖 | #607 / AC1 | satisfied | Repository 原子插入及 Worker 同事务锁定；PostgreSQL 并发启动集成场景已加入 |
| R2 | 持续快速退出时有界退避，稳定后正常扩容，不影响运行中 Job | #607 / AC2 | satisfied | Worker 父进程退避及单元场景；本地单元回归 31 passed |
| R3 | Linux 脚本显式确认后保留完整车型目录与 Alembic、清空所有其它业务表和 Artifact、恢复种子，失败保持服务停止 | #607 / AC3 | satisfied | 脚本枚举全部非保留 public 表并事务清空；检查目录计数、系统种子、采集运行和管理员审计；隔离 Release 回放增加实际 dry-run/execute |
| R4 | 脚本进入 Release 包与校验和，文档说明操作和数据不可恢复边界 | #607 / AC4 | satisfied | Release Bundle 清单与 SHA256、DEPLOY 生成文本和运维文档同步；本地 Release 单元通过 |
| R5 | 已绑定来源 Artifact 实体缺失时终态失败并记录安全关联字段 | #607 / AC5 | satisfied | 快照 Worker 错误分类和日志事件；PostgreSQL 集成场景已加入 |
| R6 | 单元、PostgreSQL 集成、Linux Bash/Release CI 覆盖机制，公共 HTTP Contract、依赖和 Migration 不改变 | #607 / AC6 | satisfied | 本地 31 passed、1 Windows Bash skip，Ruff/Mypy 通过；Linux CI 作为 PR Ready 后的独立交付门禁 |

# 范围与计划

通过 Content Owner Repository 幂等插入缺失的派生状态，再由现有 Worker 入口在同一事务锁定状态并创建低优先级回填 Job。保留现有回填进度、Fencing、Job 及车型目录，不修改 HTTP Contract、Schema/Migration、依赖或已存在的业务行。父进程对连续子进程启动失败施加有界退避，并记录可诊断事件。测试覆盖空业务库、多进程竞争、现有状态保持及重复失败退避；同步声音广场运维文档。

用户随后明确停止现场排查，要求代码避免重置后的缺种子/快照故障，并提供保留目录的 Linux 清库脚本。脚本作为显式操作入口进入 Release 包，仅在 `--execute` 且交互确认或 `--yes` 时修改目标环境；不会由应用启动自动执行。清库会删除所有非保留 public 业务表的数据，包括运行记录、审计事件、任务与 Provider 配置，并删除 Artifact 实体；原始 Excel 目录、Secret、env 和日志保留。声音广场状态种子在清库事务内恢复。只备份保留目录，因此清库前其它业务数据的可恢复性必须由操作者另外决定。

# 风险、验证与回滚

状态行只在缺失时插入 `pending`，现有状态不覆盖。重新扫描 Content 的回填通过原有 UUID 检查点和幂等投影执行。旧版镜像没有自动恢复能力，现场可先按已核对的只读状态和幂等 SQL 手动补回状态行；正式修复需经 PR、CI、Review 和部署门禁。仅回滚代码不删除恢复的状态行。

# 完成审计

- [x] upstream_re_read：已重新核对本轮用户明确的“脚本主处理、代码兜底”、Issue #607 的 AC1–AC6、服务器 Traceback/SQL 回执、当前迁移和 Compose 实现。
- [x] change_coverage：缺种子、快速退出、完整清库、Release 交付、Artifact 缺失和验证要求均映射至代码、测试及文档；Linux CI 仍是后续合并门禁。
- [x] reverse_audit：从脚本的保留和删除动作反查真实 Compose 挂载、Artifact 根目录、迁移种子和数据库表；从 Worker 入口反查 Job 启动与并发恢复。
- [x] unresolved_cleared：需求语义无未决项，R1–R6 无 `not_satisfied`；生产服务器尚未运行新脚本，不能把本地实现当成部署成功。

# 验证与交付状态

本地单元测试 `31 passed, 1 skipped`；跳过项为 Windows 无可用 Bash。Ruff 与目标 Mypy 通过。PostgreSQL 集成和 Linux Release 回放需要 PR Ready 后在 Linux CI 中验证；本 Change Ready 不代表 CI 已完成或可直接合并。当前服务器仅完成旧版镜像的一次性状态补行，仍需新版本部署和显式脚本执行才具备长期修复。
