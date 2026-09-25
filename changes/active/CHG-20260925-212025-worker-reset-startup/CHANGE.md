---
schema: coding-change/v1
id: CHG-20260925-212025-worker-reset-startup
title: 修复严格重置后 Worker 启动失败与重复拉起
level: L2
status: in_progress
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

| ID | 上游要求 | 状态 | 实现与验证 |
| --- | --- | --- | --- |
| R1 | 空业务库保留车型目录后 Worker 能启动、继续处理新导入 Job | not_satisfied | 恢复缺失的派生状态，集成验证 |
| R2 | 多 Worker 同时启动不生成重复状态或回填 Job | not_satisfied | 唯一键与事务锁，集成验证 |
| R3 | 子进程持续失败时不再每两秒无限拉起 | not_satisfied | 父进程故障退避，单元验证 |
| R4 | 给出现场恢复与重导边界，不误称原业务数据仍在 | not_satisfied | 运维文档与服务器回执 |
| R5 | 提供 Linux 严格重置脚本，只保留五张完整品牌/车型目录和 Alembic，清空采集运行、管理员操作审计等全部其它数据 | not_satisfied | Compose 目标校验、表级清空校验、Artifact 清理、Release 包验收 |
| R6 | 已绑定的源 Artifact 实体缺失时不做无效五次重试，并留下可定位的安全日志 | not_satisfied | 快照 Job 集成测试与日志事件 |

# 范围与计划

通过 Content Owner Repository 幂等插入缺失的派生状态，再由现有 Worker 入口在同一事务锁定状态并创建低优先级回填 Job。保留现有回填进度、Fencing、Job 及车型目录，不修改 HTTP Contract、Schema/Migration、依赖或已存在的业务行。父进程对连续子进程启动失败施加有界退避，并记录可诊断事件。测试覆盖空业务库、多进程竞争、现有状态保持及重复失败退避；同步声音广场运维文档。

用户随后明确停止现场排查，要求代码避免重置后的缺种子/快照故障，并提供保留目录的 Linux 清库脚本。脚本作为显式操作入口进入 Release 包，仅在 `--execute` 且交互确认或 `--yes` 时修改目标环境；不会由应用启动自动执行。清库会删除所有非保留 public 业务表的数据，包括运行记录、审计事件、任务与 Provider 配置，并删除 Artifact 实体；原始 Excel 目录、Secret、env 和日志保留。声音广场状态种子在清库事务内恢复。只备份保留目录，因此清库前其它业务数据的可恢复性必须由操作者另外决定。

# 风险、验证与回滚

状态行只在缺失时插入 `pending`，现有状态不覆盖。重新扫描 Content 的回填通过原有 UUID 检查点和幂等投影执行。旧版镜像没有自动恢复能力，现场可先按已核对的只读状态和幂等 SQL 手动补回状态行；正式修复需经 PR、CI、Review 和部署门禁。仅回滚代码不删除恢复的状态行。

# 完成审计

- [ ] 重新核对上游用户决定与当前代码/迁移/日志
- [ ] R1–R6 满足且无未解释缺口
- [ ] 适用的测试、文档和独立 Review 完成
- [ ] 当前 PR HEAD 的 CI 与交付状态记录
