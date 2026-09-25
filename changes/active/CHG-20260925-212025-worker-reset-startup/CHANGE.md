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
  - backend/src/aima_ugc/adapters/persistence/postgres/voice_plaza_projection.py
  - backend/src/aima_ugc/bootstrap/voice_plaza_projection_worker.py
  - backend/src/aima_ugc/entrypoints/worker_main.py
  - tests/integration/content/test_stage8d_voice_plaza_runtime.py
  - tests/unit/jobs/test_worker_entrypoint.py
  - docs/operations/04_声音广场读模型回填与性能验证.md
contracts: []
data_changes: []
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

# 范围与计划

通过 Content Owner Repository 幂等插入缺失的派生状态，再由现有 Worker 入口在同一事务锁定状态并创建低优先级回填 Job。保留现有回填进度、Fencing、Job 及车型目录，不修改 HTTP Contract、Schema/Migration、依赖或已存在的业务行。父进程对连续子进程启动失败施加有界退避，并记录可诊断事件。测试覆盖空业务库、多进程竞争、现有状态保持及重复失败退避；同步声音广场运维文档。

# 风险、验证与回滚

状态行只在缺失时插入 `pending`，现有状态不覆盖。重新扫描 Content 的回填通过原有 UUID 检查点和幂等投影执行。旧版镜像没有自动恢复能力，现场可先按已核对的只读状态和幂等 SQL 手动补回状态行；正式修复需经 PR、CI、Review 和部署门禁。仅回滚代码不删除恢复的状态行。

# 完成审计

- [ ] 重新核对上游用户决定与当前代码/迁移/日志
- [ ] R1–R4 满足且无未解释缺口
- [ ] 适用的测试、文档和独立 Review 完成
- [ ] 当前 PR HEAD 的 CI 与交付状态记录
