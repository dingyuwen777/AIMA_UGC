---
schema: rvc-change/v1
id: CHG-20260824-docker-desktop-mirror-verification-retry
title: 统一 Docker Hub mirror 配置并修复 Docker Desktop 验证时序
level: L2
status: done
owner: chatgpt
branch: fix/docker-desktop-mirror-verification-retry
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - local-development
  - developer-experience
  - ci
affected_paths:
  - scripts/config/docker_hub_mirrors.txt
  - scripts/dev/configure_docker_desktop_mirrors.ps1
  - scripts/setup_dev_environment.sh
  - tests/unit/test_docker_build_sources.py
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

把 Docker Hub mirror 列表收敛为仓库内唯一配置源，并修复 Windows 首次运行 `scripts/setup_dev_environment.cmd` 时 Docker Desktop 重启后的 mirror 验证假阴性。

Windows 与 Linux 初始化脚本读取同一个 mirror 配置文件；以后增删或调整 mirror 顺序只修改这一处。Docker Desktop restart 后，脚本在有界时间内持续检查 `docker info` 的 `RegistryConfig.Mirrors`，直到配置真正生效或超时失败。

# 可观察成功标准

- [x] `scripts/config/docker_hub_mirrors.txt` 是 Docker Hub mirrors 的唯一当前运行配置源；非空、非注释行按文件顺序形成 mirror 列表。
- [x] Windows `configure_docker_desktop_mirrors.ps1` 从该文件读取 mirrors，不再硬编码地址。
- [x] Linux `setup_dev_environment.sh` 从同一文件读取 mirrors，不再维护第二份地址列表。
- [x] Docker Desktop restart 后持续等待 `docker info` 报告预期 mirrors，而不是 Engine 首次可访问后只检查一次。
- [x] 验证重试有明确上限和固定间隔；真正超时仍 fail closed，并输出 daemon.json 备份/恢复提示。
- [x] 三个既有 mirror 的当前顺序、`max-download-attempts=5`、daemon.json 备份和其他配置合并逻辑保持不变。
- [x] 已经正确应用 mirrors 时直接返回，不触发无意义重启。
- [x] 文档只描述统一配置文件和运行行为，不再复制维护 mirror URL 列表。
- [x] Final Ready HEAD 的 11 个永久 workflow 全部通过，PR #190 已正常合并到 `main`。

# 范围

- Docker Hub mirror 唯一配置文件。
- Windows Docker Desktop mirror helper 的配置读取、重启后验证等待逻辑。
- Linux 宿主初始化脚本读取统一 mirror 列表。
- 对应静态回归测试和运行文档。

# 非目标

- 不更换当前三个 Docker Hub mirror，也不改变优先顺序。
- 不改变 Dockerfile、Compose、Docker image identity、npm/PyPI/Debian 下载源。
- 不改变 Docker Desktop/Engine 的其他配置项。
- 不把公共 mirror 可用性探测加入日常运行或普通 CI。

# 必须保持不变

1. 当前 mirror 顺序保持本轮修改前既有顺序，只从脚本硬编码迁移到唯一配置文件。
2. `max-download-attempts` 仍为 5。
3. 修改既有 daemon.json 前继续创建时间戳备份，并保留其他已有 Docker Engine 配置。
4. Docker Desktop CLI 不可用时继续显式 warning/skip，不伪装成功。
5. 最终超时或实际未应用时仍 fail closed。
6. Linux 继续保留 `/data/docker`、日志 driver/rotation 和 daemon 配置校验等原有行为。

# 已确认关键决策

1. 用户确认将 Docker Hub mirror 列表收敛成单一配置源，后续新增/删除 mirror 只修改一个文件。
2. Windows 与 Linux 必须消费同一配置文件，测试不再维护第二份 URL 常量。
3. 配置文件允许空行与 `#` 注释；有效行顺序即 Docker registry mirror 优先顺序。
4. 文档只引用配置文件位置，不复制 URL 清单，避免形成多个当前事实源。
5. Windows 重启后 mirror 生效允许存在短暂延迟，因此验证采用有界重试；超时仍视为失败。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复 mirror 已最终生效但脚本重启后过早报错的问题 | user:docker-desktop-mirror-verification-false-negative | satisfied | 用户本机 `daemon.json` 与稍后执行的 `docker info` 均显示预期 mirrors；`Wait-ExpectedMirrorsApplied()` 在 restart 后最多 60 次、每 2 秒检查一次；有效 Red `6a6c375d1ea37a338c86d3a924f1833721b2ea7a` 的 unit 1 failed / 603 passed；Final Ready 总 CI `32684666191` success |
| R2 | Docker Hub mirror 列表改成单一配置源，后续增删只改一处 | user:centralize-docker-hub-mirrors | satisfied | `scripts/config/docker_hub_mirrors.txt` 保存唯一地址清单；Windows/Linux 都读取该文件；测试从该文件动态读取 mirrors 并检查脚本/Guide 不复制 URL；Final Ready 总 CI `32684666191` success |
| R3 | 保持既有 mirrors、下载重试、备份、Linux daemon 行为和最终失败保护 | scripts/dev/configure_docker_desktop_mirrors.ps1 | satisfied | Windows 保持 `max-download-attempts=5`、daemon 合并/时间戳备份/超时失败；Linux 保持 `/data/docker`、日志轮转、daemon merge/validate、安全重启和 PostgreSQL smoke；Windows workflow `32684666192`、Internal V1-A `32684666169` success |
| R4 | 文档只描述最新单一事实源，不复制 URL 清单 | user:centralize-docker-hub-mirrors | satisfied | Guide 03/04 只引用 `scripts/config/docker_hub_mirrors.txt`；静态测试约束 Guide 不复制有效 mirror URL；Final Ready CI success |
| R5 | 完成 L2 Completion Audit、两阶段 Review、Ready Check、永久 CI 并合并 main | AGENTS.md | satisfied | Final Ready HEAD `544f65f1fd5ac6670f90df7b1f6df8646191129e` 的 11 个永久 workflow 全部 success；PR #190 已正常合并，implementation merge commit `f4fef4f55737d09b8c3eb62d43d72972fb22c554` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端或数据库行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract |
| Real Full-stack Golden Path | not_applicable | 不修改完整运行栈业务语义；Internal V1-A 与 Windows named-volume Runtime 作为回归门禁均通过 |
| Real Provider Probe | not_applicable | 不涉及外部 Provider |
| Docs / Governance / Other | required | 有效 Red `6a6c375d...`；Final Ready 总 CI `32684666191`、Windows PowerShell/Compose `32684666192`、Completion Gate `32684666176` 及其余永久 workflow 全部 success |

# Completion Audit

- [x] upstream_re_read: 2026-08-24 重新读取本轮用户确认、`AGENTS.md`、Reliable Vibe Coding、Blueprint 07、统一 mirror 文件、Windows helper、Linux setup、目标测试、Windows workflow、Guide 03/04 与环境总入口。
- [x] change_coverage: 独立重建并核对 R1-R5，覆盖假阴性修复、单一配置源、Windows/Linux 共用、既有安全/下载语义保持、文档与交付门禁；没有 requirement omission。
- [x] reverse_audit: 从配置文件反查 Windows/Linux 消费和测试/Guide，从两个 setup 反查配置来源；三个当前 mirror URL 只由统一配置文件维护，Dockerfile/Compose/env image identity 与 npm/PyPI/Debian 构建源均未修改；并行 Change 路径未混入本 PR。
- [x] unresolved_cleared: R1-R5 全部有当前实现/测试/运行证据；required Validation Matrix 层已覆盖，其余层确无独立证明价值。

# Review

## Requirement Review A1：上游要求 → Change

通过。用户要求先修复重启后验证误报，随后明确批准把 mirror 清单收敛成单一配置源并要求未来增删只改一处；两项都已进入 R1/R2。仓库原有 Docker Engine 安全配置形成 R3，用户对文档最新事实的要求形成 R4，AGENTS 的 L2 交付门禁形成 R5。没有把任务扩大成更换 mirror、修改 Dockerfile/Compose 或引入在线可用性探测。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。统一配置文件是唯一地址清单；PowerShell 与 Bash 都读取它并验证非空/HTTPS/重复项；PowerShell restart 后在同一循环里用实际 `docker info` 等待 mirrors 生效，避免原来“Engine ready 后单次验证”的窗口；测试动态读取配置，Guide 只引用配置路径。既有 daemon 合并、备份、下载重试、Linux Docker data-root/日志行为均保留。

## Code Quality Review

通过，无 Serious/Important finding。实现只使用现有 PowerShell/Bash/标准库能力，没有新增依赖或运行 wrapper。配置错误、重复项、非 HTTPS、最终 mirror 未生效继续 fail closed；已经生效时幂等跳过 restart。等待最多约两分钟且只发生在首次/配置变化后的 Desktop restart，不影响日常 Compose 启停。没有 Secret、业务数据、Contract、Migration 或数据库变化。

# 验证证据

## Red

有效 Red commit：`6a6c375d1ea37a338c86d3a924f1833721b2ea7a`

总 CI `32683227084` 在 Ruff / mypy 通过后进入 unit，结果 **1 failed / 603 passed**；唯一目标失败为旧 `configure_docker_desktop_mirrors.ps1` 不存在 `$MirrorVerificationAttempts = 60`，证明旧实现没有 restart 后 mirror 有界重试。

后续为单一配置源补充测试时有提交先被 Ruff formatting 拦截，未将其伪装为行为 Red；单一配置源由用户新决策、最终实现和 Green 证据验收。

## Final Ready

Final Ready HEAD：`544f65f1fd5ac6670f90df7b1f6df8646191129e`

- CI `32684666191`: success。
- Change Completion Gate `32684666176`: success。
- Windows Docker Desktop Compose Compatibility `32684666192`: success。
- Internal V1-A `32684666169`: success。
- Local Dev Bootstrap `32684666224`: success。
- Stage 8F `32684666174`: success。
- Stage 6、Stage 7 Keyword Packs、Provider Config、Scheduler、Plan Occurrence：同一 Ready HEAD 全部 success。

# Git / 交付

- Implementation branch: `fix/docker-desktop-mirror-verification-retry`
- Implementation PR: #190，已正常 merge 到 `main`
- Final Ready HEAD: `544f65f1fd5ac6670f90df7b1f6df8646191129e`
- Implementation merge commit: `f4fef4f55737d09b8c3eb62d43d72972fb22c554`
- Archive: 本文件由独立归档 PR 从 `changes/active/` 移入 `changes/archive/2026-08/`；归档 PR/merge 状态由 GitHub PR 与提交历史记录
